## scanpy.preprocessing.scale(data, \*, zero_center=True, max_value=None, copy=False, layer=None, obsm=None, mask_obs=None)
Scale data to unit variance and zero mean.

#### NOTE
Variables (genes) that do not display any variation (are constant across
all observations) are retained and (for zero_center==True) set to 0
during this operation. In the future, they might be set to NaNs.

* **Parameters:**
  **data** 
  : The (annotated) data matrix of shape `n_obs` × `n_vars`.
    Rows correspond to cells and columns to genes.

  **zero_center** 
  : If `False`, omit zero-centering variables, which allows to handle sparse
    input efficiently.

  **max_value** 
  : Clip (truncate) to this value after scaling. If `None`, do not clip.

  **copy** 
  : Whether this function should be performed inplace. If an AnnData object
    is passed, this also determines if a copy is returned.

  **layer** 
  : If provided, which element of layers to scale.

  **obsm** 
  : If provided, which element of obsm to scale.

  **mask_obs** 
  : Restrict both the derivation of scaling parameters and the scaling itself
    to a certain set of observations. The mask is specified as a boolean array
    or a string referring to an array in [`obs`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obs.html#anndata.AnnData.obs).
    This will transform data from csc to csr format if `issparse(data)`.
* **Return type:**
  [`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData) | [`csr_matrix`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.sparse.csr_matrix.html#scipy.sparse.csr_matrix) | [`csc_matrix`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.sparse.csc_matrix.html#scipy.sparse.csc_matrix) | [`ndarray`](https://numpy.org/doc/stable/reference/generated/numpy.ndarray.html#numpy.ndarray) | [`Array`](https://docs.dask.org/en/stable/generated/dask.array.Array.html#dask.array.Array) | [`None`](https://docs.python.org/3/library/constants.html#None)
* **Returns:**
  Returns `None` if `copy=False`, else returns an updated `AnnData` object. Sets the following fields:

  `adata.X` | `adata.layers[layer]`
  : Scaled count data matrix.

  `adata.var['mean']`
  : Means per gene before scaling.

  `adata.var['std']`
  : Standard deviations per gene before scaling.

  `adata.var['var']`
  : Variances per gene before scaling.

