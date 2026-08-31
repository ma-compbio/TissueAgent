---
title: "Plot scatter plot in spatial coordinates"
keywords:
  - "squidpy"
  - "spatial-scatter"
  - "plotting"
  - "visium"
  - "visualization"
  - "multi-slide"
---
# Plot scatter plot in spatial coordinates

This example shows how to use `squidpy.pl.spatial_scatter` to plot

This plotting is useful when points and underlying image are available.


```python
import anndata as ad
import scanpy as sc
import squidpy as sq

adata = sq.datasets.visium_hne_adata()
```

We can take a quick look at the Visium dataset by plotting cluster label
and gene expression of choice.


```python
sq.pl.spatial_scatter(adata, color=["Sox8", "cluster"])
```

`squidpy.pl.spatial_scatter` closely resembles `scanpy.pl.spatial` but
`shape ``\` argument it\'s possible to plot polygons such as square
purposes.


```python
sq.pl.spatial_scatter(
    adata,
    color=["Sox8", "cluster"],
    crop_coord=[(1500, 1500, 3000, 3000)],
    scalebar_dx=3.0,
    scalebar_kwargs={"scale_loc": "bottom", "location": "lower right"},
)
```

A key feature of `squidpy.pl.spatial_scatter` is that it can handle
also build the spatial graph, to show the edge plotting functionality.


```python
sq.gr.spatial_neighbors(adata)
adata2 = sc.pp.subsample(adata, fraction=0.5, copy=True)
adata2.uns["spatial"] = {}
adata2.uns["spatial"]["V2_Adult_Mouse_Brain"] = adata.uns["spatial"][
    "V1_Adult_Mouse_Brain"
]
adata_concat = ad.concat(
    {"V1_Adult_Mouse_Brain": adata, "V2_Adult_Mouse_Brain": adata2},
    label="library_id",
    uns_merge="unique",
    pairwise=True,
)
sq.pl.spatial_scatter(
    adata_concat,
    color=["Sox8", "cluster"],
    library_key="library_id",
    connectivity_key="spatial_connectivities",
    edges_width=2,
    crop_coord=[(1500, 1500, 3000, 3000), (1500, 1500, 3000, 3000)],
)
```

In the above plots, the two Visium datasets are cropped and plotted
`outline_width`[, `size`\` etc.


```python
sq.pl.spatial_scatter(
    adata_concat,
    color=["Sox8", "cluster"],
    library_key="library_id",
    library_first=False,
    connectivity_key="spatial_connectivities",
    edges_width=2,
    crop_coord=[(1500, 1500, 3000, 3000), (1500, 1500, 3000, 3000)],
    outline=True,
    outline_width=[0.05, 0.05],
    size=[1, 0.5],
    title=[
        "sox8_first_library",
        "sox8_second_library",
        "cluster_first_library",
        "cluster_second_library",
    ],
)
```

If no image is present, a simple scatter plot will be plotted, but the
`shape=None ``[ in order to default to plain scatter plot.
Furthermore, in this setting the `size`[ argument
{func}\`squidpy.pl.spatial\_scatter for documentation.


```python
sq.pl.spatial_scatter(
    adata_concat,
    shape=None,
    color=["Sox8", "cluster"],
    library_key="library_id",
    library_first=False,
    connectivity_key="spatial_connectivities",
    edges_width=2,
    crop_coord=[(1500, 1500, 3000, 3000), (1500, 1500, 3000, 3000)],
    outline=True,
    outline_width=[0.05, 0.05],
    size=[1, 0.5],
    title=[
        "sox8_first_library",
        "sox8_second_library",
        "cluster_first_library",
        "cluster_second_library",
    ],
)
```
