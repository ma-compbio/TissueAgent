"""CCC ensemble — Step 1: shared data prep for the 4-member ensemble.

Directly runnable AND importable. Run the whole step in the kernel with (adjust
only the flags for your dataset):

    %run project/skills/ccc-data-prep/scripts/ccc_data_prep.py \
        --adata project/uploads/spatial.h5ad --cell-type cell_type --species human

or import the helpers and call them yourself:

    import sys; sys.path.insert(0, "project/skills/ccc-data-prep/scripts")
    from ccc_data_prep import (build_shared_resource, compute_cell_activity,
                               crop_central, median_nn_distance, prime_resources,
                               slim_to_lr_genes)

Order matters: crop -> PROGENy activity (FULL transcriptome) -> slim. Do NOT build
the LR resource from OmniPath, hand-roll PROGENy, or change the fixed parameters
(`dis_mult`=1.5, `knn_k`=6). If var_names are Ensembl IDs, remap to symbols and
re-save the h5ad FIRST; if no discrete cell-type column exists, cluster spatial
domains first and pass that column. See ccc-data-prep.md for the rationale.
"""

import warnings; warnings.filterwarnings("ignore")
import argparse
import json, os
import numpy as np, pandas as pd, scanpy as sc
import scipy.sparse as sp
from sklearn.neighbors import NearestNeighbors


# --- spatial helpers ---
def median_nn_distance(coords):
    """Median nearest-neighbour distance in obsm['spatial'] units (radii derive from this)."""
    nn = NearestNeighbors(n_neighbors=2).fit(coords)
    d, _ = nn.kneighbors(coords)
    return float(np.median(d[:, 1]))


def crop_central(adata, target):
    """Keep the `target` cells nearest the tissue centroid (a contiguous central patch).

    COMMOT's OT solve costs seconds PER pair and grows with cell count. Rather than randomly
    thinning cells (which corrupts the OT solution by altering local ligand/receptor supply),
    analyse one contiguous full-density window. Local neighbourhoods are preserved exactly.
    """
    if adata.n_obs <= target:
        return adata
    coords = np.asarray(adata.obsm["spatial"], float)
    c = coords.mean(0)
    d = np.linalg.norm(coords - c, axis=1)
    keep = np.argsort(d)[:target]
    return adata[keep].copy()


# --- shared ligand-receptor resource ---
# prime_resources() is called once BEFORE any clustering: LIANA's select_resource can
# deadlock if first read after scanpy's neighbors/leiden numba path has run.
_RESOURCE_CACHE = {}
def _get_resource(species):
    key = "mouseconsensus" if species == "mouse" else "consensus"
    if key not in _RESOURCE_CACHE:
        import liana as li
        _RESOURCE_CACHE[key] = li.rs.select_resource(key)[["ligand", "receptor"]].copy()
    return _RESOURCE_CACHE[key]


def prime_resources():
    _get_resource("human"); _get_resource("mouse")


def consensus_lr_genes(species):
    res = _get_resource(species)
    res = res[~res.ligand.str.contains("_") & ~res.receptor.str.contains("_")]
    return set(res.ligand) | set(res.receptor)


def slim_to_lr_genes(adata, species):
    """Subset to genes that could ever join a monomeric LR pair (RAM guard).

    Run AFTER compute_cell_activity — PROGENy footprints are mostly non-LR genes.
    """
    keep = [g for g in adata.var_names if g in consensus_lr_genes(species)]
    return adata[:, keep].copy()


def build_shared_resource(adata, species, min_expr_frac=0.05, max_pairs=300):
    """The single monomeric LR resource all four members run on.

      1. LIANA consensus resource for the species; 2. keep monomeric (single-gene) pairs;
      3. keep pairs whose ligand AND receptor are on the panel and expressed in >=
         min_expr_frac of cells; 4. cap at max_pairs most-expressed pairs (bounds COMMOT memory).
    """
    res = _get_resource(species).copy()
    res = res[~res.ligand.str.contains("_") & ~res.receptor.str.contains("_")]
    var = set(adata.var_names)
    res = res[res.ligand.isin(var) & res.receptor.isin(var)].drop_duplicates()
    frac = np.asarray((adata.X > 0).mean(axis=0)).ravel()
    fr = pd.Series(frac, index=adata.var_names)
    ok = (fr[res.ligand].values >= min_expr_frac) & (fr[res.receptor].values >= min_expr_frac)
    res = res[ok].copy()
    if len(res) > max_pairs:
        res["_e"] = fr[res.ligand].values + fr[res.receptor].values
        res = res.sort_values("_e", ascending=False).head(max_pairs).drop(columns="_e")
    return res.reset_index(drop=True)


# --- PROGENy downstream-response amplitude (decoupler) ---
_NET_CACHE = {}
def _progeny_net():
    """Always load the HUMAN PROGENy net.

    decoupler's organism="mouse" path fetches an HCOP ortholog table whose URL currently
    404s; for a coarse response-amplitude proxy, matching mouse genes to human footprint
    symbols by upper-cased symbol (in compute_cell_activity) is an accepted mapping.
    """
    import decoupler as dc
    if "human" not in _NET_CACHE:
        _NET_CACHE["human"] = dc.op.progeny(organism="human")
    return _NET_CACHE["human"]


def compute_cell_activity(adata_full, species):
    """Per-cell downstream response amplitude from PROGENy footprints.

    Runs on the FULL gene matrix (footprint genes are mostly non-LR), so call this BEFORE
    slim_to_lr_genes. Returns (a, info): a = length-n_obs amplitude (per-pathway z-scored,
    then L2 over pathways); info records footprint-gene overlap. Activity is intrinsic
    (per-observation ULM), so it carries to slimmed copies / folds by row-subsetting.
    Mouse symbols are upper-cased to match human footprints (documented coarse mapping).
    """
    import decoupler as dc
    net = _progeny_net()
    ad = adata_full
    if species == "mouse":
        ad = adata_full.copy()
        ad.var_names = [str(g).upper() for g in ad.var_names]
        ad.var_names_make_unique()
    n_overlap = len(set(net["target"]) & set(map(str, ad.var_names)))
    dc.mt.ulm(data=ad, net=net, tmin=5)                     # -> obsm['score_ulm']
    A = np.nan_to_num(np.asarray(ad.obsm["score_ulm"].values, float))
    sd = A.std(0); sd[sd == 0] = 1.0
    Az = (A - A.mean(0)) / sd
    a = np.sqrt((Az ** 2).sum(1))
    return a, dict(n_pathways=A.shape[1], n_footprint_genes=int(n_overlap))


def main(argv=None):
    ap = argparse.ArgumentParser(description="CCC ensemble Step 1 — shared data prep.")
    ap.add_argument("--adata", default="project/uploads/spatial.h5ad",
                    help="spatial h5ad with raw counts + obsm['spatial'] (symbols, not Ensembl)")
    ap.add_argument("--cell-type", default="cell_type",
                    help=".obs column of discrete labels ('_ct' is derived from it)")
    ap.add_argument("--species", default="human", choices=["human", "mouse"],
                    help="explicit species — never inferred from gene casing")
    ap.add_argument("--crop-n", type=int, default=2000,
                    help="contiguous central-patch cap (COMMOT tractability)")
    ap.add_argument("--max-pairs", type=int, default=50,
                    help="cap on the shared LR universe (COMMOT ~sec/pair)")
    ap.add_argument("--knn-k", type=int, default=6,
                    help="kNN degree for the decoupler receiving graph")
    args = ap.parse_args(argv)

    ADATA_IN, CELL_TYPE, SPECIES = args.adata, args.cell_type, args.species
    CROP_N, MAX_PAIRS, KNN_K = args.crop_n, args.max_pairs, args.knn_k

    prime_resources()                              # load LR resources before any clustering/numba

    adata = sc.read_h5ad(ADATA_IN)
    adata.var_names_make_unique()
    # If var_names are Ensembl IDs, remap to symbols FIRST, then var_names_make_unique() again —
    # all members match on symbols, not Ensembl IDs.

    adata.layers["counts"] = adata.X.copy()
    sc.pp.normalize_total(adata, target_sum=10000.0)
    sc.pp.log1p(adata)                             # .X is now log1p-normalized (all members use .X)

    adata.obs["_ct"] = adata.obs[CELL_TYPE].astype(str).astype("category")
    assert adata.obs["_ct"].nunique() >= 2, "need >=2 cell/domain categories"
    assert adata.obs["_ct"].value_counts().min() >= 10, "need >=10 cells per category"

    adata.obsm["spatial"] = np.asarray(adata.obsm["spatial"], float)
    assert adata.obsm["spatial"].shape == (adata.n_obs, 2) and np.isfinite(adata.obsm["spatial"]).all()

    small_panel = adata.n_vars < 1000              # measured on the FULL gene set

    adata = crop_central(adata, CROP_N)            # contiguous central patch; NEVER random-subsample
    dact, dinfo = compute_cell_activity(adata, SPECIES)   # PROGENy amplitude on the FULL transcriptome
    adata.obs["_dact"] = np.asarray(dact, float)   # carried into ccc_base.h5ad for the decoupler step
    adata = slim_to_lr_genes(adata, SPECIES)       # NOW drop to LR-candidate genes (RAM guard)

    median_nn = median_nn_distance(np.asarray(adata.obsm["spatial"], float))
    resource = build_shared_resource(adata, SPECIES,
                                     min_expr_frac=0.03 if small_panel else 0.05,
                                     max_pairs=MAX_PAIRS)

    os.makedirs("project/outputs/logs", exist_ok=True)
    resource[["ligand", "receptor"]].to_csv("project/outputs/ccc_lr_common.csv", index=False)
    adata.write("project/outputs/ccc_base.h5ad")
    json.dump({"species": SPECIES, "median_nn": median_nn, "small_panel": bool(small_panel),
               "n_obs": int(adata.n_obs), "n_pairs": int(len(resource)), "crop_n": CROP_N,
               "max_pairs": MAX_PAIRS, "dis_mult": 1.5, "knn_k": KNN_K,
               "n_footprint_genes": int(dinfo["n_footprint_genes"]),
               "n_pathways": int(dinfo["n_pathways"])},
              open("project/outputs/logs/ccc_data_prep.json", "w"), indent=2)
    print(f"ccc_base {adata.shape}; median_nn={median_nn:.1f}; LR pairs={len(resource)}; "
          f"PROGENy footprint genes={dinfo['n_footprint_genes']}/{dinfo['n_pathways']}")


if __name__ == "__main__":
    main()
