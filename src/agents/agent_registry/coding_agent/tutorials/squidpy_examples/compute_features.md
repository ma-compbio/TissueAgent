---
title: "Extract image features"
keywords:
  - "squidpy"
  - "image features"
  - "calculate_image_features"
  - "visium"
  - "summary features"
  - "texture features"
  - "histogram features"
  - "mask_circle"
  - "spot_scale"
  - "parallelization"
---

# Extract image features

This example shows spot-wise feature extraction from Visium images using `squidpy.im.calculate_image_features`.

```python
import numpy as np

import seaborn as sns

import squidpy as sq

# get spatial dataset including high-resolution tissue image
img = sq.datasets.visium_hne_image_crop()
adata = sq.datasets.visium_hne_adata_crop()
```

Plot spots overlaid on the tissue image.

```python
np.set_printoptions(threshold=10)
print(img)
print(adata.obsm["spatial"])

sq.pl.spatial_scatter(adata, outline=True, size=0.3)
```

Key parameters for `calculate_image_features`:
- `layer` - image layer for feature calculation
- `features` and `features_kwargs` - type of features to calculate
- `mask_circle`, `scale`, `spot_scale` - crop appearance options
- `n_jobs`, `backend`, `show_progress_bar` - parallelization
- `key_added`, `copy` - output control

Calculate summary features.

```python
sq.im.calculate_image_features(
    adata, img, features="summary", key_added="features", show_progress_bar=False
)

# show the calculated features
adata.obsm["features"].head()
```

Plot the features on the tissue image.

```python
sq.pl.spatial_scatter(
    sq.pl.extract(adata, "features"),
    color=[
        "summary_ch-0_quantile-0.5",
        "summary_ch-0_quantile-0.5",
        "summary_ch-2_quantile-0.5",
    ],
)
```

## Specify crop appearance

Use `mask_circle = True` to only use tissue under round Visium spots. Use `scale` to downscale crops. Use `spot_scale` to extract crops larger than the Visium spot.

```python
adata_sml = adata[:50].copy()

# calculate default features
sq.im.calculate_image_features(
    adata_sml,
    img,
    features=["summary", "texture", "histogram"],
    key_added="features",
    show_progress_bar=False,
)
# calculate features with masking
sq.im.calculate_image_features(
    adata_sml,
    img,
    features=["summary", "texture", "histogram"],
    key_added="features_masked",
    mask_circle=True,
    show_progress_bar=False,
)
# calculate features with scaling and larger context
sq.im.calculate_image_features(
    adata_sml,
    img,
    features=["summary", "texture", "histogram"],
    key_added="features_scaled",
    mask_circle=True,
    spot_scale=2,
    scale=0.5,
    show_progress_bar=False,
)

# plot distribution of median for different cropping options
_ = sns.displot(
    {
        "features": adata_sml.obsm["features"]["summary_ch-0_quantile-0.5"],
        "features_masked": adata_sml.obsm["features_masked"][
            "summary_ch-0_quantile-0.5"
        ],
        "features_scaled": adata_sml.obsm["features_scaled"][
            "summary_ch-0_quantile-0.5"
        ],
    },
    kind="kde",
)
```

## Parallelization

Set `n_jobs` to speed up feature extraction.

```python
sq.im.calculate_image_features(
    adata,
    img,
    features="summary",
    key_added="features",
    n_jobs=4,
    show_progress_bar=False,
)
```
