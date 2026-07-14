---
title: "Compute Sepal score"
keywords:
  - "squidpy"
  - "sepal"
  - "spatially variable genes"
  - "diffusion"
  - "spatial autocorrelation"
  - "spatial neighbors"
  - "grid graph"
  - "visium"
---

# Compute Sepal score

This example shows how to compute the Sepal score for spatially variable genes identification using a diffusion process.

Important considerations:
- Only accepts grid-like spatial graphs. Set `max_neighs=6` for hexagonal grids (Visium).
- Filter out genes expressed in very few observations to avoid false positives.

```python
import squidpy as sq

adata = sq.datasets.visium_hne_adata()
adata
```

Compute spatial neighbors, filter genes, then compute the Sepal score.

```python
sq.gr.spatial_neighbors(adata)
genes = adata.var_names[(adata.var.n_cells > 100) & adata.var.highly_variable][0:100]
sq.gr.sepal(adata, max_neighs=6, genes=genes, n_jobs=1)
adata.uns["sepal_score"].head(10)
```

Visualize top spatially variable genes.

```python
sq.pl.spatial_scatter(adata, color=["Lct", "Ecel1", "Cfap65"])
```
