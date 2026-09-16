---
title: "Crop images with ImageContainer"
keywords:
  - "squidpy"
  - "image cropping"
  - "imagecontainer"
  - "crop_corner"
  - "crop_center"
  - "visium"
  - "image processing"
  - "subset"
---

# Crop images with ImageContainer

This example shows how to crop images using `crop_corner` and `crop_center` from `squidpy.im.ImageContainer`.

```python
import matplotlib.pyplot as plt

import squidpy as sq
```

Load the fluorescence Visium image.

```python
img = sq.datasets.visium_fluo_image_crop()
```

Crop by corner coordinate or center coordinate. Coordinates can be in pixels (`int`) or percentage of total image size (`float`). A scaling factor can also be specified.

```python
crop_corner = img.crop_corner(1000, 1000, size=800)

crop_center = img.crop_center(1400, 1400, radius=400)

fig, axes = plt.subplots(1, 2)
crop_corner.show(ax=axes[0])
crop_center.show(ax=axes[1])
```

The result of cropping is another ImageContainer.

```python
crop_corner
```

Subset the associated `adata` to the cropped image using `subset`.

```python
adata = sq.datasets.visium_fluo_adata_crop()
adata
```

```python
adata_crop = crop_corner.subset(adata)
adata_crop
```
