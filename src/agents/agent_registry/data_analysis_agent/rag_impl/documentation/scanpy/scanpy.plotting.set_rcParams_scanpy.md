## scanpy.plotting.set_rcParams_scanpy(fontsize=14, color_map=None)
Set matplotlib.rcParams to Scanpy defaults.

Call this through `settings.set_figure_params`.

### *class* scanpy.plotting.StackedViolin(adata, var_names, groupby, \*, use_raw=None, log=False, num_categories=7, categories_order=None, title=None, figsize=None, gene_symbols=None, var_group_positions=None, var_group_labels=None, var_group_rotation=None, layer=None, standard_scale=None, ax=None, vmin=None, vmax=None, vcenter=None, norm=None, \*\*kwds)

Bases: `BasePlot`

Stacked violin plots.

Makes a compact image composed of individual violin plots
(from [`violinplot()`](https://seaborn.pydata.org/generated/seaborn.violinplot.html#seaborn.violinplot)) stacked on top of each other.
Useful to visualize gene expression per cluster.

Wraps [`seaborn.violinplot()`](https://seaborn.pydata.org/generated/seaborn.violinplot.html#seaborn.violinplot) for [`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData).

* **Parameters:**
  **adata** 
  : Annotated data matrix.

  **var_names** 
  : `var_names` should be a valid subset of `adata.var_names`.
    If `var_names` is a mapping, then the key is used as label
    to group the values (see `var_group_labels`). The mapping values
    should be sequences of valid `adata.var_names`. In this
    case either coloring or ‘brackets’ are used for the grouping
    of var names depending on the plot. When `var_names` is a mapping,
    then the `var_group_labels` and `var_group_positions` are set.

  **groupby** 
  : The key of the observation grouping to consider.

  **use_raw** 
  : Use `raw` attribute of `adata` if present.

  **log** 
  : Plot on logarithmic axis.

  **num_categories** 
  : Only used if groupby observation is not categorical. This value
    determines the number of groups into which the groupby observation
    should be subdivided.

  **categories_order** 
  : Order in which to show the categories. Note: add_dendrogram or add_totals
    can change the categories order.

  **figsize** 
  : Figure size when `multi_panel=True`.
    Otherwise the `rcParam['figure.figsize]` value is used.
    Format is (width, height)

  **dendrogram**
  : If True or a valid dendrogram key, a dendrogram based on the hierarchical
    clustering between the `groupby` categories is added.
    The dendrogram information is computed using `scanpy.tl.dendrogram()`.
    If `tl.dendrogram` has not been called previously the function is called
    with default parameters.

  **gene_symbols** 
  : Column name in `.var` DataFrame that stores gene symbols.
    By default `var_names` refer to the index column of the `.var` DataFrame.
    Setting this option allows alternative names to be used.

  **var_group_positions** 
  : Use this parameter to highlight groups of `var_names`.
    This will draw a ‘bracket’ or a color block between the given start and end
    positions. If the parameter `var_group_labels` is set, the corresponding
    labels are added on top/left. E.g. `var_group_positions=[(4,10)]`
    will add a bracket between the fourth `var_name` and the tenth `var_name`.
    By giving more positions, more brackets/color blocks are drawn.

  **var_group_labels** 
  : Labels for each of the `var_group_positions` that want to be highlighted.

  **var_group_rotation** 
  : Label rotation degrees.
    By default, labels larger than 4 characters are rotated 90 degrees.

  **layer** 
  : Name of the AnnData object layer that wants to be plotted. By default adata.raw.X is plotted.
    If `use_raw=False` is set, then `adata.X` is plotted. If `layer` is set to a valid layer name,
    then the layer is plotted. `layer` takes precedence over `use_raw`.

  **title** 
  : Title for the figure

  **stripplot**
  : Add a stripplot on top of the violin plot.
    See [`stripplot()`](https://seaborn.pydata.org/generated/seaborn.stripplot.html#seaborn.stripplot).

  **jitter**
  : Add jitter to the stripplot (only when stripplot is True)
    See [`stripplot()`](https://seaborn.pydata.org/generated/seaborn.stripplot.html#seaborn.stripplot).

  **size**
  : Size of the jitter points.

  **order**
  : Order in which to show the categories. Note: if `dendrogram=True`
    the categories order will be given by the dendrogram and `order`
    will be ignored.

  **density_norm**
  : The method used to scale the width of each violin.
    If ‘width’ (the default), each violin will have the same width.
    If ‘area’, each violin will have the same area.
    If ‘count’, a violin’s width corresponds to the number of observations.

  **row_palette**
  : The row palette determines the colors to use for the stacked violins.
    The value should be a valid seaborn or matplotlib palette name
    (see [`color_palette()`](https://seaborn.pydata.org/generated/seaborn.color_palette.html#seaborn.color_palette)).
    Alternatively, a single color name or hex value can be passed,
    e.g. `'red'` or `'#cc33ff'`.

  **standard_scale** 
  : Whether or not to standardize a dimension between 0 and 1,
    meaning for each variable or observation,
    subtract the minimum and divide each by its maximum.

  **swap_axes**
  : By default, the x axis contains `var_names` (e.g. genes) and the y axis
    the `groupby` categories. By setting `swap_axes` then x are the `groupby`
    categories and y the `var_names`. When swapping
    axes var_group_positions are no longer used

  **kwds**
  : Are passed to [`violinplot()`](https://seaborn.pydata.org/generated/seaborn.violinplot.html#seaborn.violinplot).

#### SEE ALSO
`stacked_violin()`
: simpler way to call StackedViolin but with less options.

`violin()`
: to plot marker genes identified using `rank_genes_groups()`

### Examples

```pycon
>>> import scanpy as sc
>>> adata = sc.datasets.pbmc68k_reduced()
>>> markers = ["C1QA", "PSAP", "CD79A", "CD79B", "CST3", "LYZ"]
>>> sc.pl.StackedViolin(
...     adata, markers, groupby="bulk_labels", dendrogram=True
... )  
<scanpy.plotting._stacked_violin.StackedViolin object at 0x...>
```

Using var_names as dict:

```pycon
>>> markers = {"T-cell": "CD3D", "B-cell": "CD79A", "myeloid": "CST3"}
>>> sc.pl.StackedViolin(
...     adata, markers, groupby="bulk_labels", dendrogram=True
... )  
<scanpy.plotting._stacked_violin.StackedViolin object at 0x...>
```

#### DEFAULT_SAVE_PREFIX *= 'stacked_violin_'*

#### DEFAULT_COLOR_LEGEND_TITLE *= 'Median expression\\nin group'*

#### DEFAULT_COLORMAP *= 'Blues'*

#### DEFAULT_STRIPPLOT *= False*

#### DEFAULT_JITTER *= False*

#### DEFAULT_JITTER_SIZE *= 1*

#### DEFAULT_LINE_WIDTH *= 0.2*

#### DEFAULT_ROW_PALETTE *= None*

#### DEFAULT_DENSITY_NORM *: DensityNorm* *= 'width'*

#### DEFAULT_PLOT_YTICKLABELS *= False*

#### DEFAULT_YLIM *= None*

#### DEFAULT_PLOT_X_PADDING *= 0.5*

#### DEFAULT_PLOT_Y_PADDING *= 0.5*

#### DEFAULT_CUT *= 0*

#### DEFAULT_INNER *= None*

#### style(\*, cmap=\_empty, stripplot=\_empty, jitter=\_empty, jitter_size=\_empty, linewidth=\_empty, row_palette=\_empty, density_norm=\_empty, yticklabels=\_empty, ylim=\_empty, x_padding=\_empty, y_padding=\_empty, scale=\_empty)

Modify plot visual parameters.

* **Parameters:**
  **cmap** 
  : Matplotlib color map, specified by name or directly.
    If `None`, use [`matplotlib.rcParams`](https://matplotlib.org/stable/api/matplotlib_configuration_api.html#matplotlib.rcParams)`["image.cmap"]`

  **stripplot** 
  : Add a stripplot on top of the violin plot.
    See [`stripplot()`](https://seaborn.pydata.org/generated/seaborn.stripplot.html#seaborn.stripplot).

  **jitter** 
  : Add jitter to the stripplot (only when stripplot is True)
    See [`stripplot()`](https://seaborn.pydata.org/generated/seaborn.stripplot.html#seaborn.stripplot).

  **jitter_size** 
  : Size of the jitter points.

  **linewidth** 
  : line width for the violin plots.
    If None, use [`matplotlib.rcParams`](https://matplotlib.org/stable/api/matplotlib_configuration_api.html#matplotlib.rcParams)`["lines.linewidth"]`

  **row_palette** 
  : The row palette determines the colors to use for the stacked violins.
    If `None`, use [`matplotlib.rcParams`](https://matplotlib.org/stable/api/matplotlib_configuration_api.html#matplotlib.rcParams)`["axes.prop_cycle"]`
    The value should be a valid seaborn or matplotlib palette name
    (see [`color_palette()`](https://seaborn.pydata.org/generated/seaborn.color_palette.html#seaborn.color_palette)).
    Alternatively, a single color name or hex value can be passed,
    e.g. `'red'` or `'#cc33ff'`.

  **density_norm** 
  : The method used to scale the width of each violin.
    If ‘width’ (the default), each violin will have the same width.
    If ‘area’, each violin will have the same area.
    If ‘count’, a violin’s width corresponds to the number of observations.

  **yticklabels** 
  : Set to true to view the y tick labels.

  **ylim** 
  : minimum and maximum values for the y-axis.
    If not `None`, all rows will have the same y-axis range.
    Example: `ylim=(0, 5)`

  **x_padding** 
  : Space between the plot left/right borders and the violins. A unit
    is the distance between the x ticks.

  **y_padding** 
  : Space between the plot top/bottom borders and the violins. A unit is
    the distance between the y ticks.
* **Return type:**
  `Self`
* **Returns:**
  `StackedViolin`

### Examples

```pycon
>>> import scanpy as sc
>>> adata = sc.datasets.pbmc68k_reduced()
>>> markers = ['C1QA', 'PSAP', 'CD79A', 'CD79B', 'CST3', 'LYZ']
```

Change color map and turn off edges

```pycon
>>> sc.pl.StackedViolin(adata, markers, groupby='bulk_labels') \
...     .style(row_palette='Blues', linewidth=0).show()
```

#### getdoc() → [str](https://docs.python.org/3/library/stdtypes.html#str) | [None](https://docs.python.org/3/library/constants.html#None)

