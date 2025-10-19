## scanpy.preprocessing.sqrt(data, \*, copy=False, chunked=False, chunk_size=None)
Take square root of the data matrix.

Computes $X = \sqrt(X)$.

* **Parameters:**
  **data** 
  : The (annotated) data matrix of shape `n_obs` × `n_vars`.
    Rows correspond to cells and columns to genes.

  **copy** 
  : If an [`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData) object is passed,
    determines whether a copy is returned.

  **chunked** 
  : Process the data matrix in chunks, which will save memory.
    Applies only to [`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData).

  **chunk_size** 
  : `n_obs` of the chunks to process the data in.
* **Return type:**
  [`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData) | [`csr_matrix`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.sparse.csr_matrix.html#scipy.sparse.csr_matrix) | [`csc_matrix`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.sparse.csc_matrix.html#scipy.sparse.csc_matrix) | [`ndarray`](https://numpy.org/doc/stable/reference/generated/numpy.ndarray.html#numpy.ndarray) | [`None`](https://docs.python.org/3/library/constants.html#None)
* **Returns:**
  Returns or updates `data`, depending on `copy`.

