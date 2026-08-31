---
title: "Generate cropped images from spots"
keywords:
  - "squidpy"
  - "generate_spot_crops"
  - "imagecontainer"
  - "visium"
  - "image cropping"
  - "spot crops"
  - "generator"
  - "scale"
  - "spot_scale"
---

# Generate cropped images from spots

This example shows how to use `squidpy.im.ImageContainer.generate_spot_crops` to iterate over spots and extract image crops.

```python
import matplotlib.pyplot as plt

import squidpy as sq
```

Load the H&E image and corresponding anndata.

```python
img = sq.datasets.visium_hne_image_crop()
adata = sq.datasets.visium_hne_adata_crop()
```

Create a generator that yields cropped images. The `as_array` argument controls the return type: pass a layer name for `numpy.ndarray`, `True` for a dict of arrays, or `False` for an `ImageContainer`.

```python
gen = img.generate_spot_crops(adata, scale=0.5, as_array="image", squeeze=True)
```

Plot consecutive cropped images.

```python
fig, axes = plt.subplots(1, 5)
fig.set_size_inches((20, 6))
for i in range(5):
    axes[i].set_title(f"Cropped image {i+1}")
    axes[i].axis("off")
    axes[i].imshow(next(gen))
```

Increase `scale` to crop larger areas around spots.

```python
gen = img.generate_spot_crops(adata, scale=1.5, as_array="image", squeeze=True)
fig, axes = plt.subplots(1, 5)
fig.set_size_inches((20, 6))
for i in range(5):
    axes[i].set_title(f"Cropped spot {i}")
    axes[i].axis("off")
    axes[i].imshow(next(gen))
```

Use `spot_scale` to control crop size relative to spot diameter.

```python
gen = img.generate_spot_crops(adata, spot_scale=2, as_array="image", squeeze=True)
fig, axes = plt.subplots(1, 5)
fig.set_size_inches((20, 6))
for i in range(5):
    axes[i].set_title(f"Cropped spot {i}")
    axes[i].axis("off")
    axes[i].imshow(next(gen))
```

With `as_array=True`, returns a dict with layer names as keys and arrays as values.

```python
gen = img.generate_spot_crops(adata, spot_scale=0.5, as_array=True, squeeze=True)
dic = next(gen)
image = dic["image"]
plt.imshow(image)
```

With `as_array=False`, returns an `ImageContainer`.

```python
gen = img.generate_spot_crops(adata, spot_scale=2, as_array=False, squeeze=True)
for _ in range(5):
    next(gen).show(figsize=(2, 2), dpi=40)
```

With `return_obs=True`, yields a tuple of (cropped image, obs_name).

```python
gen = img.generate_spot_crops(
    adata, spot_scale=2, as_array="image", squeeze=True, return_obs=True
)
image, obs_name = next(gen)
plt.imshow(image)
plt.title(obs_name)
```
