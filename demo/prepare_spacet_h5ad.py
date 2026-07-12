#!/usr/bin/env python3
"""Prepare SpaCET fixture h5ad from public 10x Visium breast cancer data.

Falls back to a compact synthetic-labeled Visium-like object only if download fails;
prefer the real 10x dataset for recovery runs.
"""

from __future__ import annotations

import argparse
import json
import tarfile
import tempfile
import urllib.request
from pathlib import Path

# 10x Genomics: Human Breast Cancer (Block A Section 1) — filtered feature matrix + spatial
# Using the feature-barcode matrix tarball commonly mirrored for Visium demos.
TENX_FILTERED = (
    "https://cf.10xgenomics.com/samples/spatial-exp/1.1.0/"
    "V1_Breast_Cancer_Block_A_Section_1/"
    "V1_Breast_Cancer_Block_A_Section_1_filtered_feature_bc_matrix.tar.gz"
)
TENX_SPATIAL = (
    "https://cf.10xgenomics.com/samples/spatial-exp/1.1.0/"
    "V1_Breast_Cancer_Block_A_Section_1/"
    "V1_Breast_Cancer_Block_A_Section_1_spatial.tar.gz"
)


def _download(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file() and dest.stat().st_size > 1000:
        return dest
    print(f"Downloading {url} -> {dest}")
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; TissueAgent/1.0)"},
    )
    with urllib.request.urlopen(req, timeout=600) as resp, dest.open("wb") as out:
        while True:
            chunk = resp.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)
    return dest


def build(download_dir: Path, out_h5ad: Path) -> Path:
    import anndata as ad
    import numpy as np
    import pandas as pd
    import scanpy as sc

    mtx_tar = _download(TENX_FILTERED, download_dir / "filtered_feature_bc_matrix.tar.gz")
    spat_tar = _download(TENX_SPATIAL, download_dir / "spatial.tar.gz")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_p = Path(tmp)
        with tarfile.open(mtx_tar, "r:gz") as tf:
            tf.extractall(tmp_p)
        with tarfile.open(spat_tar, "r:gz") as tf:
            tf.extractall(tmp_p)

        mtx_dirs = list(tmp_p.rglob("matrix.mtx*"))
        if not mtx_dirs:
            raise FileNotFoundError("No matrix.mtx in 10x tarball")
        adata = sc.read_10x_mtx(mtx_dirs[0].parent, var_names="gene_symbols", cache=False)
        adata.var_names_make_unique()

        pos = list(tmp_p.rglob("tissue_positions*.csv")) + list(
            tmp_p.rglob("tissue_positions_list.csv")
        )
        if pos:
            sp = pd.read_csv(pos[0], header=None)
            # Newer files may include a header row
            if str(sp.iloc[0, 0]).lower().startswith("barcode"):
                sp = pd.read_csv(pos[0])
                rename = {}
                for c in sp.columns:
                    cl = str(c).lower()
                    if "barcode" in cl:
                        rename[c] = "barcode"
                    elif "row_in_fullres" in cl or cl == "pxl_row_in_fullres":
                        rename[c] = "pxl_row"
                    elif "col_in_fullres" in cl or cl == "pxl_col_in_fullres":
                        rename[c] = "pxl_col"
                    elif cl == "in_tissue":
                        rename[c] = "in_tissue"
                sp = sp.rename(columns=rename)
            else:
                sp.columns = [
                    "barcode",
                    "in_tissue",
                    "array_row",
                    "array_col",
                    "pxl_row",
                    "pxl_col",
                ][: sp.shape[1]]
            sp["bc_short"] = sp["barcode"].astype(str).str.split("-").str[0]
            sp = sp.drop_duplicates("bc_short").set_index("bc_short")
            adata.obs["bc_short"] = adata.obs_names.astype(str).str.split("-").str[0]
            merged = adata.obs.join(sp, on="bc_short", how="left")
            if {"pxl_col", "pxl_row"} <= set(merged.columns):
                adata.obsm["spatial"] = merged[["pxl_col", "pxl_row"]].to_numpy(
                    dtype=float
                )
            for c in ("in_tissue", "array_row", "array_col"):
                if c in merged.columns:
                    adata.obs[c] = merged[c].values

    # Lightweight proxy lineage scores for SpaCET-style exploration (not gold labels).
    # Agents may invent analyses from expression; these columns are optional hints only
    # if present as continuous scores — we store gene-module proxies under .obs.
    gene_sets = {
        "score_CAF": ["COL1A1", "COL3A1", "DCN", "LUM", "FAP"],
        "score_M2": ["CD163", "MRC1", "MSR1", "MS4A4A"],
        "score_malignant": ["EPCAM", "KRT8", "KRT18", "MKI67"],
        "score_Tcell": ["CD3D", "CD3E", "CD8A", "IL7R"],
    }
    X = adata.X
    if hasattr(X, "toarray"):
        # keep sparse; use scanpy score_genes if available
        try:
            for name, genes in gene_sets.items():
                present = [g for g in genes if g in adata.var_names]
                if len(present) >= 2:
                    sc.tl.score_genes(adata, present, score_name=name, use_raw=False)
        except Exception:
            pass

    adata.uns["paper_id"] = "2023_NC_SpaCET"
    adata.uns["sample_id"] = "V1_Breast_Cancer_Block_A_Section_1"
    adata.uns["source"] = "10x Genomics Visium breast cancer demo"
    out_h5ad.parent.mkdir(parents=True, exist_ok=True)
    adata.write_h5ad(out_h5ad, compression="gzip")
    return out_h5ad


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--download-dir",
        type=Path,
        default=Path("benchmark/hypothesis_recovery/2023_NC_SpaCET/_download"),
    )
    p.add_argument(
        "--out",
        type=Path,
        default=Path("benchmark/hypothesis_recovery/2023_NC_SpaCET/dataset.h5ad"),
    )
    args = p.parse_args()
    path = build(args.download_dir, args.out)
    print(f"Wrote {path}")

    import anndata as ad

    a = ad.read_h5ad(path, backed="r")
    manifest_path = path.parent / "dataset_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    try:
        rel = str(path.resolve().relative_to(Path.cwd().resolve()))
    except ValueError:
        rel = str(path)
    manifest.update(
        {
            "status": "ready",
            "h5ad_path": rel,
            "n_obs": int(a.n_obs),
            "n_vars": int(a.n_vars),
            "sample_id": "V1_Breast_Cancer_Block_A_Section_1",
            "note": "Public 10x Visium breast cancer section for SpaCET-style recovery.",
        }
    )
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
