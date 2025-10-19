## scanpy.get.rank_genes_groups_df(adata, group, \*, key='rank_genes_groups', pval_cutoff=None, log2fc_min=None, log2fc_max=None, gene_symbols=None)
Get `scanpy.tl.rank_genes_groups()` results in the form of a [`DataFrame`](https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.html#pandas.DataFrame).

* **Parameters:**
  **adata** 
  : Object to get results from.

  **group** 
  : Which group (as in `scanpy.tl.rank_genes_groups()`’s `groupby`
    argument) to return results from. Can be a list. All groups are
    returned if groups is `None`.

  **key** 
  : Key differential expression groups were stored under.

  **pval_cutoff** 
  : Return only adjusted p-values below the  cutoff.

  **log2fc_min** 
  : Minimum logfc to return.

  **log2fc_max** 
  : Maximum logfc to return.

  **gene_symbols** 
  : Column name in `.var` DataFrame that stores gene symbols. Specifying
    this will add that column to the returned dataframe.
* **Return type:**
  [`DataFrame`](https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.html#pandas.DataFrame)

### Example

```pycon
>>> import scanpy as sc
>>> pbmc = sc.datasets.pbmc68k_reduced()
>>> sc.tl.rank_genes_groups(pbmc, groupby="louvain", use_raw=True)
>>> dedf = sc.get.rank_genes_groups_df(pbmc, group="0")
```

