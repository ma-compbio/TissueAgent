---
title: "Building spatial neighbors graph"
keywords:
  - "squidpy"
  - "spatial neighbors"
  - "spatial graph"
  - "connectivity"
  - "coord_type"
  - "delaunay"
  - "n_rings"
  - "n_neighs"
  - "radius"
---

# Building spatial neighbors graph

This example shows how to compute spatial neighbors graphs for different spatial dataset types using `squidpy.gr.spatial_neighbors`.

```python
import numpy as np

import squidpy as sq
```

## Visium grid datasets

Load a Visium dataset and compute neighbors with `coord_type='grid'`. The `n_rings` parameter specifies how many hexagonal rings around each spot are considered neighbors.

```python
adata = sq.datasets.visium_fluo_adata()
adata
```

```python
sq.gr.spatial_neighbors(adata, n_rings=2, coord_type="grid", n_neighs=6)
```

Results are saved in `adata.obsp['spatial_connectivities']` and `adata.obsp['spatial_distances']`.

```python
adata.obsp["spatial_connectivities"]
```

```python
adata.obsp["spatial_distances"]
```

Visualize the neighbors of a specific point.

```python
_, idx = adata.obsp["spatial_connectivities"][420, :].nonzero()
idx = np.append(idx, 420)
sq.pl.spatial_scatter(
    adata[idx, :],
    connectivity_key="spatial_connectivities",
    img=False,
    na_color="lightgrey",
)
```

## Non-grid datasets

Use `coord_type='generic'` with `n_neighs` for fixed number of nearest neighbors, or `delaunay=True` for Delaunay triangulation.

```python
adata = sq.datasets.imc()
adata
```

Fixed number of nearest neighbors.

```python
sq.gr.spatial_neighbors(adata, n_neighs=10, coord_type="generic")
_, idx = adata.obsp["spatial_connectivities"][420, :].nonzero()
idx = np.append(idx, 420)
sq.pl.spatial_scatter(
    adata[idx, :],
    shape=None,
    color="cell type",
    connectivity_key="spatial_connectivities",
    size=100,
)
```

Delaunay triangulation graph.

```python
sq.gr.spatial_neighbors(adata, delaunay=True, coord_type="generic")
_, idx = adata.obsp["spatial_connectivities"][420, :].nonzero()
idx = np.append(idx, 420)
sq.pl.spatial_scatter(
    adata[idx, :],
    shape=None,
    color="cell type",
    connectivity_key="spatial_connectivities",
    size=100,
)
```

Radius-based neighbors (units of spatial coordinates).

```python
sq.gr.spatial_neighbors(adata, radius=0.3, coord_type="generic")

adata.obsp["spatial_connectivities"]
adata.obsp["spatial_distances"]
```
