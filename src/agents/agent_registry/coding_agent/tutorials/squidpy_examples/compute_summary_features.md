---
title: "Extract summary features"
keywords:
  - "squidpy"
  - "summary features"
  - "image features"
  - "calculate_image_features"
  - "quantiles"
  - "visium"
  - "mask_circle"
  - "fluorescence"
---

# Extract summary features

This example shows how to extract summary features (intensity statistics per channel) from tissue images. Use `features='summary'` with `calculate_image_features`.

Key `features_kwargs` parameter:
- `quantiles` - quantiles to compute (default: 0.9, 0.5, 0.1)

```python
import squidpy as sq
```

Load the fluorescence Visium dataset.

```python
# get spatial dataset including hires tissue image
img = sq.datasets.visium_fluo_image_crop()
adata = sq.datasets.visium_fluo_adata_crop()
```

Calculate the 0.1th quantile, mean, and standard deviation for channels 0 (DAPI) and 1 (GFAP). Use `mask_circle=True` to restrict to tissue under spots.

```python
# calculate summary features and save in key "summary_features"
sq.im.calculate_image_features(
    adata,
    img,
    features="summary",
    features_kwargs={
        "summary": {
            "quantiles": [0.1],
            "channels": [0, 1],
        }
    },
    key_added="summary_features",
    mask_circle=True,
    show_progress_bar=False,
)
```

The result is stored in `adata.obsm['summary_features']`.

```python
adata.obsm["summary_features"].head()
```

Plot the summary features on the tissue image.

```python
sq.pl.spatial_scatter(
    sq.pl.extract(adata, "summary_features"),
    color=[None, "summary_ch-0_mean", "summary_ch-1_mean"],
    img_cmap="gray",
)
```
