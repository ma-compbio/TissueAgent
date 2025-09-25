## scanpy.plotting.paga_path(adata, nodes, keys, \*, use_raw=True, annotations=('dpt_pseudotime',), color_map=None, color_maps_annotations=mappingproxy({'dpt_pseudotime': 'Greys'}), palette_groups=None, n_avg=1, groups_key=None, xlim=(None, None), title=None, left_margin=None, ytick_fontsize=None, title_fontsize=None, show_node_names=True, show_yticks=True, show_colorbar=True, legend_fontsize=None, legend_fontweight=None, normalize_to_zero_one=False, as_heatmap=True, return_data=False, show=None, save=None, ax=None)
Gene expression and annotation changes along paths in the abstracted graph.

* **Parameters:**
  **adata** 
  : An annotated data matrix.

  **nodes** 
  : A path through nodes of the abstracted graph, that is, names or indices
    (within `.categories`) of groups that have been used to run PAGA.

  **keys** 
  : Either variables in `adata.var_names` or annotations in
    `adata.obs`. They are plotted using `color_map`.

  **use_raw** 
  : Use `adata.raw` for retrieving gene expressions if it has been set.

  **annotations** 
  : Plot these keys with `color_maps_annotations`. Need to be keys for
    `adata.obs`.

  **color_map** 
  : Matplotlib colormap.

  **color_maps_annotations** 
  : Color maps for plotting the annotations. Keys of the dictionary must
    appear in `annotations`.

  **palette_groups** 
  : Ususally, use the same `sc.pl.palettes...` as used for coloring the
    abstracted graph.

  **n_avg** 
  : Number of data points to include in computation of running average.

  **groups_key** 
  : Key of the grouping used to run PAGA. If `None`, defaults to
    `adata.uns['paga']['groups']`.

  **as_heatmap** 
  : Plot the timeseries as heatmap. If not plotting as heatmap,
    `annotations` have no effect.

  **show_node_names** 
  : Plot the node names on the nodes bar.

  **show_colorbar** 
  : Show the colorbar.

  **show_yticks** 
  : Show the y ticks.

  **normalize_to_zero_one** 
  : Shift and scale the running average to [0, 1] per gene.

  **return_data** 
  : Return the timeseries data in addition to the axes if `True`.

  **show** 
  : Show the plot, do not return axis.

  **save** 
  : If `True` or a `str`, save the figure.
    A string is appended to the default filename.
    Infer the filetype if ending on {`'.pdf'`, `'.png'`, `'.svg'`}.

  **ax** 
  : A matplotlib axes object.
* **Return type:**
  [`tuple`](https://docs.python.org/3/library/stdtypes.html#tuple)[[`Axes`](https://matplotlib.org/stable/api/_as_gen/matplotlib.axes.Axes.html#matplotlib.axes.Axes), [`DataFrame`](https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.html#pandas.DataFrame)] | [`Axes`](https://matplotlib.org/stable/api/_as_gen/matplotlib.axes.Axes.html#matplotlib.axes.Axes) | [`DataFrame`](https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.html#pandas.DataFrame) | [`None`](https://docs.python.org/3/library/constants.html#None)
* **Returns:**
  A [`Axes`](https://matplotlib.org/stable/api/_as_gen/matplotlib.axes.Axes.html#matplotlib.axes.Axes) object, if `ax` is `None`, else `None`.
  If `return_data`, return the timeseries data in addition to an axes.

