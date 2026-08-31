---
title: "Compute Moran's I score"
keywords:
  - "squidpy"
  - "moran's i"
  - "spatial autocorrelation"
  - "spatial_autocorr"
  - "spatial neighbors"
  - "spatially variable genes"
  - "geary's c"
---

# Compute Moran's I score

This example shows how to compute Moran's I global spatial auto-correlation statistics to evaluate whether genes show clustered, dispersed, or random patterns.

```python
import squidpy as sq

adata = sq.datasets.visium_hne_adata()
adata
```

Compute spatial neighbors, then compute Moran's I with `mode='moran'`. You can also use `mode='geary'` for Geary's C.

```python
genes = adata[:, adata.var.highly_variable].var_names.values[:100]
sq.gr.spatial_neighbors(adata)
sq.gr.spatial_autocorr(
    adata,
    mode="moran",
    genes=genes,
    n_perms=100,
    n_jobs=1,
)
adata.uns["moranI"].head(10)
```

Visualize top spatially variable genes.

```python
sq.pl.spatial_scatter(adata, color=["Resp18", "Tuba4a"])
```
