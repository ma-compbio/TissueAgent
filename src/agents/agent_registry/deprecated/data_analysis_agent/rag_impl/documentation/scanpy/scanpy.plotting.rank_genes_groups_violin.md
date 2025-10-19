## scanpy.plotting.rank_genes_groups_violin(adata, groups=None, \*, n_genes=20, gene_names=None, gene_symbols=None, use_raw=None, key=None, split=True, density_norm='width', strip=True, jitter=True, size=1, ax=None, show=None, save=None, scale=\_empty)
Plot ranking of genes for all tested comparisons.

* **Parameters:**
  **adata** 
  : Annotated data matrix.

  **groups** 
  : List of group names.

  **n_genes** 
  : Number of genes to show. Is ignored if `gene_names` is passed.

  **gene_names** 
  : List of genes to plot. Is only useful if interested in a custom gene list,
    which is not the result of `scanpy.tl.rank_genes_groups()`.

  **gene_symbols** 
  : Key for field in `.var` that stores gene symbols if you do not want to
    use `.var_names` displayed in the plot.

  **use_raw** 
  : Use `raw` attribute of `adata` if present. Defaults to the value that
    was used in `rank_genes_groups()`.

  **split** 
  : Whether to split the violins or not.

  **density_norm** 
  : See [`violinplot()`](https://seaborn.pydata.org/generated/seaborn.violinplot.html#seaborn.violinplot).

  **strip** 
  : Show a strip plot on top of the violin plot.

  **jitter** 
  : If set to 0, no points are drawn. See [`stripplot()`](https://seaborn.pydata.org/generated/seaborn.stripplot.html#seaborn.stripplot).

  **size** 
  : Size of the jitter points.

  **show** 
  : Show the plot, do not return axis.

  **save** 
  : If `True` or a `str`, save the figure.
    A string is appended to the default filename.
    Infer the filetype if ending on {`'.pdf'`, `'.png'`, `'.svg'`}.

  **ax** 
  : A matplotlib axes object. Only works if plotting a single component.

