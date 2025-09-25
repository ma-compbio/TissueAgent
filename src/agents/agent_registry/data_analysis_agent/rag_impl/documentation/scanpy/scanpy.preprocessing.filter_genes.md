## scanpy.preprocessing.filter_genes(data, \*, min_counts=None, min_cells=None, max_counts=None, max_cells=None, inplace=True, copy=False)
Filter genes based on number of cells or counts.

Keep genes that have at least `min_counts` counts or are expressed in at
least `min_cells` cells or have at most `max_counts` counts or are expressed
in at most `max_cells` cells.

Only provide one of the optional parameters `min_counts`, `min_cells`,
`max_counts`, `max_cells` per call.

* **Parameters:**
  **data** 
  : An annotated data matrix of shape `n_obs` × `n_vars`. Rows correspond
    to cells and columns to genes.

  **min_counts** 
  : Minimum number of counts required for a gene to pass filtering.

  **min_cells** 
  : Minimum number of cells expressed required for a gene to pass filtering.

  **max_counts** 
  : Maximum number of counts required for a gene to pass filtering.

  **max_cells** 
  : Maximum number of cells expressed required for a gene to pass filtering.

  **inplace** 
  : Perform computation inplace or return result.
* **Return type:**
  [`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData) | [`tuple`](https://docs.python.org/3/library/stdtypes.html#tuple)[[`ndarray`](https://numpy.org/doc/stable/reference/generated/numpy.ndarray.html#numpy.ndarray), [`ndarray`](https://numpy.org/doc/stable/reference/generated/numpy.ndarray.html#numpy.ndarray)] | [`None`](https://docs.python.org/3/library/constants.html#None)
* **Returns:**
  Depending on `inplace`, returns the following arrays or directly subsets
  and annotates the data matrix

  gene_subset
  : Boolean index mask that does filtering. `True` means that the
    gene is kept. `False` means the gene is removed.

  number_per_gene
  : Depending on what was thresholded (`counts` or `cells`), the array stores
    `n_counts` or `n_cells` per gene.

