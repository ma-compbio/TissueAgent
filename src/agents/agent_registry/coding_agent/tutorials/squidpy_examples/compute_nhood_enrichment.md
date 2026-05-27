---
title: "Neighbors enrichment analysis"
keywords:
  - "squidpy"
  - "neighborhood enrichment"
  - "nhood_enrichment"
  - "spatial neighbors"
  - "z-score"
  - "permutation test"
  - "cluster proximity"
---

# Neighbors enrichment analysis

This example shows how to compute neighborhood enrichment scores based on proximity in the connectivity graph.

```python
import squidpy as sq

adata = sq.datasets.visium_fluo_adata()
adata
```

Compute a connectivity matrix from spatial coordinates.

```python
sq.gr.spatial_neighbors(adata)
```

Calculate the neighborhood enrichment score.

```python
sq.gr.nhood_enrichment(adata, cluster_key="cluster")
```

Visualize the results.

```python
sq.pl.nhood_enrichment(adata, cluster_key="cluster")
```
