## scanpy.preprocessing.recipe_weinreb17(adata, \*, log=True, mean_threshold=0.01, cv_threshold=2, n_pcs=50, svd_solver='randomized', random_state=0, copy=False)
Normalize and filter as of [[Weinreb *et al.*, 2017](../references.md#id59)].

Expects non-logarithmized data.
If using logarithmized data, pass `log=False`.

* **Parameters:**
  **adata** 
  : Annotated data matrix.

  **log** 
  : Logarithmize data?

  **copy** 
  : Return a copy if true.
* **Return type:**
  [`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData) | [`None`](https://docs.python.org/3/library/constants.html#None)

