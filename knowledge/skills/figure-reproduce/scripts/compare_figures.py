#!/usr/bin/env python3
"""compare_figures.py -- fidelity self-evaluation for the 'figure-reproduce' skill.

WHAT IT DOES
    Compares a reproduced figure against the target (original) figure and returns a
    similarity verdict. This is the numeric feedback that drives the agent's
    reflect-and-retry loop: if the reproduction is far from the target, the agent
    should inspect *why* and try again.

    Metrics computed (each degrades gracefully if an optional dep is missing):
      * pHash Hamming distance  -- perceptual hash difference (0 = identical layout).
      * SSIM                     -- structural similarity on 512x512 grayscale (0..1).
      * ORB good-match count     -- number of robust keypoint matches (higher = better).
      * Palette dE               -- CIELAB distance between the two palettes (color).
      * Text diff                -- OCR'd on-panel strings present/missing/near-miss.
      * B-level prior            -- a coarse B1..B5 bucket, floored by ALL of the above.

    WHY THE COLOR/TEXT METRICS EXIST
        pHash, SSIM and ORB are all computed on GRAYSCALE, so they are blind to the
        three most common reproduction errors: a wrong palette, a wrong category
        order, and paraphrased axis/legend text. A figure with the wrong colormap and
        rewritten labels can score SSIM 0.96 and land at "B5" on a SSIM-only ladder.
        The palette-dE and text-diff metrics below exist to catch exactly that, and
        the B-level is the MINIMUM across every available signal -- so a strong
        structural match can no longer paper over a color or label failure.

    The B-level remains a prior, not a verdict: the agent's visual judgment against
    the B1..B5 rubric is still authoritative (a correct reproduction can score low on
    a stochastic embedding; a wrong one can score high). But it now fails in the safe
    direction.

USAGE
    python compare_figures.py <original_image> <reproduced_image> [--out compare_diff.png] [--json]
                              [--no-color] [--no-text]

    --out       Where to write the side-by-side (original | reproduced) PNG.
                Default: ./compare_diff.png
    --json      Emit all metrics as machine-readable JSON instead of prose.
    --no-color  Skip the palette comparison (e.g. an intentionally grayscale target).
    --no-text   Skip the OCR text diff (faster; also silences the tesseract hint).

PORTABILITY
    Part of the 'figure-reproduce' skill: a single self-contained file with NO
    dependency on any project package. It runs anywhere Pillow + numpy are present.
    scikit-image (SSIM), opencv (ORB), and imagehash (pHash) are optional enhancers;
    when absent the script uses built-in numpy fallbacks or skips that metric with a
    one-line install hint.
"""

from __future__ import annotations

import argparse
import json
import sys

# --- Mandatory deps: Pillow + numpy. Everything else is optional. -----------------
try:
    import numpy as np
    from PIL import Image
except ImportError as exc:  # pragma: no cover - hard requirement
    sys.stderr.write(
        f"FATAL: this script needs numpy and Pillow ({exc}). "
        "Install with: pip install numpy Pillow\n"
    )
    sys.exit(2)


# ---------------------------------------------------------------------------------
# Image loading helpers
# ---------------------------------------------------------------------------------
def load_rgb(path: str) -> Image.Image:
    """Open an image as RGB, or exit non-zero on a real usage error (bad path)."""
    try:
        return Image.open(path).convert("RGB")
    except (FileNotFoundError, OSError) as exc:
        sys.stderr.write(f"ERROR: cannot read image '{path}': {exc}\n")
        sys.exit(2)


def to_gray_array(img: Image.Image, size: int = 512) -> np.ndarray:
    """Grayscale, resized to size x size, as float64 in [0, 255]."""
    gray = img.convert("L").resize((size, size), Image.BILINEAR)
    return np.asarray(gray, dtype=np.float64)


# ---------------------------------------------------------------------------------
# pHash: prefer imagehash, else a compact 8x8 DCT perceptual hash
# ---------------------------------------------------------------------------------
def _dct_1d(matrix: np.ndarray) -> np.ndarray:
    """Type-II DCT applied along the last axis (no scipy needed)."""
    n = matrix.shape[-1]
    k = np.arange(n)
    # basis[u, x] = cos(pi/N * (x + 0.5) * u)
    basis = np.cos(np.pi / n * (k[:, None] + 0.5) * k[None, :])
    return matrix @ basis.T


def phash_bits(img: Image.Image, hash_size: int = 8, highfreq_factor: int = 4) -> np.ndarray:
    """Compact DCT-based 64-bit perceptual hash returned as a boolean array."""
    img_size = hash_size * highfreq_factor
    pixels = np.asarray(
        img.convert("L").resize((img_size, img_size), Image.BILINEAR),
        dtype=np.float64,
    )
    # 2D DCT = 1D DCT on rows then on columns.
    dct = _dct_1d(_dct_1d(pixels).T).T
    low = dct[:hash_size, :hash_size]  # keep the low-frequency top-left block
    med = np.median(low[1:, 1:])  # exclude the DC term (low[0,0]) from the median
    return (low > med).flatten()


def phash_hamming(orig: Image.Image, repro: Image.Image) -> tuple[int, str]:
    """Return (hamming_distance, path_label). Prefers the imagehash library."""
    try:
        import imagehash

        h1 = imagehash.phash(orig)
        h2 = imagehash.phash(repro)
        return int(h1 - h2), "imagehash"
    except ImportError:
        b1 = phash_bits(orig)
        b2 = phash_bits(repro)
        return int(np.count_nonzero(b1 != b2)), "numpy-dct-fallback"


# ---------------------------------------------------------------------------------
# SSIM: prefer skimage, else a windowed numpy fallback
# ---------------------------------------------------------------------------------
def _ssim_numpy(a: np.ndarray, b: np.ndarray, win: int = 7) -> float:
    """Windowed mean/variance/covariance SSIM (Wang et al. 2004) in pure numpy.

    Uses a uniform (box) sliding window of size `win`; constants match the standard
    SSIM formulation for an 8-bit dynamic range (L=255).
    """
    c1 = (0.01 * 255) ** 2
    c2 = (0.03 * 255) ** 2

    # Sliding local statistics via a box filter implemented with cumulative sums.
    def box_mean(x: np.ndarray) -> np.ndarray:
        pad = win // 2
        xp = np.pad(x, pad, mode="reflect")
        # integral image for O(1) window sums
        cs = np.cumsum(np.cumsum(xp, axis=0), axis=1)
        cs = np.pad(cs, ((1, 0), (1, 0)), mode="constant")
        h, w = x.shape
        s = (
            cs[win:win + h, win:win + w]
            - cs[0:h, win:win + w]
            - cs[win:win + h, 0:w]
            + cs[0:h, 0:w]
        )
        return s / (win * win)

    mu_a = box_mean(a)
    mu_b = box_mean(b)
    mu_a2, mu_b2, mu_ab = mu_a * mu_a, mu_b * mu_b, mu_a * mu_b
    var_a = box_mean(a * a) - mu_a2
    var_b = box_mean(b * b) - mu_b2
    cov_ab = box_mean(a * b) - mu_ab

    ssim_map = ((2 * mu_ab + c1) * (2 * cov_ab + c2)) / (
        (mu_a2 + mu_b2 + c1) * (var_a + var_b + c2)
    )
    return float(np.clip(ssim_map.mean(), -1.0, 1.0))


def compute_ssim(orig: Image.Image, repro: Image.Image) -> tuple[float, str]:
    """Return (ssim, path_label) on 512x512 grayscale. Prefers scikit-image."""
    a = to_gray_array(orig)
    b = to_gray_array(repro)
    try:
        from skimage.metrics import structural_similarity as sk_ssim

        val = sk_ssim(a, b, data_range=255.0)
        return float(val), "skimage"
    except ImportError:
        return _ssim_numpy(a, b), "numpy-fallback"


# ---------------------------------------------------------------------------------
# ORB good-match count (opencv only; skipped if cv2 is absent)
# ---------------------------------------------------------------------------------
def orb_good_matches(orig: Image.Image, repro: Image.Image) -> tuple[int | None, str]:
    """Return (good_match_count, note). None when opencv is not installed."""
    try:
        import cv2
    except ImportError:
        return None, "skipped: opencv not installed (pip install opencv-python-headless)"

    a = np.asarray(orig.convert("L"))
    b = np.asarray(repro.convert("L"))
    orb = cv2.ORB_create(nfeatures=500)
    _, des_a = orb.detectAndCompute(a, None)
    _, des_b = orb.detectAndCompute(b, None)
    if des_a is None or des_b is None:
        return 0, "computed: no descriptors in one image"

    matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    matches = matcher.match(des_a, des_b)
    good = sum(1 for m in matches if m.distance < 64)
    return good, "computed"


# ---------------------------------------------------------------------------------
# Palette comparison (CIELAB) -- the color signal SSIM cannot see
# ---------------------------------------------------------------------------------
# Pixels this close to white/black/gray are chrome (background, axes, text), not data.
WHITE_CUT, BLACK_CUT, MIN_CHROMA = 242, 28, 18


def _srgb_to_lab(rgb: np.ndarray) -> np.ndarray:
    """sRGB [0,255] -> CIELAB (D65). Accepts (...,3).

    RGB distance correlates poorly with 'looks wrong'; LAB is roughly perceptually
    uniform, so one dE threshold means the same thing across the whole space.
    """
    arr = np.asarray(rgb, dtype=np.float64).reshape(-1, 3) / 255.0
    lin = np.where(arr <= 0.04045, arr / 12.92, ((arr + 0.055) / 1.055) ** 2.4)
    m = np.array([
        [0.4124564, 0.3575761, 0.1804375],
        [0.2126729, 0.7151522, 0.0721750],
        [0.0193339, 0.1191920, 0.9503041],
    ])
    xyz = lin @ m.T
    t = xyz / np.array([0.95047, 1.00000, 1.08883])
    d = 6.0 / 29.0
    f = np.where(t > d ** 3, np.cbrt(t), t / (3 * d * d) + 4.0 / 29.0)
    return np.stack([116.0 * f[:, 1] - 16.0,
                     500.0 * (f[:, 0] - f[:, 1]),
                     200.0 * (f[:, 1] - f[:, 2])], axis=1)


def _delta_e(a, b) -> float:
    """CIE76 dE between two sRGB triples. ~2.3 = just-noticeable difference."""
    return float(np.sqrt(np.sum((_srgb_to_lab(np.asarray([a], float))[0]
                                 - _srgb_to_lab(np.asarray([b], float))[0]) ** 2)))


def dominant_colors(img: Image.Image, max_colors: int = 10):
    """[(rgb, share)] of dominant non-chrome colors, most common first.

    Two-stage, because an exact-value histogram alone only works on flat/vector
    output. A published raster (JPEG-ish, small anti-aliased markers) can carry ~as
    many distinct RGBs as it has data pixels -- measured 0.82 distinct-per-pixel on
    the Lohoff 2b reference -- so every individual share falls under the floor and
    the histogram returns NOTHING. That silently removed the palette gate on exactly
    the figures it exists to judge, so fall back to LAB clustering.
    """
    px = np.asarray(img.convert("RGB")).reshape(-1, 3)
    mx, mn = px.max(axis=1), px.min(axis=1)
    chroma = mx.astype(np.int16) - mn.astype(np.int16)
    data = px[~((mn > WHITE_CUT) | (mx < BLACK_CUT) | (chroma < MIN_CHROMA))]
    if data.size == 0:
        return []
    packed = (data[:, 0].astype(np.uint32) << 16) | (data[:, 1].astype(np.uint32) << 8) | data[:, 2]
    vals, counts = np.unique(packed, return_counts=True)
    total = float(counts.sum())
    out = []
    for i in np.argsort(-counts):
        if len(out) >= max_colors:
            break
        share = counts[i] / total
        if share < 0.004:
            break
        v = int(vals[i])
        rgb = ((v >> 16) & 255, (v >> 8) & 255, v & 255)
        if any(_delta_e(rgb, prev) < 6.0 for prev, _ in out):   # merge anti-aliasing
            continue
        out.append((rgb, float(share)))

    if sum(s for _, s in out) >= 0.25 and len(out) >= 2:
        return out
    return _cluster_colors_lab(data, max_colors=max_colors)


def _cluster_colors_lab(data: np.ndarray, max_colors: int = 10,
                        iters: int = 10, sample_cap: int = 40000):
    """k-means in CIELAB over non-chrome pixels -> [(rgb, share)].

    Deterministic (farthest-point init from the darkest pixel) so the same pair of
    figures always yields the same dE -- a fidelity gate that changed run to run
    would be worse than none.
    """
    if len(data) == 0:
        return []
    sample = data[::max(1, len(data) // sample_cap + 1)]
    lab = _srgb_to_lab(sample.astype(np.float64))
    k = int(max(2, min(max_colors, len(np.unique(sample, axis=0)))))

    centers = [lab[int(np.argmin(lab[:, 0]))]]
    for _ in range(k - 1):
        d = np.min(np.stack([np.sum((lab - c) ** 2, axis=1) for c in centers]), axis=0)
        centers.append(lab[int(np.argmax(d))])
    C = np.stack(centers)

    assign = np.zeros(len(lab), dtype=np.int64)
    for _ in range(iters):
        new = ((lab[:, None, :] - C[None, :, :]) ** 2).sum(axis=2).argmin(axis=1)
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
        if share < 0.004:
            continue
        members = sample[assign == j]
        if not len(members):
            continue
        mlab = _srgb_to_lab(members.astype(np.float64))
        rgb = tuple(int(v) for v in members[int(np.argmin(((mlab - C[j]) ** 2).sum(axis=1)))])
        if any(_delta_e(rgb, prev) < 6.0 for prev, _ in out):
            continue
        out.append((rgb, share))
        if len(out) >= max_colors:
            break
    return out


def palette_delta_e(orig: Image.Image, repro: Image.Image, max_colors: int = 10):
    """Greedily match the two palettes and return (mean_dE, n_matched, detail).

    Greedy nearest-neighbour rather than Hungarian: it needs no scipy, and with the
    handful of well-separated colors a plot palette contains the two agree in
    practice. Unmatched target colors are reported, not silently dropped -- a missing
    category is a real reproduction failure.
    """
    a = dominant_colors(orig, max_colors)
    b = dominant_colors(repro, max_colors)
    if not a or not b:
        return None, 0, ("no non-chrome colors in %s"
                         % ("target" if not a else "reproduction"))

    # Match each target color to its perceptually nearest color in the reproduction,
    # WITHOUT consuming it. Anti-aliased edge pixels shift the frequency ranking when
    # marker size or DPI differs, so a consuming match would pair a real color against
    # an edge artifact and report a large dE for two figures that use the same palette
    # -- punishing a point-size change as a color error.
    pairs, weights, unmatched = [], [], []
    for rgb_a, share_a in a:
        j = min(range(len(b)), key=lambda k: _delta_e(rgb_a, b[k][0]))
        d = _delta_e(rgb_a, b[j][0])
        pairs.append((to_hex(rgb_a), to_hex(b[j][0]), round(d, 2)))
        weights.append(share_a)
        if d > 20.0:      # nothing in the reproduction resembles this target color
            unmatched.append(to_hex(rgb_a))
    if not pairs:
        return None, 0, "no comparable colors"

    # Share-weighted: a dominant series color matters more than a sliver of edge tint.
    wsum = float(sum(weights)) or 1.0
    mean_d = float(sum(p[2] * w for p, w in zip(pairs, weights)) / wsum)

    # Colors the reproduction introduced that have no counterpart in the target.
    extra = [to_hex(rgb_b) for rgb_b, _ in b
             if min(_delta_e(rgb_b, rgb_a) for rgb_a, _ in a) > 20.0]
    detail = {"pairs": pairs, "unmatched_target": unmatched, "extra_in_repro": extra}
    return mean_d, len(pairs), detail


def to_hex(rgb) -> str:
    r, g, b = (int(round(float(v))) for v in rgb[:3])
    return "#%02x%02x%02x" % (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))


# ---------------------------------------------------------------------------------
# Text comparison (OCR) -- the label signal SSIM cannot see
# ---------------------------------------------------------------------------------
def _norm_text(s: str) -> str:
    """Casefold and strip punctuation/space so 'Cell Type:' == 'cell_type'."""
    return "".join(ch for ch in s.lower() if ch.isalnum())


def _edit_ratio(a: str, b: str) -> float:
    """Similarity in [0,1] via difflib (stdlib -- no extra dependency)."""
    import difflib
    return difflib.SequenceMatcher(None, a, b).ratio()


def ocr_strings(img: Image.Image):
    """Return (list_of_strings, status). Degrades with a hint if OCR is absent."""
    try:
        import pytesseract
    except ImportError:
        return [], ("skipped: pytesseract not installed (pip install pytesseract; "
                    "also needs the 'tesseract' binary)")
    up = img.convert("L")
    up = up.resize((up.width * 2, up.height * 2), Image.LANCZOS)   # small text needs ~2x
    try:
        data = pytesseract.image_to_data(up, output_type=pytesseract.Output.DICT)
    except Exception as exc:
        return [], f"skipped: OCR failed ({exc}); is the 'tesseract' binary installed?"
    out = []
    for i, txt in enumerate(data.get("text", [])):
        t = (txt or "").strip()
        if not t:
            continue
        try:
            if float(data["conf"][i]) < 40:
                continue
        except (ValueError, KeyError, TypeError):
            pass
        out.append(t)
    return out, "computed"


def text_diff(orig: Image.Image, repro: Image.Image):
    """Compare on-panel text. Returns (summary_dict, status).

    Near-misses matter more than exact misses: 'Expression (log2 CPM)' vs
    'expression' is a paraphrase the agent introduced, and it is precisely the kind
    of error a grayscale structural metric scores as perfect.
    """
    a, sa = ocr_strings(orig)
    if sa != "computed":
        return None, sa
    b, sb = ocr_strings(repro)
    if sb != "computed":
        return None, sb
    na = [(_norm_text(s), s) for s in a if _norm_text(s)]
    nb = [(_norm_text(s), s) for s in b if _norm_text(s)]
    pool = [x[0] for x in nb]
    exact, near, missing = [], [], []
    for key, raw in na:
        if key in pool:
            exact.append(raw)
            pool.remove(key)
            continue
        best, ratio = None, 0.0
        for cand in pool:
            r = _edit_ratio(key, cand)
            if r > ratio:
                best, ratio = cand, r
        if best is not None and ratio >= 0.75:
            near.append({"target": raw, "repro": best, "similarity": round(ratio, 2)})
            pool.remove(best)
        else:
            missing.append(raw)
    total = max(1, len(na))
    return {
        "target_strings": len(na),
        "exact_matches": len(exact),
        "near_misses": near[:12],
        "missing_from_repro": missing[:12],
        "extra_in_repro": pool[:12],
        "match_rate": round(len(exact) / total, 3),
    }, "computed"


# ---------------------------------------------------------------------------------
# B-level prior -- the MINIMUM across every available signal
# ---------------------------------------------------------------------------------
_LADDER = ("B1", "B2", "B3", "B4", "B5")


def b_level_from_ssim(ssim: float) -> str:
    if ssim >= 0.95:
        return "B5"
    if ssim >= 0.85:
        return "B4"
    if ssim >= 0.70:
        return "B3"
    if ssim >= 0.40:
        return "B2"
    return "B1"


def b_level_from_color(mean_de: float | None) -> str | None:
    """Cap implied by palette agreement. dE ~2.3 is the just-noticeable threshold."""
    if mean_de is None:
        return None
    if mean_de <= 3.0:
        return "B5"      # perceptually identical palette
    if mean_de <= 8.0:
        return "B4"      # same palette family, slight shift
    if mean_de <= 18.0:
        return "B3"      # visibly different colors
    if mean_de <= 32.0:
        return "B2"      # wrong palette
    return "B1"          # unrelated colors


def b_level_from_text(td: dict | None) -> str | None:
    """Cap implied by label agreement (exact-match rate over target strings)."""
    if not td or td.get("target_strings", 0) == 0:
        return None
    rate = td["match_rate"]
    if rate >= 0.95:
        return "B5"
    if rate >= 0.80:
        return "B4"
    if rate >= 0.55:
        return "B3"
    if rate >= 0.25:
        return "B2"
    return "B1"


def combine_b_levels(levels: dict) -> tuple[str, str]:
    """Floor the B-level across all present signals; report what set the cap.

    A high SSIM must not survive a wrong palette or rewritten labels -- taking the
    minimum is what makes the ladder fail in the safe direction.
    """
    present = {k: v for k, v in levels.items() if v}
    if not present:
        return "B1", "no signals"
    worst = min(present.values(), key=_LADDER.index)
    limiters = sorted(k for k, v in present.items() if v == worst)
    return worst, "+".join(limiters)


# ---------------------------------------------------------------------------------
# Side-by-side comparison image
# ---------------------------------------------------------------------------------
def write_side_by_side(orig: Image.Image, repro: Image.Image, out_path: str) -> None:
    """Write 'original | reproduced' scaled to a common height, with a gap."""
    target_h = max(orig.height, repro.height)

    def scale_to_h(img: Image.Image) -> Image.Image:
        w = max(1, round(img.width * target_h / img.height))
        return img.resize((w, target_h), Image.BILINEAR)

    left = scale_to_h(orig)
    right = scale_to_h(repro)
    gap = 10
    canvas = Image.new("RGB", (left.width + gap + right.width, target_h), "white")
    canvas.paste(left, (0, 0))
    canvas.paste(right, (left.width + gap, 0))
    canvas.save(out_path)


# ---------------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare a reproduced figure against the target and report similarity.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("original", help="path to the original / target figure")
    parser.add_argument("reproduced", help="path to the reproduced figure")
    parser.add_argument("--out", default="./compare_diff.png", help="side-by-side PNG output path")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument("--no-color", action="store_true", help="skip the palette comparison")
    parser.add_argument("--no-text", action="store_true", help="skip the OCR text diff")
    args = parser.parse_args()

    orig = load_rgb(args.original)
    repro = load_rgb(args.reproduced)

    ham, phash_path = phash_hamming(orig, repro)
    ssim, ssim_path = compute_ssim(orig, repro)
    orb_count, orb_note = orb_good_matches(orig, repro)

    if args.no_color:
        mean_de, n_pairs, color_detail, color_status = None, 0, None, "skipped (--no-color)"
    else:
        mean_de, n_pairs, color_detail = palette_delta_e(orig, repro)
        color_status = "computed" if mean_de is not None else str(color_detail)

    if args.no_text:
        td, text_status = None, "skipped (--no-text)"
    else:
        td, text_status = text_diff(orig, repro)

    ssim_level = b_level_from_ssim(ssim)
    color_level = b_level_from_color(mean_de)
    text_level = b_level_from_text(td)
    b_prior, limited_by = combine_b_levels({
        "ssim": ssim_level, "color": color_level, "text": text_level,
    })

    write_side_by_side(orig, repro, args.out)

    which = {
        "phash": phash_path,
        "ssim": ssim_path,
        "orb": "cv2" if orb_count is not None else "unavailable",
        "color": color_status,
        "text": text_status,
    }

    if args.json:
        payload = {
            "original": args.original,
            "reproduced": args.reproduced,
            "phash_hamming": ham,
            "ssim": round(ssim, 4),
            "orb_good_matches": orb_count,
            "palette_mean_delta_e": None if mean_de is None else round(mean_de, 2),
            "palette_pairs_matched": n_pairs,
            "palette_detail": color_detail if isinstance(color_detail, dict) else None,
            "text_diff": td,
            "b_levels": {
                "ssim": ssim_level, "color": color_level, "text": text_level,
                "combined": b_prior, "limited_by": limited_by,
            },
            "b_level_prior": b_prior,
            "b_level_prior_note": (
                "Numeric prior = the MINIMUM across the SSIM, palette-dE and text-diff "
                "ladders, so a strong structural match can no longer mask a wrong palette "
                "or rewritten labels. Signals that could not be computed are excluded "
                "(see which_metrics_computed) -- a missing signal is NOT a pass. Category "
                "ORDER is still unmeasured here: verify it against the legend/tick order "
                "from extract_reference_spec.py. Your visual B1-B5 judgment remains "
                "authoritative."
            ),
            "which_metrics_computed": which,
            "diff_image": args.out,
            "next_step": (
                f"read('{args.out}') -- the side-by-side is written to disk, NOT returned "
                "inline, so it enters your context only if you open it. Compare the panels "
                "element by element (color+binding, order, label text, marker size, aspect, "
                "underlay, colorbar range/direction, presence/absence), name every "
                "difference, and assign B1-B5 from that list. Then ask what would make it "
                "closer and batch the cheap fixes into ONE polish re-render (which counts "
                "as a reproduction attempt). Stop when you cannot name a concrete "
                "difference from the target -- a preference is not a defect."
            ),
        }
        print(json.dumps(payload, indent=2))
    else:
        orb_str = str(orb_count) if orb_count is not None else f"(n/a - {orb_note})"
        de_str = f"{mean_de:.2f}" if mean_de is not None else f"(n/a - {color_status})"
        print("Figure comparison (fidelity self-evaluation)")
        print(f"  original    : {args.original}")
        print(f"  reproduced  : {args.reproduced}")
        print("  ---")
        print(f"  pHash Hamming distance : {ham:>4}   [{phash_path}]  (0 = identical, lower better)")
        print(f"  SSIM (512x512 gray)    : {ssim:.4f} [{ssim_path}]  (1.0 = identical)")
        print(f"  ORB good matches       : {orb_str:>4}   [{which['orb']}]  (higher better)")
        print(f"  Palette mean dE (LAB)  : {de_str:>6}  ({n_pairs} colors matched; <2.3 = imperceptible)")
        if isinstance(color_detail, dict):
            for tgt, rep, d in color_detail["pairs"][:6]:
                flag = "  <-- MISMATCH" if d > 8.0 else ""
                print(f"      target {tgt} -> repro {rep}   dE={d}{flag}")
            if color_detail["unmatched_target"]:
                print(f"      MISSING from reproduction: {', '.join(color_detail['unmatched_target'])}")
            if color_detail["extra_in_repro"]:
                print(f"      EXTRA in reproduction    : {', '.join(color_detail['extra_in_repro'])}")
        if td:
            print(f"  Text match rate        : {td['match_rate']:.2f}  "
                  f"({td['exact_matches']}/{td['target_strings']} strings exact)")
            for nm in td["near_misses"][:5]:
                print(f"      NEAR-MISS: target '{nm['target']}' -> repro '{nm['repro']}' ({nm['similarity']})")
            if td["missing_from_repro"]:
                print(f"      MISSING  : {', '.join(td['missing_from_repro'][:6])}")
        else:
            print(f"  Text diff              : (n/a - {text_status})")
        print("  ---")
        print(f"  B-level PRIOR          : {b_prior}   (min across signals; limited by: {limited_by})")
        print(f"      ssim->{ssim_level}   color->{color_level or 'n/a'}   text->{text_level or 'n/a'}")
        print("  NOTE: the B-level is the MINIMUM across the available ladders, so a high")
        print("        SSIM can no longer mask a wrong palette or rewritten labels. A signal")
        print("        that could NOT be computed is excluded -- absence is not a pass.")
        print("        Category ORDER is not measured here: check it against the legend/tick")
        print("        order from extract_reference_spec.py. Your visual B1-B5 judgment is")
        print("        still authoritative -- confirm or override by eye.")
        print("  ---")
        print(f"  NEXT: read('{args.out}') and compare the two panels ELEMENT BY ELEMENT.")
        print("        This image is on disk, NOT returned inline -- it enters your context")
        print("        only if you open it. Name every difference you can see (colors and")
        print("        their category binding, order, label text, marker size, aspect,")
        print("        underlay, colorbar range/direction, anything present in one and not")
        print("        the other), THEN assign B1-B5 from that list rather than from an")
        print("        overall impression. Finally ask what would make it closer and batch")
        print("        the cheap fixes into ONE polish re-render -- which counts as a")
        print("        reproduction attempt. Stop when you cannot name a concrete difference")
        print("        from the target: 'could look nicer' is a preference, not a defect.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
