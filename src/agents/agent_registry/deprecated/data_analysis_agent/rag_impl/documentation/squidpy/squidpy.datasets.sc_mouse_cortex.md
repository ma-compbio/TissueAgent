# squidpy.datasets.sc_mouse_cortex

### squidpy.datasets.sc_mouse_cortex(path=None, \*\*kwargs)

Pre-processed [scRNA-seq mouse cortex](https://doi.org/10.1038/s41586-018-0654-5).

The shape of this [`anndata.AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData) object `(21697, 36826)`.

* **Parameters:**
  * **path** ([`PathLike`](https://docs.python.org/3/library/os.html#os.PathLike)[[`str`](https://docs.python.org/3/library/stdtypes.html#str)] | [`str`](https://docs.python.org/3/library/stdtypes.html#str)) – Path where to save the dataset.
  * **kwargs** ([`Any`](https://docs.python.org/3/library/typing.html#typing.Any)) – Keyword arguments for [`scanpy.read()`](https://scanpy.readthedocs.io/en/stable/generated/scanpy.read.html#scanpy.read).
* **Return type:**
  [`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData)
* **Returns:**
  :
  The dataset.
