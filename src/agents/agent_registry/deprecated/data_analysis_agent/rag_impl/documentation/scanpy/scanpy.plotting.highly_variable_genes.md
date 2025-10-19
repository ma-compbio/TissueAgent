## scanpy.plotting.highly_variable_genes(adata_or_result, \*, log=False, show=None, save=None, highly_variable_genes=True)
Plot dispersions or normalized variance versus means for genes.

Produces Supp. Fig. 5c of Zheng et al. (2017) and MeanVarPlot() and
VariableFeaturePlot() of Seurat.

* **Parameters:**
  **adata**
  : Result of `highly_variable_genes()`.

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

