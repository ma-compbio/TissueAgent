# squidpy.pl.co_occurrence

### squidpy.pl.co_occurrence(adata, cluster_key, palette=None, clusters=None, figsize=None, dpi=None, save=None, legend_kwargs=mappingproxy({}), \*\*kwargs)

Plot co-occurrence probability ratio for each cluster.

The co-occurrence is computed by [`squidpy.gr.co_occurrence()`](squidpy.gr.co_occurrence.md#squidpy.gr.co_occurrence).

* **Parameters:**
  * **adata** ([`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData)) – Annotated data object.
  * **cluster_key** ([`str`](https://docs.python.org/3/library/stdtypes.html#str)) – Key in [`anndata.AnnData.obs`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obs.html#anndata.AnnData.obs) where clustering is stored.
  * **clusters** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`Sequence`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Sequence)[[`str`](https://docs.python.org/3/library/stdtypes.html#str)] | [`None`](https://docs.python.org/3/library/constants.html#None)) – Cluster instances for which to plot conditional probability.
  * **palette** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`ListedColormap`](https://matplotlib.org/stable/api/_as_gen/matplotlib.colors.ListedColormap.html#matplotlib.colors.ListedColormap) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Categorical colormap for the clusters.
    If `None`, use [`anndata.AnnData.uns`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.uns.html#anndata.AnnData.uns) `['{cluster_key}_colors']`, if available.
  * **figsize** ([`tuple`](https://docs.python.org/3/library/stdtypes.html#tuple)[[`float`](https://docs.python.org/3/library/functions.html#float), [`float`](https://docs.python.org/3/library/functions.html#float)] | [`None`](https://docs.python.org/3/library/constants.html#None)) – Size of the figure in inches.
  * **dpi** ([`int`](https://docs.python.org/3/library/functions.html#int) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Dots per inch.
  * **save** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`Path`](https://docs.python.org/3/library/pathlib.html#pathlib.Path) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Whether to save the plot.
  * **scalebar_kwargs** – Keyword arguments for `matplotlib_scalebar.ScaleBar()`.
  * **edges_kwargs** – Keyword arguments for `networkx.draw_networkx_edges()`.
  * **kwargs** ([`Any`](https://docs.python.org/3/library/typing.html#typing.Any)) – Keyword arguments for [`matplotlib.pyplot.scatter()`](https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.scatter.html#matplotlib.pyplot.scatter) or [`matplotlib.pyplot.imshow()`](https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.imshow.html#matplotlib.pyplot.imshow).
  * **legend_kwargs** ([`Mapping`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping)[[`str`](https://docs.python.org/3/library/stdtypes.html#str), [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]) – Keyword arguments for [`matplotlib.pyplot.legend()`](https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.legend.html#matplotlib.pyplot.legend).
  * **kwargs** – Keyword arguments for [`seaborn.lineplot()`](https://seaborn.pydata.org/generated/seaborn.lineplot.html#seaborn.lineplot).
* **Return type:**
  [`None`](https://docs.python.org/3/library/constants.html#None)
* **Returns:**
  :
  Nothing, just plots the figure and optionally saves the plot.
