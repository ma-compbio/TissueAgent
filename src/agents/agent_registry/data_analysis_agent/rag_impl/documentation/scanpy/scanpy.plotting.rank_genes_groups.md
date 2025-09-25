## scanpy.plotting.rank_genes_groups(adata, groups=None, \*, n_genes=20, gene_symbols=None, key='rank_genes_groups', fontsize=8, ncols=4, sharey=True, show=None, save=None, ax=None, \*\*kwds)
Plot ranking of genes.

* **Parameters:**
  **adata** 
  : Annotated data matrix.

  **groups** 
  : The groups for which to show the gene ranking.

  **gene_symbols** 
  : Key for field in `.var` that stores gene symbols if you do not want to
    use `.var_names`.

  **n_genes** 
  : Number of genes to show.

  **fontsize** 
  : Fontsize for gene names.

  **ncols** 
  : Number of panels shown per row.

  **sharey** 
  : Controls if the y-axis of each panels should be shared. But passing
    `sharey=False`, each panel has its own y-axis range.

  **show** 
  : Show the plot, do not return axis.

  **save** 
  : If `True` or a `str`, save the figure.
    A string is appended to the default filename.
    Infer the filetype if ending on {`'.pdf'`, `'.png'`, `'.svg'`}.

  **ax** 
  : A matplotlib axes object. Only works if plotting a single component.
* **Return type:**
  [`list`](https://docs.python.org/3/library/stdtypes.html#list)[[`Axes`](https://matplotlib.org/stable/api/_as_gen/matplotlib.axes.Axes.html#matplotlib.axes.Axes)] | [`None`](https://docs.python.org/3/library/constants.html#None)
* **Returns:**
  List of each group’s matplotlib axis or `None` if `show=True`.

### Examples

```python
import scanpy as sc
adata = sc.datasets.pbmc68k_reduced()
sc.pl.rank_genes_groups(adata)
```

![image](_build/markdown/plot_directive/api/scanpy-plotting-35.*)

Plot top 10 genes (default 20 genes)

```python
sc.pl.rank_genes_groups(adata, n_genes=10)
```

![image](_build/markdown/plot_directive/api/scanpy-plotting-36.*)

#### SEE ALSO
`tl.rank_genes_groups`

