#!/usr/bin/env python3
"""build_colormap.py -- produce the ONE colormap.yaml a reproduction plots from.

Part of the 'figure-reproduce' skill. Portable and self-contained: it imports NO
project package. Only PyYAML-free stdlib + numpy/Pillow (for the image tier) are
needed; anndata/h5py are used lazily for the dataset tier.

WHY THIS EXISTS
    Color has several possible sources of wildly different trustworthiness -- a
    user-supplied file, colors stored in the dataset, a reference figure's legend,
    or pixels sampled off a panel. Left implicit, the plotting code silently ends up
    on whichever one happened to be easiest, and nothing records which. This script
    tries them in priority order, writes ONE colormap.yaml, and stamps the tier it
    actually used so "colors came from the dataset" is never confused with "colors
    were guessed from a degraded raster".

TIERS (highest trust first)
    1 supplied    an existing palette file (--palette): user/authors' own mapping
    2 dataset     colors stored with the data (AnnData .uns["<key>_colors"])
    3 legend      swatches measured from a reference figure's legend
    4 pixels      dominant colors sampled off the panel  [ONLY if reliable]
    5 default     a named fallback palette -- a DEVIATION, never silent

    Categories and their ORDER come from the dataset whenever it has them
    (obs["<key>"].cat.categories), independent of where the colors came from.

USAGE
    python build_colormap.py -o colormap.yaml
        [--dataset data.h5ad --key celltype]     # categories + order (+ tier 2 colors)
        [--palette supplied.yaml]                # tier 1
        [--reference fig.png [--legend-box x0,y0,x1,y1]]   # tier 3 / 4
        [--allow-default]                        # permit tier 5 instead of failing

EXAMPLES
    # dataset supplies names+order, reference legend supplies colors
    python build_colormap.py --dataset adata.h5ad --key cell_type \
                             --reference fig2b.png -o colormap.yaml

    # user handed us the palette: it wins outright
    python build_colormap.py --palette uploads/colormap.yaml -o colormap.yaml

EXIT CODES
    0 wrote a colormap   1 no trustworthy source (use --allow-default to override)
    2 usage error
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)


def hint(pkg: str) -> str:
    return f"[degraded] optional dependency '{pkg}' not installed - try: pip install {pkg}"


# --------------------------------------------------------------------------- #
# Minimal YAML I/O (a flat "key: value" mapping -- no PyYAML required)
# --------------------------------------------------------------------------- #
def read_simple_yaml(path: str) -> dict:
    """Read a flat mapping. Uses PyYAML when present, else a tolerant fallback."""
    text = open(path).read()
    try:
        import yaml
        data = yaml.safe_load(text)
        return data if isinstance(data, dict) else {}
    except ImportError:
        out = {}
        for line in text.splitlines():
            line = line.split("#", 1)[0].rstrip()
            if not line or line.startswith(("-", " ")) or ":" not in line:
                continue
            k, v = line.split(":", 1)
            out[k.strip().strip('"\'')] = v.strip().strip('"\'')
        return out


def _norm_label(s: str) -> str:
    """Fold a legend label to a form that survives typography differences.

    A paper's legend and a dataset's categories routinely disagree on
    capitalisation, on punctuation inside compound names, and on British vs
    American spelling of the same term. Those are the same class, and refusing
    to pair them throws away a perfectly good measured palette.

    The fold is deliberately shallow -- case, non-alphanumerics, and the ae/e
    digraph -- because anything more aggressive starts merging categories that
    are genuinely distinct.
    """
    t = "".join(ch for ch in s.casefold() if ch.isalnum() or ch in "/ ")
    return " ".join(t.replace("ae", "e").split())


def _provenance_hash(mapping: dict, order: list, tier) -> str:
    """Short digest binding a colormap's colors, order and tier together.

    A tier stamp on its own is only a claim: a model can write `colormap.yaml`
    by hand -- header and all -- and present a default palette as a resolved one.
    That happened in a real run. Recomputing this digest proves the file came
    from this script and has not been edited since, which turns "please use the
    script" from a request into something `--verify` can check.
    """
    payload = json.dumps(
        {"tier": str(tier), "order": list(order),
         "map": {k: mapping[k] for k in order if k in mapping}},
        sort_keys=True, separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def verify_colormap(path: str) -> tuple[bool, str]:
    """Re-derive the digest from a colormap file and compare it to the stamp."""
    try:
        text = pathlib.Path(path).read_text()
    except OSError as e:
        return False, "cannot read %s: %s" % (path, e)

    stamped = tier = None
    mapping, order = {}, []
    for line in text.splitlines():
        st = line.strip()
        if st.startswith("# provenance"):
            stamped = st.split(":", 1)[1].strip()
        elif st.startswith("# source_tier"):
            tier = st.split(":", 1)[1].strip()
        elif st and not st.startswith("#") and ":" in st:
            k, v = st.split(":", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if v.startswith("#") and len(v) in (4, 7):
                mapping[k] = v
                order.append(k)

    if stamped is None:
        return False, (
            "no '# provenance' stamp: this file was NOT produced by "
            "build_colormap.py. A hand-written colormap is not a resolved one -- "
            "re-run the script and use its output."
        )
    actual = _provenance_hash(mapping, order, tier)
    if actual != stamped:
        return False, (
            "provenance mismatch (stamped %s, recomputed %s): the palette, its "
            "order, or the tier was edited after the script wrote it."
            % (stamped, actual)
        )
    return True, "provenance OK (tier %s, %d categories)" % (tier, len(order))


def write_colormap_yaml(path: str, mapping: dict, order: list, meta: dict) -> None:
    """Write colormap.yaml: provenance header, then `Category: "#hex"` in order."""
    L = ["# colormap.yaml -- the single source of truth for this figure's colors.",
         "# Generated by build_colormap.py. Plot from THIS file; do not re-derive",
         "# colors by eye and do not fall back to library defaults.",
         "#"]
    # Hash only the categories actually WRITTEN. `order` may list categories that
    # got no swatch (a label the legend lacks), and those lines never reach the
    # file -- so hashing the full order makes --verify recompute a different
    # digest and reject a legitimately generated colormap.
    written = [c for c in order if c in mapping]
    L.append("# provenance  : %s" % _provenance_hash(mapping, written, meta.get("tier")))
    L.append("# source_tier : %s" % meta.get("tier"))
    L.append("# how         : %s" % meta.get("how"))
    if meta.get("order_from"):
        L.append("# order_from  : %s" % meta["order_from"])
    if meta.get("warnings"):
        for w in meta["warnings"]:
            L.append("# WARNING     : %s" % w)
    L.append("")
    for cat in order:
        if cat in mapping:
            L.append('%s: "%s"' % (cat, mapping[cat]))
    for cat in mapping:                      # any not covered by `order`
        if cat not in order:
            L.append('%s: "%s"' % (cat, mapping[cat]))
    open(path, "w").write("\n".join(L) + "\n")


# --------------------------------------------------------------------------- #
# Categories + order, and tier-2 colors, from the dataset
# --------------------------------------------------------------------------- #
def from_dataset(path: str, key: str | None):
    """Return (categories, colors_or_None, key_used, note).

    Reads AnnData via `anndata` when available, else directly from the HDF5 layout
    (an .h5ad is just HDF5, and the categorical encoding is stable enough to read
    without the library -- which matters because the plotting env often has anndata
    but a helper-script env may not).
    """
    try:
        import anndata  # noqa: F401
        return _from_dataset_anndata(path, key)
    except ImportError:
        pass
    try:
        import h5py  # noqa: F401
        return _from_dataset_h5py(path, key)
    except ImportError:
        return [], None, None, hint("anndata (or h5py)") + " -- dataset tier skipped"


def _pick_key(candidates: list, key: str | None):
    if key:
        return key if key in candidates else None
    for c in candidates:                     # prefer an obvious cell-type column
        if any(h in c.lower() for h in ("celltype", "cell_type", "annotation", "cluster", "leiden", "louvain")):
            return c
    return candidates[0] if len(candidates) == 1 else None


def _from_dataset_anndata(path: str, key: str | None):
    import anndata
    a = anndata.read_h5ad(path, backed="r")
    cats_cols = [c for c in a.obs.columns
                 if str(a.obs[c].dtype) == "category" and len(a.obs[c].cat.categories) <= 200]
    k = _pick_key(cats_cols, key)
    if k is None:
        return [], None, None, ("dataset has no single obvious categorical column; "
                                "pass --key (candidates: %s)" % ", ".join(cats_cols[:8]))
    cats = [str(c) for c in a.obs[k].cat.categories]
    colors = None
    ck = f"{k}_colors"
    if ck in a.uns and len(a.uns[ck]) == len(cats):
        colors = [str(c) for c in a.uns[ck]]
    return cats, colors, k, "read via anndata"


def _from_dataset_h5py(path: str, key: str | None):
    import h5py
    with h5py.File(path, "r") as f:
        if "obs" not in f:
            return [], None, None, "no /obs group in file"
        cand = []
        for name in f["obs"]:
            g = f["obs"][name]
            if isinstance(g, h5py.Group) and "categories" in g:
                cand.append(name)
        k = _pick_key(cand, key)
        if k is None:
            return [], None, None, ("no single obvious categorical column; pass --key "
                                    "(candidates: %s)" % ", ".join(cand[:8]))
        raw = f["obs"][k]["categories"][...]
        cats = [c.decode() if isinstance(c, bytes) else str(c) for c in raw]
        colors = None
        ck = f"{k}_colors"
        if "uns" in f and ck in f["uns"]:
            raw = f["uns"][ck][...]
            vals = [c.decode() if isinstance(c, bytes) else str(c) for c in raw]
            if len(vals) == len(cats):
                colors = vals
        return cats, colors, k, "read via h5py (anndata not installed)"


# --------------------------------------------------------------------------- #
# Colors from a reference figure (tiers 3 and 4)
# --------------------------------------------------------------------------- #
def from_reference(image: str, legend_box=None, max_colors: int = 40):
    """Return (entries, palette_reliability, note) using extract_reference_spec."""
    try:
        from PIL import Image
        import extract_reference_spec as ers
    except ImportError as exc:
        return [], {}, f"[degraded] cannot load the extractor ({exc})"
    try:
        img = Image.open(image).convert("RGB")
    except OSError as exc:
        return [], {}, f"cannot read reference '{image}': {exc}"

    box = legend_box or ers.autodetect_legend_box(img)
    entries, status = ([], "no legend region found") if box is None else \
        ers.find_legend_swatches(img, box, max_colors)

    # Believing the parser rather than the measurement is how a legendless panel ends
    # up with a palette. On a violin figure with no legend at all, three fragments of
    # violin outline in the margin parsed cleanly and became a two-colour "palette"
    # that beat every later tier -- including the marks tier that would have read the
    # panel correctly. A legend we cannot vouch for must not outrank one we can.
    if entries and box:
        verdict, ev = ers.legend_confidence(entries, box[2] - box[0], box[3] - box[1])
        if verdict == "rejected":
            return [], {}, ("legend candidate rejected: %s" % ev.get("reason", "not a legend"))
        if verdict == "low":
            status = "%s; LOW CONFIDENCE: %s" % (status, ev.get("reason", ""))

    # Attach OCR labels to each swatch. extract_reference_spec does this inline in
    # its main(), so a caller reaching find_legend_swatches directly gets colors
    # with no names -- which forces positional pairing, and positional pairing is
    # wrong whenever the figure shows classes the dataset lacks. Labels let the
    # swatches be matched by name instead.
    if entries and box:
        lx0, ly0, lx1, ly1 = box
        try:
            items, txt_status = ers.ocr_lines(
                img, (lx0, ly0, min(img.width, lx1 + 260), ly1), axis="y")
        except Exception:
            items, txt_status = [], "ocr unavailable"
        if txt_status == "ok":
            # OCR coords are crop-relative; entry boxes are absolute.
            for i in items:
                i["y"] += ly0
                i["x"] += lx0
            for e in entries:
                ey0, ey1 = e["box"][1], e["box"][3]
                mid = (ey0 + ey1) / 2.0
                near = [i for i in items
                        if (ey0 - 6 <= i["y"] <= ey1 + 6 or abs(i["y"] - mid) < 10)
                        and i["x"] >= e["box"][0] - 4]
                if near:
                    e["label"] = " ".join(
                        i["text"] for i in sorted(near, key=lambda d: d["x"]))

    import numpy as np
    px = np.asarray(img)
    flat = px.reshape(-1, 3)
    data = flat[~ers.is_chrome(flat)]
    rel = {}
    if len(data) > 100:
        ratio = len(np.unique(data, axis=0)) / float(len(data))
        rel = {"distinct_color_ratio": round(float(ratio), 3),
               "reliable": ratio <= 0.5}
    return entries, rel, status


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
DEFAULT_PALETTE = [   # Okabe-Ito (colorblind-safe) then tab10 -- only as tier 5
    "#e69f00", "#56b4e9", "#009e73", "#f0e442", "#0072b2", "#d55e00", "#cc79a7",
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2",
    "#7f7f7f", "#bcbd22", "#17becf", "#aec7e8", "#ffbb78", "#98df8a",
]


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Build one colormap.yaml from the most trustworthy source available.",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-o", "--out", default="colormap.yaml", help="output path")
    ap.add_argument("--dataset", help=".h5ad providing categories + order (and maybe colors)")
    ap.add_argument("--key", help="obs column holding the categories")
    ap.add_argument("--palette", help="an existing palette file (tier 1, wins outright)")
    ap.add_argument("--reference", help="reference figure to read a legend from")
    ap.add_argument("--legend-box", help="x0,y0,x1,y1 of the legend in --reference")
    ap.add_argument("--marks-box", metavar="x0,y0,x1,y1",
                    help="tier 4: plot area of a LEGENDLESS categorical panel "
                         "(bar/violin/box). Reads one colour per mark along the "
                         "category axis, in plotting order.")
    ap.add_argument("--marks-axis", choices=("x", "y"), default="x",
                    help="category axis for --marks-box (default x)")
    ap.add_argument("--verify", metavar="FILE", default=None,
                    help="check FILE carries a valid provenance stamp, then exit")
    ap.add_argument("--allow-default", action="store_true",
                    help="permit the tier-5 default palette instead of failing")
    ap.add_argument("--json", action="store_true", help="also print the result as JSON")
    args = ap.parse_args()

    if args.verify:
        ok, msg = verify_colormap(args.verify)
        sys.stdout.write(("OK: " if ok else "FAIL: ") + msg + "\n")
        return 0 if ok else 1

    warnings: list[str] = []
    order: list[str] = []
    order_from = None

    # ---- categories + order (independent of the color source) ----
    ds_colors = None
    if args.dataset:
        cats, ds_colors, key_used, note = from_dataset(args.dataset, args.key)
        if cats:
            order, order_from = cats, f"dataset obs['{key_used}'] ({note})"
        else:
            warnings.append(f"dataset gave no categories: {note}")

    mapping: dict = {}
    tier = how = None

    # Measured-from-the-target sources are tried FIRST whenever a reference figure is
    # available. A stored or supplied palette describes *a* colouring; the legend
    # describes *this figure's* colouring, and only the second is evidence about the
    # thing being reproduced. Measured on a real task, `uns[<key>_colors]` was
    # byte-identical to the plotting library's default palette and a mean RGB distance
    # of 127 from the published panel -- every category wrong, from a source that is
    # stored, correctly keyed, correctly ordered and exactly the right length, so no
    # structural check can reject it. Deferring it costs nothing when it happens to be
    # right and saves the whole figure when it is not.
    reference_available = bool(args.reference)

    # ---- tier 1: a supplied palette (deferred when the target can be measured) ----
    if args.palette and not reference_available:
        if not os.path.exists(args.palette):
            sys.stderr.write(f"ERROR: --palette '{args.palette}' not found\n")
            return 2
        supplied = read_simple_yaml(args.palette)
        supplied = {k: v for k, v in supplied.items() if isinstance(v, str) and v.startswith("#")}
        if supplied:
            mapping, tier, how = supplied, "1-supplied", f"user-supplied file {args.palette}"
            if not order:
                order, order_from = list(supplied), "supplied palette file"

    # ---- tier 2: colors stored with the data (deferred when measurable) ----
    if (not mapping and not reference_available
            and ds_colors and order and len(ds_colors) == len(order)):
        mapping = dict(zip(order, ds_colors))
        tier, how = "2-dataset", f"AnnData uns['{args.key or 'auto'}_colors']"

    # ---- tiers 3/4: measured off the reference figure ----
    if not mapping and args.reference:
        box = None
        if args.legend_box:
            try:
                box = tuple(int(float(v)) for v in args.legend_box.split(","))
                assert len(box) == 4
            except (ValueError, AssertionError):
                sys.stderr.write("ERROR: --legend-box expects x0,y0,x1,y1\n")
                return 2
        entries, rel, note = from_reference(args.reference, box)
        labeled = [e for e in entries if e.get("label")]
        if labeled and order and len(labeled) != len(order):
            # Counts differ, but labels exist: pair them by NORMALISED label rather
            # than refusing. A near-miss is the common case (a scale bar or an
            # orientation compass read as an extra swatch, or the figure showing
            # classes the dataset lacks), and the paired colors are still measured.
            by_norm = {_norm_label(e["label"]): e["hex"] for e in labeled}
            matched = {c: by_norm[_norm_label(c)] for c in order if _norm_label(c) in by_norm}
            if len(matched) >= max(1, int(0.8 * len(order))):
                mapping = matched
                tier, how = "3-legend", f"legend swatches in {args.reference} (matched by label)"
                missing = [c for c in order if c not in matched]
                extra = [e["label"] for e in labeled
                         if _norm_label(e["label"]) not in {_norm_label(c) for c in order}]
                if missing:
                    warnings.append(
                        "no legend swatch matched these dataset categories: %s -- they "
                        "are absent from colormap.yaml; plot them explicitly or exclude "
                        "them." % ", ".join(missing))
                if extra:
                    warnings.append(
                        "legend entries with no dataset category: %s (figure shows "
                        "classes this dataset lacks) -- note this in the repro note."
                        % ", ".join(extra))
            else:
                labeled = []          # too few matched; fall through to the branches below
        if mapping:
            pass                      # already resolved by label matching above
        elif labeled and (not order or len(labeled) == len(order)):
            keys = [e["label"] for e in labeled] if not order else order
            mapping = dict(zip(keys, [e["hex"] for e in labeled]))
            tier, how = "3-legend", f"legend swatches in {args.reference}"
            if not order:
                order, order_from = keys, "reference legend (top->bottom)"
        elif entries and order and abs(len(entries) - len(order)) <= 2:
            # Swatches found but unlabeled: order comes from the dataset, colors from
            # the legend's reading order. An exact count match is ideal, but a
            # near-miss is common and recoverable -- a scale bar or an orientation
            # compass reads as an extra swatch, and a figure may show classes the
            # dataset lacks. Refusing on a 23-vs-22 gap discards a fully measured
            # palette and forces an invented one, which is strictly worse.
            n = min(len(entries), len(order))
            mapping = dict(zip(order[:n], [e["hex"] for e in entries[:n]]))
            tier, how = "3-legend", f"legend swatches in {args.reference} (unlabeled; aligned by order)"
            warnings.append("legend swatches were unlabeled; colors aligned to dataset "
                            "category order -- VERIFY this pairing against the figure")
            if len(entries) != len(order):
                warnings.append(
                    "legend had %d swatches for %d categories; paired the first %d in "
                    "reading order. Check the first and last few pairings against the "
                    "figure -- a stray swatch (scale bar, compass) shifts everything "
                    "after it." % (len(entries), len(order), n))
        elif entries and not order and args.marks_box and len(entries) < 4:
            # A handful of unlabeled, unnamed swatches is weak evidence, and accepting
            # it here would consume the run before the marks tier -- which was asked
            # for explicitly -- ever got to look at the panel.
            warnings.append(
                "ignoring %d weak unlabeled legend swatch(es) in favour of --marks-box"
                % len(entries))
        elif entries and not order:
            # Swatches found, but we have neither OCR labels nor dataset categories to
            # name them. The colors and their ORDER are still measured facts, so emit
            # them under positional placeholders rather than discarding the one thing
            # the figure did tell us. The agent renames these from the panel.
            keys = ["category_%02d" % (i + 1) for i in range(len(entries))]
            mapping = dict(zip(keys, [e["hex"] for e in entries]))
            order, order_from = keys, "reference legend (top->bottom)"
            tier, how = "3-legend", f"legend swatches in {args.reference} (unlabeled, positional keys)"
            warnings.append(
                "swatch labels unavailable (no OCR and no --dataset): keys are "
                "POSITIONAL placeholders in the legend's reading order. Rename them to "
                "the panel's category names -- keep the order -- before plotting.")
        elif entries and order:
            warnings.append(
                "legend has %d swatches but the dataset has %d categories; refusing to "
                "guess the pairing. Pass --legend-box to tighten the crop, or supply "
                "--palette." % (len(entries), len(order)))
        else:
            if not rel.get("reliable", False):
                warnings.append(
                    "reference palette is NOT reliably recoverable "
                    f"(distinct_color_ratio={rel.get('distinct_color_ratio')}, >0.5 means "
                    "sub-pixel/compressed markers): pixel sampling was refused")
            else:
                warnings.append(f"no usable legend in {args.reference}: {note}")

    # ---- tier 4: colours read off the MARKS of a legendless categorical panel ----
    # Bar/violin/box panels name their categories on the tick axis and colour the marks
    # themselves. There is no legend to read, so tiers 1-3 all miss and the run would
    # otherwise fall through to an invented default palette -- for a figure whose
    # colours are sitting right there, fully measurable.
    if not mapping and args.reference and args.marks_box:
        try:
            mbox = tuple(int(float(v)) for v in args.marks_box.split(","))
            assert len(mbox) == 4
        except (ValueError, AssertionError):
            sys.stderr.write("ERROR: --marks-box expects x0,y0,x1,y1\n")
            return 2
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import extract_reference_spec as ers
        from PIL import Image
        marks, mstatus = ers.find_mark_colors(
            Image.open(args.reference).convert("RGB"), mbox, axis=args.marks_axis)
        if marks and order:
            if len(marks) == len(order):
                mapping = dict(zip(order, [m["hex"] for m in marks]))
                tier = "4-marks"
                how = (f"per-category mark colours in {args.reference} "
                       f"({args.marks_axis}-axis order)")
                warnings.append(
                    "colours came from the MARKS, paired to dataset category order by "
                    "position. The figure's category order must match the dataset's for "
                    "this to be right -- check the first and last mark against the panel.")
            else:
                warnings.append(
                    "found %d marks but the dataset has %d categories; refusing to guess "
                    "the pairing. Tighten --marks-box, or reorder/subset the dataset "
                    "categories to the panel's %d." % (len(marks), len(order), len(marks)))
        elif marks:
            keys = ["category_%02d" % (i + 1) for i in range(len(marks))]
            mapping = dict(zip(keys, [m["hex"] for m in marks]))
            order, order_from = keys, "reference marks (category-axis order)"
            tier = "4-marks"
            how = f"per-category mark colours in {args.reference} (positional keys)"
            warnings.append(
                "no --dataset categories: keys are POSITIONAL placeholders in the "
                "panel's category-axis order. Rename them -- keep the order.")
        else:
            warnings.append(f"no marks readable in {args.reference}: {mstatus}")

    # ---- deferred tiers 1/2: the target could not be measured after all ----
    # Preferring the legend must not mean LOSING a usable palette when the legend turns
    # out to be unreadable, so the sources skipped above are reconsidered here -- with a
    # warning, because they were not checked against the panel.
    if not mapping and reference_available and args.palette:
        if os.path.exists(args.palette):
            supplied = read_simple_yaml(args.palette)
            supplied = {k: v for k, v in supplied.items()
                        if isinstance(v, str) and v.startswith("#")}
            if supplied:
                mapping, tier = supplied, "1-supplied"
                how = f"user-supplied file {args.palette} (reference not measurable)"
                if not order:
                    order, order_from = list(supplied), "supplied palette file"
                warnings.append(
                    "fell back to the supplied palette because the reference legend could "
                    "not be measured; these colours have NOT been checked against the "
                    "panel -- spot-check a few before trusting them.")
    if (not mapping and reference_available
            and ds_colors and order and len(ds_colors) == len(order)):
        mapping = dict(zip(order, ds_colors))
        tier = "2-dataset"
        how = f"AnnData uns['{args.key or 'auto'}_colors'] (reference not measurable)"
        warnings.append(
            "fell back to colours stored in the dataset because the reference legend "
            "could not be measured. A stored colour list is often the plotting library's "
            "default rather than the figure's palette -- spot-check several categories "
            "against reference pixels before trusting this.")

    # ---- tier 5: a documented default, never silent ----
    if not mapping:
        if not args.allow_default:
            sys.stderr.write(
                "ERROR: no trustworthy color source.\n"
                "  Tried: --palette (tier 1), dataset uns colors (tier 2), "
                "reference legend (tier 3).\n"
                "  Colors sampled off a dense/compressed panel are refused on purpose "
                "-- they are not recoverable.\n"
                "  Fix by supplying one of:\n"
                "    --palette <file>            the authors'/user's own mapping\n"
                "    --reference <fig> --legend-box x0,y0,x1,y1   if a legend exists\n"
                "  Or re-run with --allow-default to assign a documented fallback "
                "palette (records a DEVIATION).\n")
            for w in warnings:
                sys.stderr.write(f"  note: {w}\n")
            return 1
        if not order:
            sys.stderr.write("ERROR: --allow-default needs categories; pass --dataset/--key.\n")
            return 2
        mapping = {c: DEFAULT_PALETTE[i % len(DEFAULT_PALETTE)] for i, c in enumerate(order)}
        tier, how = "5-default", "fallback palette (Okabe-Ito + tab10)"
        warnings.append("DEVIATION: colors are a default palette, NOT the target's. "
                        "Record this in the repro note.")

    meta = {"tier": tier, "how": how, "order_from": order_from, "warnings": warnings}
    if not order:
        order = list(mapping)
    write_colormap_yaml(args.out, mapping, order, meta)

    print(f"wrote {args.out}")
    print(f"  tier       : {tier}")
    print(f"  how        : {how}")
    print(f"  categories : {len(mapping)}" + (f"  (order from {order_from})" if order_from else ""))
    for w in warnings:
        print(f"  WARNING    : {w}")
    if args.json:
        print(json.dumps({"tier": tier, "how": how, "order": order,
                          "colormap": mapping, "warnings": warnings}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
