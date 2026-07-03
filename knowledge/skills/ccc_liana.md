---
name: ccc-liana
description: Run LIANA+'s multi-method consensus ligand-receptor inference (rank_aggregate over CellPhoneDB, NATMI, Connectome, CellChat, LogFC, SingleCellSignalR, geometric mean) on a preprocessed AnnData, producing a per-(LR, source, target) ranked table in adata.uns['liana_res']. Designed to slot into the ccc_ensemble plan.
applies_to: [coding]
tags: [ccc, liana, ligand-receptor]
status: enable
---

# CCC — LIANA+ rank_aggregate

## When to use

Step 2 of the `ccc_ensemble` plan. Also usable standalone when the user wants the per-(LR, sender, receiver) consensus that LIANA+ provides — but if the request is "ligand-receptor analysis" without ensemble framing, prefer the simpler `lr_analysis` plan, which is a thinner wrapper.

The `liana` package is pre-installed in the coding-agent Docker image (`docker/Dockerfile`), no install step required.

## Input

- AnnData from [[ccc-data-prep]] (`ccc_prepped.h5ad`) — `.X` = log1p-normalized counts, `.obs['_ccc_cell_type']` populated.
- Species (`"human"` or `"mouse"`) — determines `resource_name`.

## Output

Mutates the in-memory AnnData. Writes back to disk:

- `ccc_prepped.h5ad` (overwrites; `adata.uns['liana_res']` added)
- `liana_res.csv` — flat CSV of `adata.uns['liana_res']` for the aggregation step.

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

## Workflow

1. Load `ccc_prepped.h5ad`.
2. Pick `resource_name`: `'consensus'` for human, `'mouseconsensus'` for mouse.
3. Run `li.mt.rank_aggregate(adata, groupby='_ccc_cell_type', resource_name=<resource>, expr_prop=0.1, verbose=True)`.
4. `adata.uns['liana_res'].to_csv('liana_res.csv', index=False)`.
5. Re-write `ccc_prepped.h5ad` so the next skill sees the updated `uns`.

## Code Template

```python
import scanpy as sc
import liana as li

adata = sc.read_h5ad("ccc_prepped.h5ad")
species = "human"   # read from logs/ccc_data_prep.json in practice
resource = "consensus" if species == "human" else "mouseconsensus"

li.mt.rank_aggregate(
    adata,
    groupby="_ccc_cell_type",
    resource_name=resource,
    expr_prop=0.1,        # min fraction of cells expressing each partner
    verbose=True,
)

lr = adata.uns["liana_res"]
print("LIANA+ produced", len(lr), "interaction rows")
lr.to_csv("liana_res.csv", index=False)
adata.write("ccc_prepped.h5ad")
```

## Common Issues

- **Empty result / many missing entities.** Usually caused by `expr_prop` too high for sparse spatial data — try 0.05. Otherwise a species mismatch (mouse data + human resource); confirm `resource_name`.
- **`groupby` column is `object` not category.** `rank_aggregate` is fine either way, but downstream `li.pl.dotplot` expects categorical. The data-prep skill already enforces categorical.
- **MuData input.** `rank_aggregate` accepts `MuData`; pass `mdata_kwargs` to select modalities. Not needed for the ensemble (we use AnnData).
- **Determinism.** `seed=1337` is the default; pass explicitly if you need reproducibility across re-runs.
- **`magnitude_rank` vs `specificity_rank`.** Don't conflate them. Magnitude = how strongly the LR pair is expressed; specificity = how restricted the signal is to a particular (sender, receiver). The ensemble aggregation uses specificity.

## References

- LIANA+ tutorial (in-repo): `src/agents/agent_registry/coding_agent/tutorials/liana-examples/basic_usage.md`
- LIANA+ API docs (indexed): `search_documentation(name='rank_aggregate', library='liana')`.
- LIANA+ method list: <https://liana-py.readthedocs.io/en/latest/api/liana.mt.html>
- RRA paper (Stuart's method, used inside `rank_aggregate`): Kolde et al., *Bioinformatics* 2012.
- Related skills: [[ccc-data-prep]], [[ccc-commot]], [[ccc-stlearn]].
