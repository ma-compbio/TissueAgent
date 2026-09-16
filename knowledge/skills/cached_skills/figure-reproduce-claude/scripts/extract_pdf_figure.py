#!/usr/bin/env python3
"""Extract a figure image + its caption from a paper PDF.

Part of the 'figure-reproduce' skill. This is a self-contained stand-in for the
platform 'pdf_reader' agent: given a paper PDF it acquires the reproduction
*target* — a rendered page image, any embedded raster figures on that page, and
the surrounding figure-caption text — so the agent can identify the plot type,
its panels, and the color encoding before attempting to redraw it.

The script is portable and has NO dependency on any project package. PyMuPDF
('fitz') is the preferred engine; if it is missing the script degrades to
text-only caption extraction via 'pypdf' or 'pdfplumber' when available.

Usage
-----
    # Render page 1 to PNG, dump embedded images, print nearby captions:
    python extract_pdf_figure.py paper.pdf --page 1 --out ./pdf_figures

    # No --page: scan the whole PDF and print an index (page -> first caption):
    python extract_pdf_figure.py paper.pdf

    # Jump to the first page whose caption matches a label:
    python extract_pdf_figure.py paper.pdf --fig "Figure 3" --out ./figs

    # Isolate a sub-PANEL: after viewing the whole page, crop a fractional bbox
    # (x0,y0,x1,y1 as fractions of the page; e.g. the top-left panel):
    python extract_pdf_figure.py paper.pdf --page 8 --crop 0,0,0.33,0.5 --out ./figs

    # Machine-readable output:
    python extract_pdf_figure.py paper.pdf --page 1 --json

Exit codes: non-zero ONLY on a real usage error (bad/missing/unreadable path).
A merely-unavailable capability (optional dependency missing) is a warning.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Caption markers commonly used in Nature-series and general biology papers.
CAPTION_RE = re.compile(
    r"^\s*(Extended\s+Data\s+(Fig(?:ure)?|Table)|Supplementary\s+Fig(?:ure)?|Fig(?:ure)?)\b",
    re.IGNORECASE,
)


def _warn(msg: str) -> None:
    """Print a one-line warning to stderr (non-fatal)."""
    print(f"[warn] {msg}", file=sys.stderr)


def _try_import_fitz():
    """Return the PyMuPDF module or None (with an install hint)."""
    try:
        import fitz  # type: ignore

        return fitz
    except ImportError:
        _warn("PyMuPDF not found — image rendering disabled. Install: pip install PyMuPDF")
        return None


def _first_caption_line(text: str) -> str:
    """Return the first line in a text block that looks like a caption, else ''."""
    for line in text.splitlines():
        if CAPTION_RE.match(line):
            return line.strip()
    return ""


# --------------------------------------------------------------------------- #
# PyMuPDF path (rendering + embedded images + captions)
# --------------------------------------------------------------------------- #
def _page_captions(page) -> list[str]:
    """Collect FULL caption paragraphs on a fitz page, in reading order.

    A figure caption usually spans several layout blocks: the ``Fig. N | Title``
    block is followed by the per-panel description (``a ...``, ``b ...``, ``c ...``)
    in separate blocks that do NOT start with a figure marker. We start a caption
    at a block matching ``CAPTION_RE`` and greedily append the following blocks
    (the continuation) until the next caption marker, a length cap, or a block
    budget — so the returned caption includes the sub-panel text the reproduction
    needs (not just the truncated first line).
    """
    blocks = [b for b in page.get_text("blocks") if b[4].strip()]  # reading order
    captions: list[str] = []
    i, n = 0, len(blocks)
    while i < n:
        if not CAPTION_RE.match(blocks[i][4].strip()):
            i += 1
            continue
        parts = [blocks[i][4].strip()]
        total = len(parts[0])
        j = i + 1
        appended = 0
        # Append continuation blocks: stop at the next caption, ~1600 chars, or 10 blocks.
        while j < n and total < 1600 and appended < 10:
            btext = blocks[j][4].strip()
            if CAPTION_RE.match(btext):
                break
            parts.append(btext)
            total += len(btext)
            appended += 1
            j += 1
        captions.append(re.sub(r"\s+", " ", " ".join(parts)))
        i = j
    return captions


def _render_page(fitz, page, out_dir: Path, page_num: int, dpi: int) -> str:
    """Render a page to PNG at the given DPI. Return the saved path."""
    pix = page.get_pixmap(dpi=dpi)
    dest = out_dir / f"page{page_num:03d}.png"
    pix.save(dest)
    return str(dest)


def _render_crop(fitz, page, out_dir: Path, page_num: int, dpi: int,
                 crop: tuple[float, float, float, float]) -> str:
    """Render a fractional sub-rectangle of a page to PNG (panel isolation).

    ``crop`` is (x0, y0, x1, y1) as fractions of the page in [0, 1]. Use it to
    cut a single panel out of a multi-panel figure page AFTER viewing the whole
    page. Returns the saved path.
    """
    x0, y0, x1, y1 = crop
    r = page.rect
    clip = fitz.Rect(
        r.x0 + x0 * r.width, r.y0 + y0 * r.height,
        r.x0 + x1 * r.width, r.y0 + y1 * r.height,
    )
    pix = page.get_pixmap(dpi=dpi, clip=clip)
    dest = out_dir / f"page{page_num:03d}_crop.png"
    pix.save(dest)
    return str(dest)


def _extract_embedded(fitz, doc, page, out_dir: Path, page_num: int) -> list[str]:
    """Save embedded raster images referenced by a page. Return saved paths."""
    saved: list[str] = []
    for idx, info in enumerate(page.get_images(full=True), start=1):
        xref = info[0]
        try:
            data = doc.extract_image(xref)
        except Exception as exc:  # corrupt/unsupported image object
            _warn(f"could not extract image xref={xref}: {exc}")
            continue
        ext = data.get("ext", "png")
        dest = out_dir / f"page{page_num:03d}_img{idx:02d}.{ext}"
        dest.write_bytes(data["image"])
        saved.append(str(dest))
    return saved


def _scan_index(fitz, doc, fig_label: str | None) -> tuple[list[dict], int | None]:
    """Scan all pages for caption markers.

    Returns (index, matched_page) where index is [{page, caption}] for pages
    that contain a caption, and matched_page is the 1-based page whose caption
    matches --fig (or None).
    """
    index: list[dict] = []
    matched: int | None = None
    needle = re.sub(r"\s+", " ", fig_label).lower() if fig_label else None
    for i in range(doc.page_count):
        captions = _page_captions(doc[i])
        if not captions:
            continue
        first = captions[0]
        # The index shows the caption TITLE only (captions are now full paragraphs).
        title = first if len(first) <= 100 else first[:100].rstrip() + " …"
        index.append({"page": i + 1, "caption": title})
        # Anchor --fig matching to the caption TITLE (first ~48 chars), so a body
        # that merely references another figure ("...explained in Fig. 3...") does
        # not falsely match.
        if needle and matched is None:
            if any(needle in re.sub(r"\s+", " ", c).lower()[:48] for c in captions):
                matched = i + 1
    return index, matched


def _process_page(fitz, doc, page_num: int, out_dir: Path, dpi: int,
                  crop: tuple[float, float, float, float] | None = None) -> dict:
    """Render + extract images + captions for a single 1-based page.

    When ``crop`` is given, also save a cropped render of that fractional
    sub-rectangle (panel isolation).
    """
    if page_num < 1 or page_num > doc.page_count:
        raise ValueError(f"--page {page_num} out of range (1..{doc.page_count})")
    out_dir.mkdir(parents=True, exist_ok=True)
    page = doc[page_num - 1]
    saved = [_render_page(fitz, page, out_dir, page_num, dpi)]
    if crop is not None:
        saved.append(_render_crop(fitz, page, out_dir, page_num, dpi, crop))
    saved.extend(_extract_embedded(fitz, doc, page, out_dir, page_num))
    captions = _page_captions(page)
    return {"page": page_num, "saved_images": saved, "captions": captions}


# --------------------------------------------------------------------------- #
# Text-only fallback (no PyMuPDF): caption extraction via pypdf/pdfplumber
# --------------------------------------------------------------------------- #
def _fallback_captions(pdf_path: Path, page_num: int | None) -> list[dict] | None:
    """Extract captions without rendering. Return per-page dicts, or None."""
    pages_text: list[str] = []
    try:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(str(pdf_path))
        pages_text = [(p.extract_text() or "") for p in reader.pages]
    except ImportError:
        try:
            import pdfplumber  # type: ignore

            with pdfplumber.open(str(pdf_path)) as pdf:
                pages_text = [(pg.extract_text() or "") for pg in pdf.pages]
        except ImportError:
            _warn("no PDF text engine — install one of: pip install PyMuPDF pypdf pdfplumber")
            return None

    results: list[dict] = []
    for i, text in enumerate(pages_text):
        if page_num is not None and (i + 1) != page_num:
            continue
        caps = [re.sub(r"\s+", " ", ln.strip()) for ln in text.splitlines() if CAPTION_RE.match(ln)]
        if caps or page_num is not None:
            results.append({"page": i + 1, "saved_images": [], "captions": caps})
    return results


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Extract a figure image + caption from a paper PDF (figure-reproduce skill).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("pdf_path", help="Path to the paper PDF.")
    p.add_argument("--page", type=int, default=None, help="1-based page to render/extract.")
    p.add_argument("--fig", default=None, help='Jump to first page whose caption matches, e.g. "Figure 3".')
    p.add_argument("--out", default="./pdf_figures", help="Output directory (default: ./pdf_figures).")
    p.add_argument("--dpi", type=int, default=200, help="Render DPI for --page (default: 200).")
    p.add_argument("--crop", default=None,
                   help='Isolate a sub-panel: fractional bbox "x0,y0,x1,y1" in [0,1] of the page '
                        '(requires --page).')
    p.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    return p


def _parse_crop(spec: str) -> tuple[float, float, float, float]:
    """Parse a "x0,y0,x1,y1" fractional crop; raise ValueError on bad input."""
    parts = [float(x) for x in spec.split(",")]
    if len(parts) != 4:
        raise ValueError("--crop needs 4 comma-separated numbers: x0,y0,x1,y1")
    if any(v < 0.0 or v > 1.0 for v in parts):
        raise ValueError("--crop fractions must be in [0,1]")
    x0, y0, x1, y1 = parts
    if x1 <= x0 or y1 <= y0:
        raise ValueError("--crop requires x0<x1 and y0<y1")
    return (x0, y0, x1, y1)


def _emit(payload: dict, as_json: bool) -> None:
    """Print results either as JSON or human-readable text."""
    if as_json:
        print(json.dumps(payload, indent=2))
        return
    if "index" in payload:
        print(f"Caption index for {payload['pdf']} ({payload['page_count']} pages):")
        if not payload["index"]:
            print("  (no figure captions detected)")
        for entry in payload["index"]:
            print(f"  p{entry['page']:>3}: {entry['caption']}")
        if payload.get("matched_page"):
            print(f"\nMatched --fig on page {payload['matched_page']}. Re-run with --page to render it.")
        return
    # Single-page result
    print(f"Page {payload['page']} of {payload['pdf']}")
    print("Saved images:")
    for path in payload["saved_images"]:
        print(f"  {path}")
    if not payload["saved_images"]:
        print("  (none)")
    print("Captions found:")
    if payload["captions"]:
        for cap in payload["captions"]:
            print(f"  - {cap}")
    else:
        print("  (none on this page)")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    pdf_path = Path(args.pdf_path).expanduser()
    if not pdf_path.is_file():
        print(f"error: PDF not found or not a file: {pdf_path}", file=sys.stderr)
        return 2

    crop = None
    if args.crop:
        try:
            crop = _parse_crop(args.crop)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

    fitz = _try_import_fitz()

    # --- Text-only fallback when PyMuPDF is unavailable --------------------- #
    if fitz is None:
        results = _fallback_captions(pdf_path, args.page)
        if results is None:
            print("error: no usable PDF engine installed; cannot proceed.", file=sys.stderr)
            return 1  # nothing could be done at all
        if args.page is not None:
            payload = {"pdf": str(pdf_path), **(results[0] if results else
                       {"page": args.page, "saved_images": [], "captions": []})}
            _emit(payload, args.json)
        else:
            index = [{"page": r["page"], "caption": (r["captions"][0] if r["captions"] else "")}
                     for r in results if r["captions"]]
            _emit({"pdf": str(pdf_path), "page_count": len(results),
                   "index": index, "matched_page": None}, args.json)
        _warn("text-only mode (PyMuPDF missing): no page/figure images were rendered.")
        return 0

    # --- Full PyMuPDF path -------------------------------------------------- #
    try:
        doc = fitz.open(str(pdf_path))
    except Exception as exc:
        print(f"error: cannot open PDF ({exc})", file=sys.stderr)
        return 2

    try:
        # Resolve target page: explicit --page wins, else --fig lookup, else index scan.
        page_num = args.page
        if page_num is None and args.fig:
            _, matched = _scan_index(fitz, doc, args.fig)
            if matched is None:
                _warn(f'no caption matched --fig "{args.fig}"; showing full index instead.')
            page_num = matched

        if page_num is not None:
            result = _process_page(fitz, doc, page_num, Path(args.out).expanduser(), args.dpi, crop)
            _emit({"pdf": str(pdf_path), **result}, args.json)
        else:
            index, matched = _scan_index(fitz, doc, args.fig)
            _emit({"pdf": str(pdf_path), "page_count": doc.page_count,
                   "index": index, "matched_page": matched}, args.json)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    finally:
        doc.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
