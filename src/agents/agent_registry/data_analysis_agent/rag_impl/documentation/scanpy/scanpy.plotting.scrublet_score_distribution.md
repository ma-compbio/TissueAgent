## scanpy.plotting.scrublet_score_distribution(adata, \*, scale_hist_obs='log', scale_hist_sim='linear', figsize=(8, 3), return_fig=False, show=True, save=None)
Plot histogram of doublet scores for observed transcriptomes and simulated doublets.

The histogram for simulated doublets is useful for determining the correct doublet
score threshold.

Scrublet must have been run previously with the input object.

* **Parameters:**
  **adata** 
  : An AnnData object resulting from `scrublet()`.

  **scale_hist_obs** 
  : Set y axis scale transformation in matplotlib for the plot of observed transcriptomes

  **scale_hist_sim** 
  : Set y axis scale transformation in matplotlib for the plot of simulated doublets

  **figsize** 
  : width, height

  **show** 
  : Show the plot, do not return axis.

  **save** 
  : If [`True`](https://docs.python.org/3/library/constants.html#True) or a [`str`](https://docs.python.org/3/library/stdtypes.html#str), save the figure.
    A string is appended to the default filename.
    Infer the filetype if ending on {`'.pdf'`, `'.png'`, `'.svg'`}.
* **Return type:**
  [`Figure`](https://matplotlib.org/stable/api/_as_gen/matplotlib.figure.Figure.html#matplotlib.figure.Figure) | [`Sequence`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Sequence)[[`tuple`](https://docs.python.org/3/library/stdtypes.html#tuple)[[`Axes`](https://matplotlib.org/stable/api/_as_gen/matplotlib.axes.Axes.html#matplotlib.axes.Axes), [`Axes`](https://matplotlib.org/stable/api/_as_gen/matplotlib.axes.Axes.html#matplotlib.axes.Axes)]] | [`tuple`](https://docs.python.org/3/library/stdtypes.html#tuple)[[`Axes`](https://matplotlib.org/stable/api/_as_gen/matplotlib.axes.Axes.html#matplotlib.axes.Axes), [`Axes`](https://matplotlib.org/stable/api/_as_gen/matplotlib.axes.Axes.html#matplotlib.axes.Axes)] | [`None`](https://docs.python.org/3/library/constants.html#None)
* **Returns:**
  If `return_fig` is True, a [`Figure`](https://matplotlib.org/stable/api/_as_gen/matplotlib.figure.Figure.html#matplotlib.figure.Figure).
  If `show==False` a list of [`Axes`](https://matplotlib.org/stable/api/_as_gen/matplotlib.axes.Axes.html#matplotlib.axes.Axes).

#### SEE ALSO
`scrublet()`
: Main way of running Scrublet, runs preprocessing, doublet simulation and calling.

`scrublet_simulate_doublets()`
: Run Scrublet’s doublet simulation separately for advanced usage.

