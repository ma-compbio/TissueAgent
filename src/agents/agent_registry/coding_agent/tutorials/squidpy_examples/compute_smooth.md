# Smooth an image

This example shows how to use `squidpy.im.process` to smooth an image
layer of {func}`squidpy.im.ImageContainer`.

We use the argument `method="smooth"` to smooth the image. This calls
`skimage.filters.gaussian` in the background. Keyword arguments `kwargs`
are passed to the wrapped function. This allows us to set the width of
the Gaussian kernel, $\\sigma$, used for smoothing.

::: {seealso}
-   {doc}`compute_gray`.
-   {doc}`compute_process_hires`.

:::



```python
import matplotlib.pyplot as plt

import squidpy as sq

# load the H&E stained tissue image
img = sq.datasets.visium_hne_image_crop()
```

Smooth the image with `sigma = 2`. With the argument `layer` we can
select the image layer that should be processed. By default, the
resulting image is saved in the layer `image_smooth`. This behavior can
be changed with the arguments `copy` and `layer_added`.



```python
sq.im.process(img, layer="image", method="smooth", sigma=2)
```

Now we can look at the result on a cropped part of the image.



```python
crop = img.crop_corner(0, 0, size=200)

fig, axes = plt.subplots(1, 2)
for i, layer in enumerate(["image", "image_smooth"]):
    crop.show(layer, ax=axes[i])
    axes[i].set_title(layer)
```
