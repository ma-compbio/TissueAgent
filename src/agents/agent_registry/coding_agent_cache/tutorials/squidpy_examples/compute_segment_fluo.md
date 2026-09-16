---
title: "Cell-segmentation for fluorescence images"
keywords:
  - "squidpy"
  - "cell segmentation"
  - "fluorescence"
  - "watershed"
  - "nuclei segmentation"
  - "sq.im.segment"
  - "dapi"
  - "otsu threshold"
---

# Cell-segmentation for fluorescence images

This example shows how to segment nuclei from fluorescence images using `squidpy.im.segment`. Built-in method `'watershed'` is provided, and custom models can be used via `squidpy.im.SegmentationCustom`.

```python
import numpy as np

import matplotlib.pyplot as plt

import squidpy as sq

# load fluorescence tissue image
img = sq.datasets.visium_fluo_image_crop()
```

Crop the image to a smaller region.

```python
crop = img.crop_corner(1000, 1000, size=1000)
```

Visualize the fluorescence channels.

```python
crop.show("image", channelwise=True)
```

Segment using watershed on the DAPI channel (channel 0). Set `thresh=None` for automatic Otsu thresholding. Use `geq=True` (default) to treat values >= threshold as foreground, or `geq=False` for values < threshold.

```python
sq.im.segment(
    img=crop, layer="image", channel=0, method="watershed", thresh=None, geq=True
)
```

The result is saved in layer `segmented_watershed`. View the segmentation.

```python
print(crop)
print(f"Number of segments in crop: {len(np.unique(crop['segmented_watershed']))}")

fig, axes = plt.subplots(1, 2)
crop.show("image", channel=0, ax=axes[0])
_ = axes[0].set_title("DAPI")
crop.show("segmented_watershed", cmap="jet", interpolation="none", ax=axes[1])
_ = axes[1].set_title("segmentation")
```
