---
name: ccc-liana
description: Run LIANA+ on the shared CCC resource — rank_aggregate for a directed cell-type ligand-receptor consensus, and (on spatial input) bivariate for LR-level spatial co-expression hotspots at two bandwidths. Emits one standardized long CSV for the ensemble aggregator plus its operable LR universe.
applies_to: [coding_agent]
tags: [ccc, liana, ligand-receptor]
status: enable
---

# CCC — LIANA+

## When to use

Step 2 of the `ccc_ensemble` plan, after [[ccc-data-prep]]. LIANA contributes two
things, from two **modes of one engine**:

- **`rank_aggregate`** — a directed cell-type consensus (`source`→`target`) built by
  aggregating CellPhoneDB/NATMI/Connectome/CellChat/LogFC/SingleCellSignalR/geometric-mean
  ranks. **Non-spatial** (treats spots/cells as dissociated) — a cluster co-expression
  check, not spatial communication.
- **`bivariate`** — local spatial LR co-expression; its global Moran's statistic is an
  **LR-level spatial hotspot** score. It has **no cell-type direction** — it corroborates a
  ligand-receptor pair spatially but never produces `source`/`target`.

Both modes run on the **shared resource** from [[ccc-data-prep]] (`ccc_lr_common.csv`), not
LIANA's native default, so all three ensemble methods test the same pairs.

`liana` is pre-installed in the coding-agent image.

## Input

- `ccc_base.h5ad` (immutable) — copy it; `.X` is log1p-normalized. Never overwrite it.
- `ccc_lr_common.csv` — shared monomeric resource (`ligand,receptor`).
- `logs/ccc_data_prep.json` — read `species`, `resolution_mode`, `median_nn` (native units),
  `small_panel`, `sample_col`.

## Output

- `liana_ccc.csv` — standardized long table for [[ccc-aggregate]]. One block from
  `rank_aggregate` (level `celltype_pair`, regime `coexpr`) and, on spatial input, one block
  each from `bivariate` at the contact and diffusion bandwidths (level `lr`). Schema:
  `engine, mode, regime, level, spatial, ligand, receptor, source, target, score,
  higher_better, pvalue, contrib_dist`.
- `liana_universe.csv` — operable pairs (`ligand,receptor`): shared-resource pairs whose
  both genes clear `expr_prop`. Drives `n_capable`/coverage in the aggregator.
- `liana_res.csv` — the raw `adata.uns['liana_res']` (full columns) for inspection/plots.
- `logs/ccc_liana.json` — `{species, expr_prop, use_raw, bandwidths, n_rank, n_biv}`.

`adata.uns['liana_res']` key columns: `source`, `target`, `ligand_complex`,
`receptor_complex`, `lr_means` (magnitude), `magnitude_rank` (lower=stronger),
`specificity_rank` (lower=more cell-type-specific), plus per-method score columns. The
aggregator ranks on `specificity_rank`. Treat ranks as prioritization scores, **not**
calibrated p-values (RRA scores are not CellPhoneDB permutation p-values).

## Success criteria

- `adata.uns['liana_res']` is a non-empty DataFrame; `magnitude_rank`/`specificity_rank`
  in `[0,1]`; `source`/`target` ⊆ `_ccc_cell_type` categories.
- On spatial input, both bivariate bandwidths produced rows and a valid
  `obsp['spatial_connectivities']` graph exists.
- `liana_ccc.csv` has the schema above; `liana_universe.csv` non-empty.

## Workflow

1. Load `ccc_base.h5ad` (copy) and `ccc_lr_common.csv`; read the prep log.
2. `expr_prop = 0.05 if small_panel else 0.10` (imaging panels drop the whole resource at 0.1).
3. **`rank_aggregate`** with `use_raw=False` (critical — LIANA defaults `use_raw=True` and will
   silently use a stale `.raw` if present), `resource=<shared>`, `groupby='_ccc_cell_type'`.
4. **`bivariate`** (spatial input only) at **two bandwidths**, multiples of `median_nn` in
   the coordinate units (native — never a hardcoded µm/pixel number):
   - contact bandwidth ≈ `1.5 × median_nn`, `max_neighbours = 6` (spots) / `20` (cells).
   - diffusion bandwidth ≈ `3 × median_nn`.
   For each: build the graph with `li.ut.spatial_neighbors(...)`, then call
   `li.mt.bivariate(..., use_raw=False)`, which **returns a new AnnData** — local scores in
   `.X`, per-obs p-values in `.layers['pvals']`, and per-LR global stats
   (`morans`, `morans_pvals`) in `.var`. Emit the `.var` block as LR-level rows.
   *(bandwidth is a Gaussian kernel, not a hard radius; with `cutoff=0.1` weights reach
   ~2.15× the bandwidth — treat the two bandwidths as short vs paracrine, not exact cutoffs.)*
5. If `sample_col` is set, run steps 3–4 **per sample** and concatenate (don't build graphs
   across sections).
6. Write the three CSVs and the log.

## Code template

```python
import json
import numpy as np, pandas as pd, scanpy as sc, liana as li

prep = json.load(open("logs/ccc_data_prep.json"))
species, res_mode = prep["species"], prep["resolution_mode"]
median_nn, small_panel = prep["median_nn"], prep.get("small_panel", False)

adata = sc.read_h5ad("ccc_base.h5ad")              # copy of the immutable base
resource = pd.read_csv("ccc_lr_common.csv")[["ligand", "receptor"]]
expr_prop = 0.05 if small_panel else 0.10

# 3. rank_aggregate — directed cell-type consensus (NON-spatial). use_raw=False!
li.mt.rank_aggregate(adata, groupby="_ccc_cell_type", resource=resource,
                     use_raw=False, expr_prop=expr_prop, min_cells=10,
                     n_perms=1000, seed=1337, verbose=True)
lr = adata.uns["liana_res"]
lr.to_csv("liana_res.csv", index=False)

rows = [dict(engine="liana", mode="rank_aggregate", regime="coexpr",
             level="celltype_pair", spatial=False,
             ligand=r.ligand_complex, receptor=r.receptor_complex,
             source=r.source, target=r.target,
             score=r.specificity_rank, higher_better=False,
             pvalue=r.specificity_rank, contrib_dist=np.nan)
        for r in lr.itertuples()]

# 4. bivariate — LR-level spatial hotspots at two bandwidths (spatial input only)
bandwidths, n_biv = {}, {}
if res_mode in ("spot_multicell", "single_cell") and median_nn:
    K = 6 if res_mode == "spot_multicell" else 20
    bandwidths = {"contact": 1.5 * median_nn, "diffusion": 3.0 * median_nn}
    for regime, bw in bandwidths.items():
        li.ut.spatial_neighbors(adata, bandwidth=bw, cutoff=0.1,
                                max_neighbours=K, kernel="gaussian", set_diag=False)
        biv = li.mt.bivariate(adata, resource=resource, local_name="cosine",
                              global_name="morans", n_perms=1000, nz_prop=expr_prop,
                              use_raw=False, verbose=True)   # returns a NEW AnnData
        v = biv.var.reset_index()                             # per-LR global stats
        n_biv[regime] = int(len(v))
        rows += [dict(engine="liana", mode="bivariate", regime=regime, level="lr",
                      spatial=True, ligand=r.ligand, receptor=r.receptor,
                      source=np.nan, target=np.nan,
                      score=r.morans, higher_better=True,
                      pvalue=r.morans_pvals, contrib_dist=np.nan)
                     for r in v.itertuples()]

pd.DataFrame(rows).to_csv("liana_ccc.csv", index=False)

# operable universe: shared pairs whose both genes clear expr_prop
X = adata.layers["counts"]
frac = np.asarray((X > 0).mean(axis=0)).ravel()
expressed = set(adata.var_names[frac >= expr_prop])
operable = resource[resource.ligand.isin(expressed) & resource.receptor.isin(expressed)]
operable.to_csv("liana_universe.csv", index=False)

json.dump({"species": species, "expr_prop": expr_prop, "use_raw": False,
           "bandwidths": bandwidths, "n_rank": int(len(lr)), "n_biv": n_biv},
          open("logs/ccc_liana.json", "w"), indent=2)
print(f"LIANA done — rank rows {len(lr)}, bivariate {n_biv}")
```

## Common issues

- **`.raw` used instead of `.X`.** LIANA defaults `use_raw=True`; pass `use_raw=False` in
  **both** `rank_aggregate` and `bivariate` or it silently ignores the prepared `.X`.
- **`bivariate` results not in `.uns`.** In LIANA ≥1.6 `bivariate` **returns** an AnnData —
  it does not write `adata.uns['local_scores']`, and `li.ut.summarise_bivariate` is not a
  stable API. Capture the return; read `.var` (global) / `.layers['pvals']` (local).
- **Bivariate is not directed.** It has no cell-type labels — don't fabricate `source`/
  `target` from neighbours. It supports the LR pair spatially; the aggregator uses it only
  as `lr_spatial_support`.
- **Empty result / dropped entities.** Usually `expr_prop` too high for a sparse imaging
  panel (auto-dropped to 0.05 via `small_panel`) or a species/resource mismatch.
- **Dominant-label spots.** `rank_aggregate` treats each spot as one cell type; on
  deconvolved Visium that's a dominant-label approximation, not per-cell — report it as such.
- **Determinism.** `seed=1337` default; pass explicitly for reproducibility.

## References

- LIANA+ tutorial (in-repo): `src/agents/agent_registry/coding_agent/tutorials/liana-examples/basic_usage.md`
- Bivariate tutorial: <https://liana-py.readthedocs.io/en/latest/notebooks/bivariate.html>
- The call signatures above are complete for this task — copy them verbatim; do not
  introspect. (`li.mt.rank_aggregate`/`li.mt.bivariate` are class instances, so
  `inspect.signature` on them raises `TypeError` anyway.)
- Related skills: [[ccc-data-prep]], [[ccc-commot]], [[ccc-stlearn]], [[ccc-aggregate]].
