## scanpy.plotting.dotplot(adata, var_names, groupby, \*, use_raw=None, log=False, num_categories=7, categories_order=None, expression_cutoff=0.0, mean_only_expressed=False, standard_scale=None, title=None, colorbar_title='Mean expression\\\\nin group', size_title='Fraction of cells\\\\nin group (%)', figsize=None, dendrogram=False, gene_symbols=None, var_group_positions=None, var_group_labels=None, var_group_rotation=None, layer=None, swap_axes=False, dot_color_df=None, show=None, save=None, ax=None, return_fig=False, vmin=None, vmax=None, vcenter=None, norm=None, cmap='Reds', dot_max=None, dot_min=None, smallest_dot=0.0, \*\*kwds)
Make a *dot plot* of the expression values of `var_names`.

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
across  multiple clusters.

This function provides a convenient interface to the `DotPlot`
class. If you need more flexibility, you should use `DotPlot`
directly.

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

  **colorbar_title** 
  : Title for the color bar. New line character (n) can be used.

  **cmap** 
  : String denoting matplotlib color map.

  **standard_scale** 
  : Whether or not to standardize the given dimension between 0 and 1, meaning for
    each variable or group, subtract the minimum and divide each by its maximum.

  **swap_axes** 
  : By default, the x axis contains `var_names` (e.g. genes) and the y axis
    the `groupby` categories. By setting `swap_axes` then x are the
    `groupby` categories and y the `var_names`.

  **return_fig** 
  : Returns [`DotPlot`](#scanpy.plotting.DotPlot) object. Useful for fine-tuning
    the plot. Takes precedence over `show=False`.

  **size_title** 
  : Title for the size legend. New line character (n) can be used.

  **expression_cutoff** 
  : Expression cutoff that is used for binarizing the gene expression and
    determining the fraction of cells expressing given genes. A gene is
    expressed only if the expression value is greater than this threshold.

  **mean_only_expressed** 
  : If True, gene expression is averaged only over the cells
    expressing the given genes.

  **dot_max** 
  : If `None`, the maximum dot size is set to the maximum fraction value found
    (e.g. 0.6). If given, the value should be a number between 0 and 1.
    All fractions larger than dot_max are clipped to this value.

  **dot_min** 
  : If `None`, the minimum dot size is set to 0. If given,
    the value should be a number between 0 and 1.
    All fractions smaller than dot_min are clipped to this value.

  **smallest_dot** 
  : All expression levels with `dot_min` are plotted with this size.

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

  **kwds**
  : Are passed to [`matplotlib.pyplot.scatter()`](https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.scatter.html#matplotlib.pyplot.scatter).
* **Return type:**
  `DotPlot` | [`dict`](https://docs.python.org/3/library/stdtypes.html#dict) | [`None`](https://docs.python.org/3/library/constants.html#None)
* **Returns:**
  If `return_fig` is `True`, returns a `DotPlot` object,
  else if `show` is false, return axes dict

#### SEE ALSO
`DotPlot`
: The DotPlot class can be used to to control several visual parameters not available in this function.

`rank_genes_groups_dotplot()`
: to plot marker genes identified using the `rank_genes_groups()` function.

### Examples

Create a dot plot using the given markers and the PBMC example dataset grouped by
the category ‘bulk_labels’.

```python
import scanpy as sc
adata = sc.datasets.pbmc68k_reduced()
markers = ['C1QA', 'PSAP', 'CD79A', 'CD79B', 'CST3', 'LYZ']
sc.pl.dotplot(adata, markers, groupby='bulk_labels', dendrogram=True)
```

![image](_build/markdown/plot_directive/api/scanpy-plotting-12.*)

Using var_names as dict:

```python
markers = {'T-cell': 'CD3D', 'B-cell': 'CD79A', 'myeloid': 'CST3'}
sc.pl.dotplot(adata, markers, groupby='bulk_labels', dendrogram=True)
```

![image](_build/markdown/plot_directive/api/scanpy-plotting-13.*)

Get DotPlot object for fine tuning

```python
dp = sc.pl.dotplot(adata, markers, 'bulk_labels', return_fig=True)
dp.add_totals().style(dot_edge_color='black', dot_edge_lw=0.5).show()
```

![image](_build/markdown/plot_directive/api/scanpy-plotting-14.*)

The axes used can be obtained using the get_axes() method

```python
axes_dict = dp.get_axes()
print(axes_dict)
```

### *class* scanpy.plotting.MatrixPlot(adata, var_names, groupby, \*, use_raw=None, log=False, num_categories=7, categories_order=None, title=None, figsize=None, gene_symbols=None, var_group_positions=None, var_group_labels=None, var_group_rotation=None, layer=None, standard_scale=None, ax=None, values_df=None, vmin=None, vmax=None, vcenter=None, norm=None, \*\*kwds)

Bases: `BasePlot`

Allows the visualization of values using a color map.

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
  : Title for the figure.

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

  **values_df** 
  : Optionally, a dataframe with the values to plot can be given. The
    index should be the grouby categories and the columns the genes names.

  **kwds**
  : Are passed to [`matplotlib.pyplot.scatter()`](https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.scatter.html#matplotlib.pyplot.scatter).

#### SEE ALSO
`matrixplot()`
: Simpler way to call MatrixPlot but with less options.

`rank_genes_groups_matrixplot()`
: to plot marker genes identified using the `rank_genes_groups()` function.

### Examples

Simple visualization of the average expression of a few genes grouped by
the category ‘bulk_labels’.

```python
import scanpy as sc
adata = sc.datasets.pbmc68k_reduced()
markers = ['C1QA', 'PSAP', 'CD79A', 'CD79B', 'CST3', 'LYZ']
sc.pl.MatrixPlot(adata, markers, groupby='bulk_labels').show()
```

![image](_build/markdown/plot_directive/api/scanpy-plotting-15.*)

Same visualization but passing var_names as dict, which adds a grouping of
the genes on top of the image:

```python
markers = {'T-cell': 'CD3D', 'B-cell': 'CD79A', 'myeloid': 'CST3'}
sc.pl.MatrixPlot(adata, markers, groupby='bulk_labels').show()
```

![image](_build/markdown/plot_directive/api/scanpy-plotting-16.*)

#### DEFAULT_SAVE_PREFIX *= 'matrixplot_'*

#### DEFAULT_COLOR_LEGEND_TITLE *= 'Mean expression\\nin group'*

#### DEFAULT_COLORMAP *= 'viridis'*

#### DEFAULT_EDGE_COLOR *= 'gray'*

#### DEFAULT_EDGE_LW *= 0.1*

#### style(cmap=\_empty, edge_color=\_empty, edge_lw=\_empty)

Modify plot visual parameters.

* **Parameters:**
  **cmap** 
  : Matplotlib color map, specified by name or directly.
    If `None`, use [`matplotlib.rcParams`](https://matplotlib.org/stable/api/matplotlib_configuration_api.html#matplotlib.rcParams)`["image.cmap"]`

  **edge_color** 
  : Edge color between the squares of matrix plot.
    If `None`, use [`matplotlib.rcParams`](https://matplotlib.org/stable/api/matplotlib_configuration_api.html#matplotlib.rcParams)`["patch.edgecolor"]`

  **edge_lw** 
  : Edge line width.
    If `None`, use [`matplotlib.rcParams`](https://matplotlib.org/stable/api/matplotlib_configuration_api.html#matplotlib.rcParams)`["lines.linewidth"]`
* **Return type:**
  `Self`
* **Returns:**
  `MatrixPlot`

### Examples

```python
import scanpy as sc

adata = sc.datasets.pbmc68k_reduced()
markers = ['C1QA', 'PSAP', 'CD79A', 'CD79B', 'CST3', 'LYZ']
```

Change color map and turn off edges:

```python
(
    sc.pl.MatrixPlot(adata, markers, groupby='bulk_labels')
    .style(cmap='Blues', edge_color='none')
    .show()
)
```

![image](_build/markdown/plot_directive/api/scanpy-plotting-18.*)

#### getdoc() → [str](https://docs.python.org/3/library/stdtypes.html#str) | [None](https://docs.python.org/3/library/constants.html#None)

