## scanpy.plotting.rank_genes_groups_stacked_violin(adata, groups=None, \*, n_genes=None, groupby=None, gene_symbols=None, var_names=None, min_logfoldchange=None, key=None, show=None, save=None, return_fig=False, \*\*kwds)
Plot ranking of genes using stacked_violin plot.

(See `stacked_violin()`)

* **Parameters:**
  **adata** 
  : Annotated data matrix.

  **groups** 
  : The groups for which to show the gene ranking.

  **n_genes** 
  : Number of genes to show. This can be a negative number to show for
    example the down regulated genes. eg: num_genes=-10. Is ignored if
    `gene_names` is passed.

  **gene_symbols** 
  : Column name in `.var` DataFrame that stores gene symbols. By default `var_names`
    refer to the index column of the `.var` DataFrame. Setting this option allows
    alternative names to be used.

  **groupby** 
  : The key of the observation grouping to consider. By default,
    the groupby is chosen from the rank genes groups parameter but
    other groupby options can be used.  It is expected that
    groupby is a categorical. If groupby is not a categorical observation,
    it would be subdivided into `num_categories` (see `dotplot()`).

  **min_logfoldchange** 
  : Value to filter genes in groups if their logfoldchange is less than the
    min_logfoldchange

  **key** 
  : Key used to store the ranking results in `adata.uns`.

  **show** 
  : Show the plot, do not return axis.

  **save** 
  : If `True` or a `str`, save the figure.
    A string is appended to the default filename.
    Infer the filetype if ending on {`'.pdf'`, `'.png'`, `'.svg'`}.

  **ax**
  : A matplotlib axes object. Only works if plotting a single component.

  **return_fig** 
  : Returns [`StackedViolin`](#scanpy.plotting.StackedViolin) object. Useful for fine-tuning
    the plot. Takes precedence over `show=False`.

  **\*\*kwds**
  : Are passed to `stacked_violin()`.
* **Returns:**
  If `return_fig` is `True`, returns a [`StackedViolin`](#scanpy.plotting.StackedViolin) object,
  else if `show` is false, return axes dict

### Examples

```pycon
>>> import scanpy as sc
>>> adata = sc.datasets.pbmc68k_reduced()
>>> sc.tl.rank_genes_groups(adata, "bulk_labels")
```

```pycon
>>> sc.pl.rank_genes_groups_stacked_violin(
...     adata, n_genes=4, min_logfoldchange=4, figsize=(8, 6)
... )
```

