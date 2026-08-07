---
name: ccc-data-prep
description: Step 1 of the ccc_ensemble workflow. Writes the verbatim shared library `ensemble_ccc.py`, preprocesses a spatial transcriptomics AnnData once into an immutable base object (log1p .X, `_ct` labels, native-unit spatial coords), and builds the ONE shared monomeric ligand-receptor resource that both LIANA+ and COMMOT run on. Emits ccc_base.h5ad, ccc_lr_common.csv, and a calibration log.
applies_to: [coding_agent]
tags: [ccc, ligand-receptor, spatial, preprocessing, ensemble]
status: enable
---

# CCC Data Prep — shared setup for the LIANA+COMMOT ensemble

## ⚠️ This is a fixed, validated pipeline — do not deviate

The ensemble is **LIANA+ ⊕ COMMOT** combined by percentile-rank consensus. The code
below is copied from a validated analysis and must be reproduced **verbatim**. Do **not**
add methods (no stLearn, no bivariate, no cluster-level permutation tests), do **not** add
regimes (there is a single COMMOT distance), do **not** add evaluation/metrics, and do
**not** "improve" or refactor the library functions. If a step fails, fix the *environment
or the inputs*, never the method code.

## When to use

Run this **once** at the start of a `ccc_ensemble` workflow, before [[ccc-liana]],
[[ccc-commot]], and [[ccc-aggregate]]. It does three jobs the whole ensemble depends on:

1. **Writes `ensemble_ccc.py`** — the shared library every downstream step imports
   (`run_liana`, `run_commot`, `build_ensemble`, plus the resource/spatial helpers).
   Reproduce it verbatim from the block below.
2. **Writes the immutable base object** (`ccc_base.h5ad`): `.X` = log1p-normalized (both
   LIANA and COMMOT consume `.X`), `obs['_ct']` = discrete cell/domain labels,
   `obsm['spatial']` = float `(n,2)` native-unit coordinates. Each downstream skill
   **copies** this and writes its own outputs — nothing overwrites the base.
3. **Builds the one shared LR resource** (`ccc_lr_common.csv`) both tools run on. Their
   native databases overlap only ~0.17 Jaccard, so without a shared resource "consensus"
   would measure database agreement, not method agreement. It is monomeric (single-gene
   pairs), expression-filtered, and capped at `MAX_PAIRS`.

## Input

- **Spatial h5ad** — `.obsm['spatial']` populated (or `obs['x','y']`); raw counts in `.X`
  or `layers['counts']`; human or mouse **gene symbols** (map Ensembl IDs first).
- **species** — `"human"` or `"mouse"` (explicit; never inferred from gene casing).
- **platform** — `visium | xenium | merfish | seqfish | ...` (a hint; inspect the data).
- **cell_type_col** — `.obs` column of discrete labels (≥2 categories, ≥10 cells each).
  If the data ships no labels, derive spatial domains by unsupervised clustering (e.g.
  KMeans on PCA of HVGs) *before* building the resource.

## Output (project working dir)

- `ensemble_ccc.py` — the verbatim shared library (below).
- `ccc_base.h5ad` — immutable. `.X` log1p-normalized; `layers['counts']` raw;
  `obs['_ct']` cleaned categorical labels; `obsm['spatial']` float `(n,2)`.
- `ccc_lr_common.csv` — shared monomeric resource, columns `ligand,receptor`.
- `logs/ccc_data_prep.json` — calibration record every downstream skill reads:

  ```json
  {
    "species": "human|mouse", "platform": "visium|merfish|...",
    "median_nn": 118.0,        // in obsm['spatial'] UNITS — COMMOT's dis_thr derives from this
    "small_panel": false,      // n_genes < 1000 (targeted imaging) -> widen expr filter
    "n_obs": 2000, "n_pairs": 50,
    "crop_n": 2000, "max_pairs": 50, "dis_mult": 1.5
  }
  ```

## Success criteria

- `ensemble_ccc.py` exists and imports cleanly (`from ensemble_ccc import run_liana`).
- `ccc_base.h5ad` loads with `.X` log1p, `layers['counts']`, `obs['_ct']` (≥2 categories,
  ≥10 cells each), `obsm['spatial']` float `(n,2)` with no NaN.
- `median_nn > 0`; `ccc_lr_common.csv` has ≥4 pairs (else check species / gene symbols /
  panel coverage).
- `logs/ccc_data_prep.json` has `species`, `median_nn`, `small_panel` populated.

## Shared library — write this VERBATIM to `ensemble_ccc.py`

Do not edit any function body. (This is the analysis library with the evaluation-only
functions removed — the method itself is unchanged.)

```python
"""
ensemble_ccc.py — shared library for the LIANA+ ⊕ COMMOT ensemble CCC workflow.

Two methodologically complementary tools on ONE shared ligand-receptor resource:
  * LIANA+ rank_aggregate  — non-spatial cell-group expression consensus.
  * COMMOT spatial_communication — spatial optimal-transport signalling flow.
The ensemble promotes an LR pair only when BOTH axes agree (mean of percentile ranks).

Write this file verbatim in Step 1; every downstream step imports from it. Do NOT edit.
"""
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import scipy.sparse as sp
from sklearn.neighbors import NearestNeighbors


# ---------------------------------------------------------------------------------------
# Spatial helpers
# ---------------------------------------------------------------------------------------
def median_nn_distance(coords):
    """Median nearest-neighbour distance in the units of obsm['spatial'].

    COMMOT's dis_thr lives in these native units, so the radius is a multiple of this scalar.
    """
    nn = NearestNeighbors(n_neighbors=2).fit(coords)
    d, _ = nn.kneighbors(coords)
    return float(np.median(d[:, 1]))


def crop_central(adata, target):
    """Keep the `target` cells nearest the tissue centroid (a contiguous central patch).

    COMMOT's optimal-transport solve costs several seconds PER LR pair and grows with cell
    count. Rather than randomly thinning cells (which changes local ligand/receptor supply and
    corrupts the OT solution), analyse one contiguous full-density window: the `target` cells
    closest to the section centroid. Local neighbourhoods are preserved exactly.
    """
    if adata.n_obs <= target:
        return adata
    coords = np.asarray(adata.obsm["spatial"], float)
    c = coords.mean(0)
    d = np.linalg.norm(coords - c, axis=1)
    keep = np.argsort(d)[:target]
    return adata[keep].copy()


# ---------------------------------------------------------------------------------------
# Shared ligand-receptor resource
# ---------------------------------------------------------------------------------------
# LIANA's select_resource reads a CSV that can DEADLOCK if first called after scanpy's
# neighbors/leiden numba path has run. prime_resources() is called once at startup, before
# any clustering, so every later lookup hits this cache and never re-reads the CSV.
_RESOURCE_CACHE = {}


def _get_resource(species):
    key = "mouseconsensus" if species == "mouse" else "consensus"
    if key not in _RESOURCE_CACHE:
        import liana as li
        _RESOURCE_CACHE[key] = li.rs.select_resource(key)[["ligand", "receptor"]].copy()
    return _RESOURCE_CACHE[key]


def prime_resources():
    """Pre-load both species resources while the process is still numba-clean."""
    _get_resource("human")
    _get_resource("mouse")


def consensus_lr_genes(species):
    """All single-gene ligand/receptor symbols in the species consensus resource."""
    res = _get_resource(species)
    res = res[~res.ligand.str.contains("_") & ~res.receptor.str.contains("_")]
    return set(res.ligand) | set(res.receptor)


def slim_to_lr_genes(adata, species):
    """Subset to genes that could ever participate in a monomeric LR pair (RAM guard)."""
    keep = [g for g in adata.var_names if g in consensus_lr_genes(species)]
    return adata[:, keep].copy()


def build_shared_resource(adata, species, min_expr_frac=0.05, max_pairs=300):
    """Build the single monomeric LR resource both tools run on.

      1. LIANA's curated consensus resource for the species.
      2. Keep only monomeric (single-gene) pairs -- the common denominator across tools.
      3. Keep pairs whose ligand AND receptor are both on the panel and expressed in at
         least `min_expr_frac` of cells (so both tools can actually score them).
      4. Cap at `max_pairs` most-expressed pairs to bound COMMOT's per-pair obsp memory.
    """
    res = _get_resource(species).copy()
    res = res[~res.ligand.str.contains("_") & ~res.receptor.str.contains("_")]

    var = set(adata.var_names)
    res = res[res.ligand.isin(var) & res.receptor.isin(var)].drop_duplicates()

    X = adata.X
    frac = np.asarray((X > 0).mean(axis=0)).ravel()
    fr = pd.Series(frac, index=adata.var_names)
    ok = (fr[res.ligand].values >= min_expr_frac) & (fr[res.receptor].values >= min_expr_frac)
    res = res[ok].copy()

    if len(res) > max_pairs:
        res["_e"] = fr[res.ligand].values + fr[res.receptor].values
        res = res.sort_values("_e", ascending=False).head(max_pairs).drop(columns="_e")
    res = res.reset_index(drop=True)
    return res


# ---------------------------------------------------------------------------------------
# Method 1: LIANA+ rank_aggregate  (non-spatial expression consensus)
# ---------------------------------------------------------------------------------------
def run_liana(adata, resource, expr_prop=0.1, seed=1337, n_perms=100):
    """Run LIANA+ rank_aggregate on the shared resource; return LR-level scores.

    liana_score = 1 - min magnitude_rank over all (source,target) cell-group pairs
    (higher = stronger). use_raw=False is critical -- LIANA defaults True and would silently
    use a stale .raw. n_perms is low on purpose: the magnitude_rank is deterministic (from
    expression means), so permutations barely affect the ranking axis but are the slow step.
    """
    import liana as li
    li.mt.rank_aggregate(
        adata, groupby="_ct", resource=resource[["ligand", "receptor"]],
        use_raw=False, expr_prop=expr_prop, min_cells=10, n_perms=n_perms,
        seed=seed, verbose=False,
    )
    lr = adata.uns["liana_res"]
    g = (lr.assign(mag=lr["magnitude_rank"])
           .groupby(["ligand_complex", "receptor_complex"])["mag"].min()
           .reset_index())
    g.columns = ["ligand", "receptor", "min_mag_rank"]
    g["liana_score"] = 1.0 - g["min_mag_rank"]     # higher = better
    return g[["ligand", "receptor", "liana_score"]], lr


# ---------------------------------------------------------------------------------------
# Method 2: COMMOT  (spatial optimal-transport signalling)
# ---------------------------------------------------------------------------------------
def run_commot(adata, resource, dis_thr):
    """Run COMMOT spatial_communication on the shared resource; return LR-level scores.

    commot_score = total routed OT flow (sum of the per-pair spot x spot matrix) -- a clean
    magnitude needing no permutation test. dis_thr is in native spatial units (a multiple of
    median_nn), because COMMOT does not convert pixels/um. Higher = more communication.
    """
    import commot as ct
    df = resource[["ligand", "receptor"]].copy()
    df["pathway"] = "unannotated"
    db = "shared"
    ct.tl.spatial_communication(
        adata, database_name=db, df_ligrec=df, dis_thr=dis_thr,
        heteromeric=False, pathway_sum=False, cost_type="euc",
    )
    rows = []
    for lig, rec in df[["ligand", "receptor"]].itertuples(index=False):
        key = f"commot-{db}-{lig}-{rec}"
        if key not in adata.obsp:      # COMMOT did not route this pair (no signal)
            continue
        rows.append(dict(ligand=lig, receptor=rec,
                         commot_score=float(adata.obsp[key].sum())))
    out = pd.DataFrame(rows)
    # free the (potentially large) per-pair obsp matrices immediately
    for k in [k for k in list(adata.obsp.keys()) if k.startswith("commot-")]:
        del adata.obsp[k]
    for k in [k for k in list(adata.obsm.keys()) if k.startswith("commot-")]:
        del adata.obsm[k]
    for k in [k for k in list(adata.uns.keys()) if k.startswith("commot-")]:
        del adata.uns[k]
    return out


# ---------------------------------------------------------------------------------------
# Ensemble: percentile-rank consensus over the shared universe
# ---------------------------------------------------------------------------------------
def build_ensemble(liana_df, commot_df, resource):
    """Combine LIANA and COMMOT into a consensus ranking.

    Universe U = shared-resource pairs scored by BOTH tools. Within U each tool's score is
    converted to a percentile rank (0..1, robust to scale), and the ensemble score is the mean
    of the two percentile ranks -- a standard rank aggregation that promotes pairs strong on
    BOTH axes.
    """
    uni = resource[["ligand", "receptor"]].merge(liana_df, on=["ligand", "receptor"]) \
                                          .merge(commot_df, on=["ligand", "receptor"])
    uni = uni.dropna(subset=["liana_score", "commot_score"]).reset_index(drop=True)
    uni["liana_pct"] = uni["liana_score"].rank(pct=True)
    uni["commot_pct"] = uni["commot_score"].rank(pct=True)
    uni["ensemble_score"] = 0.5 * (uni["liana_pct"] + uni["commot_pct"])
    return uni
```

## Prep driver — adjust only the marked INPUT constants

```python
import json, os
import numpy as np, pandas as pd, scanpy as sc
from ensemble_ccc import (median_nn_distance, prime_resources, slim_to_lr_genes,
                          crop_central, build_shared_resource)

# ---- INPUTS (adjust these only) ----
ADATA_IN   = "uploads/spatial.h5ad"   # spatial h5ad with raw counts + obsm['spatial']
CELL_TYPE  = "cell_type"              # .obs column of discrete labels ('_ct' is derived)
SPECIES    = "human"                  # "human" or "mouse" — explicit, never inferred
PLATFORM   = "visium"                 # visium | xenium | merfish | seqfish | ...
CROP_N     = 2000                     # contiguous central-patch cap (COMMOT tractability)
MAX_PAIRS  = 50                       # cap on the shared LR universe (COMMOT ~sec/pair)

prime_resources()                     # load LR CSVs before any clustering/numba (avoids deadlock)

adata = sc.read_h5ad(ADATA_IN)
adata.var_names_make_unique()
# If var_names are Ensembl IDs (ENSG/ENSMUSG), remap to symbols FIRST (e.g. adata.var['gene_symbol'])
# and var_names_make_unique() again — LIANA/COMMOT match on symbols, not Ensembl IDs.

adata.layers["counts"] = adata.X.copy()
sc.pp.normalize_total(adata, target_sum=10000.0)
sc.pp.log1p(adata)                                  # .X is now log1p-normalized (LIANA + COMMOT use .X)

# cell/domain labels -> _ct (exactly the column run_liana groups on).
# If no labels ship with the data, derive spatial domains by unsupervised clustering first.
adata.obs["_ct"] = adata.obs[CELL_TYPE].astype(str).astype("category")
assert adata.obs["_ct"].nunique() >= 2, "need >=2 cell/domain categories"
assert adata.obs["_ct"].value_counts().min() >= 10, "need >=10 cells per category"

adata.obsm["spatial"] = np.asarray(adata.obsm["spatial"], float)
assert adata.obsm["spatial"].shape == (adata.n_obs, 2) and np.isfinite(adata.obsm["spatial"]).all()

small_panel = adata.n_vars < 1000
adata = slim_to_lr_genes(adata, SPECIES)            # keep only LR-candidate genes (RAM guard)
adata = crop_central(adata, CROP_N)                 # contiguous central patch; NEVER random-subsample
median_nn = median_nn_distance(np.asarray(adata.obsm["spatial"], float))

resource = build_shared_resource(adata, SPECIES,
                                 min_expr_frac=0.03 if small_panel else 0.05,
                                 max_pairs=MAX_PAIRS)
resource[["ligand", "receptor"]].to_csv("ccc_lr_common.csv", index=False)

os.makedirs("logs", exist_ok=True)
adata.write("ccc_base.h5ad")
json.dump({"species": SPECIES, "platform": PLATFORM, "median_nn": median_nn,
           "small_panel": bool(small_panel), "n_obs": int(adata.n_obs),
           "n_pairs": int(len(resource)), "crop_n": CROP_N, "max_pairs": MAX_PAIRS,
           "dis_mult": 1.5},
          open("logs/ccc_data_prep.json", "w"), indent=2)
print(f"ccc_base {adata.shape}; median_nn={median_nn:.1f}; shared LR pairs={len(resource)}")
```

## Multi-sample data

CCC must be run **per physical section** — mixing sections mixes coordinate systems. If the
object holds multiple sections/animals/FOVs sharing a coordinate frame, subset to **one
coherent section first** (as the analysis subset MERFISH to Animal 1 / one Bregma slice and
DLPFC to one `sample_name`). Do not pool sections before inference.

## Common issues

- **Ensembl IDs → ~0 LR pairs.** The consensus resource uses symbols; map Ensembl to symbols
  first, then `var_names_make_unique()`.
- **`prime_resources()` deadlock if skipped.** Call it once at the very top, before any
  clustering/leiden/KMeans, or LIANA's first `select_resource` can deadlock under numba.
- **Standardized coords.** If `obsm['spatial']` is mean-centered/scaled, radii are meaningless —
  re-pull raw coordinates before calibrating `median_nn`.
- **Very few pairs.** Usually a species mismatch (human resource on mouse data) or a sparse
  imaging panel — the driver already drops `min_expr_frac` to 0.03 for `small_panel`.

## References

- LIANA+ resources: `li.rs.select_resource`, `li.rs.show_resources()`.
- Related skills: [[ccc-liana]], [[ccc-commot]], [[ccc-aggregate]]; parent plan `ccc_ensemble`.
</content>
</invoke>
