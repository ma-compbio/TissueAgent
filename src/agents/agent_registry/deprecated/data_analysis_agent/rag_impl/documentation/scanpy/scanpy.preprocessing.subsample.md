## scanpy.preprocessing.subsample(data, fraction=None, \*, n_obs=None, random_state=0, copy=False)
Subsample to a fraction of the number of observations.

#### Deprecated
Deprecated since version 1.11.0: Use `sample()` instead.

* **Parameters:**
  **data** 
  : The (annotated) data matrix of shape `n_obs` × `n_vars`.
    Rows correspond to cells and columns to genes.

  **fraction** 
  : Subsample to this `fraction` of the number of observations.

  **n_obs** 
  : Subsample to this number of observations.

  **random_state** 
  : Random seed to change subsampling.

  **copy** 
  : If an [`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData) is passed,
    determines whether a copy is returned.
* **Return type:**
  [`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData) | [`tuple`](https://docs.python.org/3/library/stdtypes.html#tuple)[[`ndarray`](https://numpy.org/doc/stable/reference/generated/numpy.ndarray.html#numpy.ndarray) | [`csr_matrix`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.sparse.csr_matrix.html#scipy.sparse.csr_matrix) | [`csc_matrix`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.sparse.csc_matrix.html#scipy.sparse.csc_matrix), [`ndarray`](https://numpy.org/doc/stable/reference/generated/numpy.ndarray.html#numpy.ndarray)[[`tuple`](https://docs.python.org/3/library/stdtypes.html#tuple)[[`int`](https://docs.python.org/3/library/functions.html#int), [`...`](https://docs.python.org/3/library/constants.html#Ellipsis)], [`dtype`](https://numpy.org/doc/stable/reference/generated/numpy.dtype.html#numpy.dtype)[`int64`]]] | [`None`](https://docs.python.org/3/library/constants.html#None)
* **Returns:**
  Returns `X[obs_indices], obs_indices` if data is array-like, otherwise
  subsamples the passed [`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData) (`copy == False`) or
  returns a subsampled copy of it (`copy == True`).
