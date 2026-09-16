---
title: "Extract texture features"
keywords:
  - "squidpy"
  - "texture features"
  - "glcm"
  - "image features"
  - "calculate_image_features"
  - "visium"
  - "co-occurrence matrix"
  - "spot_scale"
---

# Extract texture features

This example shows how to extract texture features based on a grey-level co-occurrence matrix (GLCM). Use `features='texture'` with `calculate_image_features`.

Key `features_kwargs` parameters:
- `distances` - distances for finding repeating patterns
- `angles` - angles for the GLCM
- `props` - texture properties extracted from the GLCM

For texture features, consider using a larger crop size (e.g., `spot_scale=2` or `spot_scale=4`).

```python
import squidpy as sq
```

Load the fluorescence Visium dataset and calculate texture features with `spot_scale=2`.

```python
# get spatial dataset including high-resolution tissue image
img = sq.datasets.visium_fluo_image_crop()
adata = sq.datasets.visium_fluo_adata_crop()

# calculate texture features and save in key "texture_features"
sq.im.calculate_image_features(
    adata,
    img,
    features="texture",
    key_added="texture_features",
    spot_scale=2,
    show_progress_bar=False,
)
```

The result is stored in `adata.obsm['texture_features']`.

```python
adata.obsm["texture_features"].head()
```

Plot the texture features on the tissue image.

```python
sq.pl.spatial_scatter(
    sq.pl.extract(adata, "texture_features"),
    color=[
        None,
        "texture_ch-0_contrast_dist-1_angle-0.00",
        "texture_ch-1_contrast_dist-1_angle-0.00",
    ],
    img_cmap="gray",
)
```
