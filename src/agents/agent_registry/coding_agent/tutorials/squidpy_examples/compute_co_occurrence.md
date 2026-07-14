---
title: "Compute co-occurrence probability"
keywords:
  - "squidpy"
  - "co-occurrence"
  - "spatial patterns"
  - "cluster proximity"
  - "spatial statistics"
  - "cell type"
  - "conditional probability"
---

# Compute co-occurrence probability

This example shows how to compute the co-occurrence score across increasing radii around each cell.

```python
import squidpy as sq

adata = sq.datasets.imc()
adata
```

Compute co-occurrence and visualize results.

```python
sq.gr.co_occurrence(adata, cluster_key="cell type")
sq.pl.co_occurrence(adata, cluster_key="cell type", clusters="basal CK tumor cell")
```

Visualize tissue organization in spatial coordinates.

```python
sq.pl.spatial_scatter(adata, color="cell type", size=10, shape=None)
```
