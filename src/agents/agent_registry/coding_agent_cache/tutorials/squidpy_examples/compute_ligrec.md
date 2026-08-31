---
title: "Receptor-ligand analysis"
keywords:
  - "squidpy"
  - "receptor-ligand"
  - "ligrec"
  - "cellphonedb"
  - "permutation test"
  - "omnipath"
  - "cell communication"
  - "interaction"
---

# Receptor-ligand analysis

This example shows how to run receptor-ligand analysis using `squidpy.gr.ligrec`, an efficient re-implementation of the CellPhoneDB algorithm.

```python
import squidpy as sq

adata = sq.datasets.seqfish()
adata
```

Key parameters for `squidpy.gr.ligrec`:
- `n_perms` - number of permutations for the permutation test
- `interactions` - list of interactions (default: all from omnipath)
- `transmitter_params` / `receiver_params` - filter by categories
- `threshold` - percentage of cells required to be expressed in a cluster
- `corr_method` - FDR correction method

Run the analysis with ligand/receptor categories.

```python
res = sq.gr.ligrec(
    adata,
    n_perms=1000,
    cluster_key="celltype_mapped_refined",
    copy=True,
    use_raw=False,
    transmitter_params={"categories": "ligand"},
    receiver_params={"categories": "receptor"},
)
```

Inspect the calculated means (rows = interacting pairs, columns = cluster combinations).

```python
res["means"].head()
```

Inspect the p-values (NaN indicates interactions that did not pass the filtering threshold).

```python
res["pvalues"].head()
```

Access interaction metadata from omnipath.

```python
res["metadata"].head()
```

Plot results. Key plot parameters: `source_groups`/`target_groups`, `dendrogram`, `mean_range`, `pval_threshold`.

```python
sq.pl.ligrec(res, source_groups="Erythroid", alpha=0.005)
```
