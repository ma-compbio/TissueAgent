# squidpy.datasets.merfish

### squidpy.datasets.merfish(path=None, \*\*kwargs)

Pre-processed MERFISH dataset from [Moffitt et al](https://doi.org/10.1126/science.aau5324).

The shape of this [`anndata.AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData) object `(73655, 161)`.

* **Parameters:**
  * **path** ([`PathLike`](https://docs.python.org/3/library/os.html#os.PathLike)[[`str`](https://docs.python.org/3/library/stdtypes.html#str)] | [`str`](https://docs.python.org/3/library/stdtypes.html#str)) – Path where to save the dataset.
  * **kwargs** ([`Any`](https://docs.python.org/3/library/typing.html#typing.Any)) – Keyword arguments for [`scanpy.read()`](https://scanpy.readthedocs.io/en/stable/generated/scanpy.read.html#scanpy.read).
* **Return type:**
  [`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData)
* **Returns:**
  :
  The dataset.
