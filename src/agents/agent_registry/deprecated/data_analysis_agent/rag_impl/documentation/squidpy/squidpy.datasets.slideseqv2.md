# squidpy.datasets.slideseqv2

### squidpy.datasets.slideseqv2(path=None, \*\*kwargs)

Pre-processed SlideseqV2 dataset from [Stickles et al](https://doi.org/10.1038/s41587-020-0739-1).

The shape of this [`anndata.AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData) object `(41786, 4000)`.

* **Parameters:**
  * **path** ([`PathLike`](https://docs.python.org/3/library/os.html#os.PathLike)[[`str`](https://docs.python.org/3/library/stdtypes.html#str)] | [`str`](https://docs.python.org/3/library/stdtypes.html#str)) – Path where to save the dataset.
  * **kwargs** ([`Any`](https://docs.python.org/3/library/typing.html#typing.Any)) – Keyword arguments for [`scanpy.read()`](https://scanpy.readthedocs.io/en/stable/generated/scanpy.read.html#scanpy.read).
* **Return type:**
  [`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData)
* **Returns:**
  :
  The dataset.
