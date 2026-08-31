---
title: "Compute centrality scores"
keywords:
  - "squidpy"
  - "centrality scores"
  - "spatial graph"
  - "closeness centrality"
  - "degree centrality"
  - "clustering coefficient"
  - "spatial neighbors"
  - "cell type annotation"
---

# Compute centrality scores

This example shows how to compute centrality scores (closeness centrality, degree centrality, clustering coefficient) given a spatial graph and cell type annotation.

```python
import squidpy as sq

adata = sq.datasets.imc()
adata
```

Compute a connectivity matrix from spatial coordinates.

```python
sq.gr.spatial_neighbors(adata)
```

Compute centrality scores per cell type.

```python
sq.gr.centrality_scores(adata, "cell type")
```

Visualize the results.

```python
sq.pl.centrality_scores(adata, "cell type")
```
