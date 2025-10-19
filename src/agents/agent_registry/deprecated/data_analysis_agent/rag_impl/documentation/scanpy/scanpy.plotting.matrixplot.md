## scanpy.plotting.matrixplot(adata, var_names, groupby, \*, use_raw=None, log=False, num_categories=7, categories_order=None, figsize=None, dendrogram=False, title=None, cmap='viridis', colorbar_title='Mean expression\\\\nin group', gene_symbols=None, var_group_positions=None, var_group_labels=None, var_group_rotation=None, layer=None, standard_scale=None, values_df=None, swap_axes=False, show=None, save=None, ax=None, return_fig=False, vmin=None, vmax=None, vcenter=None, norm=None, \*\*kwds)
Create a heatmap of the mean expression values per group of each var_names.

This function provides a convenient interface to the `MatrixPlot`
class. If you need more flexibility, you should use `MatrixPlot`
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
  : Are passed to [`matplotlib.pyplot.pcolor()`](https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.pcolor.html#matplotlib.pyplot.pcolor).
* **Return type:**
  `MatrixPlot` | [`dict`](https://docs.python.org/3/library/stdtypes.html#dict)[[`str`](https://docs.python.org/3/library/stdtypes.html#str), [`Axes`](https://matplotlib.org/stable/api/_as_gen/matplotlib.axes.Axes.html#matplotlib.axes.Axes)] | [`None`](https://docs.python.org/3/library/constants.html#None)
* **Returns:**
  If `return_fig` is `True`, returns a `MatrixPlot` object,
  else if `show` is false, return axes dict

#### SEE ALSO
`MatrixPlot`
: The MatrixPlot class can be used to to control several visual parameters not available in this function.

`rank_genes_groups_matrixplot()`
: to plot marker genes identified using the `rank_genes_groups()` function.

### Examples

```python
import scanpy as sc
adata = sc.datasets.pbmc68k_reduced()
markers = ['C1QA', 'PSAP', 'CD79A', 'CD79B', 'CST3', 'LYZ']
sc.pl.matrixplot(adata, markers, groupby='bulk_labels', dendrogram=True)
```

![image](_build/markdown/plot_directive/api/scanpy-plotting-19.*)

Using var_names as dict:

```python
markers = {'T-cell': 'CD3D', 'B-cell': 'CD79A', 'myeloid': 'CST3'}
sc.pl.matrixplot(adata, markers, groupby='bulk_labels', dendrogram=True)
```

![image](_build/markdown/plot_directive/api/scanpy-plotting-20.*)

Get Matrix object for fine tuning:

```python
mp = sc.pl.matrixplot(adata, markers, 'bulk_labels', return_fig=True)
mp.add_totals().style(edge_color='black').show()
```

![image](_build/markdown/plot_directive/api/scanpy-plotting-21.*)

The axes used can be obtained using the get_axes() method

```python
axes_dict = mp.get_axes()
```

