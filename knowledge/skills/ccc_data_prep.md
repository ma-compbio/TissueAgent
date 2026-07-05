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
- **Gene-symbol convention** — gene names must be **symbols** (HGNC for human, MGI for mouse). If `.var_names` look like Ensembl IDs (start with `ENSG`/`ENSMUSG`), the skill maps them via the same `mygene` workflow used in [[cell-type-annotation]].

## Output

Written to the active project's `outputs/` folder:

- `ccc_prepped.h5ad` — single AnnData with:
  - `.X` = log1p-normalized to 1e4 (LIANA+/COMMOT-ready)
  - `.layers['counts']` = raw integer counts (preserved)
  - `.layers['norm_no_log']` = `normalize_total` only, **no log1p** (stLearn-ready)
  - `.obs['_ccc_cell_type']` = a clean copy of the user's cell-type column with `str` dtype + categorical conversion + invalid-character scrub
  - `.obsm['spatial']` = float array, shape `(n_obs, 2)`
- `logs/ccc_data_prep.json` — `{species, cell_type_col, n_cells, n_genes, n_categories, min_cells_per_category, spatial_coord_range, gene_symbol_convention, mapped_n_genes}`.

## Success Criteria

- `ccc_prepped.h5ad` loads and contains the three layers above.
- `_ccc_cell_type` has ≥2 categories AND `min_cells_per_category ≥ 10`.
- `adata.obsm['spatial'].shape == (n_obs, 2)` and contains no NaNs.
- ≥1000 genes survive QC (otherwise LR overlap will be too small downstream — flag this and stop).

## Workflow

1. Load the h5ad, find raw counts (prefer `layers['counts']`, else `.X` if `.X.dtype` is integer, else error).
2. Validate spatial coords: if `obsm['spatial']` absent and `obs[['x','y']]` present, build `obsm['spatial'] = obs[['x','y']].to_numpy(float)`. Assert no NaN, no all-zero rows.
3. Validate `cell_type_col`: assert column exists, `nunique() >= 2`, `value_counts().min() >= 10`. Copy to `obs['_ccc_cell_type']` with strings (no leading digits, no `|` or `/`, replace whitespace with `_`).
4. Gene-symbol check: peek at `var_names[:10]`. If they match `ENSG\d+` (or `ENSMUSG\d+` for mouse), map to symbols via `mygene.MyGeneInfo().querymany(..., species=species, scopes='ensembl.gene', fields='symbol')`. Drop unmapped.
5. Basic QC: `sc.pp.filter_genes(adata, min_cells=3)`, `sc.pp.filter_cells(adata, min_genes=10)`. If `<1000` genes remain, raise (the ensemble would be uninformative).
6. Cache raw counts to `adata.layers['counts']`.
7. Build the two normalized variants: `normalize_total → layers['norm_no_log']`, then `normalize_total + log1p → .X`.
8. Write `ccc_prepped.h5ad` and the JSON log.

## Code Template

```python
import json
import numpy as np
import scanpy as sc

ADATA_IN   = "uploads/spatial.h5ad"   # adjust
CELL_TYPE  = "cell_type"              # adjust
SPECIES    = "human"                  # or "mouse"

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

# 3. cell type
assert CELL_TYPE in adata.obs and adata.obs[CELL_TYPE].nunique() >= 2
adata.obs["_ccc_cell_type"] = (
    adata.obs[CELL_TYPE].astype(str)
    .str.replace(r"[\s|/]+", "_", regex=True)
    .astype("category")
)
assert adata.obs["_ccc_cell_type"].value_counts().min() >= 10, \
    "Need >=10 cells per cell type for permutation tests"

# 4. (omit gene-symbol mapping if names already look like symbols)

# 5. QC
sc.pp.filter_genes(adata, min_cells=3)
sc.pp.filter_cells(adata, min_genes=10)
assert adata.n_vars >= 1000, "Too few genes survive QC; CCC ensemble unlikely to be informative"

# 6 + 7. counts + two normalization variants
adata.layers["counts"] = adata.layers.get("counts", adata.X.copy())
norm_only = sc.pp.normalize_total(adata, target_sum=1e4, inplace=False)["X"]
adata.layers["norm_no_log"] = norm_only
sc.pp.normalize_total(adata, target_sum=1e4)
sc.pp.log1p(adata)

import os; os.makedirs("logs", exist_ok=True)
adata.write("ccc_prepped.h5ad")
json.dump({"species": SPECIES, "cell_type_col": "_ccc_cell_type",
           "n_cells": int(adata.n_obs), "n_genes": int(adata.n_vars),
           "n_categories": int(adata.obs["_ccc_cell_type"].nunique()),
           "min_cells_per_category": int(adata.obs["_ccc_cell_type"].value_counts().min())},
          open("logs/ccc_data_prep.json", "w"), indent=2)
print("ccc_prepped.h5ad ready:", adata.shape)
```

## Common Issues

- **`.X` already log-normalized → stLearn output is garbage.** stLearn explicitly wants `normalize_total` without log1p; this skill saves the right variant in `layers['norm_no_log']`. The stLearn skill swaps `.X = layers['norm_no_log']` before running.
- **Ensembl gene IDs not symbols → all three methods drop ~100% of LR pairs.** LIANA+/COMMOT/stLearn LR resources all use symbols. Map first.
- **Mouse data with `resource_name='consensus'` (human) → empty results.** Pass `species='mouse'` and use the matching resource downstream.
- **One-cell-type "spatial domain" labels.** Permutation tests require multiple categories with reasonable cell counts. <10 cells/category produces unstable permutation p-values; the skill aborts.
- **Non-integer counts in `.X`.** Some platforms (Xenium, MERFISH after probe normalization) ship floats. Check the source pipeline — if counts are truly probabilistic, save `np.round(...).astype(int)` to `layers['counts']` only after confirming with the user.

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
