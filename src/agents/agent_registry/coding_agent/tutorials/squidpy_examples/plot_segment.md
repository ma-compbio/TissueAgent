---
title: "Plot segmentation masks"
keywords:
  - "squidpy"
  - "segmentation"
  - "plotting"
  - "spatial-segment"
  - "mibitof"
  - "visualization"
---
# Plot segmentation masks

This example shows how to use `squidpy.pl.spatial_segment` to plot

This plotting is useful when segmentation masks and underlying image are


```python
import squidpy as sq

adata = sq.datasets.mibitof()
adata.uns["spatial"].keys()
```

In this dataset we have 3 unique keys, which means that there are 3
The information to link the library ids to the observations are stored
in `adata.obs`.


```python
adata.obs
```

Specifically, the key `library_id ``[ in
`squidpy.pl.spatial_segment`.


```python
sq.pl.spatial_segment(
    adata, color="Cluster", library_key="library_id", seg_cell_id="cell_id"
)
```

There are several parameters that can be controlled. For instance, it is
cropped FOV.


```python
sq.pl.spatial_segment(
    adata,
    color="Cluster",
    library_key="library_id",
    library_id="point8",
    seg_cell_id="cell_id",
    seg_contourpx=10,
    crop_coord=[(0, 0, 300, 300)],
)
```

It\'s also possible to add an outline to better distinguish segmentation
gray scaled or single channels can be plotted.


```python
sq.pl.spatial_segment(
    adata,
    color="Cluster",
    groups=["Fibroblast", "Epithelial"],
    library_key="library_id",
    library_id=["point8", "point16"],
    seg_cell_id="cell_id",
    seg_outline=True,
    img_channel=0,
    img_cmap="magma",
)
```

If groups of observations are plotted (as above), it\'s possible to
to visualize them nonetheless


```python
sq.pl.spatial_segment(
    adata,
    color="Cluster",
    groups=["Fibroblast", "Epithelial"],
    library_key="library_id",
    seg_cell_id="cell_id",
    seg_outline=True,
    img=False,
    frameon=False,
)
```

Finally, a scale bar can be added, where size and pixel units must be
purely visualization purposes.


```python
sq.pl.spatial_segment(
    adata,
    color="CD68",
    library_key="library_id",
    seg_cell_id="cell_id",
    img=False,
    cmap="inferno",
    scalebar_dx=2.0,
    scalebar_kwargs={"scale_loc": "bottom", "location": "lower right"},
)
```
