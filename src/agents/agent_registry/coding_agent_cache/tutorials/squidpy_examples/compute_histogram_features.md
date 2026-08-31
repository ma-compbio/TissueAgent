---
title: "Extract histogram features"
keywords:
  - "squidpy"
  - "histogram features"
  - "image features"
  - "calculate_image_features"
  - "visium"
  - "color histogram"
  - "bin counts"
---

# Extract histogram features

This example shows how to extract histogram features from a tissue image. Histogram features compute a histogram of each image channel and return bin-counts per spot.

Key `features_kwargs` parameters:
- `bins` - number of histogram bins (default 10)
- `v_range` - range for binning values (default: whole image range)

```python
import squidpy as sq
```

Load the fluorescence Visium dataset and calculate histogram features with 3 bins for channels 0 and 1.

```python
# get spatial dataset including high-resolution tissue image
img = sq.datasets.visium_fluo_image_crop()
adata = sq.datasets.visium_fluo_adata_crop()

# calculate histogram features and save in key "histogram_features"
sq.im.calculate_image_features(
    adata,
    img,
    features="histogram",
    features_kwargs={"histogram": {"bins": 3, "channels": [0, 1]}},
    key_added="histogram_features",
)
```

The result is stored in `adata.obsm['histogram_features']`.

```python
adata.obsm["histogram_features"].head()
```

Plot histogram features on the tissue image.

```python
sq.pl.spatial_scatter(
    sq.pl.extract(adata, "histogram_features"),
    color=[
        None,
        "histogram_ch-0_bin-0",
        "histogram_ch-0_bin-1",
        "histogram_ch-0_bin-2",
    ],
    img_cmap="gray",
)
```
