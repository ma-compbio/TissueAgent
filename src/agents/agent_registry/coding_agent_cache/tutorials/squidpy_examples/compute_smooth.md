---
title: "Smooth an image"
keywords:
  - "squidpy"
  - "image smoothing"
  - "gaussian"
  - "sq.im.process"
  - "imagecontainer"
  - "sigma"
  - "visium"
---

# Smooth an image

This example shows how to use `squidpy.im.process` with `method="smooth"` to apply Gaussian smoothing. The `sigma` keyword argument controls the kernel width.

```python
import matplotlib.pyplot as plt

import squidpy as sq

# load the H&E stained tissue image
img = sq.datasets.visium_hne_image_crop()
```

Smooth the image. The result is saved in layer `image_smooth` by default (configurable via `layer_added`).

```python
sq.im.process(img, layer="image", method="smooth", sigma=2)
```

View the result on a cropped region.

```python
crop = img.crop_corner(0, 0, size=200)

fig, axes = plt.subplots(1, 2)
for i, layer in enumerate(["image", "image_smooth"]):
    crop.show(layer, ax=axes[i])
    axes[i].set_title(layer)
```
