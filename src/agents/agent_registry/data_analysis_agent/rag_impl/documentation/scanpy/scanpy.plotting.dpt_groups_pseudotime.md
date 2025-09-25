## scanpy.plotting.dpt_groups_pseudotime(adata, \*, color_map=None, palette=None, show=None, save=None, marker='.')
Plot groups and pseudotime.

* **Parameters:**
  **adata** 
  : Annotated data matrix.

  **color_map** 
  : Color map to use for continous variables. Can be a name or a
    [`Colormap`](https://matplotlib.org/stable/api/_as_gen/matplotlib.colors.Colormap.html#matplotlib.colors.Colormap) instance (e.g. `"magma`”, `"viridis"`
    or `mpl.cm.cividis`), see [`get_cmap()`](https://matplotlib.org/stable/api/cm_api.html#matplotlib.cm.ColormapRegistry.get_cmap).
    If `None`, the value of `mpl.rcParams["image.cmap"]` is used.
    The default `color_map` can be set using [`set_figure_params()`](scanpy.md#scanpy.set_figure_params).

  **palette** 
  : Colors to use for plotting categorical annotation groups.
    The palette can be a valid [`ListedColormap`](https://matplotlib.org/stable/api/_as_gen/matplotlib.colors.ListedColormap.html#matplotlib.colors.ListedColormap) name
    (`'Set2'`, `'tab20'`, …), a [`Cycler`](https://matplotlib.org/cycler/generated/cycler.Cycler.html#cycler.Cycler) object, a dict mapping
    categories to colors, or a sequence of colors. Colors must be valid to
    matplotlib. (see [`is_color_like()`](https://matplotlib.org/stable/api/_as_gen/matplotlib.colors.is_color_like.html#matplotlib.colors.is_color_like)).
    If `None`, `mpl.rcParams["axes.prop_cycle"]` is used unless the categorical
    variable already has colors stored in `adata.uns["{var}_colors"]`.
    If provided, values of `adata.uns["{var}_colors"]` will be set.

  **show** 
  : Show the plot, do not return axis.

  **save** 
  : If `True` or a `str`, save the figure.
    A string is appended to the default filename.
    Infer the filetype if ending on {`'.pdf'`, `'.png'`, `'.svg'`}.

  **marker** 
  : Marker style. See [`markers`](https://matplotlib.org/stable/api/markers_api.html#module-matplotlib.markers) for details.

