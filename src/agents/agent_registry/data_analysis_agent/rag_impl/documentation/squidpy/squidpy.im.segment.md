# squidpy.im.segment

### squidpy.im.segment(img, layer=None, library_id=None, method='watershed', channel=0, chunks=None, lazy=False, layer_added=None, copy=False, \*\*kwargs)

Segment an image.

* **Parameters:**
  * **img** ([`ImageContainer`](../classes/squidpy.im.ImageContainer.md#squidpy.im.ImageContainer)) – High-resolution image.
  * **layer** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Image layer in `img` that should be processed. If None and only 1 layer is present, it will be selected.
  * **library_id** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`Sequence`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Sequence)[[`str`](https://docs.python.org/3/library/stdtypes.html#str)] | [`None`](https://docs.python.org/3/library/constants.html#None)) – Name of the Z-dimension(s) that this function should be applied to.
    For not specified Z-dimensions, the identity function is applied.
    If None, all Z-dimensions are segmented separately.
  * **method** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | `SegmentationModel` | [`Callable`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Callable)[[`...`](https://docs.python.org/3/library/constants.html#Ellipsis), [`ndarray`](https://numpy.org/doc/stable/reference/generated/numpy.ndarray.html#numpy.ndarray)[[`tuple`](https://docs.python.org/3/library/stdtypes.html#tuple)[[`int`](https://docs.python.org/3/library/functions.html#int), [`...`](https://docs.python.org/3/library/constants.html#Ellipsis)], [`dtype`](https://numpy.org/doc/stable/reference/generated/numpy.dtype.html#numpy.dtype)[[`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]]]) – 

    Segmentation method to use. Valid options are:
    > - ’watershed’ - [`skimage.segmentation.watershed()`](https://scikit-image.org/docs/stable/api/skimage.segmentation.html#skimage.segmentation.watershed).

    Alternatively, any [`callable()`](https://docs.python.org/3/library/functions.html#callable) can be passed as long as it has the following signature:
    [`numpy.ndarray`](https://numpy.org/doc/stable/reference/generated/numpy.ndarray.html#numpy.ndarray) `(height, width, channels)` **->** [`numpy.ndarray`](https://numpy.org/doc/stable/reference/generated/numpy.ndarray.html#numpy.ndarray) `(height, width[, channels])`.
  * **channel** ([`int`](https://docs.python.org/3/library/functions.html#int) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Channel index to use for segmentation. If None, use all channels.
  * **chunks** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`int`](https://docs.python.org/3/library/functions.html#int) | [`tuple`](https://docs.python.org/3/library/stdtypes.html#tuple)[[`int`](https://docs.python.org/3/library/functions.html#int), [`int`](https://docs.python.org/3/library/functions.html#int)] | [`None`](https://docs.python.org/3/library/constants.html#None)) – Number of chunks for `dask`. For automatic chunking, use `chunks = 'auto'`.
  * **lazy** ([`bool`](https://docs.python.org/3/library/functions.html#bool)) – Whether to lazily compute the result or not. Only used when `chunks != None`.
  * **layer_added** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Layer of new image layer to add into `img` object. If None, use `'segmented_{model}'`.
  * **thresh** – Threshold for creation of masked image. The areas to segment should be contained in this mask.
    If None, it is determined by [Otsu’s method](https://en.wikipedia.org/wiki/Otsu%27s_method).
    Only used if `method = 'watershed'`.
  * **geq** – Treat `thresh` as upper or lower bound for defining areas to segment. If `geq = True`, mask is defined
    as `mask = arr >= thresh`, meaning high values in `arr` denote areas to segment.
    Only used if `method = 'watershed'`.
  * **copy** ([`bool`](https://docs.python.org/3/library/functions.html#bool)) – If `True`, return the result, otherwise save it to the image container.
  * **kwargs** ([`Any`](https://docs.python.org/3/library/typing.html#typing.Any)) – Keyword arguments for the underlying model.
* **Return type:**
  [`ImageContainer`](../classes/squidpy.im.ImageContainer.md#squidpy.im.ImageContainer) | [`None`](https://docs.python.org/3/library/constants.html#None)
* **Returns:**
  :
  If `copy = True`, returns a new container with the segmented image in `'{layer_added}'`.

  Otherwise, modifies the `img` with the following key:
  > - [`squidpy.im.ImageContainer`](../classes/squidpy.im.ImageContainer.md#squidpy.im.ImageContainer) `['{layer_added}']` - the segmented image.
