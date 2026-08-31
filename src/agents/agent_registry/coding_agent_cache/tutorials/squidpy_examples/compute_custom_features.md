---
title: "Extract custom features"
keywords:
  - "squidpy"
  - "custom features"
  - "image features"
  - "calculate_image_features"
  - "feature extraction"
  - "visium"
  - "image analysis"
  - "additional_layers"
---

# Extract custom features

This example shows how to extract features from the tissue image using a custom function.

Custom features are calculated with `features = 'custom'`. Key `features_kwargs` parameters:
- `func` - custom feature extraction function
- `additional_layers` - names of image layers passed to `func` together with `layer`

```python
import squidpy as sq
```

Load the H&E Visium dataset.

```python
# get spatial dataset including high-resolution tissue image
img = sq.datasets.visium_hne_image_crop()
adata = sq.datasets.visium_hne_adata_crop()
```

Define a custom feature extraction function.

```python
def mean_fn(arr):
    """Compute mean of arr."""
    import numpy as np

    return np.mean(arr)
```

Extract features using the custom function via `features_kwargs`.

```python
sq.im.calculate_image_features(
    adata,
    img,
    features="custom",
    features_kwargs={"custom": {"func": mean_fn}},
    key_added="custom_features",
    show_progress_bar=False,
)
```

The result is stored in `adata.obsm['custom_features']`.

```python
adata.obsm["custom_features"].head()
```

Plot the custom features on the tissue image.

```python
sq.pl.spatial_scatter(
    sq.pl.extract(adata, "custom_features"), color=[None, "mean_fn_0"], img_cmap="gray"
)
```

Pass multiple image layers to the custom function using `additional_layers`.

```python
def sum_fn(arr, extra_layer):
    """Compute sum of two image layers."""
    import numpy as np

    return np.sum(arr + extra_layer)


img.add_img(img["image"].values, layer="extra_layer")

sq.im.calculate_image_features(
    adata,
    img,
    layer="image",
    features="custom",
    features_kwargs={"custom": {"func": sum_fn, "additional_layers": ["extra_layer"]}},
    key_added="custom_features",
    show_progress_bar=False,
)
```
