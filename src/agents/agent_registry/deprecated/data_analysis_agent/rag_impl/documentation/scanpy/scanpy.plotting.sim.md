## scanpy.plotting.sim(adata, \*, tmax_realization=None, as_heatmap=False, shuffle=False, show=None, save=None, marker='.')
Plot results of simulation.

* **Parameters:**
  **tmax_realization** 
  : Number of observations in one realization of the time series. The data matrix
    adata.X consists in concatenated realizations.

  **as_heatmap** 
  : Plot the timeseries as heatmap.

  **shuffle** 
  : Shuffle the data.

  **show** 
  : Show the plot, do not return axis.

  **save** 
  : If `True` or a `str`, save the figure.
    A string is appended to the default filename.
    Infer the filetype if ending on {{`'.pdf'`, `'.png'`, `'.svg'`}}.
* **Return type:**
  [`None`](https://docs.python.org/3/library/constants.html#None)

