## scanpy.get.get.obs_df(adata, keys=(), obsm_keys=(), \*, layer=None, gene_symbols=None, use_raw=False)
Return values for observations in adata.

* **Parameters:**
  **adata** 
  : AnnData object to get values from.

  **keys** 
  : Keys from either `.var_names`, `.var[gene_symbols]`, or `.obs.columns`.

  **obsm_keys** 
  : Tuples of `(key from obsm, column index of obsm[key])`.

  **layer** 
  : Layer of `adata` to use as expression values.

  **gene_symbols** 
  : Column of `adata.var` to search for `keys` in.

  **use_raw** 
  : Whether to get expression values from `adata.raw`.
* **Return type:**
  [`DataFrame`](https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.html#pandas.DataFrame)
* **Returns:**
  A dataframe with `adata.obs_names` as index, and values specified by `keys`
  and `obsm_keys`.

### Examples

Getting value for plotting:

```pycon
>>> import scanpy as sc
>>> pbmc = sc.datasets.pbmc68k_reduced()
>>> plotdf = sc.get.obs_df(
...     pbmc, keys=["CD8B", "n_genes"], obsm_keys=[("X_umap", 0), ("X_umap", 1)]
... )
>>> plotdf.columns
Index(['CD8B', 'n_genes', 'X_umap-0', 'X_umap-1'], dtype='object')
>>> plotdf.plot.scatter("X_umap-0", "X_umap-1", c="CD8B")  
<Axes: xlabel='X_umap-0', ylabel='X_umap-1'>
```

Calculating mean expression for marker genes by cluster:

```pycon
>>> pbmc = sc.datasets.pbmc68k_reduced()
>>> marker_genes = ["CD79A", "MS4A1", "CD8A", "CD8B", "LYZ"]
>>> genedf = sc.get.obs_df(pbmc, keys=["louvain", *marker_genes])
>>> grouped = genedf.groupby("louvain", observed=True)
>>> mean, var = grouped.mean(), grouped.var()
```

