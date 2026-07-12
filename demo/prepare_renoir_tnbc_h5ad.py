#!/usr/bin/env python3
"""Build Renoir TNBC Visium AnnData from Zenodo 4739739 downloads.

The Zenodo archive ships 10x-like files with a ``.gz`` suffix that are often
*not* gzip-compressed. This script handles both cases.
"""

from __future__ import annotations

import argparse
import gzip
import json
import shutil
import tempfile
from pathlib import Path

import anndata as ad
import pandas as pd
from scipy.io import mmread


def _open_text(path: Path):
    raw = path.read_bytes()[:2]
    if raw == b"\x1f\x8b":
        return gzip.open(path, "rt")
    return path.open("rt")


def _ensure_real_gzip(src: Path, dest: Path) -> None:
    raw = src.read_bytes()[:2]
    if raw == b"\x1f\x8b":
        shutil.copy2(src, dest)
        return
    # Plain text mislabeled as .gz — compress into dest
    with src.open("rb") as fin, gzip.open(dest, "wb") as fout:
        shutil.copyfileobj(fin, fout)


def build(download_dir: Path, sample: str, out_h5ad: Path) -> Path:
    mtx_dir = download_dir / "filtered_count_matrices" / f"{sample}_filtered_count_matrix"
    if not mtx_dir.is_dir():
        raise FileNotFoundError(mtx_dir)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_p = Path(tmp)
        for name in ("matrix.mtx.gz", "features.tsv.gz", "barcodes.tsv.gz"):
            _ensure_real_gzip(mtx_dir / name, tmp_p / name)

        # features may be single-column gene symbols
        genes = pd.read_csv(tmp_p / "features.tsv.gz", header=None, sep="\t")
        barcodes = pd.read_csv(tmp_p / "barcodes.tsv.gz", header=None, sep="\t")[0].astype(str)
        gene_names = genes[1].astype(str).values if genes.shape[1] > 1 else genes[0].astype(str).values
        X = mmread(tmp_p / "matrix.mtx.gz").T.tocsr()
        adata = ad.AnnData(X)
        adata.obs_names = barcodes.values
        adata.var_names = gene_names
        adata.var_names_make_unique()

    sp_dir = download_dir / "spatial" / f"{sample}_spatial"
    pos_files = list(sp_dir.glob("tissue_positions*"))
    if pos_files:
        sp = pd.read_csv(pos_files[0], header=None)
        sp.columns = ["barcode", "in_tissue", "array_row", "array_col", "pxl_row", "pxl_col"][
            : sp.shape[1]
        ]
        sp["bc_short"] = sp["barcode"].astype(str).str.split("-").str[0]
        sp = sp.drop_duplicates("bc_short").set_index("bc_short")
        adata.obs["bc_short"] = adata.obs_names.astype(str).str.split("-").str[0]
        merged = adata.obs.join(sp, on="bc_short", how="left")
        if {"pxl_col", "pxl_row"} <= set(merged.columns):
            adata.obsm["spatial"] = merged[["pxl_col", "pxl_row"]].to_numpy(dtype=float)
        for c in ("in_tissue", "array_row", "array_col"):
            if c in merged.columns:
                adata.obs[c] = merged[c].values

    meta_path = download_dir / "metadata" / f"{sample}_metadata.csv"
    if meta_path.is_file():
        meta = pd.read_csv(meta_path, index_col=0)
        meta.index = meta.index.astype(str).str.split("-").str[0]
        if "bc_short" not in adata.obs:
            adata.obs["bc_short"] = adata.obs_names.astype(str).str.split("-").str[0]
        for col in meta.columns:
            adata.obs[str(col)] = meta.reindex(adata.obs["bc_short"])[col].values

    adata.uns["paper_id"] = "2026_NC_Renoir"
    adata.uns["sample_id"] = sample
    adata.uns["source"] = "zenodo:10.5281/zenodo.4739739"
    out_h5ad.parent.mkdir(parents=True, exist_ok=True)
    adata.write_h5ad(out_h5ad, compression="gzip")
    return out_h5ad


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--download-dir",
        type=Path,
        default=Path("benchmark/hypothesis_recovery/2026_NC_Renoir/_download"),
    )
    p.add_argument("--sample", default="CID44971")
    p.add_argument(
        "--out",
        type=Path,
        default=Path("benchmark/hypothesis_recovery/2026_NC_Renoir/dataset.h5ad"),
    )
    args = p.parse_args()
    path = build(args.download_dir, args.sample, args.out)
    print(f"Wrote {path}")
    manifest_path = path.parent / "dataset_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "status": "ready",
            "h5ad_path": str(path),
            "sample_id": args.sample,
        }
    )
    try:
        manifest["h5ad_path"] = str(path.resolve().relative_to(Path.cwd().resolve()))
    except ValueError:
        pass
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
