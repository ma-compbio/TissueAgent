# squidpy.datasets.mibitof

### squidpy.datasets.mibitof(path=None, \*\*kwargs)

Pre-processed MIBI-TOF dataset from [Hartmann et al](https://doi.org/10.1101/2020.01.17.909796).

The shape of this [`anndata.AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData) object `(3309, 36)`.

* **Parameters:**
  * **path** ([`PathLike`](https://docs.python.org/3/library/os.html#os.PathLike)[[`str`](https://docs.python.org/3/library/stdtypes.html#str)] | [`str`](https://docs.python.org/3/library/stdtypes.html#str)) – Path where to save the dataset.
  * **kwargs** ([`Any`](https://docs.python.org/3/library/typing.html#typing.Any)) – Keyword arguments for [`scanpy.read()`](https://scanpy.readthedocs.io/en/stable/generated/scanpy.read.html#scanpy.read).
* **Return type:**
  [`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData)
* **Returns:**
  :
  The dataset.
