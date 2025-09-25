## scanpy.preprocessing.log1p(data, \*, base=None, copy=False, chunked=None, chunk_size=None, layer=None, obsm=None)
Logarithmize the data matrix.

Computes $X = \log(X + 1)$,
where $log$ denotes the natural logarithm unless a different base is given.

* **Parameters:**
  **data** 
  : The (annotated) data matrix of shape `n_obs` × `n_vars`.
    Rows correspond to cells and columns to genes.

  **base** 
  : Base of the logarithm. Natural logarithm is used by default.

  **copy** 
  : If an [`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData) is passed, determines whether a copy
    is returned.

  **chunked** 
  : Process the data matrix in chunks, which will save memory.
    Applies only to [`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData).

  **chunk_size** 
  : `n_obs` of the chunks to process the data in.

  **layer** 
  : Entry of layers to transform.

  **obsm** 
  : Entry of obsm to transform.
* **Return type:**
  [`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData) | [`ndarray`](https://numpy.org/doc/stable/reference/generated/numpy.ndarray.html#numpy.ndarray) | [`csr_matrix`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.sparse.csr_matrix.html#scipy.sparse.csr_matrix) | [`csc_matrix`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.sparse.csc_matrix.html#scipy.sparse.csc_matrix) | [`None`](https://docs.python.org/3/library/constants.html#None)
* **Returns:**
  Returns or updates `data`, depending on `copy`.

