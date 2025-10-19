## scanpy.plotting.scatter(adata, x=None, y=None, \*, color=None, use_raw=None, layers=None, sort_order=True, alpha=None, basis=None, groups=None, components=None, projection='2d', legend_loc='right margin', legend_fontsize=None, legend_fontweight=None, legend_fontoutline=None, color_map=None, palette=None, frameon=None, right_margin=None, left_margin=None, size=None, marker='.', title=None, show=None, save=None, ax=None)
Scatter plot along observations or variables axes.

Color the plot using annotations of observations (`.obs`), variables
(`.var`) or expression of genes (`.var_names`).

* **Parameters:**
  **adata** 
  : Annotated data matrix.

  **x** 
  : x coordinate.

  **y** 
  : y coordinate.

  **color** 
  : Keys for annotations of observations/cells or variables/genes,
    or a hex color specification, e.g.,
    `'ann1'`, `'#fe57a1'`, or `['ann1', 'ann2']`.

  **use_raw** 
  : Whether to use `raw` attribute of `adata`. Defaults to `True` if `.raw` is present.

  **layers** 
  : Use the `layers` attribute of `adata` if present: specify the layer for
    `x`, `y` and `color`. If `layers` is a string, then it is expanded to
    `(layers, layers, layers)`.

  **basis** 
  : String that denotes a plotting tool that computed coordinates.

  **sort_order** 
  : For continuous annotations used as color parameter, plot data points
    with higher values on top of others.

  **groups** 
  : Restrict to a few categories in categorical observation annotation.
    The default is not to restrict to any groups.

  **dimensions**
  : 0-indexed dimensions of the embedding to plot as integers. E.g. [(0, 1), (1, 2)].
    Unlike `components`, this argument is used in the same way as `colors`, e.g. is
    used to specify a single plot at a time. Will eventually replace the components
    argument.

  **components** 
  : For instance, `['1,2', '2,3']`. To plot all available components use
    `components='all'`.

  **projection** 
  : Projection of plot (default: `'2d'`).

  **legend_loc** 
  : Location of legend, either `'on data'`, `'right margin'`, `None`,
    or a valid keyword for the `loc` parameter of [`Legend`](https://matplotlib.org/stable/api/legend_api.html#matplotlib.legend.Legend).

  **legend_fontsize** 
  : Numeric size in pt or string describing the size.
    See [`set_fontsize()`](https://matplotlib.org/stable/api/text_api.html#matplotlib.text.Text.set_fontsize).

  **legend_fontweight** 
  : Legend font weight. A numeric value in range 0-1000 or a string.
    Defaults to `'bold'` if `legend_loc == 'on data'`, otherwise to `'normal'`.
    See [`set_fontweight()`](https://matplotlib.org/stable/api/text_api.html#matplotlib.text.Text.set_fontweight).

  **legend_fontoutline** 
  : Line width of the legend font outline in pt. Draws a white outline using
    the path effect [`withStroke`](https://matplotlib.org/stable/api/patheffects_api.html#matplotlib.patheffects.withStroke).

  **colorbar_loc**
  : Where to place the colorbar for continous variables. If `None`, no colorbar
    is added.

  **size** 
  : Point size. If `None`, is automatically computed as 120000 / n_cells.
    Can be a sequence containing the size for each cell. The order should be
    the same as in adata.obs.

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

  **na_color**
  : Color to use for null or masked values. Can be anything matplotlib accepts as a
    color. Used for all points if `color=None`.

  **na_in_legend**
  : If there are missing values, whether they get an entry in the legend. Currently
    only implemented for categorical legends.

  **frameon** 
  : Draw a frame around the scatter plot. Defaults to value set in
    [`set_figure_params()`](scanpy.md#scanpy.set_figure_params), defaults to `True`.

  **title** 
  : Provide title for panels either as string or list of strings,
    e.g. `['title1', 'title2', ...]`.

  **show** 
  : Show the plot, do not return axis.

  **save** 
  : If `True` or a `str`, save the figure.
    A string is appended to the default filename.
    Infer the filetype if ending on {`'.pdf'`, `'.png'`, `'.svg'`}.

  **ax** 
  : A matplotlib axes object. Only works if plotting a single component.
* **Return type:**
  [`Axes`](https://matplotlib.org/stable/api/_as_gen/matplotlib.axes.Axes.html#matplotlib.axes.Axes) | [`list`](https://docs.python.org/3/library/stdtypes.html#list)[[`Axes`](https://matplotlib.org/stable/api/_as_gen/matplotlib.axes.Axes.html#matplotlib.axes.Axes)] | [`None`](https://docs.python.org/3/library/constants.html#None)
* **Returns:**
  If `show==False` a [`Axes`](https://matplotlib.org/stable/api/_as_gen/matplotlib.axes.Axes.html#matplotlib.axes.Axes) or a list of it.

