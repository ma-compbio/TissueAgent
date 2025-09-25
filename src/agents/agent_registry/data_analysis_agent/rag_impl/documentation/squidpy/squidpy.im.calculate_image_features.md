# squidpy.im.calculate_image_features

### squidpy.im.calculate_image_features(adata, img, layer=None, library_id=None, features='summary', features_kwargs=mappingproxy({}), key_added='img_features', copy=False, n_jobs=None, backend='loky', show_progress_bar=True, \*\*kwargs)

Calculate image features for all observations in `adata`.

* **Parameters:**
  * **adata** ([`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData)) – Annotated data object.
  * **img** ([`ImageContainer`](../classes/squidpy.im.ImageContainer.md#squidpy.im.ImageContainer)) – High-resolution image.
  * **layer** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Image layer in `img` that should be processed. If None and only 1 layer is present, it will be selected.
  * **library_id** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`Sequence`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Sequence)[[`str`](https://docs.python.org/3/library/stdtypes.html#str)] | [`None`](https://docs.python.org/3/library/constants.html#None)) – 
    - If None, there should only exist one entry in [`anndata.AnnData.uns`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.uns.html#anndata.AnnData.uns) `['{spatial_key}']`.
    - If a [`str`](https://docs.python.org/3/library/stdtypes.html#str), first search [`anndata.AnnData.obs`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obs.html#anndata.AnnData.obs) `['{library_id}']` which contains the mapping
      from observations to library ids, then search [`anndata.AnnData.uns`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.uns.html#anndata.AnnData.uns) `['{spatial_key}']`.
  * **features** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`Sequence`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Sequence)[[`str`](https://docs.python.org/3/library/stdtypes.html#str)]) – 

    Features to be calculated. Valid options are:
    - ’texture’ - summary stats based on repeating patterns
      [`squidpy.im.ImageContainer.features_texture()`](../classes/squidpy.im.ImageContainer.features_texture.md#squidpy.im.ImageContainer.features_texture).
    - ’summary’ - summary stats of each image channel
      [`squidpy.im.ImageContainer.features_summary()`](../classes/squidpy.im.ImageContainer.features_summary.md#squidpy.im.ImageContainer.features_summary).
    - ’histogram’ - counts in bins of image channel’s histogram
      [`squidpy.im.ImageContainer.features_histogram()`](../classes/squidpy.im.ImageContainer.features_histogram.md#squidpy.im.ImageContainer.features_histogram).
    - ’segmentation’ - stats of a cell segmentation mask
      [`squidpy.im.ImageContainer.features_segmentation()`](../classes/squidpy.im.ImageContainer.features_segmentation.md#squidpy.im.ImageContainer.features_segmentation).
    - ’custom’ - extract features using a custom function
      [`squidpy.im.ImageContainer.features_custom()`](../classes/squidpy.im.ImageContainer.features_custom.md#squidpy.im.ImageContainer.features_custom).
  * **features_kwargs** ([`Mapping`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping)[[`str`](https://docs.python.org/3/library/stdtypes.html#str), [`Mapping`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping)[[`str`](https://docs.python.org/3/library/stdtypes.html#str), [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]]) – Keyword arguments for the different features that should be generated, such as
    `{ 'texture': { ... }, ... }`.
  * **key_added** ([`str`](https://docs.python.org/3/library/stdtypes.html#str)) – Key in [`anndata.AnnData.obsm`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obsm.html#anndata.AnnData.obsm) where to store the calculated features.
  * **copy** ([`bool`](https://docs.python.org/3/library/functions.html#bool)) – If `True`, return the result, otherwise save it to the `adata` object.
  * **n_jobs** ([`int`](https://docs.python.org/3/library/functions.html#int) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Number of parallel jobs.
  * **backend** ([`str`](https://docs.python.org/3/library/stdtypes.html#str)) – Parallelization backend to use. See [`joblib.Parallel`](https://joblib.readthedocs.io/en/latest/generated/joblib.Parallel.html#joblib.Parallel) for available options.
  * **show_progress_bar** ([`bool`](https://docs.python.org/3/library/functions.html#bool)) – Whether to show the progress bar or not.
  * **kwargs** ([`Any`](https://docs.python.org/3/library/typing.html#typing.Any)) – Keyword arguments for [`squidpy.im.ImageContainer.generate_spot_crops()`](../classes/squidpy.im.ImageContainer.generate_spot_crops.md#squidpy.im.ImageContainer.generate_spot_crops).
* **Return type:**
  [`DataFrame`](https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.html#pandas.DataFrame) | [`None`](https://docs.python.org/3/library/constants.html#None)
* **Returns:**
  :
  If `copy = True`, returns a [`pandas.DataFrame`](https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.html#pandas.DataFrame) where columns correspond to the calculated features.

  Otherwise, modifies the `adata` object with the following key:
  > - [`anndata.AnnData.uns`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.uns.html#anndata.AnnData.uns) `['{key_added}']` - the above mentioned dataframe.
* **Raises:**
  [**ValueError**](https://docs.python.org/3/library/exceptions.html#ValueError) – If a feature is not known.
