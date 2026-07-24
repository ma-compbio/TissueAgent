#!/usr/bin/env python3
"""Isolated smoke test for the CCC **LIANA step** (knowledge/skills/ccc_liana.md).

Runs just the LIANA portion of the ccc_ensemble workflow against a real dataset,
so you can iterate on the ccc-liana skill's recipe without dispatching the whole
agent pipeline. It:

  1. builds a CORRECT ccc_base.h5ad + ccc_lr_common.csv from the raw dataset using
     the ccc-data-prep recipe (the workspace copy is the agent's broken OmniPath
     output, wrong schema — so we regenerate);
  2. runs the ccc-liana recipe VERBATIM (rank_aggregate + bivariate at two
     bandwidths) against installed LIANA;
  3. validates the standardized outputs.

This tests that the skill's CODE is correct against the installed library versions.
It does NOT test agent behaviour (whether the coding agent chooses to follow the
skill) — that needs the LLM. Use it to catch API/recipe breakage fast.

Usage:
  python scripts/test_ccc_liana_step.py \
    --dataset workspace/library/datasets/dataset_lohoff_et_al_seqfish.h5ad \
    --celltype celltype_mapped_refined --species mouse \
    --outdir /tmp/ccc_liana_test --fast
"""
from __future__ import annotations

import argparse
import json
import os
from importlib.metadata import version
from pathlib import Path

import numpy as np
import pandas as pd
import scanpy as sc
from sklearn.neighbors import NearestNeighbors


def prep_base(args) -> dict:
    """ccc-data-prep recipe (minimal): produce ccc_base.h5ad + ccc_lr_common.csv."""
    import liana as li

    adata = sc.read_h5ad(args.dataset)

    # counts (integer-like, not dtype)
    def counts_like(X):
        v = X.data if hasattr(X, "data") else np.asarray(X).ravel()
        v = v[:100000]
        return np.isfinite(v).all() and (v >= 0).all() and np.allclose(v, np.round(v))

    if "counts" not in adata.layers:
        if counts_like(adata.X):
            adata.layers["counts"] = adata.X.copy()
        else:
            raise SystemExit("No integer-like counts in .X and no layers['counts'] — "
                             "point --dataset at raw counts.")

    # spatial + native-unit median_nn
    coords = np.asarray(adata.obsm["spatial"], float)
    assert coords.shape == (adata.n_obs, 2) and np.isfinite(coords).all()
    rng = np.random.default_rng(1337)
    samp = coords[rng.choice(coords.shape[0], min(2000, coords.shape[0]), replace=False)]
    d, _ = NearestNeighbors(n_neighbors=2).fit(coords).kneighbors(samp)
    median_nn = float(np.median(d[:, 1]))

    # cell types
    lab = (adata.obs[args.celltype].astype(str).str.replace(r"[\s/|]+", "_", regex=True))
    adata.obs["_ccc_cell_type"] = lab.astype("category")
    assert adata.obs["_ccc_cell_type"].nunique() >= 2

    # QC + layers (reset .X from counts so no double-normalize)
    sc.pp.filter_genes(adata, min_cells=3)
    sc.pp.filter_cells(adata, min_genes=10)
    small_panel = adata.n_vars < 1000
    adata.X = adata.layers["counts"].copy()
    adata.layers["norm_no_log"] = sc.pp.normalize_total(adata, target_sum=1e4, inplace=False)["X"]
    sc.pp.normalize_total(adata, target_sum=1e4)
    sc.pp.log1p(adata)
    adata.obs["imagecol"] = adata.obsm["spatial"][:, 0]
    adata.obs["imagerow"] = adata.obsm["spatial"][:, 1]

    # shared monomeric LR resource
    res = li.rs.select_resource("consensus" if args.species == "human" else "mouseconsensus")
    res = res[["ligand", "receptor"]].astype(str).drop_duplicates()
    genes = set(adata.var_names.astype(str))
    mono = res[~res.ligand.str.contains("_") & ~res.receptor.str.contains("_")
               & res.ligand.isin(genes) & res.receptor.isin(genes)].reset_index(drop=True)
    if len(mono) < 5:
        raise SystemExit(f"Only {len(mono)} measurable LR pairs on this panel — "
                         "targeted panel + LIANA consensus overlap is small; "
                         "the LIANA step will still run but expect few triples.")

    out = Path(args.outdir)
    (out / "logs").mkdir(parents=True, exist_ok=True)
    adata.write(out / "ccc_base.h5ad")
    mono.to_csv(out / "ccc_lr_common.csv", index=False)
    prep = {"species": args.species, "platform": args.platform,
            "resolution_mode": args.resolution_mode, "median_nn": median_nn,
            "median_nn_um": None, "cell_type_col": "_ccc_cell_type",
            "small_panel": bool(small_panel), "sample_col": None,
            "n_lr_common": int(len(mono))}
    json.dump(prep, open(out / "logs" / "ccc_data_prep.json", "w"), indent=2)
    print(f"[prep] ccc_base {adata.shape} | median_nn={median_nn:.4g} | "
          f"LR common={len(mono)} | small_panel={small_panel}")
    return prep


def run_liana(args, prep: dict) -> None:
    """ccc-liana recipe, verbatim from knowledge/skills/ccc_liana.md."""
    import liana as li

    out = Path(args.outdir)
    adata = sc.read_h5ad(out / "ccc_base.h5ad")
    resource = pd.read_csv(out / "ccc_lr_common.csv")[["ligand", "receptor"]]
    median_nn, res_mode = prep["median_nn"], prep["resolution_mode"]
    expr_prop = 0.05 if prep.get("small_panel") else 0.10
    n_perms = 100 if args.fast else 1000

    # rank_aggregate — directed cell-type consensus (NON-spatial). use_raw=False!
    li.mt.rank_aggregate(adata, groupby="_ccc_cell_type", resource=resource,
                         use_raw=False, expr_prop=expr_prop, min_cells=10,
                         n_perms=n_perms, seed=1337, verbose=True)
    lr = adata.uns["liana_res"]
    lr.to_csv(out / "liana_res.csv", index=False)
    rows = [dict(engine="liana", mode="rank_aggregate", regime="coexpr",
                 level="celltype_pair", spatial=False,
                 ligand=r.ligand_complex, receptor=r.receptor_complex,
                 source=r.source, target=r.target,
                 score=r.specificity_rank, higher_better=False,
                 pvalue=r.specificity_rank, contrib_dist=np.nan)
            for r in lr.itertuples()]

    # bivariate — LR-level spatial hotspots at two bandwidths
    bandwidths, n_biv = {}, {}
    if res_mode in ("spot_multicell", "single_cell") and median_nn:
        K = 6 if res_mode == "spot_multicell" else 20
        bandwidths = {"contact": 1.5 * median_nn, "diffusion": 3.0 * median_nn}
        for regime, bw in bandwidths.items():
            li.ut.spatial_neighbors(adata, bandwidth=bw, cutoff=0.1,
                                    max_neighbours=K, kernel="gaussian", set_diag=False)
            biv = li.mt.bivariate(adata, resource=resource, local_name="cosine",
                                  global_name="morans", n_perms=n_perms,
                                  nz_prop=expr_prop, use_raw=False, verbose=True)
            v = biv.var.reset_index()
            n_biv[regime] = int(len(v))
            rows += [dict(engine="liana", mode="bivariate", regime=regime, level="lr",
                          spatial=True, ligand=r.ligand, receptor=r.receptor,
                          source=np.nan, target=np.nan,
                          score=r.morans, higher_better=True,
                          pvalue=r.morans_pvals, contrib_dist=np.nan)
                         for r in v.itertuples()]

    pd.DataFrame(rows).to_csv(out / "liana_ccc.csv", index=False)
    X = adata.layers["counts"]
    frac = np.asarray((X > 0).mean(axis=0)).ravel()
    expressed = set(adata.var_names[frac >= expr_prop])
    operable = resource[resource.ligand.isin(expressed) & resource.receptor.isin(expressed)]
    operable.to_csv(out / "liana_universe.csv", index=False)
    json.dump({"species": prep["species"], "expr_prop": expr_prop, "use_raw": False,
               "bandwidths": bandwidths, "n_rank": int(len(lr)), "n_biv": n_biv,
               "n_perms": n_perms}, open(out / "logs" / "ccc_liana.json", "w"), indent=2)
    print(f"[liana] rank rows={len(lr)} | bivariate={n_biv} | n_perms={n_perms}")


def validate(args) -> None:
    out = Path(args.outdir)
    ccc = pd.read_csv(out / "liana_ccc.csv")
    uni = pd.read_csv(out / "liana_universe.csv")
    need = {"engine", "mode", "regime", "level", "spatial", "ligand", "receptor",
            "source", "target", "score", "higher_better", "pvalue", "contrib_dist"}
    problems = []
    if not need.issubset(ccc.columns):
        problems.append(f"liana_ccc.csv missing cols: {need - set(ccc.columns)}")
    if (ccc["mode"] == "rank_aggregate").sum() == 0:
        problems.append("no rank_aggregate rows")
    modes = set(ccc["mode"])
    if args.resolution_mode in ("spot_multicell", "single_cell") and "bivariate" not in modes:
        problems.append("no bivariate rows on spatial input")
    if len(uni) == 0:
        problems.append("empty liana_universe.csv")
    print("\n=== validation ===")
    print("liana_ccc rows:", len(ccc), "| modes:", sorted(modes),
          "| regimes:", sorted(set(ccc["regime"])))
    print("universe pairs:", len(uni))
    if problems:
        print("FAIL:\n - " + "\n - ".join(problems)); raise SystemExit(1)
    print("PASS: LIANA step produced a valid standardized long table + universe.")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dataset", default="workspace/library/datasets/dataset_lohoff_et_al_seqfish.h5ad")
    p.add_argument("--celltype", default="celltype_mapped_refined")
    p.add_argument("--species", choices=["human", "mouse"], default="mouse")
    p.add_argument("--platform", default="seqfish")
    p.add_argument("--resolution-mode", dest="resolution_mode",
                   choices=["spot_multicell", "single_cell"], default="single_cell")
    p.add_argument("--outdir", default="/tmp/ccc_liana_test")
    p.add_argument("--fast", action="store_true", help="n_perms=100 (smoke) instead of 1000")
    p.add_argument("--reuse-base", action="store_true",
                   help="skip prep if ccc_base.h5ad already exists in --outdir")
    args = p.parse_args()

    print("versions:", {m: version(m) for m in ["liana", "scanpy", "anndata"]})
    base = Path(args.outdir) / "ccc_base.h5ad"
    if args.reuse_base and base.exists():
        prep = json.load(open(Path(args.outdir) / "logs" / "ccc_data_prep.json"))
        print("[prep] reusing existing base")
    else:
        prep = prep_base(args)
    run_liana(args, prep)
    validate(args)


if __name__ == "__main__":
    main()
