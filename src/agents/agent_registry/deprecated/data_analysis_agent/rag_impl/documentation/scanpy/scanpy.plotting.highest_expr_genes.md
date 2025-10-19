## scanpy.plotting.highest_expr_genes(adata, n_top=30, \*, layer=None, gene_symbols=None, log=False, show=None, save=None, ax=None, \*\*kwds)
Fraction of counts assigned to each gene over all cells.

Computes, for each gene, the fraction of counts assigned to that gene within
a cell. The `n_top` genes with the highest mean fraction over all cells are
plotted as boxplots.

This plot is similar to the `scater` package function `plotHighestExprs(type
= "highest-expression")`, see [here](https://bioconductor.org/packages/devel/bioc/vignettes/scater/inst/doc/vignette-qc.html). Quoting
from there:

> *We expect to see the “usual suspects”, i.e., mitochondrial genes, actin,
> ribosomal protein, MALAT1. A few spike-in transcripts may also be
> present here, though if all of the spike-ins are in the top 50, it
> suggests that too much spike-in RNA was added. A large number of
> pseudo-genes or predicted genes may indicate problems with alignment.*
> – Davis McCarthy and Aaron Lun
* **Parameters:**
  **adata** 
  : Annotated data matrix.

  **n_top** 
  : Number of top

  **layer** 
  : Layer from which to pull data.

  **gene_symbols** 
  : Key for field in .var that stores gene symbols if you do not want to use .var_names.

  **log** 
  : Plot x-axis in log scale

  **show** 
  : Show the plot, do not return axis.

  **save** 
  : If `True` or a `str`, save the figure.
    A string is appended to the default filename.
    Infer the filetype if ending on {`'.pdf'`, `'.png'`, `'.svg'`}.

  **ax** 
  : A matplotlib axes object. Only works if plotting a single component.

  **\*\*kwds**
  : Are passed to [`boxplot()`](https://seaborn.pydata.org/generated/seaborn.boxplot.html#seaborn.boxplot).
* **Returns:**
  If `show==False` a [`Axes`](https://matplotlib.org/stable/api/_as_gen/matplotlib.axes.Axes.html#matplotlib.axes.Axes).

