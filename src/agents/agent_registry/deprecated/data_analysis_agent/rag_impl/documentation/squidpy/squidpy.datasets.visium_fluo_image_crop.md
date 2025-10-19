# squidpy.datasets.visium_fluo_image_crop

### squidpy.datasets.visium_fluo_image_crop(path=None, \*\*kwargs)

Cropped Fluorescent image from [10x Genomics Visium dataset](https://support.10xgenomics.com/spatial-gene-expression/datasets/1.1.0/V1_Adult_Mouse_Brain_Coronal_Section_2).

The shape of this image is `(7272, 7272)`.

* **Parameters:**
  * **path** ([`PathLike`](https://docs.python.org/3/library/os.html#os.PathLike)[[`str`](https://docs.python.org/3/library/stdtypes.html#str)] | [`str`](https://docs.python.org/3/library/stdtypes.html#str)) – Path where to save the .tiff image.
  * **kwargs** ([`Any`](https://docs.python.org/3/library/typing.html#typing.Any)) – Keyword arguments for [`squidpy.im.ImageContainer.add_img()`](../classes/squidpy.im.ImageContainer.add_img.md#squidpy.im.ImageContainer.add_img).
* **Returns:**
  :
  [`squidpy.im.ImageContainer`](../classes/squidpy.im.ImageContainer.md#squidpy.im.ImageContainer) The image data.
