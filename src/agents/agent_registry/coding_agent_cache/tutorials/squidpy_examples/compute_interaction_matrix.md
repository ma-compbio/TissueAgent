---
title: "Compute interaction matrix"
keywords:
  - "squidpy"
  - "interaction matrix"
  - "spatial graph"
  - "spatial neighbors"
  - "cell type"
  - "edge counting"
  - "spatial statistics"
---

# Compute interaction matrix

This example shows how to compute the interaction matrix, which quantifies the number of edges shared between annotations in the spatial graph.

```python
import squidpy as sq

adata = sq.datasets.imc()
adata
```

Compute a connectivity matrix from spatial coordinates.

```python
sq.gr.spatial_neighbors(adata)
```

Compute the interaction matrix. Use `normalized=True` for a row-normalized matrix.

```python
sq.gr.interaction_matrix(adata, cluster_key="cell type")
sq.pl.interaction_matrix(adata, cluster_key="cell type")
```
