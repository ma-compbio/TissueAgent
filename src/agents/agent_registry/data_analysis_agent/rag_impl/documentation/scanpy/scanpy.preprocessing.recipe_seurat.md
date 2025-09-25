## scanpy.preprocessing.recipe_seurat(adata, \*, log=True, plot=False, copy=False)
Normalize and filter as of Seurat [[Satija *et al.*, 2015](../references.md#id47)].

This uses a particular preprocessing.

Expects non-logarithmized data.
If using logarithmized data, pass `log=False`.

* **Parameters:**
  **adata** 
  : Annotated data matrix.

  **log** 
  : Logarithmize data?

  **plot** 
  : Show a plot of the gene dispersion vs. mean relation.

  **copy** 
  : Return a copy if true.
* **Return type:**
  [`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData) | [`None`](https://docs.python.org/3/library/constants.html#None)

