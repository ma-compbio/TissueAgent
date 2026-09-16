---
title: "Extract segmentation features"
keywords:
  - "squidpy"
  - "segmentation features"
  - "calculate_image_features"
  - "nuclei segmentation"
  - "watershed"
  - "regionprops"
  - "label"
  - "area"
  - "mean_intensity"
---

# Extract segmentation features

This example shows how to extract features from a nucleus segmentation. Use `features='segmentation'` with `calculate_image_features`.

Key `features_kwargs` parameters:
- `label_layer` - name of the label image layer
- `props` - segmentation properties to calculate (see `skimage.measure.regionprops_table`)

```python
import matplotlib.pyplot as plt

import squidpy as sq
```

Load the fluorescence Visium dataset.

```python
img = sq.datasets.visium_fluo_image_crop()
adata = sq.datasets.visium_fluo_adata_crop()
```

First compute a segmentation.

```python
sq.im.segment(
    img=img,
    layer="image",
    layer_added="segmented_watershed",
    method="watershed",
    channel=0,
)
```

Calculate segmentation features: nuclei count, mean area, and mean intensity of channels 1 and 2.

```python
sq.im.calculate_image_features(
    adata,
    img,
    layer="image",
    features="segmentation",
    key_added="segmentation_features",
    features_kwargs={
        "segmentation": {
            "label_layer": "segmented_watershed",
            "props": ["label", "area", "mean_intensity"],
            "channels": [1, 2],
        }
    },
    mask_circle=True,
)
```

The result is stored in `adata.obsm['segmentation_features']`.

```python
adata.obsm["segmentation_features"].head()
```

Plot the segmentation features.

```python
# show all channels (using low-res image contained in adata to save memory)
fig, axes = plt.subplots(1, 3, figsize=(8, 4))
for i, ax in enumerate(axes):
    ax.imshow(
        adata.uns["spatial"]["V1_Adult_Mouse_Brain_Coronal_Section_2"]["images"][
            "hires"
        ][:, :, i]
    )
    ax.set_title(f"ch{i}")

# plot segmentation features
sq.pl.spatial_scatter(
    sq.pl.extract(adata, "segmentation_features"),
    color=[
        "segmentation_label",
        "segmentation_area_mean",
        "segmentation_ch-1_mean_intensity_mean",
        "segmentation_ch-2_mean_intensity_mean",
    ],
    img_cmap="gray",
    ncols=2,
)
```
