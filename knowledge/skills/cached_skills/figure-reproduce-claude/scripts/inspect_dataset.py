#!/usr/bin/env python3
"""Inspect a dataset before reproducing a figure from it.

Part of the 'figure-reproduce' skill. This script is portable and self-contained:
it imports NO project package and has no hard dependency on any third-party library.
Optional readers (pandas, anndata, pyarrow, openpyxl) are imported lazily and, when
missing, the script prints a one-line install hint and degrades gracefully instead
of crashing.

WHAT IT DOES
    The "inspect the dataset" step of figure reproduction: before you plot, confirm
    that the fields the target figure needs actually exist. Given a dataset path, it
    prints the structure so you know what you can color / plot by, and explicitly
    flags CANDIDATE COLOR / CATEGORY / COORDINATE / EMBEDDING fields.

SUPPORTED FORMATS (detected by extension)
    .h5ad            AnnData  (needs `anndata`)
    .csv/.tsv/.txt   table    (pandas if present, else stdlib csv)
    .parquet         table    (needs pandas + pyarrow)
    .xlsx            workbook (needs pandas + openpyxl)

USAGE
    python inspect_dataset.py DATA_PATH [--max-rows N] [--json]

    python inspect_dataset.py data/umap.csv
    python inspect_dataset.py source_data.xlsx --max-rows 3
    python inspect_dataset.py adata.h5ad --json
"""

from __future__ import annotations

import argparse
import json
import os
import sys

# A column whose name matches one of these is a likely plot coordinate.
COORD_HINTS = ("x", "y", "umap", "tsne", "t-sne", "pca", "spatial", "coord", "dim")
# .obsm keys matching these are likely 2D embeddings you can scatter-plot.
EMBED_HINTS = ("umap", "tsne", "pca", "spatial", "diffmap", "phate")
# Categorical columns with at most this many distinct values are good color fields.
LOW_CARD_MAX = 50


def hint(pkg: str) -> str:
    """One-line install hint for a missing optional dependency."""
    return f"[degraded] optional dependency '{pkg}' not installed - try: pip install {pkg}"


def name_matches(name: str, hints: tuple[str, ...]) -> bool:
    low = str(name).lower()
    return any(h in low for h in hints)


# --------------------------------------------------------------------------- #
# AnnData (.h5ad)
# --------------------------------------------------------------------------- #
def inspect_h5ad(path: str, max_rows: int) -> dict:
    try:
        import anndata  # noqa: F401
    except ImportError:
        return {"format": "h5ad", "warning": hint("anndata")}

    import anndata as ad

    adata = ad.read_h5ad(path, backed="r")
    obs = adata.obs

    obs_cols = []
    color_fields = []
    for col in obs.columns:
        series = obs[col]
        dtype = str(series.dtype)
        info = {"name": col, "dtype": dtype}
        is_cat = dtype == "category" or series.dtype == object
        # Only compute cardinality for categorical / low-signal columns.
        if is_cat or series.nunique(dropna=True) <= LOW_CARD_MAX:
            uniques = series.dropna().unique()
            info["n_unique"] = int(len(uniques))
            info["examples"] = [str(u) for u in list(uniques)[:6]]
            if info["n_unique"] <= LOW_CARD_MAX:
                color_fields.append(col)
        obs_cols.append(info)

    obsm_keys = list(adata.obsm.keys())
    embeddings = [k for k in obsm_keys if name_matches(k, EMBED_HINTS)]

    return {
        "format": "h5ad",
        "shape": {"n_obs": int(adata.n_obs), "n_vars": int(adata.n_vars)},
        "obs_columns": obs_cols,
        "var_names_sample": [str(v) for v in list(adata.var_names[:10])],
        "obsm_keys": obsm_keys,
        "layers": list(adata.layers.keys()),
        "uns_keys": list(adata.uns.keys()),
        "candidate_color_fields": color_fields,
        "candidate_embeddings": embeddings,
    }


# --------------------------------------------------------------------------- #
# Tables (.csv / .tsv / .txt / .parquet / .xlsx)
# --------------------------------------------------------------------------- #
def _dataframe_summary(df, max_rows: int) -> dict:
    """Summarise a single pandas DataFrame (shape, columns, head, candidates)."""
    coord_cols = [c for c in df.columns if name_matches(c, COORD_HINTS)]
    category_cols = []
    columns = []
    for col in df.columns:
        dtype = str(df[col].dtype)
        columns.append({"name": str(col), "dtype": dtype})
        is_stringy = dtype == "object" or dtype.startswith("category")
        if is_stringy or df[col].nunique(dropna=True) <= LOW_CARD_MAX:
            if df[col].nunique(dropna=True) <= LOW_CARD_MAX:
                category_cols.append(str(col))
    head = df.head(max_rows).astype(str).values.tolist()
    return {
        "shape": {"rows": int(df.shape[0]), "cols": int(df.shape[1])},
        "columns": columns,
        "head": {"header": [str(c) for c in df.columns], "rows": head},
        "candidate_coordinate_columns": coord_cols,
        "candidate_category_columns": category_cols,
    }


def inspect_table_pandas(path: str, ext: str, max_rows: int) -> dict:
    import pandas as pd

    if ext == ".parquet":
        try:
            df = pd.read_parquet(path)
        except ImportError:
            return {"format": "parquet", "warning": hint("pyarrow")}
        out = _dataframe_summary(df, max_rows)
        out["format"] = "parquet"
        return out

    if ext == ".xlsx":
        try:
            book = pd.read_excel(path, sheet_name=None)  # dict of {sheet: df}
        except ImportError:
            return {"format": "xlsx", "warning": hint("openpyxl")}
        sheets = {name: _dataframe_summary(df, max_rows) for name, df in book.items()}
        return {"format": "xlsx", "sheet_names": list(book.keys()), "sheets": sheets}

    sep = "\t" if ext in (".tsv", ".txt") else ","
    df = pd.read_csv(path, sep=sep)
    out = _dataframe_summary(df, max_rows)
    out["format"] = "delimited"
    return out


def inspect_table_stdlib(path: str, ext: str, max_rows: int) -> dict:
    """Fallback CSV/TSV reader using only the standard library (no pandas)."""
    import csv

    delim = "\t" if ext in (".tsv", ".txt") else ","
    with open(path, newline="", encoding="utf-8", errors="replace") as fh:
        reader = csv.reader(fh, delimiter=delim)
        rows = list(reader)
    if not rows:
        return {"format": "delimited", "warning": "file is empty"}

    header, data = rows[0], rows[1:]
    # Infer a coarse dtype per column: int / float / str.
    dtypes, uniques = [], []
    for idx in range(len(header)):
        col = [r[idx] for r in data if idx < len(r)]
        dtypes.append(_infer_dtype(col))
        uniques.append(len({v for v in col}))

    columns = [{"name": h, "dtype": d} for h, d in zip(header, dtypes)]
    category_cols = [h for h, u in zip(header, uniques) if u <= LOW_CARD_MAX]
    coord_cols = [h for h in header if name_matches(h, COORD_HINTS)]
    return {
        "format": "delimited",
        "note": hint("pandas") + " (using stdlib csv fallback)",
        "shape": {"rows": len(data), "cols": len(header)},
        "columns": columns,
        "head": {"header": header, "rows": data[:max_rows]},
        "candidate_coordinate_columns": coord_cols,
        "candidate_category_columns": category_cols,
    }


def _infer_dtype(values: list[str]) -> str:
    seen_float = False
    for v in values:
        if v == "":
            continue
        try:
            int(v)
        except ValueError:
            try:
                float(v)
                seen_float = True
            except ValueError:
                return "str"
    return "float" if seen_float else "int"


def inspect_table(path: str, ext: str, max_rows: int) -> dict:
    try:
        import pandas  # noqa: F401
    except ImportError:
        if ext in (".csv", ".tsv", ".txt"):
            return inspect_table_stdlib(path, ext, max_rows)
        return {"format": ext.lstrip("."), "warning": hint("pandas")}
    return inspect_table_pandas(path, ext, max_rows)


# --------------------------------------------------------------------------- #
# Dispatch + rendering
# --------------------------------------------------------------------------- #
def inspect(path: str, max_rows: int) -> dict:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".h5ad":
        return inspect_h5ad(path, max_rows)
    if ext in (".csv", ".tsv", ".txt", ".parquet", ".xlsx"):
        return inspect_table(path, ext, max_rows)
    return {"format": ext or "unknown", "warning": f"unsupported extension '{ext}'"}


def render_text(path: str, report: dict) -> None:
    """Human-readable rendering of the inspection report."""
    print(f"=== dataset: {path} ===")
    print(f"format: {report.get('format', '?')}")
    if "warning" in report:
        print(f"WARNING: {report['warning']}")
        return
    if "note" in report:
        print(f"note: {report['note']}")

    if report["format"] == "xlsx":
        print(f"sheets: {report['sheet_names']}")
        for name, sheet in report["sheets"].items():
            print(f"\n-- sheet '{name}' --")
            _render_table(sheet)
        return
    if report["format"] == "h5ad":
        _render_h5ad(report)
        return
    _render_table(report)


def _render_table(rep: dict) -> None:
    shape = rep["shape"]
    print(f"shape: {shape['rows']} rows x {shape['cols']} cols")
    print("columns:")
    for c in rep["columns"]:
        print(f"  - {c['name']}: {c['dtype']}")
    head = rep["head"]
    print(f"head ({len(head['rows'])} rows):")
    print("  " + " | ".join(head["header"]))
    for row in head["rows"]:
        print("  " + " | ".join(str(v) for v in row))
    print(f"CANDIDATE COORDINATE columns: {rep['candidate_coordinate_columns'] or '(none)'}")
    print(f"CANDIDATE CATEGORY/COLOR columns: {rep['candidate_category_columns'] or '(none)'}")


def _render_h5ad(rep: dict) -> None:
    s = rep["shape"]
    print(f"shape: {s['n_obs']} obs x {s['n_vars']} vars")
    print("obs columns:")
    for c in rep["obs_columns"]:
        extra = ""
        if "n_unique" in c:
            extra = f"  n_unique={c['n_unique']} e.g. {c['examples']}"
        print(f"  - {c['name']}: {c['dtype']}{extra}")
    print(f"var_names sample: {rep['var_names_sample']}")
    print(f"obsm keys: {rep['obsm_keys']}")
    print(f"layers: {rep['layers']}")
    print(f"uns keys: {rep['uns_keys']}")
    print(f"CANDIDATE COLOR FIELDS: {rep['candidate_color_fields'] or '(none)'}")
    print(f"CANDIDATE EMBEDDINGS: {rep['candidate_embeddings'] or '(none)'}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Inspect a dataset's structure before reproducing a figure from it.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("path", help="path to the dataset (.h5ad/.csv/.tsv/.txt/.parquet/.xlsx)")
    parser.add_argument("--max-rows", type=int, default=5, help="rows of preview to show (default 5)")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args(argv)

    # Real usage errors -> non-zero exit.
    if not os.path.exists(args.path):
        print(f"error: path not found: {args.path}", file=sys.stderr)
        return 2
    if not os.path.isfile(args.path):
        print(f"error: not a file: {args.path}", file=sys.stderr)
        return 2

    try:
        report = inspect(args.path, args.max_rows)
    except Exception as exc:  # unreadable / corrupt file is a real failure
        print(f"error: failed to read {args.path}: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        render_text(args.path, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
