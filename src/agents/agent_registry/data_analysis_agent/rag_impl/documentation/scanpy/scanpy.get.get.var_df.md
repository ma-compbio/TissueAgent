## scanpy.get.get.var_df(adata, keys=(), varm_keys=(), \*, layer=None)
Return values for observations in adata.

* **Parameters:**
  **adata** 
  : AnnData object to get values from.

  **keys** 
  : Keys from either `.obs_names`, or `.var.columns`.

  **varm_keys** 
  : Tuples of `(key from varm, column index of varm[key])`.

  **layer** 
  : Layer of `adata` to use as expression values.
* **Return type:**
  [`DataFrame`](https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.html#pandas.DataFrame)
* **Returns:**
  A dataframe with `adata.var_names` as index, and values specified by `keys`
  and `varm_keys`.
