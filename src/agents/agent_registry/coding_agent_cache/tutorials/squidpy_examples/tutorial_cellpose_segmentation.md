---
title: "Nuclei segmentation using Cellpose"
keywords:
  - "squidpy"
  - "cellpose"
  - "segmentation"
  - "nuclei"
  - "fluorescence"
  - "h&e"
---
# Nuclei segmentation using Cellpose

In this tutorial we show how we can use the anatomical segmentation algorithm Cellpose in `squidpy.im.segment` for nuclei segmentation.

**Cellpose** , (code) is a novel anatomical segmentation algorithm. To use it in this example, we need to install it first via: `pip install cellpose`.


```python
import numpy as np

import matplotlib.pyplot as plt

import squidpy as sq
```

## Prepare custom segmentation function using Cellpose

Import the Cellpose segmentation model. See https://cellpose.readthedocs.io/en/latest/api.html#cellpose-class.


```python
from cellpose import models
```

The method parameter of the `sq.im.segment` method accepts any callable with the signature:
`numpy.ndarray` (height, width, channels) -> `numpy.ndarray` (height, width[, channels]).
Additional model specific arguments will also be passed on.
To use the Cellpose model, we define a wrapper that initializes the model, evaluates it and returns the
number of pixels per mask `min_size`.


```python
def cellpose(img, min_size=15):
    model = models.Cellpose(model_type="nuclei")
    res, _, _, _ = model.eval(
        img,
        channels=[0, 0],
        diameter=None,
        min_size=min_size,
    )
    return res
```

## Cell segmentation on Visium fluorescence data

Load the image and visualize its channels.


```python
img = sq.datasets.visium_fluo_image_crop()
crop = img.crop_corner(1000, 1000, size=1000)
crop.show(channelwise=True)
```

Segment the DAPI channel using the `cellpose` function defined above.


```python
sq.im.segment(img=crop, layer="image", channel=0, method=cellpose)
```

Plot the DAPI channel of the image crop and the segmentation result.


```python
print(crop)
print(f"Number of segments in crop: {len(np.unique(crop['segmented_custom']))}")

fig, axes = plt.subplots(1, 2, figsize=(10, 20))
crop.show("image", channel=0, ax=axes[0])
_ = axes[0].set_title("DAPI")
crop.show("segmented_custom", cmap="jet", interpolation="none", ax=axes[1])
_ = axes[1].set_title("Cellpose segmentation")
```

The `sq.im.segment` method will pass any additional arguments to the `cellpose` function,
segmentation result from above that works with the default of 15 pixels.


```python
sq.im.segment(img=crop, layer="image", channel=0, method=cellpose, min_size=200)

print(crop)
print(f"Number of segments in crop: {len(np.unique(crop['segmented_custom']))}")

fig, axes = plt.subplots(1, 2, figsize=(10, 20))
crop.show("image", channel=0, ax=axes[0])
_ = axes[0].set_title("DAPI")
crop.show("segmented_custom", cmap="jet", interpolation="none", ax=axes[1])
_ = axes[1].set_title("Cellpose segmentation")
```

## Cell segmentation on H&E stained tissue data

For the fluorescence data, we did nuclei segmentation on the DAPI channel simply by just passing on that channel to the Cellpose model. For the H&E images, we will use the `nuclei` model again. The `Cellpose` documentation states:


Let's look at the image below


```python
img = sq.datasets.visium_hne_image_crop()
crop = img.crop_corner(0, 0, size=1000)
crop.show("image")
```

The channels below correspond to:
- `image:0` -> red
- `image:1` -> green
- `image:2` -> blue


```python
crop.show("image", channelwise=True)
```

Based on these two images we can suggest two approaches:

A) Due to the H&E staining process, the nuclei seem to have a mostly blue/purple hue, so we could feed the entire H&E image into Cellpose and set the segmentation mode to `blue` (using `3` as the Cellpose channel number)

B) We see above that the red channel (`image:0`) has a particular good contrast, so we could use only that channel and treat it as a greyscale image (using `0` as the Cellpose channel number).

Let's define our custom segmentation function and then try both scenarios. Here, we set the second value in channels to `0` as we will only pass one image.


```python
def cellpose_he(img, min_size=15, flow_threshold=0.4, channel_cellpose=0):
    model = models.Cellpose(model_type="nuclei")
    res, _, _, _ = model.eval(
        img,
        channels=[channel_cellpose, 0],  # second channel is always 0
        diameter=None,
        min_size=min_size,
        invert=True,
        flow_threshold=flow_threshold,
    )
    return res
```

Scenario A: All channels as input, Cellpose set to blue (`3`) mode.


```python
hne_channel_to_segment = None  # so that we feed in all channels
cellpose_channel_setting = 3  # corresponds to "blue"

sq.im.segment(
    img=crop,
    layer="image",
    channel=hne_channel_to_segment,
    method=cellpose_he,
    channel_cellpose=cellpose_channel_setting,
)

print(crop)
print(f"Number of segments in crop: {len(np.unique(crop['segmented_custom']))}")

fig, axes = plt.subplots(1, 2, figsize=(10, 20))
crop.show("image", channel=hne_channel_to_segment, ax=axes[0])
_ = axes[0].set_title("H&E")
crop.show("segmented_custom", cmap="jet", interpolation="none", ax=axes[1])
_ = axes[1].set_title("Cellpose segmentation")
```

Scenario B: Only the red channel as input, Cellpose set to greyscale (`0`) mode.


```python
hne_channel_to_segment = 0  # corresponds to the red channel
cellpose_channel_setting = 0  # corresponds to "greyscale" mode

sq.im.segment(
    img=crop,
    layer="image",
    channel=hne_channel_to_segment,
    method=cellpose_he,
    channel_cellpose=cellpose_channel_setting,
)

print(crop)
print(f"Number of segments in crop: {len(np.unique(crop['segmented_custom']))}")

fig, axes = plt.subplots(1, 2, figsize=(10, 20))
crop.show("image", channel=hne_channel_to_segment, ax=axes[0])
_ = axes[0].set_title("H&E")
crop.show("segmented_custom", cmap="jet", interpolation="none", ax=axes[1])
_ = axes[1].set_title("Cellpose segmentation")
```


```python
hne_channel_to_segment = 0  # corresponds to the red channel
cellpose_channel_setting = 0  # corresponds to "greyscale" mode

sq.im.segment(
    img=crop,
    layer="image",
    channel=hne_channel_to_segment,
    method=cellpose_he,
    flow_threshold=0.8,
    channel_cellpose=cellpose_channel_setting,
)

print(crop)
print(f"Number of segments in crop: {len(np.unique(crop['segmented_custom']))}")

fig, axes = plt.subplots(1, 2, figsize=(10, 20))
crop.show("image", channel=None, ax=axes[0])
_ = axes[0].set_title("H&E")
crop.show("segmented_custom", cmap="jet", interpolation="none", ax=axes[1])
_ = axes[1].set_title("Cellpose segmentation")
```
