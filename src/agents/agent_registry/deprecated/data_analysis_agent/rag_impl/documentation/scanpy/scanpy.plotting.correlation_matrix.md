## scanpy.plotting.correlation_matrix(adata, groupby, \*, show_correlation_numbers=False, dendrogram=None, figsize=None, show=None, save=None, ax=None, vmin=None, vmax=None, vcenter=None, norm=None, \*\*kwds)
Plot the correlation matrix computed as part of `sc.tl.dendrogram`.

* **Parameters:**
  **adata** 

  **groupby** 
  : Categorical data column used to create the dendrogram

  **show_correlation_numbers** 
  : If `show_correlation=True`, plot the correlation on top of each cell.

  **dendrogram** 
  : If True or a valid dendrogram key, a dendrogram based on the
    hierarchical clustering between the `groupby` categories is added.
    The dendrogram is computed using `scanpy.tl.dendrogram()`.
    If `tl.dendrogram` has not been called previously,
    the function is called with default parameters.

  **figsize** 
  : By default a figure size that aims to produce a squared correlation
    matrix plot is used. Format is (width, height)

  **show** 
  : Show the plot, do not return axis.

  **save** 
  : If `True` or a `str`, save the figure.
    A string is appended to the default filename.
    Infer the filetype if ending on {`'.pdf'`, `'.png'`, `'.svg'`}.

  **ax** 
  : A matplotlib axes object. Only works if plotting a single component.

  **vmin** 
  : The value representing the lower limit of the color scale. Values smaller than vmin are plotted
    with the same color as vmin.

  **vmax** 
  : The value representing the upper limit of the color scale. Values larger than vmax are plotted
    with the same color as vmax.

  **vcenter** 
  : The value representing the center of the color scale. Useful for diverging colormaps.

  **norm** 
  : Custom color normalization object from matplotlib. See
    `https://matplotlib.org/stable/tutorials/colors/colormapnorms.html` for details.

  **\*\*kwds**
  : Only if `show_correlation` is True:
    Are passed to [`matplotlib.pyplot.pcolormesh()`](https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.pcolormesh.html#matplotlib.pyplot.pcolormesh) when plotting the
    correlation heatmap. `cmap` can be used to change the color palette.
* **Return type:**
  [`list`](https://docs.python.org/3/library/stdtypes.html#list)[[`Axes`](https://matplotlib.org/stable/api/_as_gen/matplotlib.axes.Axes.html#matplotlib.axes.Axes)] | [`None`](https://docs.python.org/3/library/constants.html#None)
* **Returns:**
  If `show=False`, returns a list of [`matplotlib.axes.Axes`](https://matplotlib.org/stable/api/_as_gen/matplotlib.axes.Axes.html#matplotlib.axes.Axes) objects.

### Examples

```pycon
>>> import scanpy as sc
>>> adata = sc.datasets.pbmc68k_reduced()
>>> sc.tl.dendrogram(adata, "bulk_labels")
>>> sc.pl.correlation_matrix(adata, "bulk_labels")
```

