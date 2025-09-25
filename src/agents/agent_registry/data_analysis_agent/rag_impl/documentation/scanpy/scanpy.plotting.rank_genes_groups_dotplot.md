## scanpy.plotting.rank_genes_groups_dotplot(adata, groups=None, \*, n_genes=None, groupby=None, values_to_plot=None, var_names=None, gene_symbols=None, min_logfoldchange=None, key=None, show=None, save=None, return_fig=False, \*\*kwds)
Plot ranking of genes using dotplot plot (see `dotplot()`).

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

  **values_to_plot** 
  : Instead of the mean gene value, plot the values computed by `sc.rank_genes_groups`.
    The options are: [‘scores’, ‘logfoldchanges’, ‘pvals’, ‘pvals_adj’,
    ‘log10_pvals’, ‘log10_pvals_adj’]. When plotting logfoldchanges a divergent
    colormap is recommended. See examples below.

  **var_names** 
  : Genes to plot. Sometimes is useful to pass a specific list of var names (e.g. genes)
    to check their fold changes or p-values, instead of the top/bottom genes. The
    var_names could be a dictionary or a list as in `dotplot()` or
    `matrixplot()`. See examples below.

  **show** 
  : Show the plot, do not return axis.

  **save** 
  : If `True` or a `str`, save the figure.
    A string is appended to the default filename.
    Infer the filetype if ending on {`'.pdf'`, `'.png'`, `'.svg'`}.

  **ax**
  : A matplotlib axes object. Only works if plotting a single component.

  **return_fig** 
  : Returns [`DotPlot`](#scanpy.plotting.DotPlot) object. Useful for fine-tuning
    the plot. Takes precedence over `show=False`.

  **\*\*kwds**
  : Are passed to `dotplot()`.
* **Returns:**
  If `return_fig` is `True`, returns a [`DotPlot`](#scanpy.plotting.DotPlot) object,
  else if `show` is false, return axes dict

### Examples

```python
import scanpy as sc
adata = sc.datasets.pbmc68k_reduced()
sc.tl.rank_genes_groups(adata, 'bulk_labels', n_genes=adata.raw.shape[1])
```

Plot top 2 genes per group.

```python
sc.pl.rank_genes_groups_dotplot(adata,n_genes=2)
```

![image](_build/markdown/plot_directive/api/scanpy-plotting-38.*)

Plot with scaled expressions for easier identification of differences.

```python
sc.pl.rank_genes_groups_dotplot(adata, n_genes=2, standard_scale='var')
```

![image](_build/markdown/plot_directive/api/scanpy-plotting-39.*)

Plot `logfoldchanges` instead of gene expression. In this case a diverging colormap
like `bwr` or `seismic` works better. To center the colormap in zero, the minimum
and maximum values to plot are set to -4 and 4 respectively.
Also, only genes with a log fold change of 3 or more are shown.

```python
sc.pl.rank_genes_groups_dotplot(
    adata,
    n_genes=4,
    values_to_plot="logfoldchanges", cmap='bwr',
    vmin=-4,
    vmax=4,
    min_logfoldchange=3,
    colorbar_title='log fold change'
)
```

![image](_build/markdown/plot_directive/api/scanpy-plotting-40.*)

Also, the last genes can be plotted. This can be useful to identify genes
that are lowly expressed in a group. For this `n_genes=-4` is used

```python
sc.pl.rank_genes_groups_dotplot(
    adata,
    n_genes=-4,
    values_to_plot="logfoldchanges",
    cmap='bwr',
    vmin=-4,
    vmax=4,
    min_logfoldchange=3,
    colorbar_title='log fold change',
)
```

![image](_build/markdown/plot_directive/api/scanpy-plotting-41.*)

A list specific genes can be given to check their log fold change. If a
dictionary, the dictionary keys will be added as labels in the plot.

```python
var_names = {'T-cell': ['CD3D', 'CD3E', 'IL32'],
              'B-cell': ['CD79A', 'CD79B', 'MS4A1'],
              'myeloid': ['CST3', 'LYZ'] }
sc.pl.rank_genes_groups_dotplot(
    adata,
    var_names=var_names,
    values_to_plot="logfoldchanges",
    cmap='bwr',
    vmin=-4,
    vmax=4,
    min_logfoldchange=3,
    colorbar_title='log fold change',
)
```

![image](_build/markdown/plot_directive/api/scanpy-plotting-42.*)

#### SEE ALSO
`tl.rank_genes_groups`

