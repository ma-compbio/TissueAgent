---
title: "Convert to grayscale"
keywords:
  - "squidpy"
  - "grayscale"
  - "image processing"
  - "imagecontainer"
  - "sq.im.process"
  - "rgb2gray"
  - "visium"
---

# Convert to grayscale

This example shows how to use `squidpy.im.process` to convert an image layer to grayscale using `method='gray'`.

```python
import matplotlib.pyplot as plt

import squidpy as sq
```

Load the H&E stained tissue image.

```python
img = sq.datasets.visium_hne_image_crop()
```

Convert to grayscale. The `layer` argument selects which image layer to process. The result is saved in `image_gray` by default (configurable via `layer_added`).

```python
sq.im.process(img, layer="image", method="gray")

fig, axes = plt.subplots(1, 2)
img.show("image", ax=axes[0])
_ = axes[0].set_title("original")
img.show("image_gray", cmap="gray", ax=axes[1])
_ = axes[1].set_title("grayscale")
```
