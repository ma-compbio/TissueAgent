#!/usr/bin/env python3
"""extract_reference_spec.py -- read the target figure's *symbolic* spec before plotting.

Part of the 'figure-reproduce' skill. Portable and self-contained: it imports NO
project package. numpy + Pillow are the only hard requirements; pytesseract (OCR)
and matplotlib (colormap matching) are optional and degrade with an install hint.

WHY THIS EXISTS
    Color, category order, and on-panel text are *discrete, symbolic* properties,
    but a vision model reads them out of a downsampled raster and guesses: it names
    a color ("blue") instead of measuring it, scrambles which category maps to which
    swatch, and paraphrases axis labels. Those three failure modes are invisible to
    SSIM/pHash/ORB (all grayscale), so nothing downstream catches them.

    This script measures them from pixels instead:
      * legend swatches -> ORDERED [(label, #hex)] ... palette + binding + order
      * axis tick strips -> ORDERED tick labels     ... row/column/bar order
      * colorbar strip   -> best-matching cmap name ... including "_r" reversal

    The emitted YAML is meant to be treated as ground truth by the plotting code:
    take `palette`, `order`, and label text FROM IT rather than from library
    defaults or from eyeballing the image.

USAGE
    python extract_reference_spec.py TARGET_IMAGE [-o spec.yaml] [--json]
                                     [--legend-box x0,y0,x1,y1]
                                     [--colorbar-box x0,y0,x1,y1]
                                     [--xtick-box x0,y0,x1,y1]
                                     [--ytick-box x0,y0,x1,y1]
                                     [--max-colors N] [--debug-crops DIR]

    Boxes are pixel coordinates on the *target* image. All are optional: with none
    given the script auto-detects a legend region and reports what it found. Auto-
    detection is a heuristic -- when a crop looks wrong, pass the box explicitly
    (use --debug-crops to see exactly what was read).

EXAMPLES
    python extract_reference_spec.py fig2b.png -o spec.yaml
    python extract_reference_spec.py fig2b.png --legend-box 820,60,1000,400 -o spec.yaml
    python extract_reference_spec.py heat.png --colorbar-box 900,100,930,500 --json
"""

from __future__ import annotations

import argparse
import json
import os
import sys

try:
    import numpy as np
    from PIL import Image
except ImportError as exc:  # pragma: no cover - hard requirement
    sys.stderr.write(
        f"FATAL: this script needs numpy and Pillow ({exc}). "
        "Install with: pip install numpy Pillow\n"
    )
    sys.exit(2)


# Pixels this close to white/black are chrome (background, axes, text), not data.
WHITE_CUT = 242
BLACK_CUT = 28
# A swatch candidate must be at least this saturated OR this far from gray.
MIN_CHROMA = 18
# Colormaps papers actually use, in rough order of frequency. Both directions are
# tested, so listing the base name also covers its "_r" reverse.
CMAP_CANDIDATES = (
    "viridis", "magma", "inferno", "plasma", "cividis",
    "RdBu", "coolwarm", "bwr", "seismic", "Spectral", "RdYlBu",
    "Reds", "Blues", "Greens", "Purples", "Oranges", "Greys",
    "YlOrRd", "YlGnBu", "BuPu", "GnBu", "OrRd", "PuBu",
    "jet", "rainbow", "turbo", "hot", "afmhot", "gray",
)


def hint(pkg: str) -> str:
    """One-line install hint for a missing optional dependency."""
    return f"[degraded] optional dependency '{pkg}' not installed - try: pip install {pkg}"


# --------------------------------------------------------------------------- #
# Color helpers -- comparisons happen in CIELAB, never in RGB
# --------------------------------------------------------------------------- #
def to_hex(rgb) -> str:
    r, g, b = (int(round(float(v))) for v in rgb[:3])
    return "#%02x%02x%02x" % (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))


def srgb_to_lab(rgb: np.ndarray) -> np.ndarray:
    """sRGB [0,255] -> CIELAB (D65). Accepts (...,3); returns the same leading shape.

    RGB distance correlates poorly with 'looks wrong' -- two colors 30 apart in RGB
    can be indistinguishable or obviously different depending where they sit. LAB is
    roughly perceptually uniform, so a single dE threshold means the same thing
    everywhere in the space.
    """
    arr = np.asarray(rgb, dtype=np.float64).reshape(-1, 3) / 255.0
    # inverse sRGB companding
    lin = np.where(arr <= 0.04045, arr / 12.92, ((arr + 0.055) / 1.055) ** 2.4)
    m = np.array([
        [0.4124564, 0.3575761, 0.1804375],
        [0.2126729, 0.7151522, 0.0721750],
        [0.0193339, 0.1191920, 0.9503041],
    ])
    xyz = lin @ m.T
    white = np.array([0.95047, 1.00000, 1.08883])
    t = xyz / white
    d = 6.0 / 29.0
    f = np.where(t > d ** 3, np.cbrt(t), t / (3 * d * d) + 4.0 / 29.0)
    lab = np.stack([
        116.0 * f[:, 1] - 16.0,
        500.0 * (f[:, 0] - f[:, 1]),
        200.0 * (f[:, 1] - f[:, 2]),
    ], axis=1)
    return lab.reshape(np.asarray(rgb).shape)


def delta_e(a, b) -> float:
    """CIE76 dE between two sRGB triples. ~2.3 = just-noticeable difference."""
    la, lb = srgb_to_lab(np.asarray(a, float)), srgb_to_lab(np.asarray(b, float))
    return float(np.sqrt(np.sum((la - lb) ** 2)))


def is_chrome(px: np.ndarray) -> np.ndarray:
    """Boolean mask of 'not data' pixels: near-white, near-black, or near-gray."""
    mx, mn = px.max(axis=-1), px.min(axis=-1)
    chroma = mx.astype(np.int16) - mn.astype(np.int16)
    return (mn > WHITE_CUT) | (mx < BLACK_CUT) | (chroma < MIN_CHROMA)


# --------------------------------------------------------------------------- #
# Palette extraction
# --------------------------------------------------------------------------- #
def quantize_colors(px: np.ndarray, max_colors: int = 16, min_share: float = 0.004):
    """Return [(hex, share, rgb)] of dominant non-chrome colors, most common first.

    Two-stage. An exact-value histogram alone only works on flat-rendered vector
    output: a JPEG-compressed scatter of small anti-aliased markers can have ~as many
    distinct RGBs as it has data pixels (measured: 59k colors over 72k pixels), so
    every individual share falls under min_share and nothing survives. So:

      1. exact-value histogram -- cheap, and exact on flat/vector figures;
      2. if that yields little, cluster the pixels in CIELAB and use the cluster
         centroids, which is robust to compression noise and anti-aliasing.

    Stage 2 reports the centroid nearest an actual observed pixel rather than the raw
    mean, so the returned hex is a color that genuinely appears in the figure.
    """
    flat = px.reshape(-1, 3)
    keep = ~is_chrome(flat)
    data = flat[keep]
    if data.size == 0:
        return []

    # ---- stage 1: exact-value histogram (flat / vector figures) ----
    packed = (data[:, 0].astype(np.uint32) << 16) | (data[:, 1].astype(np.uint32) << 8) | data[:, 2]
    vals, counts = np.unique(packed, return_counts=True)
    order = np.argsort(-counts)
    total = float(counts.sum())

    out: list[tuple[str, float, tuple[int, int, int]]] = []
    for i in order:
        if len(out) >= max_colors:
            break
        share = counts[i] / total
        if share < min_share:
            break
        v = int(vals[i])
        rgb = ((v >> 16) & 255, (v >> 8) & 255, v & 255)
        # merge into an existing entry if perceptually the same color (anti-aliasing)
        if any(delta_e(rgb, prev) < 6.0 for _, _, prev in out):
            continue
        out.append((to_hex(rgb), round(share, 5), rgb))

    # A well-quantized figure gives several colors covering most of the ink. If the
    # histogram is that diffuse, the image is compressed/anti-aliased -> cluster.
    if sum(s for _, s, _ in out) >= 0.25 and len(out) >= 2:
        return out
    return _cluster_colors_lab(data, max_colors=max_colors, min_share=min_share)


def _cluster_colors_lab(data: np.ndarray, max_colors: int = 16, min_share: float = 0.004,
                        iters: int = 12, sample_cap: int = 60000):
    """k-means in CIELAB over non-chrome pixels -> [(hex, share, rgb)].

    Plain numpy (no sklearn dependency), seeded deterministically by k-means++ style
    farthest-point selection so repeated runs on the same figure agree -- a spec that
    changed between runs would be useless as ground truth.
    """
    if len(data) == 0:
        return []
    # deterministic subsample for speed on large panels
    if len(data) > sample_cap:
        step = len(data) // sample_cap + 1
        sample = data[::step]
    else:
        sample = data
    lab = srgb_to_lab(sample.astype(np.float64))
    k = int(max(2, min(max_colors, len(np.unique(sample, axis=0)))))

    # farthest-point init (deterministic: always start from the darkest pixel)
    centers = [lab[np.argmin(lab[:, 0])]]
    for _ in range(k - 1):
        d = np.min(np.stack([np.sum((lab - c) ** 2, axis=1) for c in centers]), axis=0)
        centers.append(lab[int(np.argmax(d))])
    C = np.stack(centers)

    assign = np.zeros(len(lab), dtype=np.int64)
    for _ in range(iters):
        d2 = ((lab[:, None, :] - C[None, :, :]) ** 2).sum(axis=2)
        new = d2.argmin(axis=1)
        if np.array_equal(new, assign):
            break
        assign = new
        for j in range(len(C)):
            m = assign == j
            if m.any():
                C[j] = lab[m].mean(axis=0)

    total = float(len(lab))
    out = []
    for j in np.argsort(-np.bincount(assign, minlength=len(C))):
        share = float((assign == j).sum()) / total
        if share < min_share:
            continue
        members = sample[assign == j]
        if not len(members):
            continue
        # report an OBSERVED pixel near the centroid, not the raw mean
        mlab = srgb_to_lab(members.astype(np.float64))
        rgb = tuple(int(v) for v in members[int(np.argmin(((mlab - C[j]) ** 2).sum(axis=1)))])
        if any(delta_e(rgb, prev) < 6.0 for _, _, prev in out):
            continue
        out.append((to_hex(rgb), round(share, 5), rgb))
        if len(out) >= max_colors:
            break
    return out


def find_legend_swatches(img: Image.Image, box=None, max_colors: int = 16):
    """Find legend swatches and return them in reading order (top->bottom).

    Order matters as much as the values: the legend's vertical sequence IS the
    target's category order, which is what makes bar/heatmap/z-order match.
    """
    crop = img.crop(box) if box else img
    px = np.asarray(crop.convert("RGB"))
    if px.size == 0:
        return [], "empty crop"

    h, w = px.shape[:2]
    mask = ~is_chrome(px)
    if not mask.any():
        return [], "no non-chrome pixels in crop"

    # Group swatch pixels into horizontal bands; each band is one legend entry.
    rows = np.where(mask.any(axis=1))[0]
    bands: list[tuple[int, int]] = []
    start = prev = rows[0]
    for r in rows[1:]:
        if r - prev > 2:            # a gap of >2px ends the band
            bands.append((start, prev))
            start = r
        prev = r
    bands.append((start, prev))

    ox, oy = (box[0], box[1]) if box else (0, 0)   # crop origin -> absolute coords
    entries = []
    rejected = 0
    for (r0, r1) in bands:
        if r1 - r0 < 1:             # single-pixel noise
            continue
        band = px[r0:r1 + 1]
        bmask = mask[r0:r1 + 1]
        if bmask.sum() < 4:
            continue
        cols = np.where(bmask.any(axis=0))[0]
        bw, bh = int(cols[-1] - cols[0] + 1), int(r1 - r0 + 1)
        # A legend swatch is a small, compact, mostly-filled mark. Scatter clouds and
        # plot content are large and sparse -- reject them rather than reporting a
        # cluster of data points as if it were a category swatch.
        fill = bmask[:, cols[0]:cols[-1] + 1].mean()
        if bw > 0.6 * w or bh > 0.35 * h or bw > 60 or bh > 60 or fill < 0.55:
            rejected += 1
            continue
        # the swatch is the dominant flat color in the band
        dom = quantize_colors(band[bmask].reshape(-1, 1, 3), max_colors=1, min_share=0.0)
        if not dom:
            continue
        entries.append({
            "hex": dom[0][0],
            "rgb": list(dom[0][2]),
            "box": [int(cols[0]) + ox, int(r0) + oy, int(cols[-1]) + ox, int(r1) + oy],
        })
        if len(entries) >= max_colors:
            break

    if not entries:
        return [], "no swatch-shaped marks in crop (rejected %d blob(s) as plot content)" % rejected
    # Real legend entries are left-aligned in a column; scattered x positions mean we
    # are reading plot content, not a legend.
    xs = [e["box"][0] for e in entries]
    if len(entries) > 1 and (max(xs) - min(xs)) > 0.25 * w + 12:
        return [], ("marks found but not column-aligned -- this crop is probably not a "
                    "legend; pass --legend-box explicitly")
    return entries, "ok"


def autodetect_legend_box(img: Image.Image):
    """Guess a legend region by asking which candidate strip actually parses as one.

    Scoring by color density alone picks the *plot* (it is the most colorful thing on
    the panel), so instead each candidate strip is run through find_legend_swatches
    and scored on the result: several small, column-aligned, distinctly-colored marks.
    Legends sit right or bottom in the overwhelming majority of published panels.

    Still a heuristic -- when it misses, the fix is --legend-box, and the report says
    the box was guessed rather than pretending it was a measurement.
    """
    w, h = img.width, img.height
    candidates = []
    # right-hand strips (most common legend placement), narrow -> wide
    for frac in (0.18, 0.26, 0.34):
        x0 = int(w * (1.0 - frac))
        candidates.append((x0, 0, w, h))
    # bottom strips (horizontal legends under the axes)
    for frac in (0.16, 0.24):
        y0 = int(h * (1.0 - frac))
        candidates.append((0, y0, w, h))
    # inset legend: upper-right and lower-right quadrants
    candidates.append((int(w * 0.55), 0, w, int(h * 0.45)))
    candidates.append((int(w * 0.55), int(h * 0.55), w, h))

    best, best_score = None, 0.0
    for box in candidates:
        entries, status = find_legend_swatches(img, box, max_colors=32)
        if status != "ok" or len(entries) < 2:
            continue
        # distinct colors, not one antialiased mark split into bands
        uniq = {e["hex"] for e in entries}
        if len(uniq) < 2:
            continue
        # prefer more entries, penalise very wide strips (they creep into the plot)
        area_pen = ((box[2] - box[0]) * (box[3] - box[1])) / float(w * h)
        score = len(uniq) * (1.0 - 0.5 * area_pen)
        if score > best_score:
            best_score, best = score, box
    return best


# --------------------------------------------------------------------------- #
# Colormap identification (continuous panels)
# --------------------------------------------------------------------------- #
def read_colorbar_ramp(img: Image.Image, box, samples: int = 32):
    """Sample a colorbar crop into an ordered ramp of RGB triples."""
    crop = np.asarray(img.crop(box).convert("RGB"), dtype=np.float64)
    h, w = crop.shape[:2]
    if h == 0 or w == 0:
        return []
    vertical = h >= w
    # average across the short axis to kill the border and any tick marks
    line = crop.mean(axis=1) if vertical else crop.mean(axis=0)
    if vertical:
        line = line[::-1]            # bottom = low value = ramp start
    idx = np.linspace(0, len(line) - 1, samples).round().astype(int)
    return [line[i] for i in idx]


def match_colormap(ramp):
    """Return [(name, mean_dE)] best-first over CMAP_CANDIDATES and their reverses."""
    if not ramp:
        return [], "no ramp sampled"
    try:
        import matplotlib.cm as cm
    except ImportError:
        return [], hint("matplotlib") + " (colormap matching skipped)"

    obs = np.asarray(ramp, dtype=np.float64)
    n = len(obs)
    scored = []
    for name in CMAP_CANDIDATES:
        for cand in (name, name + "_r"):
            try:
                cmap = cm.get_cmap(cand) if hasattr(cm, "get_cmap") else cm.colormaps[cand]
            except (ValueError, KeyError, AttributeError):
                continue
            ref = np.array([cmap(t)[:3] for t in np.linspace(0, 1, n)]) * 255.0
            d = float(np.mean([delta_e(obs[i], ref[i]) for i in range(n)]))
            scored.append((cand, round(d, 2)))
    scored.sort(key=lambda t: t[1])
    return scored[:5], "ok"


# --------------------------------------------------------------------------- #
# Text / tick order (OCR)
# --------------------------------------------------------------------------- #
def ocr_lines(img: Image.Image, box=None, axis: str = "y"):
    """OCR a crop and return text in plot order, or a degraded note.

    Order is taken from pixel position -- top->bottom for a y-axis or legend,
    left->right for an x-axis -- because that ordering is the thing being
    recovered, not an incidental property of the OCR output.
    """
    try:
        import pytesseract
    except ImportError:
        return [], hint("pytesseract") + " (text/tick extraction skipped; also needs the tesseract binary)"

    crop = img.crop(box) if box else img
    # upscale: tick labels are small and OCR is far more accurate at ~2x
    crop = crop.convert("L").resize((crop.width * 2, crop.height * 2), Image.LANCZOS)
    try:
        data = pytesseract.image_to_data(crop, output_type=pytesseract.Output.DICT)
    except Exception as exc:  # tesseract binary missing or unreadable crop
        return [], f"[degraded] OCR failed: {exc} (is the 'tesseract' binary installed?)"

    items = []
    for i, txt in enumerate(data.get("text", [])):
        t = (txt or "").strip()
        if not t:
            continue
        try:
            conf = float(data["conf"][i])
        except (ValueError, KeyError, TypeError):
            conf = -1.0
        if conf < 30:
            continue
        items.append({
            "text": t,
            "x": int(data["left"][i]) // 2,
            "y": int(data["top"][i]) // 2,
            "conf": round(conf, 1),
        })
    items.sort(key=lambda d: d["x"] if axis == "x" else d["y"])
    return items, "ok"


# --------------------------------------------------------------------------- #
# YAML emit (no PyYAML dependency -- the shape here is flat enough to write directly)
# --------------------------------------------------------------------------- #
def _yaml_scalar(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if v is None:
        return "null"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v)
    return '"%s"' % s.replace("\\", "\\\\").replace('"', '\\"')


def to_yaml(spec: dict) -> str:
    """Emit the spec as YAML. Hand-rolled so the script stays dependency-light."""
    L: list[str] = []
    L.append("# Reference spec extracted from the target figure by extract_reference_spec.py")
    L.append("# Treat these values as GROUND TRUTH: take palette / order / labels from")
    L.append("# here rather than from library defaults or from naming colors by eye.")
    L.append("source: %s" % _yaml_scalar(spec.get("source")))
    L.append("image_size: [%d, %d]" % tuple(spec.get("image_size", (0, 0))))

    leg = spec.get("legend") or {}
    L.append("legend:")
    L.append("  status: %s" % _yaml_scalar(leg.get("status", "not requested")))
    if leg.get("box"):
        L.append("  box: [%s]" % ", ".join(str(int(v)) for v in leg["box"]))
    L.append("  box_source: %s" % _yaml_scalar(leg.get("box_source", "none")))
    entries = leg.get("entries") or []
    L.append("  # ORDER IS MEANINGFUL: this is the target's category order.")
    L.append("  entries:%s" % ("" if entries else " []"))
    for e in entries:
        L.append("    - hex: %s" % _yaml_scalar(e["hex"]))
        L.append("      label: %s" % _yaml_scalar(e.get("label")))
        L.append("      box: [%s]" % ", ".join(str(int(v)) for v in e["box"]))

    rel = spec.get("palette_reliability") or {}
    L.append("palette_reliability:")
    L.append("  verdict: %s" % _yaml_scalar(rel.get("verdict", "unknown")))
    if "distinct_color_ratio" in rel:
        L.append("  distinct_color_ratio: %s   # >0.5 => colors are NOT recoverable"
                 % rel["distinct_color_ratio"])
        L.append("  median_chroma: %s" % rel["median_chroma"])

    L.append("palette_by_frequency:")
    L.append("  # Dominant non-chrome colors over the whole panel, most common first.")
    L.append("  # Use when there is no legend to read (e.g. a single-series plot).")
    L.append("  # CHECK palette_reliability above before trusting these as exact.")
    for hx, share, _ in spec.get("palette", []):
        L.append("  - {hex: %s, share: %s}" % (_yaml_scalar(hx), share))
    if not spec.get("palette"):
        L[-1] = "palette_by_frequency: []"

    cb = spec.get("colorbar") or {}
    L.append("colorbar:")
    L.append("  status: %s" % _yaml_scalar(cb.get("status", "not requested")))
    matches = cb.get("matches") or []
    L.append("  # best-first; dE is mean CIELAB distance across the ramp (lower = better)")
    L.append("  matches:%s" % ("" if matches else " []"))
    for name, d in matches:
        L.append("    - {cmap: %s, delta_e: %s}" % (_yaml_scalar(name), d))
    if matches:
        L.append("  best: %s" % _yaml_scalar(matches[0][0]))

    for key in ("xticks", "yticks"):
        t = spec.get(key) or {}
        L.append("%s:" % key)
        L.append("  status: %s" % _yaml_scalar(t.get("status", "not requested")))
        labels = [i["text"] for i in (t.get("items") or [])]
        L.append("  # ORDER IS MEANINGFUL: %s order as drawn." % ("left->right" if key == "xticks" else "top->bottom"))
        if labels:
            L.append("  labels: [%s]" % ", ".join(_yaml_scalar(x) for x in labels))
        else:
            L.append("  labels: []")

    txt = spec.get("text") or {}
    L.append("panel_text:")
    L.append("  status: %s" % _yaml_scalar(txt.get("status", "not requested")))
    strings = [i["text"] for i in (txt.get("items") or [])]
    L.append("  # Copy these VERBATIM into axis/legend/title calls.")
    if strings:
        L.append("  strings: [%s]" % ", ".join(_yaml_scalar(x) for x in strings))
    else:
        L.append("  strings: []")
    return "\n".join(L) + "\n"


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _parse_box(s: str | None):
    if not s:
        return None
    try:
        parts = [int(round(float(v))) for v in s.split(",")]
    except ValueError:
        sys.stderr.write(f"ERROR: bad box '{s}' - expected x0,y0,x1,y1\n")
        sys.exit(2)
    if len(parts) != 4:
        sys.stderr.write(f"ERROR: bad box '{s}' - expected 4 comma-separated numbers\n")
        sys.exit(2)
    x0, y0, x1, y1 = parts
    if x1 <= x0 or y1 <= y0:
        sys.stderr.write(f"ERROR: bad box '{s}' - need x0<x1 and y0<y1\n")
        sys.exit(2)
    return (x0, y0, x1, y1)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Extract palette, category order, colormap and text from a target figure.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("image", help="path to the target / reference figure")
    ap.add_argument("-o", "--out", help="write the spec YAML here (default: stdout)")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of YAML")
    ap.add_argument("--legend-box", help="x0,y0,x1,y1 of the legend region")
    ap.add_argument("--colorbar-box", help="x0,y0,x1,y1 of the colorbar strip")
    ap.add_argument("--xtick-box", help="x0,y0,x1,y1 of the x-axis tick label strip")
    ap.add_argument("--ytick-box", help="x0,y0,x1,y1 of the y-axis tick label strip")
    ap.add_argument(
        "--max-colors",
        type=int,
        default=16,
        help="max entries in the dominant-color summary (default 16)",
    )
    ap.add_argument(
        "--max-legend-entries",
        type=int,
        default=64,
        help="max legend swatches to read (default 64)",
    )
    ap.add_argument("--debug-crops", metavar="DIR", help="save the crops that were read, to check them")
    args = ap.parse_args()

    try:
        img = Image.open(args.image).convert("RGB")
    except (FileNotFoundError, OSError) as exc:
        sys.stderr.write(f"ERROR: cannot read image '{args.image}': {exc}\n")
        return 2

    legend_box = _parse_box(args.legend_box)
    cbar_box = _parse_box(args.colorbar_box)
    xt_box = _parse_box(args.xtick_box)
    yt_box = _parse_box(args.ytick_box)

    spec: dict = {
        "source": os.path.abspath(args.image),
        "image_size": (img.width, img.height),
    }

    # ---- palette over the whole panel ----
    px_all = np.asarray(img)
    spec["palette"] = quantize_colors(px_all, max_colors=args.max_colors)

    # ---- is this figure's palette recoverable at all? ----
    # A dense scatter of sub-pixel markers blends every color with the background and
    # its neighbours, so the TRUE category colors are never rendered anywhere in the
    # raster. Detect that and say so, rather than returning a confidently wrong
    # washed-out palette that downstream code would treat as ground truth.
    flat = px_all.reshape(-1, 3)
    data = flat[~is_chrome(flat)]
    if len(data) > 100:
        uniq_ratio = len(np.unique(data, axis=0)) / float(len(data))
        sat = (data.max(axis=1).astype(np.int16) - data.min(axis=1).astype(np.int16))
        spec["palette_reliability"] = {
            "distinct_color_ratio": round(float(uniq_ratio), 3),
            "median_chroma": int(np.median(sat)),
            "verdict": (
                "LOW -- nearly every data pixel has a unique color (compressed and/or "
                "sub-pixel markers). Individual category colors are NOT recoverable "
                "from this raster; use a supplied palette or the dataset's own color "
                "field instead. Dominant colors below are indicative only."
                if uniq_ratio > 0.5 else
                "MODERATE -- heavy anti-aliasing; dominant colors are usable, rare "
                "categories may be blended away."
                if uniq_ratio > 0.15 else
                "OK -- flat-rendered colors; extracted values should be exact."
            ),
        }
    else:
        spec["palette_reliability"] = {"verdict": "n/a -- too few data pixels"}

    # ---- legend: explicit box wins; otherwise a flagged guess ----
    box_source = "explicit"
    if legend_box is None:
        legend_box = autodetect_legend_box(img)
        box_source = "autodetected (VERIFY: pass --legend-box if this looks wrong)" if legend_box else "none"
    entries, leg_status = ([], "no legend region found") if legend_box is None else \
        find_legend_swatches(img, legend_box, args.max_legend_entries)

    # pair each swatch with the text on its right, by vertical overlap
    if entries and legend_box:
        lx0, ly0, lx1, ly1 = legend_box
        items, txt_status = ocr_lines(img, (lx0, ly0, min(img.width, lx1 + 260), ly1), axis="y")
        # OCR coords are crop-relative; entry boxes are absolute -> put both in the
        # same frame before pairing, or every label lands on the wrong swatch.
        for i in items:
            i["y"] += ly0
            i["x"] += lx0
        for e in entries:
            ey0, ey1 = e["box"][1], e["box"][3]
            mid = (ey0 + ey1) / 2.0
            near = [i for i in items
                    if (ey0 - 6 <= i["y"] <= ey1 + 6 or abs(i["y"] - mid) < 10)
                    and i["x"] >= e["box"][0] - 4]      # label sits right of its swatch
            if near:
                e["label"] = " ".join(i["text"] for i in sorted(near, key=lambda d: d["x"]))
        if txt_status != "ok":
            leg_status = f"{leg_status}; labels unavailable ({txt_status})"
    spec["legend"] = {
        "status": leg_status,
        "box": legend_box,
        "box_source": box_source,
        "entries": entries,
    }

    # ---- colorbar ----
    if cbar_box:
        ramp = read_colorbar_ramp(img, cbar_box)
        matches, cb_status = match_colormap(ramp)
        spec["colorbar"] = {"status": cb_status, "matches": matches, "box": cbar_box}
    else:
        spec["colorbar"] = {"status": "not requested (pass --colorbar-box)", "matches": []}

    # ---- ticks + free text ----
    for key, box, axis in (("xticks", xt_box, "x"), ("yticks", yt_box, "y")):
        if box:
            items, st = ocr_lines(img, box, axis=axis)
            spec[key] = {"status": st, "items": items}
        else:
            spec[key] = {"status": "not requested (pass --%s-box)" % key[:5], "items": []}

    text_items, text_status = ocr_lines(img, None, axis="y")
    spec["text"] = {"status": text_status, "items": text_items}

    # ---- optional: dump the crops so a wrong box is obvious ----
    if args.debug_crops:
        os.makedirs(args.debug_crops, exist_ok=True)
        for nm, bx in (("legend", legend_box), ("colorbar", cbar_box),
                       ("xticks", xt_box), ("yticks", yt_box)):
            if bx:
                img.crop(bx).save(os.path.join(args.debug_crops, f"{nm}.png"))
        sys.stderr.write(f"[debug] crops written to {args.debug_crops}\n")

    if args.json:
        payload = dict(spec)
        payload["palette"] = [{"hex": h, "share": s} for h, s, _ in spec["palette"]]
        payload["colorbar"] = dict(spec["colorbar"])
        payload["colorbar"]["matches"] = [
            {"cmap": n, "delta_e": d} for n, d in spec["colorbar"].get("matches", [])
        ]
        out = json.dumps(payload, indent=2)
    else:
        out = to_yaml(spec)

    if args.out:
        with open(args.out, "w") as fh:
            fh.write(out)
        n_leg = len(spec["legend"]["entries"])
        best = (spec["colorbar"].get("matches") or [(None,)])[0][0]
        print(f"wrote {args.out}")
        print(f"  legend entries : {n_leg}  [{spec['legend']['status']}]")
        print(f"  palette colors : {len(spec['palette'])}")
        print(f"  colormap guess : {best or '(no colorbar box given)'}")
        print(f"  panel strings  : {len(spec['text']['items'])}  [{spec['text']['status']}]")
        if spec["legend"]["box_source"].startswith("autodetected"):
            print("  NOTE: the legend box was GUESSED. Check it with --debug-crops and")
            print("        pass --legend-box explicitly if the entries look wrong.")
    else:
        print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
