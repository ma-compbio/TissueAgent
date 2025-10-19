# squidpy.gr.centrality_scores

### squidpy.gr.centrality_scores(adata, cluster_key, score=None, connectivity_key=None, copy=False, n_jobs=None, backend='loky', show_progress_bar=False)

Compute centrality scores per cluster or cell type.

Inspired by usage in Gene Regulatory Networks (GRNs) in [[Kamimoto *et al.*, 2020](../references.md#id3)].

* **Parameters:**
  * **adata** ([`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData) | [`SpatialData`](https://spatialdata.scverse.org/en/latest/api/SpatialData.html#spatialdata.SpatialData)) – Annotated data object.
  * **cluster_key** ([`str`](https://docs.python.org/3/library/stdtypes.html#str)) – Key in [`anndata.AnnData.obs`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obs.html#anndata.AnnData.obs) where clustering is stored.
  * **score** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`Iterable`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Iterable)[[`str`](https://docs.python.org/3/library/stdtypes.html#str)] | [`None`](https://docs.python.org/3/library/constants.html#None)) – 

    Centrality measures as described in [`networkx.algorithms.centrality`](https://networkx.org/documentation/stable/reference/algorithms/centrality.html#module-networkx.algorithms.centrality) [[Hagberg *et al.*, 2008](../references.md#id6)].
    If None, use all the options below. Valid options are:
    > - ’closeness_centrality’ - measure of how close the group is to other nodes.
    > - ’average_clustering’ - measure of the degree to which nodes cluster together.
    > - ’degree_centrality’ - fraction of non-group members connected to group members.
  * **connectivity_key** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Key in [`anndata.AnnData.obsp`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obsp.html#anndata.AnnData.obsp) where spatial connectivities are stored.
    Default is: [`anndata.AnnData.obsp`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obsp.html#anndata.AnnData.obsp) `['spatial_connectivities']`.
  * **copy** ([`bool`](https://docs.python.org/3/library/functions.html#bool)) – If `True`, return the result, otherwise save it to the `adata` object.
  * **n_jobs** ([`int`](https://docs.python.org/3/library/functions.html#int) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Number of parallel jobs.
  * **backend** ([`str`](https://docs.python.org/3/library/stdtypes.html#str)) – Parallelization backend to use. See [`joblib.Parallel`](https://joblib.readthedocs.io/en/latest/generated/joblib.Parallel.html#joblib.Parallel) for available options.
  * **show_progress_bar** ([`bool`](https://docs.python.org/3/library/functions.html#bool)) – Whether to show the progress bar or not.
* **Return type:**
  [`DataFrame`](https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.html#pandas.DataFrame) | [`None`](https://docs.python.org/3/library/constants.html#None)
* **Returns:**
  :
  If `copy = True`, returns a [`pandas.DataFrame`](https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.html#pandas.DataFrame). Otherwise, modifies the `adata` with the following key:
  > - [`anndata.AnnData.uns`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.uns.html#anndata.AnnData.uns) `['{cluster_key}_centrality_scores']` - the centrality scores,
  >   as mentioned above.
