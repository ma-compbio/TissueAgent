---
title: "Process a high-resolution image"
keywords:
  - "squidpy"
  - "image processing"
  - "high resolution"
  - "tiling"
  - "chunks"
  - "sq.im.process"
  - "dask"
  - "custom processing"
  - "border effects"
---

# Process a high-resolution image

This example shows how to use `squidpy.im.process` with tiling via the `chunks` argument for images too large to fit in memory. Use `depth` and `boundary` in `apply_kwargs` to handle border effects between chunks.

```python
import numpy as np
from scipy.ndimage import gaussian_filter

import matplotlib.pyplot as plt

import squidpy as sq
```

## Built-in processing functions

```python
# load the H&E stained tissue image
img = sq.datasets.visium_hne_image()
```

Process by tiling with `chunks=(1000, 1000)`.

```python
sq.im.process(img, layer="image", method="gray", chunks=1000)
```

View the result on a cropped region.

```python
crop = img.crop_corner(4000, 4000, size=2000)

fig, axes = plt.subplots(1, 2)
crop.show("image", ax=axes[0])
_ = axes[0].set_title("original")
crop.show("image_gray", cmap="gray", ax=axes[1])
_ = axes[1].set_title("grayscale")
```

## Custom processing functions

Use a custom function with `depth` and `boundary` to control overlap between chunks.

```python
arr = np.zeros((20, 20))
arr[10:] = 1
img = sq.im.ImageContainer(arr, layer="image")

# smooth the image using `depth` 0 and 1
sq.im.process(
    img,
    layer="image",
    method=gaussian_filter,
    layer_added="smooth_depth0",
    chunks=10,
    sigma=1,
    apply_kwargs={"depth": 0},
)
sq.im.process(
    img,
    layer="image",
    method=gaussian_filter,
    layer_added="smooth_depth1",
    chunks=10,
    sigma=1,
    apply_kwargs={"depth": 1, "boundary": "reflect"},
)
```

Using overlapping blocks with `depth=1` removes artifacts at chunk borders.

```python
fig, axes = plt.subplots(1, 3)
img.show("image", ax=axes[0])
_ = axes[0].set_title("original")
img.show("smooth_depth0", ax=axes[1])
_ = axes[1].set_title("non-overlapping crops")
img.show("smooth_depth1", ax=axes[2])
_ = axes[2].set_title("overlapping crops")
```
