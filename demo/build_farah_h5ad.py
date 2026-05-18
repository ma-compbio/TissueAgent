"""Assemble the Farah developing-human-heart MERFISH dataset into an AnnData.

Pulls together the 6 raw files downloaded from UCSC Cell Browser
(`hoc/all-merfish/`), strips columns that would leak the recovery target, and
writes the final `.h5ad` plus a transparent record of what was scrubbed.

Scrubbing rules (recovery-benchmark hygiene):
  - DROP `Communities`: literally names the structures the agent must recover
    (e.g., "AVN/AV Ring", "VCS", "Outer-LV").
  - DROP `Zone_Cluster`: integer alias of Communities (1:1 mapping).
  - KEEP `Populations`: cell-type labels (some are suggestive — e.g.
    `ncCM-AVC-like` — but they are the published cell-type vocabulary and
    leaving them gives the agent the canonical celltype space to reason over.
    The benchmark scores whether the agent discovers the *spatial-community*
    finding, not the celltype vocabulary itself.
  - KEEP `Sample_ID`, `Batch`, `UMICount`, `Complexity`, `Purity`, `leiden`.

Usage:
    conda activate tissueagent
    python demo/build_farah_h5ad.py
"""

from __future__ import annotations

import gzip
import io
from pathlib import Path

import anndata as ad
import numpy as np
import pandas as pd
from scipy import io as scipy_io
from scipy import sparse

_RAW = Path(__file__).resolve().parent / "data" / "farah_raw"
_OUT = Path(__file__).resolve().parent / "data" / "dataset_farah_heart_merfish.h5ad"
_SCRUB_LOG = Path(__file__).resolve().parent / "data" / "farah_scrub_log.md"

_LEAK_COLS = ["Communities", "Zone_Cluster"]


def _read_mtx_gz(path: Path) -> sparse.csr_matrix:
    """Read a gzipped MatrixMarket file; UCSC writes features × cells, so
    we transpose to cells × features.
    """
    with gzip.open(path, "rb") as f:
        raw = f.read()
    mtx = scipy_io.mmread(io.BytesIO(raw))
    if not sparse.issparse(mtx):
        mtx = sparse.csr_matrix(mtx)
    # UCSC convention: rows = genes, cols = cells. Transpose to .X-friendly.
    return mtx.T.tocsr()


def main() -> None:
    if not _RAW.is_dir():
        raise SystemExit(f"Raw download dir missing: {_RAW}")
    for fname in [
        "matrix.mtx.gz",
        "barcodes.tsv.gz",
        "features.tsv.gz",
        "meta.tsv",
        "Spatial.coords.tsv.gz",
        "UMAP.coords.tsv.gz",
    ]:
        path = _RAW / fname
        if not path.is_file() or path.stat().st_size == 0:
            raise SystemExit(f"Missing or empty: {path}")

    print(f"Reading {_RAW / 'matrix.mtx.gz'} (sparse) …")
    X = _read_mtx_gz(_RAW / "matrix.mtx.gz")
    print(f"  matrix shape: {X.shape}  (cells × genes)")

    barcodes = pd.read_csv(
        _RAW / "barcodes.tsv.gz", sep="\t", header=None, compression="gzip"
    )[0].astype(str).tolist()
    features = pd.read_csv(
        _RAW / "features.tsv.gz", sep="\t", header=None, compression="gzip"
    )[0].astype(str).tolist()
    print(f"  barcodes: {len(barcodes)}   features: {len(features)}")

    assert X.shape == (len(barcodes), len(features)), (
        f"Matrix shape {X.shape} disagrees with barcodes ({len(barcodes)}) / "
        f"features ({len(features)})"
    )

    print(f"Reading {_RAW / 'meta.tsv'} …")
    meta = pd.read_csv(_RAW / "meta.tsv", sep="\t")
    print(f"  meta columns: {list(meta.columns)}")
    print(f"  meta rows: {len(meta)}")

    meta_id_col = "Cell_ID"
    assert meta_id_col in meta.columns, f"{meta_id_col} not in meta.tsv"

    meta = meta.set_index(meta_id_col).reindex(barcodes)
    if meta.isna().any().any():
        n_missing = meta.index[meta.isna().any(axis=1)].size
        print(f"  WARNING: {n_missing} barcodes had no meta row; left as NaN")

    # UCSC coords files have NO header; columns are [cell_id, x, y].
    print(f"Reading spatial coords (headerless TSV) …")
    spatial = pd.read_csv(
        _RAW / "Spatial.coords.tsv.gz",
        sep="\t",
        compression="gzip",
        header=None,
        names=["cell_id", "x", "y"],
    ).set_index("cell_id").reindex(barcodes)
    print(f"  spatial range  x:[{spatial['x'].min():.1f}, {spatial['x'].max():.1f}]"
          f"  y:[{spatial['y'].min():.1f}, {spatial['y'].max():.1f}]")

    umap = pd.read_csv(
        _RAW / "UMAP.coords.tsv.gz",
        sep="\t",
        compression="gzip",
        header=None,
        names=["cell_id", "umap1", "umap2"],
    ).set_index("cell_id").reindex(barcodes)

    # Scrub leaky columns BEFORE building the AnnData.
    scrubbed = {}
    for col in _LEAK_COLS:
        if col in meta.columns:
            counts = meta[col].value_counts(dropna=False).to_dict()
            scrubbed[col] = counts
            meta = meta.drop(columns=[col])

    obs = meta.copy()
    obs.index = pd.Index(barcodes, name="cell_id")
    var = pd.DataFrame(index=pd.Index(features, name="gene_symbol"))

    adata = ad.AnnData(X=X, obs=obs, var=var)
    adata.obsm["spatial"] = spatial[["x", "y"]].to_numpy(dtype=np.float32)
    adata.obsm["X_umap"] = umap[["umap1", "umap2"]].to_numpy(dtype=np.float32)

    adata.uns["dataset_provenance"] = {
        "source": "UCSC Cell Browser (cells.ucsc.edu/hoc/all-merfish/)",
        "study": "Farah et al. 2024, developing human heart MERFISH",
        "scrubbed_for_recovery_benchmark": list(scrubbed.keys()),
    }

    print(f"\nFinal AnnData: {adata.shape}  obs cols: {list(adata.obs.columns)}")
    print(f"Writing {_OUT} …")
    adata.write_h5ad(_OUT, compression="gzip")
    print(f"  size: {_OUT.stat().st_size / 1e6:.1f} MB")

    scrub_lines = ["# Farah MERFISH scrub log\n"]
    scrub_lines.append(
        f"From the raw UCSC `hoc/all-merfish/` dataset ({adata.n_obs} cells × "
        f"{adata.n_vars} genes), the following columns were removed from "
        "`adata.obs` to prevent the recovery benchmark from being trivially "
        "solved by reading the published label.\n"
    )
    for col, counts in scrubbed.items():
        scrub_lines.append(f"\n## Dropped: `{col}`\n")
        scrub_lines.append("Original value counts:\n\n")
        for value, count in sorted(counts.items(), key=lambda kv: -kv[1]):
            scrub_lines.append(f"- `{value}`: {count}\n")
    _SCRUB_LOG.write_text("".join(scrub_lines), encoding="utf-8")
    print(f"Wrote scrub log: {_SCRUB_LOG}")


if __name__ == "__main__":
    main()
