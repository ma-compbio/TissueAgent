# squidpy.pl.ligrec

### squidpy.pl.ligrec(adata, cluster_key=None, source_groups=None, target_groups=None, means_range=(-inf, inf), pvalue_threshold=1.0, remove_empty_interactions=True, remove_nonsig_interactions=False, dendrogram=None, alpha=0.001, swap_axes=False, title=None, figsize=None, dpi=None, save=None, \*\*kwargs)

Plot the result of a receptor-ligand permutation test.

The result was computed by [`squidpy.gr.ligrec()`](squidpy.gr.ligrec.md#squidpy.gr.ligrec).

$molecule_1$ belongs to the source clusters displayed on the top (or on the right, if `swap_axes = True`,
whereas $molecule_2$ belongs to the target clusters.

* **Parameters:**
  * **adata** ([`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData) | [`Mapping`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping)[[`str`](https://docs.python.org/3/library/stdtypes.html#str), [`DataFrame`](https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.html#pandas.DataFrame)]) – Annotated data object.
    It can also be a [`dict`](https://docs.python.org/3/library/stdtypes.html#dict), as returned by [`squidpy.gr.ligrec()`](squidpy.gr.ligrec.md#squidpy.gr.ligrec).
  * **cluster_key** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Key in [`anndata.AnnData.obs`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obs.html#anndata.AnnData.obs) where clustering is stored.
    Only used when `adata` is of type `AnnData`.
  * **source_groups** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`Sequence`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Sequence)[[`str`](https://docs.python.org/3/library/stdtypes.html#str)] | [`None`](https://docs.python.org/3/library/constants.html#None)) – Source interaction clusters. If None, select all clusters.
  * **target_groups** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`Sequence`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Sequence)[[`str`](https://docs.python.org/3/library/stdtypes.html#str)] | [`None`](https://docs.python.org/3/library/constants.html#None)) – Target interaction clusters. If None, select all clusters.
  * **means_range** ([`tuple`](https://docs.python.org/3/library/stdtypes.html#tuple)[[`float`](https://docs.python.org/3/library/functions.html#float), [`float`](https://docs.python.org/3/library/functions.html#float)]) – Only show interactions whose means are within this **closed** interval.
  * **pvalue_threshold** ([`float`](https://docs.python.org/3/library/functions.html#float)) – Only show interactions with p-value <= `pvalue_threshold`.
  * **remove_empty_interactions** ([`bool`](https://docs.python.org/3/library/functions.html#bool)) – Remove rows and columns that only contain interactions with NaN values.
  * **remove_nonsig_interactions** ([`bool`](https://docs.python.org/3/library/functions.html#bool)) – Remove rows and columns that only contain interactions that are larger than `alpha`.
  * **dendrogram** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`None`](https://docs.python.org/3/library/constants.html#None)) – 

    How to cluster based on the p-values. Valid options are:
    > - None - do not perform clustering.
    > - ’interacting_molecules’ - cluster the interacting molecules.
    > - ’interacting_clusters’ - cluster the interacting clusters.
    > - ’both’ - cluster both rows and columns. Note that in this case, the dendrogram is not shown.
  * **alpha** ([`float`](https://docs.python.org/3/library/functions.html#float) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Significance threshold. All elements with p-values <= `alpha` will be marked by tori instead of dots.
  * **swap_axes** ([`bool`](https://docs.python.org/3/library/functions.html#bool)) – Whether to show the cluster combinations as rows and the interacting pairs as columns.
  * **title** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Title of the plot.
  * **figsize** ([`tuple`](https://docs.python.org/3/library/stdtypes.html#tuple)[[`float`](https://docs.python.org/3/library/functions.html#float), [`float`](https://docs.python.org/3/library/functions.html#float)] | [`None`](https://docs.python.org/3/library/constants.html#None)) – Size of the figure in inches.
  * **dpi** ([`int`](https://docs.python.org/3/library/functions.html#int) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Dots per inch.
  * **save** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`Path`](https://docs.python.org/3/library/pathlib.html#pathlib.Path) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Whether to save the plot.
  * **scalebar_kwargs** – Keyword arguments for `matplotlib_scalebar.ScaleBar()`.
  * **edges_kwargs** – Keyword arguments for `networkx.draw_networkx_edges()`.
  * **kwargs** ([`Any`](https://docs.python.org/3/library/typing.html#typing.Any)) – Keyword arguments for [`matplotlib.pyplot.scatter()`](https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.scatter.html#matplotlib.pyplot.scatter) or [`matplotlib.pyplot.imshow()`](https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.imshow.html#matplotlib.pyplot.imshow).
  * **kwargs** – Keyword arguments for [`scanpy.pl.DotPlot.style()`](https://scanpy.readthedocs.io/en/stable/api/generated/classes/scanpy.pl.DotPlot.style.html#scanpy.pl.DotPlot.style) or [`scanpy.pl.DotPlot.legend()`](https://scanpy.readthedocs.io/en/stable/api/generated/classes/scanpy.pl.DotPlot.legend.html#scanpy.pl.DotPlot.legend).
* **Return type:**
  [`None`](https://docs.python.org/3/library/constants.html#None)
* **Returns:**
  :
  Nothing, just plots the figure and optionally saves the plot.
