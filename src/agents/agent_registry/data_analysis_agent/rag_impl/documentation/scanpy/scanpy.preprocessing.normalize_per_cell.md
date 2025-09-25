## scanpy.preprocessing.normalize_per_cell(data, \*, counts_per_cell_after=None, counts_per_cell=None, key_n_counts='n_counts', copy=False, layers=(), use_rep=None, min_counts=1)
Normalize total counts per cell.

#### Deprecated
Deprecated since version 1.3.7: Use `normalize_total()` instead.
The new function is equivalent to the present
function, except that

* the new function doesn’t filter cells based on `min_counts`,
  use `filter_cells()` if filtering is needed.
* some arguments were renamed
* `copy` is replaced by `inplace`

Normalize each cell by total counts over all genes, so that every cell has
the same total count after normalization.

Similar functions are used, for example, by Seurat [[Satija *et al.*, 2015](../references.md#id47)], Cell Ranger
[[Zheng *et al.*, 2017](../references.md#id64)] or SPRING [[Weinreb *et al.*, 2017](../references.md#id59)].

* **Parameters:**
  **data** 
  : The (annotated) data matrix of shape `n_obs` × `n_vars`. Rows correspond
    to cells and columns to genes.

  **counts_per_cell_after** 
  : If `None`, after normalization, each cell has a total count equal
    to the median of the *counts_per_cell* before normalization.

  **counts_per_cell** 
  : Precomputed counts per cell.

  **key_n_counts** 
  : Name of the field in `adata.obs` where the total counts per cell are
    stored.

  **copy** 
  : If an [`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData) is passed, determines whether a copy
    is returned.

  **min_counts** 
  : Cells with counts less than `min_counts` are filtered out during
    normalization.
* **Return type:**
  [`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData) | [`ndarray`](https://numpy.org/doc/stable/reference/generated/numpy.ndarray.html#numpy.ndarray) | [`csr_matrix`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.sparse.csr_matrix.html#scipy.sparse.csr_matrix) | [`csc_matrix`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.sparse.csc_matrix.html#scipy.sparse.csc_matrix) | [`None`](https://docs.python.org/3/library/constants.html#None)
* **Returns:**
  Returns `None` if `copy=False`, else returns an updated `AnnData` object. Sets the following fields:

  `adata.X`
  : Normalized count data matrix.

### Examples

```pycon
>>> import scanpy as sc
>>> adata = AnnData(np.array([[1, 0], [3, 0], [5, 6]], dtype=np.float32))
>>> print(adata.X.sum(axis=1))
[ 1.  3. 11.]
>>> sc.pp.normalize_per_cell(adata)
>>> print(adata.obs)
   n_counts
0       1.0
1       3.0
2      11.0
>>> print(adata.X.sum(axis=1))
[3. 3. 3.]
>>> sc.pp.normalize_per_cell(
...     adata,
...     counts_per_cell_after=1,
...     key_n_counts="n_counts2",
... )
>>> print(adata.obs)
   n_counts  n_counts2
0       1.0        3.0
1       3.0        3.0
2      11.0        3.0
>>> print(adata.X.sum(axis=1))
[1. 1. 1.]
```

