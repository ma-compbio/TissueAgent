# squidpy.pl.var_by_distance

### squidpy.pl.var_by_distance(adata, var, anchor_key, design_matrix_key='design_matrix', stack_vars=False, covariate=None, order=5, show_scatter=True, color=None, line_palette=None, scatter_palette='viridis', dpi=None, figsize=None, save=None, title=None, axis_label=None, return_ax=None, regplot_kwargs=mappingproxy({}), scatterplot_kwargs=mappingproxy({}))

Plot a variable using a smooth regression line with increasing distance to an anchor point.

* **Parameters:**
  * **adata** ([`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData)) – Annotated data object.
  * **var** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`list`](https://docs.python.org/3/library/stdtypes.html#list)[[`str`](https://docs.python.org/3/library/stdtypes.html#str)]) – Variables to plot on y-axis.
  * **anchor_key** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`list`](https://docs.python.org/3/library/stdtypes.html#list)[[`str`](https://docs.python.org/3/library/stdtypes.html#str)]) – Anchor point column from which distances are taken.
  * **design_matrix_key** ([`str`](https://docs.python.org/3/library/stdtypes.html#str)) – Name of the design matrix, previously computed with [`squidpy.tl.var_by_distance()`](squidpy.tl.var_by_distance.md#squidpy.tl.var_by_distance), to use.
  * **stack_vars** ([`bool`](https://docs.python.org/3/library/functions.html#bool)) – Whether to show multiple variables on the same plot. Only works if ‘covariate’ is not specified.
  * **covariate** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`None`](https://docs.python.org/3/library/constants.html#None)) – A covariate for which separate regression lines are plotted for each category.
  * **order** ([`int`](https://docs.python.org/3/library/functions.html#int)) – Order of the polynomial fit for [`seaborn.regplot()`](https://seaborn.pydata.org/generated/seaborn.regplot.html#seaborn.regplot).
  * **show_scatter** ([`bool`](https://docs.python.org/3/library/functions.html#bool)) – Whether to show a scatter plot underlying the regression line.
  * **color** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Variables in adata.obs to plot if ‘show_scatter==True’.
  * **line_palette** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`Sequence`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Sequence)[[`str`](https://docs.python.org/3/library/stdtypes.html#str)] | `Cycler` | [`None`](https://docs.python.org/3/library/constants.html#None)) – Categorical color palette used in case a covariate is specified.
  * **scatter_palette** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`Sequence`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Sequence)[[`str`](https://docs.python.org/3/library/stdtypes.html#str)] | `Cycler` | [`None`](https://docs.python.org/3/library/constants.html#None)) – Color palette for the scatter plot underlying the [`seaborn.regplot()`](https://seaborn.pydata.org/generated/seaborn.regplot.html#seaborn.regplot).
  * **dpi** ([`int`](https://docs.python.org/3/library/functions.html#int) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Dots per inch.
  * **figsize** ([`tuple`](https://docs.python.org/3/library/stdtypes.html#tuple)[[`int`](https://docs.python.org/3/library/functions.html#int), [`int`](https://docs.python.org/3/library/functions.html#int)] | [`None`](https://docs.python.org/3/library/constants.html#None)) – Size of the figure in inches.
  * **save** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`Path`](https://docs.python.org/3/library/pathlib.html#pathlib.Path) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Whether to save the plot.
  * **title** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Panel titles.
  * **axis_label** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Panel axis labels.
  * **return_ax** ([`bool`](https://docs.python.org/3/library/functions.html#bool) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Whether to return [`matplotlib.axes.Axes`](https://matplotlib.org/stable/api/_as_gen/matplotlib.axes.Axes.html#matplotlib.axes.Axes) object(s).
  * **regplot_kwargs** ([`Mapping`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping)[[`str`](https://docs.python.org/3/library/stdtypes.html#str), [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]) – Kwargs for [`seaborn.regplot()`](https://seaborn.pydata.org/generated/seaborn.regplot.html#seaborn.regplot).
  * **scatterplot_kwargs** ([`Mapping`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping)[[`str`](https://docs.python.org/3/library/stdtypes.html#str), [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]) – Kwargs for [`matplotlib.pyplot.scatter()`](https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.scatter.html#matplotlib.pyplot.scatter).
* **Return type:**
  [`Axes`](https://matplotlib.org/stable/api/_as_gen/matplotlib.axes.Axes.html#matplotlib.axes.Axes) | [`None`](https://docs.python.org/3/library/constants.html#None)
* **Returns:**
  :
  Nothing, just plots the figure and optionally saves the plot.
