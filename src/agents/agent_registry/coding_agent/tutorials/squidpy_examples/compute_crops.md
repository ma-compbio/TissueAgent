# Crop images with ImageContainer

This example shows how crop images from `squidpy.im.ImageContainer`.

Specifically, it shows how to use:

> -   {func}`squidpy.im.ImageContainer.crop_corner()`
> -   {func}`squidpy.im.ImageContainer.crop_center()`



```python
import matplotlib.pyplot as plt

import squidpy as sq
```

Let\'s load the fluorescence Visium image.



```python
img = sq.datasets.visium_fluo_image_crop()
```

Extracting single crops: Crops need to be sized and located. We
distinguish crops located based on a corner coordinate of the crop and
crops located based on the center coordinate of the crop. You can
specify the crop coordinates in pixels (as `int`) or in percentage of
total image size (as `float`). In addition, you can specify a scaling
factor for the crop.



```python
crop_corner = img.crop_corner(1000, 1000, size=800)

crop_center = img.crop_center(1400, 1400, radius=400)

fig, axes = plt.subplots(1, 2)
crop_corner.show(ax=axes[0])
crop_center.show(ax=axes[1])
```

The result of the cropping functions is another ImageContainer.



```python
crop_corner
```

You can subset the associated `adata` to the cropped image using
{func}`squidpy.im.ImageContainer.subset`:



```python
adata = sq.datasets.visium_fluo_adata_crop()
adata
```

Note the number of observations in `adata` before and after subsetting.



```python
adata_crop = crop_corner.subset(adata)
adata_crop
```
