---
title: "Show layers of the ImageContainer"
keywords:
  - "squidpy"
  - "imagecontainer"
  - "show"
  - "visualization"
  - "segmentation overlay"
  - "mibitof"
  - "image layers"
  - "concat"
---

# Show layers of the ImageContainer

This example shows how to use `squidpy.im.ImageContainer.show` to visualize image layers, including segmentation overlays.

```python
import squidpy as sq
```

Load the Mibitof dataset.

```python
adata = sq.datasets.mibitof()
```

Visualize the spatial segments.

```python
sq.pl.spatial_segment(
    adata,
    library_id=["point16", "point23", "point8"],
    seg_cell_id="cell_id",
    color="Cluster",
    library_key="library_id",
    title=["point16", "point23", "point8"],
)
```

Extract images from the anndata object and create an `ImageContainer`.

```python
imgs = []
for library_id in adata.uns["spatial"].keys():
    img = sq.im.ImageContainer(
        adata.uns["spatial"][library_id]["images"]["hires"], library_id=library_id
    )
    img.add_img(
        adata.uns["spatial"][library_id]["images"]["segmentation"],
        library_id=library_id,
        layer="segmentation",
    )
    img["segmentation"].attrs["segmentation"] = True
    imgs.append(img)
img = sq.im.ImageContainer.concat(imgs)
```

Show each image in the container.

```python
img.show("image")
```

Overlay segmentation results on the image.

```python
img.show("image", segmentation_layer="segmentation", segmentation_alpha=0.5)
```
