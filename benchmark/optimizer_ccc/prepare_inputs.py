"""Build the pinned benchmark inputs (run once, deterministic).

Stages one labeled, single-section h5ad per dataset into
``workspace/library/datasets/`` so agent runs and the expert reference consume
byte-identical inputs. Records shapes + label distributions in
``benchmark/optimizer_ccc/inputs_manifest.json``.

Usage::

    python benchmark/optimizer_ccc/prepare_inputs.py [--datasets lymph_node dlpfc merfish] [--force]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from datasets import BENCH_DIR, DATASETS, RAW_DATASETS_DIR, SEED, staged_path  # noqa: E402

MANIFEST = BENCH_DIR / "inputs_manifest.json"


def _load_raw(name: str):
    import anndata as ad

    return ad.read_h5ad(RAW_DATASETS_DIR / DATASETS[name]["raw"])


def prepare_lymph_node():
    """No labels ship with this file: derive spatial domains deterministically.

    KMeans (not leiden) because it is bit-stable across BLAS/thread configs
    with a fixed seed — the labels must be identical every time this runs.
    """
    import numpy as np
    import scanpy as sc
    from sklearn.cluster import KMeans

    a = _load_raw("lymph_node")
    a.var_names_make_unique()
    a.obs_names_make_unique()
    a = a[a.obs["in_tissue"] == 1].copy()

    work = a.copy()
    sc.pp.normalize_total(work, target_sum=1e4)
    sc.pp.log1p(work)
    sc.pp.highly_variable_genes(work, n_top_genes=2000)
    work = work[:, work.var["highly_variable"]].copy()
    sc.pp.scale(work, max_value=10)
    sc.tl.pca(work, n_comps=30, svd_solver="arpack", random_state=SEED)
    km = KMeans(n_clusters=8, n_init=10, random_state=SEED)
    labels = km.fit_predict(np.asarray(work.obsm["X_pca"]))

    a.obs["domain"] = [f"domain_{i}" for i in labels]
    a.obs["domain"] = a.obs["domain"].astype("category")
    return a


def prepare_dlpfc():
    a = _load_raw("dlpfc")
    section = DATASETS["dlpfc"]["section"]["sample_name"]
    a = a[a.obs["sample_name"].astype(str) == section].copy()
    # var_names are Ensembl IDs; the CCC pipeline needs gene symbols.
    sym = a.var["gene_symbol"].astype(str)
    a = a[:, (sym.notna() & ~sym.isin(["", "nan", "None"])).values].copy()
    a.var_names = a.var["gene_symbol"].astype(str).values
    # Drop the source column: after make_unique the index diverges from it,
    # and anndata refuses to write an index named like a differing column.
    a.var = a.var.drop(columns=["gene_symbol"])
    a.var.index.name = None
    a.var_names_make_unique()
    labels = a.obs["layer_guess_reordered"].astype(str)
    keep = ~labels.isin(["NA", "nan", "None"])
    a = a[keep].copy()
    a.obs["layer"] = a.obs["layer_guess_reordered"].astype(str).astype("category")
    return a


def prepare_merfish():
    a = _load_raw("merfish")
    sec = DATASETS["merfish"]["section"]
    mask = (a.obs["Animal_ID"] == sec["Animal_ID"]) & (a.obs["Bregma"] == sec["Bregma"])
    a = a[mask].copy()
    labels = a.obs["Cell_class"].astype(str)
    a = a[~labels.isin(["nan", "None", "Ambiguous"])].copy()
    # The ensemble's input contract needs >=10 cells per category; drop the
    # rare tail classes rather than let every run trip on them.
    counts = a.obs["Cell_class"].astype(str).value_counts()
    keep = counts[counts >= 10].index
    a = a[a.obs["Cell_class"].astype(str).isin(keep)].copy()
    a.obs["Cell_class"] = a.obs["Cell_class"].astype(str).astype("category")
    return a


PREPARERS = {"lymph_node": prepare_lymph_node, "dlpfc": prepare_dlpfc, "merfish": prepare_merfish}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--datasets", nargs="+", default=list(DATASETS), choices=list(DATASETS))
    ap.add_argument("--force", action="store_true", help="Rebuild even if the staged file exists.")
    args = ap.parse_args(argv)

    manifest = json.loads(MANIFEST.read_text()) if MANIFEST.is_file() else {}
    for name in args.datasets:
        out = staged_path(name)
        if out.exists() and not args.force:
            print(f"[skip] {name}: {out.name} already staged (use --force to rebuild)")
            continue
        print(f"[prep] {name} …")
        a = PREPARERS[name]()
        col = DATASETS[name]["cell_type"]
        counts = a.obs[col].value_counts()
        assert "spatial" in a.obsm, f"{name}: obsm['spatial'] missing"
        assert counts.size >= 2 and counts.min() >= 10, (
            f"{name}: label column '{col}' needs >=2 categories with >=10 cells each, "
            f"got {counts.to_dict()}"
        )
        a.write_h5ad(out)
        manifest[name] = {
            "staged": out.name,
            "n_obs": int(a.n_obs),
            "n_vars": int(a.n_vars),
            "cell_type": col,
            "label_counts": {str(k): int(v) for k, v in counts.items()},
            "seed": SEED,
        }
        print(f"[done] {name}: {a.shape}, {counts.size} labels -> {out}")
    MANIFEST.write_text(json.dumps(manifest, indent=2))
    print(f"manifest: {MANIFEST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
