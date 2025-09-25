# squidpy.im.process

### squidpy.im.process(img, layer=None, library_id=None, method='smooth', chunks=None, lazy=False, layer_added=None, channel_dim=None, copy=False, apply_kwargs=mappingproxy({}), \*\*kwargs)

Process an image by applying a transformation.

* **Parameters:**
  * **img** ([`ImageContainer`](../classes/squidpy.im.ImageContainer.md#squidpy.im.ImageContainer)) – High-resolution image.
  * **layer** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Image layer in `img` that should be processed. If None and only 1 layer is present, it will be selected.
  * **library_id** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`Sequence`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Sequence)[[`str`](https://docs.python.org/3/library/stdtypes.html#str)] | [`None`](https://docs.python.org/3/library/constants.html#None)) – Name of the Z-dimension(s) that this function should be applied to.
    For not specified Z-dimensions, the identity function is applied.
    If None, all Z-dimensions are processed at once, treating the image as a 3D volume.
  * **method** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`Callable`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Callable)[[`...`](https://docs.python.org/3/library/constants.html#Ellipsis), [`ndarray`](https://numpy.org/doc/stable/reference/generated/numpy.ndarray.html#numpy.ndarray)[[`tuple`](https://docs.python.org/3/library/stdtypes.html#tuple)[[`int`](https://docs.python.org/3/library/functions.html#int), [`...`](https://docs.python.org/3/library/constants.html#Ellipsis)], [`dtype`](https://numpy.org/doc/stable/reference/generated/numpy.dtype.html#numpy.dtype)[[`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]]]) – 

    Processing method to use. Valid options are:
    > - ’smooth’ - [`skimage.filters.gaussian()`](https://scikit-image.org/docs/stable/api/skimage.filters.html#skimage.filters.gaussian).
    > - ’gray’ - [`skimage.color.rgb2gray()`](https://scikit-image.org/docs/stable/api/skimage.color.html#skimage.color.rgb2gray).

    Alternatively, any [`callable()`](https://docs.python.org/3/library/functions.html#callable) can be passed as long as it has the following signature:
    [`numpy.ndarray`](https://numpy.org/doc/stable/reference/generated/numpy.ndarray.html#numpy.ndarray) `(height, width, channels)` **->** [`numpy.ndarray`](https://numpy.org/doc/stable/reference/generated/numpy.ndarray.html#numpy.ndarray) `(height, width[, channels])`.
  * **chunks** ([`int`](https://docs.python.org/3/library/functions.html#int) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Number of chunks for `dask`. For automatic chunking, use `chunks = 'auto'`.
  * **lazy** ([`bool`](https://docs.python.org/3/library/functions.html#bool)) – Whether to lazily compute the result or not. Only used when `chunks != None`.
  * **layer_added** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Layer of new image layer to add into `img` object.
    If None, use `'{layer}_{method}'`.
  * **channel_dim** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Name of the channel dimension of the new image layer. Default is the same as the original, if the
    processing function does not change the number of channels, and `'{channel}_{processing}'` otherwise.
  * **copy** ([`bool`](https://docs.python.org/3/library/functions.html#bool)) – If `True`, return the result, otherwise save it to the image container.
  * **apply_kwargs** ([`Mapping`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping)[[`str`](https://docs.python.org/3/library/stdtypes.html#str), [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]) – Keyword arguments for [`squidpy.im.ImageContainer.apply()`](../classes/squidpy.im.ImageContainer.apply.md#squidpy.im.ImageContainer.apply).
  * **kwargs** ([`Any`](https://docs.python.org/3/library/typing.html#typing.Any)) – Keyword arguments for `method`.
* **Return type:**
  [`ImageContainer`](../classes/squidpy.im.ImageContainer.md#squidpy.im.ImageContainer) | [`None`](https://docs.python.org/3/library/constants.html#None)
* **Returns:**
  :
  If `copy = True`, returns a new container with the processed image in `'{layer_added}'`.

  Otherwise, modifies the `img` with the following key:
  > - [`squidpy.im.ImageContainer`](../classes/squidpy.im.ImageContainer.md#squidpy.im.ImageContainer) `['{layer_added}']` - the processed image.
* **Raises:**
  [**NotImplementedError**](https://docs.python.org/3/library/exceptions.html#NotImplementedError) – If `method` has not been implemented.
