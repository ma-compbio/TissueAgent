---
name: ccc-data-prep
description: Preprocess and QC a spatial transcriptomics AnnData so it can be consumed identically by LIANA+, COMMOT, and stLearn in a CCC ensemble. Validates spatial coords, cell-type column, species/gene-symbol convention, and stores both raw counts (for stLearn) and log-normalized .X (for LIANA+/COMMOT).
applies_to: [coding_agent]
tags: [ccc, ligand-receptor, spatial, preprocessing]
status: enable
---

# CCC Data Prep (shared preprocessing for the ensemble)

## When to use

Run this once at the start of a `ccc_ensemble` workflow. The three methods downstream ([[ccc-liana]], [[ccc-commot]], [[ccc-stlearn]]) have **incompatible preprocessing expectations** if applied naively — LIANA+ and COMMOT want log1p-normalized counts in `.X`; stLearn wants `sc.pp.normalize_total`-normalized counts **without** log1p. This skill normalizes once and stashes both forms so each method gets what it needs without re-running on a stale object.

Do NOT use this skill outside the ensemble — for a single-method run use the method's own preprocessing recipe directly.

## Input

- **Spatial h5ad** *(required)* — `.obsm['spatial']` populated (or `obs['x','y']` which we'll convert), raw integer counts ideally in `.X` or `adata.layers['counts']`.
- **Cell-type column** *(required)* — name of an `.obs` column with discrete cell type labels. Must have ≥2 categories with ≥10 cells each, otherwise downstream permutation tests are meaningless.
- **Species** *(required)* — `"human"` or `"mouse"`. Determines the LR resource name used downstream (`consensus` vs `mouseconsensus` for LIANA+; `'human'`/`'mouse'` for COMMOT's CellChatDB; LR DB species for stLearn).
- **Platform** *(required)* — one of `visium | visium_hd | xenium | merfish | seqfish | slide_seq | st | unknown`. Drives every downstream neighborhood parameter (COMMOT's `dis_thr`, stLearn's `distance` / gridding path, LIANA+'s `bandwidth`). Detect from `adata.uns['spatial'][library_id]['scalefactors']` when present (→ Visium/Visium HD); otherwise ask the user.
- **Coordinate units** *(required)* — `um | pixel | normalized`. Raw Visium `.obsm['spatial']` is in fullres pixels — convert to µm via the Space Ranger scalefactor. Xenium / MERFISH / seqFISH raw exports ship in µm. `normalized` means the atlas has already standardized coordinates (mean-centered, ~[-3,3]); this is UNUSABLE for physical-scale calibration — refuse and pull the raw data.
- **Gene-symbol convention** — gene names must be **symbols** (HGNC for human, MGI for mouse). If `.var_names` look like Ensembl IDs (start with `ENSG`/`ENSMUSG`), the skill maps them via the same `mygene` workflow used in [[cell-type-annotation]].

## Output

Written to the active project's `outputs/` folder:

- `ccc_prepped.h5ad` — single AnnData with:
  - `.X` = log1p-normalized to 1e4 (LIANA+/COMMOT-ready)
  - `.layers['counts']` = raw integer counts (preserved)
  - `.layers['norm_no_log']` = `normalize_total` only, **no log1p** (stLearn-ready)
  - `.obs['_ccc_cell_type']` = a clean copy of the user's cell-type column with `str` dtype + categorical conversion + invalid-character scrub
  - `.obsm['spatial']` = float array, shape `(n_obs, 2)`
- `logs/ccc_data_prep.json` — full platform + calibration record. Every downstream skill in the ensemble reads this and refuses to run if `median_nn_um` is null:

  ```json
  {
    "species":                "human | mouse",
    "platform":               "visium | visium_hd | xenium | merfish | seqfish | slide_seq | st | unknown",
    "resolution_mode":        "spot_multicell | single_cell",
    "coord_unit":             "um | pixel | normalized",
    "spot_diameter_um":       55.0,          // 55 for Visium, 2 for Visium HD, null for imaging
    "median_nn_distance":     123.4,         // median 1-NN in coord_unit
    "median_nn_um":           123.4,         // same converted to µm (null if coord_unit=normalized)
    "n_cells_per_mm2":        3400.0,        // null if coord_unit != um
    "cell_type_col":          "_ccc_cell_type",
    "n_cells":                19416,
    "n_genes":                351,
    "n_categories":           22,
    "min_cells_per_category": 45,
    "spatial_coord_range":    [xmin, ymin, xmax, ymax],
    "gene_symbol_convention": "hgnc | mgi | ensembl_mapped",
    "mapped_n_genes":         null
  }
  ```

## Success Criteria

- `ccc_prepped.h5ad` loads and contains the three layers above.
- `_ccc_cell_type` has ≥2 categories AND `min_cells_per_category ≥ 10`.
- `adata.obsm['spatial'].shape == (n_obs, 2)` and contains no NaNs.
- ≥1000 genes survive QC (otherwise LR overlap will be too small downstream — flag this and stop). Targeted imaging panels (Xenium/MERFISH/seqFISH) will often have 200–500 genes; when that's the case, DO NOT hard-fail — mark `n_genes < 1000` in the JSON log so downstream skills can widen their filters (e.g. LIANA `expr_prop=0.05`) instead.
- `platform`, `resolution_mode`, `coord_unit`, `median_nn_um` all populated in `logs/ccc_data_prep.json`. Refuse to write `ccc_prepped.h5ad` without them — every downstream skill depends on this calibration.

## Workflow

1. Load the h5ad, find raw counts (prefer `layers['counts']`, else `.X` if `.X.dtype` is integer, else error).
2. Validate spatial coords: if `obsm['spatial']` absent and `obs[['x','y']]` present, build `obsm['spatial'] = obs[['x','y']].to_numpy(float)`. Assert no NaN, no all-zero rows.
3. **Platform calibration.** This is the step that makes the ensemble platform-agnostic — every downstream method reads what it produces:
   - Determine `platform` and `coord_unit`. Prefer `adata.uns['spatial'][library_id]` (Visium/Visium HD ship a `scalefactors_json` there); else ask the user.
   - Detect pre-normalized coords early: if `|mean| < 1` on both axes AND `max(|coord|) < 10`, set `coord_unit = "normalized"` and RAISE — recalibrating downstream radii on standardized coords is meaningless.
   - If `coord_unit == "pixel"` (Visium), pull `tissue_hires_scalef` (or `microns_per_pixel`) from `.uns['spatial'][library_id]['scalefactors']` and compute `spot_diameter_um = spot_diameter_fullres × scalefactor`.
   - `median_nn_distance`: sample up to 2000 cells, compute each cell's 1-NN Euclidean distance, take the median. Convert to µm to fill `median_nn_um`.
   - `resolution_mode`: `spot_multicell` for `visium | visium_hd | st | slide_seq`; `single_cell` for `xenium | merfish | seqfish`; abort with an actionable message for `unknown`.
   - If `coord_unit == "um"`, compute `n_cells_per_mm2 = n_cells / area_mm2` from the coord range.
4. Validate `cell_type_col`: assert column exists, `nunique() >= 2`, `value_counts().min() >= 10`. Copy to `obs['_ccc_cell_type']` with strings (no leading digits, no `|` or `/`, replace whitespace with `_`).
5. Gene-symbol check: peek at `var_names[:10]`. If they match `ENSG\d+` (or `ENSMUSG\d+` for mouse), map to symbols via `mygene.MyGeneInfo().querymany(..., species=species, scopes='ensembl.gene', fields='symbol')`. Drop unmapped.
6. Basic QC: `sc.pp.filter_genes(adata, min_cells=3)`, `sc.pp.filter_cells(adata, min_genes=10)`. If `<1000` genes remain, log a warning (don't hard-fail on imaging panels; see Success Criteria).
7. Cache raw counts to `adata.layers['counts']`.
8. Build the two normalized variants: `normalize_total → layers['norm_no_log']`, then `normalize_total + log1p → .X`.
9. Write `ccc_prepped.h5ad` and the extended JSON log.

## Code Template

```python
import json, os
import numpy as np
import scanpy as sc
from sklearn.neighbors import NearestNeighbors

ADATA_IN   = "uploads/spatial.h5ad"   # adjust
CELL_TYPE  = "cell_type"              # adjust
SPECIES    = "human"                  # or "mouse"
PLATFORM   = "xenium"                 # visium | visium_hd | xenium | merfish | seqfish | slide_seq | st
COORD_UNIT = "um"                     # um | pixel | normalized

SPOT_MULTI = {"visium", "visium_hd", "st", "slide_seq"}
SPOT_UM    = {"visium": 55.0, "visium_hd": 2.0}

adata = sc.read_h5ad(ADATA_IN)

# 1. counts layer
if "counts" not in adata.layers:
    if np.issubdtype(adata.X.dtype, np.integer):
        adata.layers["counts"] = adata.X.copy()
    else:
        raise ValueError("No raw integer counts found; provide layers['counts'] or integer .X")

# 2. spatial
if "spatial" not in adata.obsm:
    adata.obsm["spatial"] = adata.obs[["x", "y"]].to_numpy(float)
assert not np.isnan(adata.obsm["spatial"]).any()
coords = adata.obsm["spatial"]

# 3. Platform calibration
# Detect pre-normalized coords (mean-centered, small range) — refuse.
if (np.abs(coords.mean(axis=0)) < 1).all() and np.abs(coords).max() < 10:
    COORD_UNIT = "normalized"
if COORD_UNIT == "normalized":
    raise ValueError(
        "Spatial coordinates look pre-normalized/standardized (|mean|<1, max<10). "
        "Downstream dis_thr/bandwidth calibration requires physical units — "
        "re-pull the raw h5ad with un-normalized coordinates."
    )

resolution_mode = "spot_multicell" if PLATFORM in SPOT_MULTI else "single_cell"

# µm-per-unit conversion for pixel coords (Visium): pull from adata.uns['spatial']
um_per_unit = 1.0
if COORD_UNIT == "pixel" and "spatial" in adata.uns:
    lib = next(iter(adata.uns["spatial"].values()))
    scale = lib.get("scalefactors", {})
    # Space Ranger publishes microns_per_pixel; fall back to tissue_hires_scalef if needed
    um_per_unit = float(scale.get("microns_per_pixel", 1.0))

# 1-NN median distance from a 2000-cell sample
rng = np.random.default_rng(1337)
sample = coords[rng.choice(coords.shape[0], size=min(2000, coords.shape[0]), replace=False)]
dists, _ = NearestNeighbors(n_neighbors=2).fit(coords).kneighbors(sample)
median_nn_distance = float(np.median(dists[:, 1]))
median_nn_um       = median_nn_distance * um_per_unit

# Density (only meaningful in µm)
n_cells_per_mm2 = None
if COORD_UNIT == "um":
    xmin, ymin = coords.min(axis=0); xmax, ymax = coords.max(axis=0)
    area_mm2 = ((xmax - xmin) * (ymax - ymin)) / 1e6
    if area_mm2 > 0:
        n_cells_per_mm2 = float(adata.n_obs / area_mm2)

# 4. cell type
assert CELL_TYPE in adata.obs and adata.obs[CELL_TYPE].nunique() >= 2
adata.obs["_ccc_cell_type"] = (
    adata.obs[CELL_TYPE].astype(str)
    .str.replace(r"[\s|/]+", "_", regex=True)
    .astype("category")
)
assert adata.obs["_ccc_cell_type"].value_counts().min() >= 10, \
    "Need >=10 cells per cell type for permutation tests"

# 5. (omit gene-symbol mapping if names already look like symbols)

# 6. QC — soft warn on small imaging panels instead of hard-failing
sc.pp.filter_genes(adata, min_cells=3)
sc.pp.filter_cells(adata, min_genes=10)
small_panel = adata.n_vars < 1000

# 7 + 8. counts + two normalization variants
adata.layers["counts"] = adata.layers.get("counts", adata.X.copy())
norm_only = sc.pp.normalize_total(adata, target_sum=1e4, inplace=False)["X"]
adata.layers["norm_no_log"] = norm_only
sc.pp.normalize_total(adata, target_sum=1e4)
sc.pp.log1p(adata)

# 9. write
os.makedirs("logs", exist_ok=True)
adata.write("ccc_prepped.h5ad")

xmin, ymin = coords.min(axis=0).tolist()
xmax, ymax = coords.max(axis=0).tolist()
json.dump({
    "species": SPECIES,
    "platform": PLATFORM,
    "resolution_mode": resolution_mode,
    "coord_unit": COORD_UNIT,
    "spot_diameter_um": SPOT_UM.get(PLATFORM),
    "median_nn_distance": median_nn_distance,
    "median_nn_um": median_nn_um,
    "n_cells_per_mm2": n_cells_per_mm2,
    "cell_type_col": "_ccc_cell_type",
    "n_cells": int(adata.n_obs),
    "n_genes": int(adata.n_vars),
    "n_categories": int(adata.obs["_ccc_cell_type"].nunique()),
    "min_cells_per_category": int(adata.obs["_ccc_cell_type"].value_counts().min()),
    "spatial_coord_range": [xmin, ymin, xmax, ymax],
    "gene_symbol_convention": "hgnc" if SPECIES == "human" else "mgi",
    "mapped_n_genes": None,
    "small_panel": bool(small_panel),
}, open("logs/ccc_data_prep.json", "w"), indent=2)
print("ccc_prepped.h5ad ready:", adata.shape, "median_nn_um:", round(median_nn_um, 2))
```

## Common Issues

- **`.X` already log-normalized → stLearn output is garbage.** stLearn explicitly wants `normalize_total` without log1p; this skill saves the right variant in `layers['norm_no_log']`. The stLearn skill swaps `.X = layers['norm_no_log']` before running.
- **Ensembl gene IDs not symbols → all three methods drop ~100% of LR pairs.** LIANA+/COMMOT/stLearn LR resources all use symbols. Map first.
- **Mouse data with `resource_name='consensus'` (human) → empty results.** Pass `species='mouse'` and use the matching resource downstream.
- **One-cell-type "spatial domain" labels.** Permutation tests require multiple categories with reasonable cell counts. <10 cells/category produces unstable permutation p-values; the skill aborts.
- **Non-integer counts in `.X`.** Some platforms (Xenium, MERFISH after probe normalization) ship floats. Check the source pipeline — if counts are truly probabilistic, save `np.round(...).astype(int)` to `layers['counts']` only after confirming with the user.
- **Pre-normalized / standardized `.obsm['spatial']`.** Atlas h5ads (seqFISH embryo atlas, some MERFISH releases) ship coordinates already mean-centered and scaled to ~[-3, 3]. This is unusable for physical-scale calibration — `dis_thr = 500`, `bandwidth = 200 pixels`, `distance = 250` all become unit-less nonsense. The workflow detects this (`|mean|<1` and `max<10`) and refuses; pull the raw un-normalized coords instead.
- **Visium coord unit ambiguity.** `.obsm['spatial']` is fullres pixels by default. Do not pass 500 as a µm value in that space — convert first via `microns_per_pixel` from `.uns['spatial'][library_id]['scalefactors']`.

## References

- Canonical RRA aggregation snippet used by step 5 of `ccc_ensemble`:

  ```python
  import numpy as np, pandas as pd
  from scipy.stats import beta
  from statsmodels.stats.multitest import multipletests

  def rra_pvalue(ranks_normalized):
      r = np.sort(ranks_normalized); k = len(r)
      if k == 0: return 1.0
      return float(min(beta.cdf(r[i], i + 1, k - i) for i in range(k)))

  def to_long(df, lig, rec, src, tgt, pcol, method):
      out = df[[lig, rec, src, tgt, pcol]].copy()
      out.columns = ["ligand", "receptor", "source", "target", "pvalue"]
      out["method"] = method
      out["rank_normalized"] = out["pvalue"].rank(method="average", pct=True)
      return out

  liana_long   = to_long(pd.read_csv("liana_res.csv"),
                         "ligand_complex", "receptor_complex", "source", "target",
                         "specificity_rank", "liana")
  commot_long  = to_long(pd.read_csv("commot_cluster_results.csv"),
                         "ligand", "receptor", "source", "target", "pvalue", "commot")
  stlearn_long = to_long(pd.read_csv("stlearn_per_lr_cci.csv").assign(
                             pvalue=lambda d: 1.0 / (1.0 + d["n_sig_spots"])),
                         "ligand", "receptor", "source", "target", "pvalue", "stlearn")

  long = pd.concat([liana_long, commot_long, stlearn_long], ignore_index=True)
  agg = (long.groupby(["ligand", "receptor", "source", "target"])
              .agg(methods=("method", lambda x: sorted(set(x))),
                   ranks=("rank_normalized", list))
              .reset_index())
  agg = agg[agg["methods"].apply(len) >= 2]
  agg["rra_pvalue"] = agg["ranks"].apply(rra_pvalue)
  agg["rra_fdr"]    = multipletests(agg["rra_pvalue"], method="fdr_bh")[1]
  agg.sort_values("rra_pvalue").drop(columns=["ranks"]).to_csv(
      "ccc_consensus_ranked.csv", index=False)
  ```

- LIANA+ basic-usage tutorial (in-repo): `src/agents/agent_registry/coding_agent/tutorials/liana-examples/basic_usage.md`
- LIANA+ API: `knowledge/docs/liana_docs.json` (search via `search_documentation(library='liana')`).
- COMMOT preprocessing: <https://commot.readthedocs.io/en/latest/notebooks/visium-mouse_brain.html>
- stLearn preprocessing quirk (no log1p): <https://stlearn.readthedocs.io/en/latest/tutorials/cell_cell_interaction.html>
- RRA paper (Stuart's method): Kolde et al., *Bioinformatics* 2012.
- Related skills: [[ccc-liana]], [[ccc-commot]], [[ccc-stlearn]], and the ensemble plan `ccc_ensemble`.
