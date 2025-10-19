## scanpy.plotting.filter_genes_dispersion(result, \*, log=False, show=None, save=None)
Plot dispersions versus means for genes.

Produces Supp. Fig. 5c of Zheng et al. (2017) and MeanVarPlot() of Seurat.

* **Parameters:**
  **result** 
  : Result of `filter_genes_dispersion()`.

  **log** 
  : Plot on logarithmic axes.

  **show** 
  : Show the plot, do not return axis.

  **save** 
  : If `True` or a `str`, save the figure.
    A string is appended to the default filename.
    Infer the filetype if ending on {{`'.pdf'`, `'.png'`, `'.svg'`}}.
* **Return type:**
  [`None`](https://docs.python.org/3/library/constants.html#None)

