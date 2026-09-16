---
title: "Cell-segmentation for H&E stains"
keywords:
  - "squidpy"
  - "cell segmentation"
  - "h&e stain"
  - "watershed"
  - "nuclei segmentation"
  - "sq.im.segment"
  - "image smoothing"
  - "manual threshold"
---

# Cell-segmentation for H&E stains

This example shows how to segment nuclei from H&E stained images using processing and segmentation functions.

```python
import numpy as np

import matplotlib.pyplot as plt
import seaborn as sns

import squidpy as sq

# load the H&E stained tissue image and crop to a smaller segment
img = sq.datasets.visium_hne_image_crop()
crop = img.crop_corner(0, 0, size=1000)
```

Smooth the image before segmentation.

```python
# smooth image
sq.im.process(crop, layer="image", method="smooth", sigma=4)

# plot the result
fig, axes = plt.subplots(1, 2)
for layer, ax in zip(["image", "image_smooth"], axes):
    crop.show(layer, ax=ax)
    ax.set_title(layer)
```

Determine a manual threshold using the histogram. For H&E, nuclei appear darker so use `geq=False`.

```python
fig, axes = plt.subplots(1, 3, figsize=(15, 4))
crop.show("image_smooth", cmap="gray", ax=axes[0])
axes[1].imshow(crop["image_smooth"][:, :, 0, 0] < 90)
_ = sns.histplot(np.array(crop["image_smooth"]).flatten(), bins=50, ax=axes[2])
plt.tight_layout()
```

Segment with watershed using `thresh=90` and `geq=False` (lower intensity = foreground for H&E).

```python
sq.im.segment(img=crop, layer="image_smooth", method="watershed", thresh=90, geq=False)
```

View the segmentation result.

```python
print(crop)
print(f"Number of segments in crop: {len(np.unique(crop['segmented_watershed']))}")

fig, axes = plt.subplots(1, 2)
crop.show("image", channel=0, ax=axes[0])
_ = axes[0].set_title("H&E")
crop.show("segmented_watershed", cmap="jet", interpolation="none", ax=axes[1])
_ = axes[1].set_title("segmentation")
```
