## scanpy.plotting.violin(adata, keys, groupby=None, \*, log=False, use_raw=None, stripplot=True, jitter=True, size=1, layer=None, density_norm='width', order=None, multi_panel=None, xlabel='', ylabel=None, rotation=None, show=None, save=None, ax=None, scale=\_empty, \*\*kwds)
Violin plot.

Wraps [`seaborn.violinplot()`](https://seaborn.pydata.org/generated/seaborn.violinplot.html#seaborn.violinplot) for [`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData).

* **Parameters:**
  **adata** 
  : Annotated data matrix.

  **keys** 
  : Keys for accessing variables of `.var_names` or fields of `.obs`.

  **groupby** 
  : The key of the observation grouping to consider.

  **log** 
  : Plot on logarithmic axis.

  **use_raw** 
  : Whether to use `raw` attribute of `adata`. Defaults to `True` if `.raw` is present.

  **stripplot** 
  : Add a stripplot on top of the violin plot.
    See [`stripplot()`](https://seaborn.pydata.org/generated/seaborn.stripplot.html#seaborn.stripplot).

  **jitter** 
  : Add jitter to the stripplot (only when stripplot is True)
    See [`stripplot()`](https://seaborn.pydata.org/generated/seaborn.stripplot.html#seaborn.stripplot).

  **size** 
  : Size of the jitter points.

  **layer** 
  : Name of the AnnData object layer that wants to be plotted. By
    default adata.raw.X is plotted. If `use_raw=False` is set,
    then `adata.X` is plotted. If `layer` is set to a valid layer name,
    then the layer is plotted. `layer` takes precedence over `use_raw`.

  **density_norm** 
  : The method used to scale the width of each violin.
    If ‘width’ (the default), each violin will have the same width.
    If ‘area’, each violin will have the same area.
    If ‘count’, a violin’s width corresponds to the number of observations.

  **order** 
  : Order in which to show the categories.

  **multi_panel** 
  : Display keys in multiple panels also when `groupby is not None`.

  **xlabel** 
  : Label of the x axis. Defaults to `groupby` if `rotation` is `None`,
    otherwise, no label is shown.

  **ylabel** 
  : Label of the y axis. If `None` and `groupby` is `None`, defaults
    to `'value'`. If `None` and `groubpy` is not `None`, defaults to `keys`.

  **rotation** 
  : Rotation of xtick labels.

  **show** 
  : Show the plot, do not return axis.

  **save** 
  : If `True` or a `str`, save the figure.
    A string is appended to the default filename.
    Infer the filetype if ending on {`'.pdf'`, `'.png'`, `'.svg'`}.

  **ax** 
  : A matplotlib axes object. Only works if plotting a single component.

  **\*\*kwds**
  : Are passed to [`violinplot()`](https://seaborn.pydata.org/generated/seaborn.violinplot.html#seaborn.violinplot).
* **Return type:**
  [`Axes`](https://matplotlib.org/stable/api/_as_gen/matplotlib.axes.Axes.html#matplotlib.axes.Axes) | [`FacetGrid`](https://seaborn.pydata.org/generated/seaborn.FacetGrid.html#seaborn.FacetGrid) | [`None`](https://docs.python.org/3/library/constants.html#None)
* **Returns:**
  A [`Axes`](https://matplotlib.org/stable/api/_as_gen/matplotlib.axes.Axes.html#matplotlib.axes.Axes) object if `ax` is `None` else `None`.

### Examples

```python
import scanpy as sc
adata = sc.datasets.pbmc68k_reduced()
sc.pl.violin(adata, keys='S_score')
```

![image](_build/markdown/plot_directive/api/scanpy-plotting-7.*)

Plot by category. Rotate x-axis labels so that they do not overlap.

```python
sc.pl.violin(adata, keys='S_score', groupby='bulk_labels', rotation=90)
```

![image](_build/markdown/plot_directive/api/scanpy-plotting-8.*)

Set order of categories to be plotted or select specific categories to be plotted.

```python
groupby_order = ['CD34+', 'CD19+ B']
sc.pl.violin(adata, keys='S_score', groupby='bulk_labels', rotation=90,
    order=groupby_order)
```

![image](_build/markdown/plot_directive/api/scanpy-plotting-9.*)

Plot multiple keys.

```python
sc.pl.violin(adata, keys=['S_score', 'G2M_score'], groupby='bulk_labels',
    rotation=90)
```

![image](_build/markdown/plot_directive/api/scanpy-plotting-10.*)

For large datasets consider omitting the overlaid scatter plot.

```python
sc.pl.violin(adata, keys='S_score', stripplot=False)
```

![image](_build/markdown/plot_directive/api/scanpy-plotting-11.*)

#### SEE ALSO
`pl.stacked_violin`

### *class* scanpy.plotting.DotPlot(adata, var_names, groupby, \*, use_raw=None, log=False, num_categories=7, categories_order=None, title=None, figsize=None, gene_symbols=None, var_group_positions=None, var_group_labels=None, var_group_rotation=None, layer=None, expression_cutoff=0.0, mean_only_expressed=False, standard_scale=None, dot_color_df=None, dot_size_df=None, ax=None, vmin=None, vmax=None, vcenter=None, norm=None, \*\*kwds)

Bases: `BasePlot`

Allows the visualization of two values that are encoded as dot size and color.

The size usually represents the fraction of cells (obs)
that have a non-zero value for genes (var).

For each var_name and each `groupby` category a dot is plotted.
Each dot represents two values: mean expression within each category
(visualized by color) and fraction of cells expressing the `var_name` in the
category (visualized by the size of the dot). If `groupby` is not given,
the dotplot assumes that all data belongs to a single category.

#### NOTE
A gene is considered expressed if the expression value in the `adata` (or
`adata.raw`) is above the specified threshold which is zero by default.

An example of dotplot usage is to visualize, for multiple marker genes,
the mean value and the percentage of cells expressing the gene
across multiple clusters.

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

  **expression_cutoff** 
  : Expression cutoff that is used for binarizing the gene expression and
    determining the fraction of cells expressing given genes. A gene is
    expressed only if the expression value is greater than this threshold.

  **mean_only_expressed** 
  : If True, gene expression is averaged only over the cells
    expressing the given genes.

  **standard_scale** 
  : Whether or not to standardize that dimension between 0 and 1,
    meaning for each variable or group,
    subtract the minimum and divide each by its maximum.

  **kwds**
  : Are passed to [`matplotlib.pyplot.scatter()`](https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.scatter.html#matplotlib.pyplot.scatter).

#### SEE ALSO
`dotplot()`
: Simpler way to call DotPlot but with less options.

`rank_genes_groups_dotplot()`
: to plot marker genes identified using the `rank_genes_groups()` function.

### Examples

```pycon
>>> import scanpy as sc
>>> adata = sc.datasets.pbmc68k_reduced()
>>> markers = ["C1QA", "PSAP", "CD79A", "CD79B", "CST3", "LYZ"]
>>> sc.pl.DotPlot(adata, markers, groupby="bulk_labels").show()
```

Using var_names as dict:

```pycon
>>> markers = {"T-cell": "CD3D", "B-cell": "CD79A", "myeloid": "CST3"}
>>> sc.pl.DotPlot(adata, markers, groupby="bulk_labels").show()
```

#### DEFAULT_SAVE_PREFIX *= 'dotplot_'*

#### DEFAULT_COLORMAP *= 'Reds'*

#### DEFAULT_COLOR_ON *= 'dot'*

#### DEFAULT_DOT_MAX *= None*

#### DEFAULT_DOT_MIN *= None*

#### DEFAULT_SMALLEST_DOT *= 0.0*

#### DEFAULT_LARGEST_DOT *= 200.0*

#### DEFAULT_DOT_EDGECOLOR *= 'black'*

#### DEFAULT_DOT_EDGELW *= 0.2*

#### DEFAULT_SIZE_EXPONENT *= 1.5*

#### DEFAULT_SIZE_LEGEND_TITLE *= 'Fraction of cells\\nin group (%)'*

#### DEFAULT_COLOR_LEGEND_TITLE *= 'Mean expression\\nin group'*

#### DEFAULT_LEGENDS_WIDTH *= 1.5*

#### DEFAULT_PLOT_X_PADDING *= 0.8*

#### DEFAULT_PLOT_Y_PADDING *= 1.0*

#### style(\*, cmap=\_empty, color_on=\_empty, dot_max=\_empty, dot_min=\_empty, smallest_dot=\_empty, largest_dot=\_empty, dot_edge_color=\_empty, dot_edge_lw=\_empty, size_exponent=\_empty, grid=\_empty, x_padding=\_empty, y_padding=\_empty)

Modify plot visual parameters.

* **Parameters:**
  **cmap** 
  : String denoting matplotlib color map.

  **color_on** 
  : By default the color map is applied to the color of the `"dot"`.
    Optionally, the colormap can be applied to a `"square"` behind the dot,
    in which case the dot is transparent and only the edge is shown.

  **dot_max** 
  : If `None`, the maximum dot size is set to the maximum fraction value found (e.g. 0.6).
    If given, the value should be a number between 0 and 1.
    All fractions larger than dot_max are clipped to this value.

  **dot_min** 
  : If `None`, the minimum dot size is set to 0.
    If given, the value should be a number between 0 and 1.
    All fractions smaller than dot_min are clipped to this value.

  **smallest_dot** 
  : All expression fractions with `dot_min` are plotted with this size.

  **largest_dot** 
  : All expression fractions with `dot_max` are plotted with this size.

  **dot_edge_color** 
  : Dot edge color.
    When `color_on='dot'`, `None` means no edge.
    When `color_on='square'`, `None` means that
    the edge color is white for darker colors and black for lighter background square colors.

  **dot_edge_lw** 
  : Dot edge line width.
    When `color_on='dot'`, `None` means no edge.
    When `color_on='square'`, `None` means a line width of 1.5.

  **size_exponent** 
  : Dot size is computed as:
    fraction  \*\* size exponent and afterwards scaled to match the
    `smallest_dot` and `largest_dot` size parameters.
    Using a different size exponent changes the relative sizes of the dots
    to each other.

  **grid** 
  : Set to true to show grid lines. By default grid lines are not shown.
    Further configuration of the grid lines can be achieved directly on the
    returned ax.

  **x_padding** 
  : Space between the plot left/right borders and the dots center. A unit
    is the distance between the x ticks. Only applied when color_on = dot

  **y_padding** 
  : Space between the plot top/bottom borders and the dots center. A unit is
    the distance between the y ticks. Only applied when color_on = dot
* **Return type:**
  `Self`
* **Returns:**
  `DotPlot`

### Examples

```pycon
>>> import scanpy as sc
>>> adata = sc.datasets.pbmc68k_reduced()
>>> markers = ['C1QA', 'PSAP', 'CD79A', 'CD79B', 'CST3', 'LYZ']
```

Change color map and apply it to the square behind the dot

```pycon
>>> sc.pl.DotPlot(adata, markers, groupby='bulk_labels') \
...     .style(cmap='RdBu_r', color_on='square').show()
```

Add edge to dots and plot a grid

```pycon
>>> sc.pl.DotPlot(adata, markers, groupby='bulk_labels') \
...     .style(dot_edge_color='black', dot_edge_lw=1, grid=True) \
...     .show()
```

#### legend(\*, show=True, show_size_legend=True, show_colorbar=True, size_title='Fraction of cells\\\\nin group (%)', colorbar_title='Mean expression\\\\nin group', width=1.5)

Configure dot size and the colorbar legends.

* **Parameters:**
  **show** 
  : Set to `False` to hide the default plot of the legends. This sets the
    legend width to zero, which will result in a wider main plot.

  **show_size_legend** 
  : Set to `False` to hide the dot size legend

  **show_colorbar** 
  : Set to `False` to hide the colorbar legend

  **size_title** 
  : Title for the dot size legend. Use `\n` to add line breaks. Appears on top
    of dot sizes

  **colorbar_title** 
  : Title for the color bar. Use `\n` to add line breaks. Appears on top of the
    color bar

  **width** 
  : Width of the legends area. The unit is the same as in matplotlib (inches).
* **Return type:**
  `Self`
* **Returns:**
  `DotPlot`

### Examples

Set color bar title:

```pycon
>>> import scanpy as sc
>>> adata = sc.datasets.pbmc68k_reduced()
>>> markers = {"T-cell": "CD3D", "B-cell": "CD79A", "myeloid": "CST3"}
>>> dp = sc.pl.DotPlot(adata, markers, groupby="bulk_labels")
>>> dp.legend(colorbar_title="log(UMI counts + 1)").show()
```

#### getdoc() → [str](https://docs.python.org/3/library/stdtypes.html#str) | [None](https://docs.python.org/3/library/constants.html#None)

