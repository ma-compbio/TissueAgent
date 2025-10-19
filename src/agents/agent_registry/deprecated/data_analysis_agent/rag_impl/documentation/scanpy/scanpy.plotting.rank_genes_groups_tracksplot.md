## scanpy.plotting.rank_genes_groups_tracksplot(adata, groups=None, \*, n_genes=None, groupby=None, var_names=None, gene_symbols=None, min_logfoldchange=None, key=None, show=None, save=None, \*\*kwds)
Plot ranking of genes using heatmap plot (see `heatmap()`).

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

  **\*\*kwds**
  : Are passed to `tracksplot()`.

### Examples

```python
import scanpy as sc
adata = sc.datasets.pbmc68k_reduced()
sc.tl.rank_genes_groups(adata, 'bulk_labels')
sc.pl.rank_genes_groups_tracksplot(adata)
```

![image](_build/markdown/plot_directive/api/scanpy-plotting-50.*)

