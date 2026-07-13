---
name: ccc-liana
description: Run LIANA+'s multi-method consensus ligand-receptor inference (rank_aggregate over CellPhoneDB, NATMI, Connectome, CellChat, LogFC, SingleCellSignalR, geometric mean) on a preprocessed AnnData, producing a per-(LR, source, target) ranked table in adata.uns['liana_res']. Designed to slot into the ccc_ensemble plan.
applies_to: [coding_agent]
tags: [ccc, liana, ligand-receptor]
status: enable
---

# CCC — LIANA+ rank_aggregate

## When to use

Step 2 of the `ccc_ensemble` plan. Also usable standalone when the user wants the per-(LR, sender, receiver) consensus that LIANA+ provides — but if the request is "ligand-receptor analysis" without ensemble framing, prefer the simpler `lr_analysis` plan, which is a thinner wrapper.

The `liana` package is pre-installed in the coding-agent Docker image (`docker/Dockerfile`), no install step required.

## Input

- AnnData from [[ccc-data-prep]] (`ccc_prepped.h5ad`) — `.X` = log1p-normalized counts, `.obs['_ccc_cell_type']` populated.
- `logs/ccc_data_prep.json` — READ `species`, `resolution_mode`, `median_nn_um`, `platform`, `small_panel`. Determines the `resource_name`, whether to run the spatial (`bivariate`) branch, and the `bandwidth` for `spatial_neighbors`.

## Output

Mutates the in-memory AnnData. Writes back to disk:

- `ccc_prepped.h5ad` (overwrites; `adata.uns['liana_res']` added; on spatial input also `adata.obsm['local_scores']` from `bivariate`).
- `liana_res.csv` — flat CSV of `adata.uns['liana_res']` (cluster-level, from `rank_aggregate`) for the aggregation step.
- `liana_bivariate.csv` — flat CSV of the spatial `bivariate` output (per-cell/per-spot local scores summarised to (LR, source, target)); **only produced when `resolution_mode` indicates spatial input**.
- `logs/ccc_liana.json` — `{species, resource_name, expr_prop, ran_bivariate, bandwidth_um, kernel, max_neighbours, n_interactions_rank_aggregate, n_interactions_bivariate}`.

`adata.uns['liana_res']` columns (from LIANA+ docs):

| Column | Meaning |
|---|---|
| `source` | Sender cell type |
| `target` | Receiver cell type |
| `ligand_complex` | Ligand gene(s); `_`-joined for heteromers |
| `receptor_complex` | Receptor gene(s); `_`-joined for heteromers |
| `lr_means` | Mean LR expression (magnitude) |
| `cellphone_pvals` | CellPhoneDB permutation p-value |
| `magnitude_rank` | RRA-aggregated rank across methods on magnitude scores — **lower is stronger** |
| `specificity_rank` | RRA-aggregated rank across methods on specificity scores — **lower is more specific** |
| + per-method score columns (`natmi.*`, `cellchat.*`, …) | |

The ensemble's aggregation step uses `specificity_rank` as this method's "p-value" — it is already a rank in `[0, 1]` with permutation semantics inherited from the methods that go into the RRA.

## Success Criteria

- `adata.uns['liana_res']` exists, is a DataFrame with ≥1 row.
- `specificity_rank` and `magnitude_rank` columns present, all values in `[0, 1]`.
- The set of unique `source`/`target` values is a subset of `adata.obs['_ccc_cell_type'].cat.categories`.
- On spatial input (`resolution_mode` populated), `liana_bivariate.csv` also exists with ≥1 row and a valid `spatial_neighbors` graph in `adata.obsp['spatial_connectivities']`.

## Workflow

1. Load `ccc_prepped.h5ad` and `logs/ccc_data_prep.json`.
2. Pick `resource_name`: `'consensus'` for human, `'mouseconsensus'` for mouse.
3. Pick `expr_prop`: `0.05` when `small_panel == True` (imaging panels of <1000 genes drop the entire LR consensus at 0.1); else `0.1`.
4. **`rank_aggregate` (cluster-level, both paths):**
   `li.mt.rank_aggregate(adata, groupby='_ccc_cell_type', resource_name=<resource>, expr_prop=<expr_prop>, verbose=True)` → `adata.uns['liana_res']`.
5. **`bivariate` (spatial branch, on `spot_multicell` OR `single_cell`):**
   - Build the spatial neighbour graph via `li.ut.spatial_neighbors(adata, bandwidth=<bandwidth_um>, kernel='gaussian', cutoff=0.1, max_neighbours=<K>)`. `bandwidth_um` comes from `median_nn_um`:
     - Visium / hex grid: bandwidth ≈ 2.5 × spot pitch (~150–200 µm) — matches LIANA+'s "first ring of neighbours" guidance.
     - Imaging (`single_cell`): bandwidth = `2 × median_nn_um` to hit the first neighbour ring; `max_neighbours=20` (imaging cells have more nearby cells than Visium's 6 hex-ring).
   - `li.mt.bivariate(adata, local_name='cosine', global_name='morans', resource_name=<resource>, nz_prop=0.05)` — Cosine is the docs' "best-on-average" recommendation.
   - Summarise per-(LR, source, target) triples: aggregate `local_scores` by cell-type identities of sender/receiver neighbours (see `local_categories` in the LIANA bivariate tutorial) → `liana_bivariate.csv`.
6. `adata.uns['liana_res'].to_csv('liana_res.csv', index=False)`.
7. Write `logs/ccc_liana.json` and re-write `ccc_prepped.h5ad`.

## Code Template

```python
import json, os
import scanpy as sc
import liana as li

with open("logs/ccc_data_prep.json") as f:
    prep = json.load(f)

species         = prep["species"]
resolution_mode = prep["resolution_mode"]
median_nn_um    = prep["median_nn_um"]
small_panel     = prep.get("small_panel", False)

adata = sc.read_h5ad("ccc_prepped.h5ad")

resource   = "consensus" if species == "human" else "mouseconsensus"
expr_prop  = 0.05 if small_panel else 0.10

# --- rank_aggregate (cluster-level; runs on both platform types) ---
li.mt.rank_aggregate(
    adata,
    groupby="_ccc_cell_type",
    resource_name=resource,
    expr_prop=expr_prop,
    verbose=True,
)
lr = adata.uns["liana_res"]
lr.to_csv("liana_res.csv", index=False)

# --- bivariate (spatial branch) ---
ran_bivariate = False
n_biv = 0
bandwidth_um = None
if resolution_mode in {"spot_multicell", "single_cell"} and median_nn_um is not None:
    if resolution_mode == "spot_multicell":
        # First-ring rule for a hex grid: ~2.5 × spot pitch
        bandwidth_um  = 2.5 * median_nn_um
        max_neighbours = 6
    else:
        bandwidth_um  = 2.0 * median_nn_um
        max_neighbours = 20

    li.ut.spatial_neighbors(
        adata,
        bandwidth=bandwidth_um,
        kernel="gaussian",
        cutoff=0.1,
        max_neighbours=max_neighbours,
    )
    li.mt.bivariate(
        adata,
        local_name="cosine",
        global_name="morans",
        resource_name=resource,
        nz_prop=0.05,
    )
    # summarise per-cell local scores to (LR, source, target) — see LIANA bivariate tutorial
    biv = li.ut.summarise_bivariate(adata, groupby="_ccc_cell_type") \
          if hasattr(li.ut, "summarise_bivariate") \
          else adata.uns["local_scores"].reset_index()   # fallback if summarise helper renamed
    biv.to_csv("liana_bivariate.csv", index=False)
    ran_bivariate = True
    n_biv = int(len(biv))

os.makedirs("logs", exist_ok=True)
json.dump({
    "species": species,
    "resource_name": resource,
    "expr_prop": expr_prop,
    "ran_bivariate": ran_bivariate,
    "bandwidth_um": bandwidth_um,
    "kernel": "gaussian" if ran_bivariate else None,
    "max_neighbours": (6 if resolution_mode == "spot_multicell" else 20) if ran_bivariate else None,
    "n_interactions_rank_aggregate": int(len(lr)),
    "n_interactions_bivariate": n_biv,
}, open("logs/ccc_liana.json", "w"), indent=2)

adata.write("ccc_prepped.h5ad")
print(f"LIANA+ done — rank_aggregate rows: {len(lr)}, bivariate: {ran_bivariate} ({n_biv} rows)")
```

## Common Issues

- **Empty result / many missing entities.** Usually caused by `expr_prop` too high for sparse spatial data — the workflow now flips to `0.05` automatically when `small_panel == True`. Otherwise a species mismatch (mouse data + human resource); confirm `resource_name`.
- **`rank_aggregate` on spatial data treats spots/cells as dissociated.** It ignores space entirely — good for a cluster-level orthogonal check, but not a spatial method. On spatial input always ALSO run the `bivariate` branch; the ensemble aggregation should use `bivariate` for spatial signal and `rank_aggregate` for cluster-level co-expression.
- **`bandwidth` in the wrong unit.** `li.ut.spatial_neighbors(bandwidth=200)` on Visium pixel-space and on µm-space are two different physical scales. This skill derives bandwidth from `median_nn_um`, which was in turn calibrated by `ccc-data-prep`. Do NOT hardcode `bandwidth=200` for imaging data.
- **`groupby` column is `object` not category.** `rank_aggregate` is fine either way, but downstream `li.pl.dotplot` expects categorical. The data-prep skill already enforces categorical.
- **MuData input.** `rank_aggregate` accepts `MuData`; pass `mdata_kwargs` to select modalities. Not needed for the ensemble (we use AnnData).
- **Determinism.** `seed=1337` is the default; pass explicitly if you need reproducibility across re-runs.
- **`magnitude_rank` vs `specificity_rank`.** Don't conflate them. Magnitude = how strongly the LR pair is expressed; specificity = how restricted the signal is to a particular (sender, receiver). The ensemble aggregation uses specificity.

## References

- LIANA+ tutorial (in-repo): `src/agents/agent_registry/coding_agent/tutorials/liana-examples/basic_usage.md`
- LIANA+ API docs (indexed): `search_documentation(name='rank_aggregate', library='liana')`.
- LIANA+ method list: <https://liana-py.readthedocs.io/en/latest/api/liana.mt.html>
- LIANA+ bivariate spatial tutorial: <https://liana-py.readthedocs.io/en/latest/notebooks/bivariate.html>
- LIANA+ `spatial_neighbors` API: <https://liana-py.readthedocs.io/en/latest/api/liana.utils.spatial_neighbors.html>
- RRA paper (Stuart's method, used inside `rank_aggregate`): Kolde et al., *Bioinformatics* 2012.
- Related skills: [[ccc-data-prep]], [[ccc-commot]], [[ccc-stlearn]].
