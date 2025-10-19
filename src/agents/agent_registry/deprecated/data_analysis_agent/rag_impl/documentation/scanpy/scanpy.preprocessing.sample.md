## scanpy.preprocessing.sample(data, fraction=None, \*, n=None, rng=None, copy=False, replace=False, axis='obs', p=None)
Sample observations or variables with or without replacement.

* **Parameters:**
  **data** 
  : The (annotated) data matrix of shape `n_obs` × `n_vars`.
    Rows correspond to cells and columns to genes.

  **fraction** 
  : Sample to this `fraction` of the number of observations or variables.
    (All of them, even if there are `0`s/`False`s in `p`.)
    This can be larger than 1.0, if `replace=True`.
    See `axis` and `replace`.

  **n** 
  : Sample to this number of observations or variables. See `axis`.

  **rng** 
  : Random seed to change subsampling.

  **copy** 
  : If an [`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData) is passed,
    determines whether a copy is returned.

  **replace** 
  : If True, samples are drawn with replacement.

  **axis** 
  : Sample `obs`ervations (axis 0) or `var`iables (axis 1).

  **p** 
  : Drawing probabilities (floats) or mask (bools).
    Either an `axis`-sized array, or the name of a column.
    If `p` is an array of probabilities, it must sum to 1.
* **Return type:**
  [`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData) | [`None`](https://docs.python.org/3/library/constants.html#None) | [`tuple`](https://docs.python.org/3/library/stdtypes.html#tuple)[[`ndarray`](https://numpy.org/doc/stable/reference/generated/numpy.ndarray.html#numpy.ndarray) | [`csr_matrix`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.sparse.csr_matrix.html#scipy.sparse.csr_matrix) | [`csc_matrix`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.sparse.csc_matrix.html#scipy.sparse.csc_matrix) | [`Array`](https://docs.dask.org/en/stable/generated/dask.array.Array.html#dask.array.Array), [`ndarray`](https://numpy.org/doc/stable/reference/generated/numpy.ndarray.html#numpy.ndarray)[[`tuple`](https://docs.python.org/3/library/stdtypes.html#tuple)[[`int`](https://docs.python.org/3/library/functions.html#int), [`...`](https://docs.python.org/3/library/constants.html#Ellipsis)], [`dtype`](https://numpy.org/doc/stable/reference/generated/numpy.dtype.html#numpy.dtype)[`int64`]]]
* **Returns:**
  If `isinstance(data, AnnData)` and `copy=False`,
  this function returns `None`. Otherwise:

  `data[indices, :]` | `data[:, indices]` (depending on `axis`)
  : If `data` is array-like or `copy=True`, returns the subset.

  `indices`
  : If `data` is array-like, also returns the indices into the original.

