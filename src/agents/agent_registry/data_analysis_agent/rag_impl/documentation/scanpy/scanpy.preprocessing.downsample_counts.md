## scanpy.preprocessing.downsample_counts(adata, counts_per_cell=None, total_counts=None, \*, random_state=0, replace=False, copy=False)
Downsample counts from count matrix.

If `counts_per_cell` is specified, each cell will downsampled.
If `total_counts` is specified, expression matrix will be downsampled to
contain at most `total_counts`.

* **Parameters:**
  **adata** 
  : Annotated data matrix.

  **counts_per_cell** 
  : Target total counts per cell. If a cell has more than ‘counts_per_cell’,
    it will be downsampled to this number. Resulting counts can be specified
    on a per cell basis by passing an array.Should be an integer or integer
    ndarray with same length as number of obs.

  **total_counts** 
  : Target total counts. If the count matrix has more than `total_counts`
    it will be downsampled to have this number.

  **random_state** 
  : Random seed for subsampling.

  **replace** 
  : Whether to sample the counts with replacement.

  **copy** 
  : Determines whether a copy of `adata` is returned.
* **Return type:**
  [`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData) | [`None`](https://docs.python.org/3/library/constants.html#None)
* **Returns:**
  Returns `None` if `copy=False`, else returns an `AnnData` object. Sets the following fields:

  `adata.X`
  : Downsampled counts matrix.

