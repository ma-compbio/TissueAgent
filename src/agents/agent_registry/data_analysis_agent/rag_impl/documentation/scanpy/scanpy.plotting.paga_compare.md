## scanpy.plotting.paga_compare(adata, basis=None, \*, edges=False, color=None, alpha=None, groups=None, components=None, projection='2d', legend_loc='on data', legend_fontsize=None, legend_fontweight='bold', legend_fontoutline=None, color_map=None, palette=None, frameon=False, size=None, title=None, right_margin=None, left_margin=0.05, show=None, save=None, title_graph=None, groups_graph=None, pos=None, \*\*paga_graph_params)
Scatter and PAGA graph side-by-side.

Consists in a scatter plot and the abstracted graph. See
`paga()` for all related parameters.

See `paga_path()` for visualizing gene changes along paths
through the abstracted graph.

Additional parameters are as follows.

* **Parameters:**
  **adata** 
  : Annotated data matrix.

  **kwds_scatter**
  : Keywords for `scatter()`.

  **kwds_paga**
  : Keywords for `paga()`.
* **Returns:**
  A list of [`Axes`](https://matplotlib.org/stable/api/_as_gen/matplotlib.axes.Axes.html#matplotlib.axes.Axes) if `show` is `False`.

