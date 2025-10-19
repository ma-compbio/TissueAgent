## scanpy.plotting.ranking(adata, attr, keys, \*, dictionary=None, indices=None, labels=None, color='black', n_points=30, log=False, include_lowest=False, show=None)
Plot rankings.

See, for example, how this is used in pl.pca_loadings.

* **Parameters:**
  **adata** 
  : The data.

  **attr** 
  : The attribute of AnnData that contains the score.

  **keys** 
  : The scores to look up an array from the attribute of adata.
* **Return type:**
  [`GridSpec`](https://matplotlib.org/stable/api/_as_gen/matplotlib.gridspec.GridSpec.html#matplotlib.gridspec.GridSpec) | [`None`](https://docs.python.org/3/library/constants.html#None)
* **Returns:**
  Returns matplotlib gridspec with access to the axes.

