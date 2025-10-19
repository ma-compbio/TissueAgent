# squidpy.pl.interaction_matrix

### squidpy.pl.interaction_matrix(adata, cluster_key, annotate=False, method=None, title=None, cmap='viridis', palette=None, cbar_kwargs=mappingproxy({}), figsize=None, dpi=None, save=None, ax=None, \*\*kwargs)

Plot cluster interaction matrix.

The interaction matrix is computed by [`squidpy.gr.interaction_matrix()`](squidpy.gr.interaction_matrix.md#squidpy.gr.interaction_matrix).

* **Parameters:**
  * **adata** ([`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData)) – Annotated data object.
  * **cluster_key** ([`str`](https://docs.python.org/3/library/stdtypes.html#str)) – Key in [`anndata.AnnData.obs`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obs.html#anndata.AnnData.obs) where clustering is stored.
  * **annotate** ([`bool`](https://docs.python.org/3/library/functions.html#bool)) – Whether to annotate the cells of the heatmap.
  * **method** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`None`](https://docs.python.org/3/library/constants.html#None)) – The linkage method to be used for dendrogram/clustering, see [`scipy.cluster.hierarchy.linkage()`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.cluster.hierarchy.linkage.html#scipy.cluster.hierarchy.linkage).
  * **title** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`None`](https://docs.python.org/3/library/constants.html#None)) – The title of the plot.
  * **cmap** ([`str`](https://docs.python.org/3/library/stdtypes.html#str)) – Continuous colormap to use.
  * **cbar_kwargs** ([`Mapping`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping)[[`str`](https://docs.python.org/3/library/stdtypes.html#str), [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]) – Keyword arguments for [`matplotlib.figure.Figure.colorbar()`](https://matplotlib.org/stable/api/_as_gen/matplotlib.figure.Figure.colorbar.html#matplotlib.figure.Figure.colorbar).
  * **palette** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`ListedColormap`](https://matplotlib.org/stable/api/_as_gen/matplotlib.colors.ListedColormap.html#matplotlib.colors.ListedColormap) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Categorical colormap for the clusters.
    If None, use [`anndata.AnnData.uns`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.uns.html#anndata.AnnData.uns) `['{cluster_key}_colors']`, if available.
  * **figsize** ([`tuple`](https://docs.python.org/3/library/stdtypes.html#tuple)[[`float`](https://docs.python.org/3/library/functions.html#float), [`float`](https://docs.python.org/3/library/functions.html#float)] | [`None`](https://docs.python.org/3/library/constants.html#None)) – Size of the figure in inches.
  * **dpi** ([`int`](https://docs.python.org/3/library/functions.html#int) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Dots per inch.
  * **save** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`Path`](https://docs.python.org/3/library/pathlib.html#pathlib.Path) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Whether to save the plot.
  * **ax** ([`Axes`](https://matplotlib.org/stable/api/_as_gen/matplotlib.axes.Axes.html#matplotlib.axes.Axes) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Axes, [`matplotlib.axes.Axes`](https://matplotlib.org/stable/api/_as_gen/matplotlib.axes.Axes.html#matplotlib.axes.Axes).
  * **kwargs** ([`Any`](https://docs.python.org/3/library/typing.html#typing.Any)) – Keyword arguments for [`matplotlib.pyplot.text()`](https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.text.html#matplotlib.pyplot.text).
* **Return type:**
  [`None`](https://docs.python.org/3/library/constants.html#None)
* **Returns:**
  :
  Nothing, just plots the figure and optionally saves the plot.
