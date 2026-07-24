---
name: ccc-data-prep
description: Preprocess a spatial transcriptomics AnnData once for the CCC ensemble (LIANA+, COMMOT, stLearn), build ONE shared ligand-receptor resource all three methods use, and calibrate spatial scale in the coordinate units the methods actually consume. Writes an immutable base object every downstream skill copies (never mutates), plus a calibration record.
applies_to: [coding_agent]
tags: [ccc, ligand-receptor, spatial, preprocessing]
status: enable
---

# CCC Data Prep (shared setup for the ensemble)

## When to use

Run this **once** at the start of a `ccc_ensemble` workflow, before [[ccc-liana]],
[[ccc-commot]], and [[ccc-stlearn]]. It does three jobs the whole ensemble depends on:

1. **One immutable base object** (`ccc_base.h5ad`) with the layers every method needs.
   Each method skill loads it, copies it, and writes its *own* outputs — nothing
   downstream overwrites the base. (The methods mutate `.X` and `.uns` in incompatible
   ways; sharing one file corrupts results depending on run order.)
2. **One shared LR resource** so all three methods test the *same* interactions.
   Their native databases overlap far less than their names suggest
   (CellChatDB↔connectomeDB ≈ 0.17 Jaccard), so without this the "consensus" is
   mostly a database artifact. We harmonize to the LIANA consensus resource.
3. **Spatial calibration in the coordinate units the methods consume.** COMMOT's
   `dis_thr`, stLearn's `distance`, and LIANA's `bandwidth` are all in the units of
   `adata.obsm['spatial']` — none of them convert pixels to microns. So we compute the
   median nearest-neighbour distance **in those same units** and downstream radii are
   multiples of it. (Physical µm is computed only for a sanity check / reporting.)

Don't use this outside the ensemble — for a single-method run use that method's own recipe.

## Route by data type (all three methods branch on this)

| Data | resolution_mode | Cell-type input | What CCC can claim |
|---|---|---|---|
| Segmented single cells (Xenium, MERFISH, seqFISH) | `single_cell` | labels | directional cell-type CCC (grid stLearn) |
| Spots + deconvolution proportions (Visium) | `spot_multicell` | proportions | probabilistic cell-type attribution |
| Spots + discrete labels (Visium, DLPFC layers) | `spot_multicell` | one label/spot | spot-domain communication (dominant-label = approximate) |
| Spots, no labels | `spot_multicell` | none | spatial LR association only, **not** cell-type CCC |

`resolution_mode` describes the **observation unit**, not the product name: Visium HD
can be 2/8/16 µm bins; a "MERFISH" object may hold molecules, cells, or regions — inspect
the data, don't assume from the platform string.

## Input

- **Spatial h5ad** — `.obsm['spatial']` populated (or `obs['x','y']`); raw counts in
  `.X` or `layers['counts']`.
- **species** — `"human"` or `"mouse"` (explicit; never inferred from gene casing).
- **platform** — `visium | visium_hd | xenium | merfish | seqfish | slide_seq | st`. A hint
  for `resolution_mode` and the coordinate unit; confirm against the data.
- **cell_type_col** — `.obs` column of discrete labels (≥2 categories, ≥10 cells each), OR
  a deconvolution-proportion matrix (spots × cell types) aligned to `obs_names`.
- **sample_col** *(if present)* — batch/section/FOV column. Sections with overlapping
  coordinate systems **must** be analysed separately; recorded here so methods split on it.

## Output (project `outputs/`)

- `ccc_base.h5ad` — immutable. `.X` = log1p-normalized (LIANA+/COMMOT); `layers['counts']`
  = raw; `layers['norm_no_log']` = `normalize_total` **without** log1p (stLearn);
  `obs['_ccc_cell_type']` = cleaned labels; `obs['imagecol']/['imagerow']` = spatial x/y
  (stLearn needs these); `uns['spatial']` present if Visium.
- `ccc_lr_common.csv` — the **shared monomeric** LR resource (`ligand,receptor`): LIANA
  consensus pairs, no complexes, both genes on the panel. This is the single universe all
  three methods run on. It is monomeric because stLearn's `L_R` format can't represent
  heteromeric complexes, so the common denominator across the three engines is single genes.
- `logs/ccc_data_prep.json` — calibration record every downstream skill reads:

  ```json
  {
    "species": "human|mouse",
    "platform": "visium|xenium|merfish|...",
    "resolution_mode": "spot_multicell|single_cell",
    "coord_unit": "um|pixel|normalized",
    "median_nn": 118.0,          // in obsm['spatial'] UNITS — methods use this
    "median_nn_um": 105.0,       // physical µm for sanity/reporting; null if unknown
    "spot_diameter_um": 55.0,    // 55 Visium, 2 Visium HD, null imaging
    "cell_type_col": "_ccc_cell_type",
    "has_deconv": false,         // true iff a proportion matrix is in uns['_ccc_deconv']
    "sample_col": null,          // batch/section column, or null for a single section
    "n_samples": 1,
    "n_cells": 4035, "n_genes": 351, "n_categories": 8,
    "min_cells_per_category": 45,
    "small_panel": true,         // n_genes < 1000 (targeted imaging) -> widen expr filters
    "n_lr_common": 812,
    "stlearn_species": "human"   // connectomeDB2020 is human-derived; see Mouse note
  }
  ```

## Success criteria

- `ccc_base.h5ad` loads with the three layers and `_ccc_cell_type` (≥2 categories, ≥10
  cells each).
- `obsm['spatial']` is float `(n_obs, 2)`, no NaN; `median_nn > 0`.
- On Visium, `median_nn_um` (when computed) lands in the ~70–160 µm band — else the
  pixel→µm conversion is wrong; leave it null rather than reporting a false µm.
- `ccc_lr_common.csv` has ≥20 pairs (else check species / gene symbols / panel coverage).
- `logs/ccc_data_prep.json` has `median_nn`, `resolution_mode`, `sample_col` populated.

## Workflow

1. **Preflight.** Print package versions once (`liana`, `stlearn`, `commot`, `scanpy`,
   `anndata`) so the run log records the API surface — these libraries evolve.
2. Load; find raw counts (prefer `layers['counts']`; else `.X` if values are integer-*like*
   — nonneg + finite + `==round`, not merely integer dtype, since counts often ship float32).
3. **Spatial.** Build `obsm['spatial']` float `(n,2)` from `obs['x','y']` if absent. Detect
   pre-normalized coords (`|mean|<1` and `max<10` on both axes → standardized) and **refuse**
   — radii on standardized coords are meaningless; re-pull raw coordinates.
4. **Calibration in native units.** `median_nn` = median 1-NN Euclidean distance on a
   sample (≤2000 cells) of `obsm['spatial']` **as stored**. This is what methods use.
   Then, only for reporting, convert to µm when the factor is known:
   - Visium pixel coords → µm via `spot_diameter_um / spot_diameter_fullres`
     (`.uns['spatial'][lib]['scalefactors']`; 55 µm Visium / 2 µm Visium HD). There is
     **no** `microns_per_pixel` key and `tissue_hires_scalef` is pixel→image, not µm.
   - Imaging (Xenium/MERFISH/seqFISH) coords are already µm → `median_nn_um = median_nn`.
   - Unknown → leave `median_nn_um = null` (never guess; downstream uses native `median_nn`).
5. **Cell types.** Copy `cell_type_col` → `_ccc_cell_type` (strings; replace `\s|/` with `_`)
   and **check for collisions** — if cleaning maps two original labels onto one, abort with
   the offending pair (don't silently merge). If deconvolution proportions were given, stash
   them in `uns['_ccc_deconv']` (reindexed to `obs_names`, rows sum to 1) and set `_ccc_cell_type`
   to the argmax label; set `has_deconv=True`.
6. **Genes.** If `var_names` look like Ensembl (`ENSG`/`ENSMUSG`), map to symbols with
   `mygene` (`scopes='ensembl.gene'`, strip version suffixes), **sum** counts for duplicate
   mapped symbols, drop unmapped. Assert `var_names.is_unique` (do NOT `make_unique()` —
   suffixed names stop matching the LR resource).
7. **QC + layers.** `filter_genes(min_cells=3)`, `filter_cells(min_genes=10)`. Set
   `small_panel = n_genes < 1000` (targeted panels: warn, don't fail). Reset `.X` from
   `counts`, then build `layers['norm_no_log']` (normalize_total only) and `.X`
   (normalize_total + log1p). Set `obs['imagecol']/['imagerow']` from `obsm['spatial']`.
8. **Shared LR resource.** From `li.rs.select_resource('consensus'|'mouseconsensus')`, build
   the monomeric common core (no `_`, both genes on panel) → `ccc_lr_common.csv`.
9. Write `ccc_base.h5ad` and `logs/ccc_data_prep.json`.

## Code template

```python
import json, os
from importlib.metadata import version
import numpy as np, pandas as pd, scanpy as sc, liana as li
from sklearn.neighbors import NearestNeighbors

ADATA_IN   = "uploads/spatial.h5ad"   # adjust
CELL_TYPE  = "cell_type"              # adjust ('_ccc_cell_type' will be derived)
SPECIES    = "human"                  # or "mouse" — explicit
PLATFORM   = "visium"                 # visium | visium_hd | xenium | merfish | seqfish | slide_seq | st
COORD_UNIT = "pixel"                  # um (imaging) | pixel (raw Visium) | normalized
SAMPLE_COL = None                     # e.g. 'library_id' if multiple sections share coords

SINGLE_CELL = {"xenium", "merfish", "seqfish"}
SPOT_UM     = {"visium": 55.0, "visium_hd": 2.0}

# 1. preflight
for p in ["liana", "stlearn", "commot", "scanpy", "anndata"]:
    try: print(p, version(p))
    except Exception: pass

adata = sc.read_h5ad(ADATA_IN)

# 2. counts (integer-LIKE, not integer dtype)
def looks_like_counts(X):
    v = X.data if hasattr(X, "data") else np.asarray(X).ravel()
    v = v[:100000]
    return np.isfinite(v).all() and (v >= 0).all() and np.allclose(v, np.round(v))
if "counts" not in adata.layers:
    if looks_like_counts(adata.X):
        adata.layers["counts"] = adata.X.copy()
    else:
        raise ValueError("No raw counts found (layers['counts'] absent, .X not count-like)")

# 3. spatial + refuse pre-normalized coords
if "spatial" not in adata.obsm:
    adata.obsm["spatial"] = adata.obs[["x", "y"]].to_numpy(float)
coords = np.asarray(adata.obsm["spatial"], float)
assert coords.shape == (adata.n_obs, 2) and np.isfinite(coords).all()
if (np.abs(coords.mean(0)) < 1).all() and np.abs(coords).max() < 10:
    raise ValueError("Coordinates look standardized (|mean|<1, max<10) — re-pull raw coords.")

resolution_mode = "single_cell" if PLATFORM in SINGLE_CELL else "spot_multicell"

# 4. calibrate in NATIVE units; µm only for reporting
rng = np.random.default_rng(1337)
samp = coords[rng.choice(coords.shape[0], min(2000, coords.shape[0]), replace=False)]
d, _ = NearestNeighbors(n_neighbors=2).fit(coords).kneighbors(samp)
median_nn = float(np.median(d[:, 1]))               # <-- methods use THIS

median_nn_um, spot_um = None, SPOT_UM.get(PLATFORM)
if COORD_UNIT == "um":
    median_nn_um = median_nn
elif COORD_UNIT == "pixel":
    lib = next(iter(adata.uns.get("spatial", {}).values()), {})
    dia_px = lib.get("scalefactors", {}).get("spot_diameter_fullres")
    if dia_px and spot_um:
        median_nn_um = median_nn * spot_um / float(dia_px)
        if PLATFORM == "visium" and not (70 < median_nn_um < 160):
            median_nn_um = None            # conversion suspect — report native only

# 5. cell types (+ collision check, + optional deconvolution)
lab = (adata.obs[CELL_TYPE].astype(str)
       .str.replace(r"[\s/|]+", "_", regex=True))
collisions = (adata.obs[CELL_TYPE].astype(str).groupby(lab).nunique())
assert (collisions <= 1).all(), f"label cleaning merges categories: {collisions[collisions>1]}"
adata.obs["_ccc_cell_type"] = lab.astype("category")
assert adata.obs["_ccc_cell_type"].nunique() >= 2
assert adata.obs["_ccc_cell_type"].value_counts().min() >= 10, "need >=10 cells/type"
has_deconv = "_ccc_deconv" in adata.uns   # set upstream if proportions were provided

# 6. genes — assume symbols here; map Ensembl first if needed (see workflow step 6)
assert adata.var_names.is_unique, "collapse duplicate symbols before CCC (no make_unique)"

# 7. QC + layers (reset .X from counts so we never double-normalize)
sc.pp.filter_genes(adata, min_cells=3)
sc.pp.filter_cells(adata, min_genes=10)
small_panel = adata.n_vars < 1000
adata.X = adata.layers["counts"].copy()
adata.layers["norm_no_log"] = sc.pp.normalize_total(adata, target_sum=1e4, inplace=False)["X"]
sc.pp.normalize_total(adata, target_sum=1e4); sc.pp.log1p(adata)
adata.obs["imagecol"] = adata.obsm["spatial"][:, 0]   # stLearn expects these
adata.obs["imagerow"] = adata.obsm["spatial"][:, 1]

# 8. shared LR resource
res = li.rs.select_resource("consensus" if SPECIES == "human" else "mouseconsensus")
res = res[["ligand", "receptor"]].astype(str).drop_duplicates()
genes = set(adata.var_names.astype(str))
mono = res[~res.ligand.str.contains("_") & ~res.receptor.str.contains("_")
           & res.ligand.isin(genes) & res.receptor.isin(genes)].reset_index(drop=True)
assert len(mono) >= 20, "very few measurable LR pairs — check species / symbols / panel"
mono.to_csv("ccc_lr_common.csv", index=False)

# 9. write
os.makedirs("logs", exist_ok=True)
adata.write("ccc_base.h5ad")
json.dump({
    "species": SPECIES, "platform": PLATFORM, "resolution_mode": resolution_mode,
    "coord_unit": COORD_UNIT, "median_nn": median_nn, "median_nn_um": median_nn_um,
    "spot_diameter_um": spot_um, "cell_type_col": "_ccc_cell_type",
    "has_deconv": bool(has_deconv), "sample_col": SAMPLE_COL,
    "n_samples": int(adata.obs[SAMPLE_COL].nunique()) if SAMPLE_COL else 1,
    "n_cells": int(adata.n_obs), "n_genes": int(adata.n_vars),
    "n_categories": int(adata.obs["_ccc_cell_type"].nunique()),
    "min_cells_per_category": int(adata.obs["_ccc_cell_type"].value_counts().min()),
    "small_panel": bool(small_panel),
    "n_lr_common": int(len(mono)),
    "stlearn_species": SPECIES,
}, open("logs/ccc_data_prep.json", "w"), indent=2)
print(f"ccc_base.h5ad {adata.shape}; median_nn={median_nn:.1f} (µm={median_nn_um}); "
      f"LR common={len(mono)}")
```

## Multi-sample data

If `sample_col` is set, sections may share a coordinate frame. Every downstream method
**runs per section** and concatenates results tagged with the sample — never build a
spatial graph across sections (it invents cross-section neighbours). Do not pool
biological replicates before inference; compare CCC at the sample level.

## Common issues

- **µm labels on pixel coords (the classic bug).** Don't label a threshold "µm" then apply
  it to pixel coordinates. This skill keeps `median_nn` in the stored units and derives all
  radii from it — correct regardless of pixel/µm. `median_nn_um` is reporting-only.
- **Double normalization.** `.X` may already be log-normalized on input. We reset `.X` from
  `layers['counts']` before normalizing, so `norm_no_log` and `.X` are both derived from raw.
- **Ensembl IDs → ~0 LR pairs.** All three LR resources use symbols; map Ensembl first, sum
  duplicates, never `make_unique()`.
- **Standardized atlas coords.** seqFISH/MERFISH atlas h5ads ship mean-centered coords —
  unusable for radius calibration; refuse and re-pull raw.
- **Mouse + stLearn.** connectomeDB2020 is human-derived. LIANA uses `mouseconsensus` and
  COMMOT has native mouse CellChatDB, but stLearn's mouse LR set is casing-converted, not a
  real orthology map. Either map the shared resource to mouse and record it, or drop stLearn
  and run a 2-method consensus (recorded in the log). The shared `mouseconsensus` resource is
  safer than stLearn's auto-conversion.

## References

- LIANA+ resources: `li.rs.select_resource`, `li.rs.show_resources()`.
- Related skills: [[ccc-liana]], [[ccc-commot]], [[ccc-stlearn]], [[ccc-aggregate]];
  parent plan `ccc_ensemble`.
