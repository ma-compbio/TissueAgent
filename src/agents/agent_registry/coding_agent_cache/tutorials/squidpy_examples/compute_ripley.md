---
title: "Compute Ripley's statistics"
keywords:
  - "squidpy"
  - "ripley"
  - "spatial statistics"
  - "point patterns"
  - "clustering"
  - "dispersion"
  - "ripley's l"
  - "ripley's k"
---

# Compute Ripley's statistics

This example shows how to compute Ripley's L function, a variance-normalized version of Ripley's K statistic for determining clustered, dispersed, or random point patterns. Modes `'F'` and `'G'` are also available.

```python
import squidpy as sq

adata = sq.datasets.slideseqv2()
adata
```

Compute Ripley's L function and visualize results.

```python
mode = "L"
sq.gr.ripley(adata, cluster_key="cluster", mode=mode)
sq.pl.ripley(adata, cluster_key="cluster", mode=mode)
```

Visualize tissue organization in spatial coordinates.

```python
sq.pl.spatial_scatter(adata, color="cluster", size=20, shape=None)
```
