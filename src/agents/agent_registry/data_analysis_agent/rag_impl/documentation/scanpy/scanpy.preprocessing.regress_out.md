## scanpy.preprocessing.regress_out(adata, keys, \*, layer=None, n_jobs=None, copy=False)
Regress out (mostly) unwanted sources of variation.

Uses simple linear regression. This is inspired by Seurat’s `regressOut`
function in R [[Satija *et al.*, 2015](../references.md#id47)]. Note that this function tends to overcorrect
in certain circumstances as described in [issue526](https://github.com/scverse/scanpy/issues/526).

* **Parameters:**
  **adata** 
  : The annotated data matrix.

  **keys** 
  : Keys for observation annotation on which to regress on.

  **layer** 
  : If provided, which element of layers to regress on.

  **n_jobs** 
  : Number of jobs for parallel computation.
    `None` means using `scanpy._settings.ScanpyConfig.n_jobs`.

  **copy** 
  : Determines whether a copy of `adata` is returned.
* **Return type:**
  [`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData) | [`None`](https://docs.python.org/3/library/constants.html#None)
* **Returns:**
  Returns `None` if `copy=False`, else returns an updated `AnnData` object. Sets the following fields:

  `adata.X` | `adata.layers[layer]`
  : Corrected count data matrix.

