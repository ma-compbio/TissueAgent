# Plot segmentation masks

This example shows how to use `squidpy.pl.spatial_segment` to plot
segmentation masks and features in `anndata.AnnData`.

This plotting is useful when segmentation masks and underlying image are
available.

:::{seealso}

    See {doc}`plot_scatter` for scatter plot.
    
:::



```python
import squidpy as sq

adata = sq.datasets.mibitof()
adata.uns["spatial"].keys()
```

In this dataset we have 3 unique keys, which means that there are 3
unique `` `library_id ``[. As detailed in
{ref}\`sphx\_glr\_auto\_tutorials\_tutorial\_read\_spatial.py]{.title-ref},
it means that there are 3 unique field of views (FOV) in this dataset.
The information to link the library ids to the observations are stored
in {attr}`adata.obs`.



```python
adata.obs
```

Specifically, the key `` `library_id ``[ in
{attr}\`adata.obs]{.title-ref} contains the same unique values contained
in {attr}`adata.uns`. We can visualize the 3 spatial dataset with
`squidpy.pl.spatial_segment`.



```python
sq.pl.spatial_segment(
    adata, color="Cluster", library_key="library_id", seg_cell_id="cell_id"
)
```

There are several parameters that can be controlled. For instance, it is
possible to plot segmentation masks as \"contours\", in order to
visualize the underlying image. Let\'s visualize it for one specific
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
masks\' boundaries. Furthermore, the underlying image can be removed,
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
modify whether to \"visualize\" the segmentation masks that do not
belong to any selected group. It is set as \"transparent\" by default
(see above) but in cases where e.g. no image is present it can be useful
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
passed. The size for this example are not the real values and are for
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
