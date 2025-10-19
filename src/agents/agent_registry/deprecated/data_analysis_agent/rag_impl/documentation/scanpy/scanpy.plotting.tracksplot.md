## scanpy.plotting.tracksplot(adata, var_names, groupby, \*, use_raw=None, log=False, dendrogram=False, gene_symbols=None, var_group_positions=None, var_group_labels=None, layer=None, show=None, save=None, figsize=None, \*\*kwds)
Compact plot of expression of a list of genes.

In this type of plot each var_name is plotted as a filled line plot where the
y values correspond to the var_name values and x is each of the cells. Best results
are obtained when using raw counts that are not log.

`groupby` is required to sort and order the values using the respective group
and should be a categorical value.

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

  **show** 
  : Show the plot, do not return axis.

  **save** 
  : If `True` or a `str`, save the figure.
    A string is appended to the default filename.
    Infer the filetype if ending on {`'.pdf'`, `'.png'`, `'.svg'`}.

  **ax**
  : A matplotlib axes object. Only works if plotting a single component.

  **\*\*kwds**
  : Are passed to [`heatmap()`](https://seaborn.pydata.org/generated/seaborn.heatmap.html#seaborn.heatmap).
* **Return type:**
  [`dict`](https://docs.python.org/3/library/stdtypes.html#dict)[[`str`](https://docs.python.org/3/library/stdtypes.html#str), [`Axes`](https://matplotlib.org/stable/api/_as_gen/matplotlib.axes.Axes.html#matplotlib.axes.Axes)] | [`None`](https://docs.python.org/3/library/constants.html#None)
* **Returns:**
  A list of [`Axes`](https://matplotlib.org/stable/api/_as_gen/matplotlib.axes.Axes.html#matplotlib.axes.Axes).

### Examples

Using var_names as list:

```python
import scanpy as sc
adata = sc.datasets.pbmc68k_reduced()
markers = ['C1QA', 'PSAP', 'CD79A', 'CD79B', 'CST3', 'LYZ']
sc.pl.tracksplot(adata, markers, groupby='bulk_labels', dendrogram=True)
```

![image](_build/markdown/plot_directive/api/scanpy-plotting-5.*)

Using var_names as dict:

```python
markers = {'T-cell': 'CD3D', 'B-cell': 'CD79A', 'myeloid': 'CST3'}
sc.pl.tracksplot(adata, markers, groupby='bulk_labels', dendrogram=True)
```

![image](_build/markdown/plot_directive/api/scanpy-plotting-6.*)

#### SEE ALSO
`pl.rank_genes_groups_tracksplot`
: to plot marker genes identified using the `rank_genes_groups()` function.

