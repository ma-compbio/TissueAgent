# squidpy.gr.ligrec

### squidpy.gr.ligrec(adata, cluster_key, interactions=None, complex_policy='min', threshold=0.01, corr_method=None, corr_axis='clusters', use_raw=True, copy=False, key_added=None, gene_symbols=None, \*\*kwargs)

Perform the permutation test as described in [[Efremova *et al.*, 2020](../references.md#id4)].

* **Parameters:**
  * **adata** ([`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData) | [`SpatialData`](https://spatialdata.scverse.org/en/latest/api/SpatialData.html#spatialdata.SpatialData)) – Annotated data object.
  * **use_raw** ([`bool`](https://docs.python.org/3/library/functions.html#bool)) – Whether to access [`anndata.AnnData.raw`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.raw.html#anndata.AnnData.raw).
  * **interactions** ([`DataFrame`](https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.html#pandas.DataFrame) | [`Mapping`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping)[[`str`](https://docs.python.org/3/library/stdtypes.html#str), [`Sequence`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Sequence)[[`str`](https://docs.python.org/3/library/stdtypes.html#str)]] | [`Sequence`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Sequence)[[`str`](https://docs.python.org/3/library/stdtypes.html#str)] | [`tuple`](https://docs.python.org/3/library/stdtypes.html#tuple)[[`Sequence`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Sequence)[[`str`](https://docs.python.org/3/library/stdtypes.html#str)], [`Sequence`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Sequence)[[`str`](https://docs.python.org/3/library/stdtypes.html#str)]] | [`Sequence`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Sequence)[[`tuple`](https://docs.python.org/3/library/stdtypes.html#tuple)[[`str`](https://docs.python.org/3/library/stdtypes.html#str), [`str`](https://docs.python.org/3/library/stdtypes.html#str)]] | [`None`](https://docs.python.org/3/library/constants.html#None)) – 

    Interaction to test. The type can be one of:
    > - [`pandas.DataFrame`](https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.html#pandas.DataFrame) - must contain at least 2 columns named ‘source’ and ‘target’.
    > - [`dict`](https://docs.python.org/3/library/stdtypes.html#dict) - dictionary with at least 2 keys named ‘source’ and ‘target’.
    > - [`typing.Sequence`](https://docs.python.org/3/library/typing.html#typing.Sequence) - Either a sequence of [`str`](https://docs.python.org/3/library/stdtypes.html#str), in which case all combinations are
    >   produced, or a sequence of [`tuple`](https://docs.python.org/3/library/stdtypes.html#tuple) of 2 [`str`](https://docs.python.org/3/library/stdtypes.html#str) or a [`tuple`](https://docs.python.org/3/library/stdtypes.html#tuple) of 2 sequences.

    If None, the interactions are extracted from `omnipath`. Protein complexes can be specified by
    delimiting the components with ‘_’, such as ‘alpha_beta_gamma’.
  * **complex_policy** ([`Literal`](https://docs.python.org/3/library/typing.html#typing.Literal)[`'min'`, `'all'`]) – 

    Policy on how to handle complexes. Valid options are:
    > - ’min’ - select gene with the minimum average expression. This is the same as in
    >   [[Efremova *et al.*, 2020](../references.md#id4)].
    > - ’all’ - select all possible combinations between ‘source’ and ‘target’ complexes.
  * **interactions_params** – Keyword arguments for [`omnipath.interactions.import_intercell_network()`](https://omnipath.readthedocs.io/en/latest/api/omnipath.interactions.import_intercell_network.html#omnipath.interactions.import_intercell_network) defining the interactions.
    These datasets from [[Türei *et al.*, 2016](../references.md#id5)] are used by default: omnipath, pathwayextra, kinaseextra and
    ligrecextra.
  * **transmitter_params** – Keyword arguments for [`omnipath.interactions.import_intercell_network()`](https://omnipath.readthedocs.io/en/latest/api/omnipath.interactions.import_intercell_network.html#omnipath.interactions.import_intercell_network) defining the transmitter
    side of intercellular connections.
  * **receiver_params** – Keyword arguments for [`omnipath.interactions.import_intercell_network()`](https://omnipath.readthedocs.io/en/latest/api/omnipath.interactions.import_intercell_network.html#omnipath.interactions.import_intercell_network) defining the receiver
    side of intercellular connections.
  * **cluster_key** ([`str`](https://docs.python.org/3/library/stdtypes.html#str)) – Key in [`anndata.AnnData.obs`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obs.html#anndata.AnnData.obs) where clustering is stored.
  * **clusters** – Clusters from [`anndata.AnnData.obs`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obs.html#anndata.AnnData.obs) `['{cluster_key}']`. Can be specified either as a sequence
    of [`tuple`](https://docs.python.org/3/library/stdtypes.html#tuple) or just a sequence of cluster names, in which case all combinations considered.
  * **n_perms** – Number of permutations for the permutation test.
  * **threshold** ([`float`](https://docs.python.org/3/library/functions.html#float)) – Do not perform permutation test if any of the interacting components is being expressed
    in less than `threshold` percent of cells within a given cluster.
  * **seed** – Random seed for reproducibility.
  * **corr_method** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Correction method for multiple testing. See [`statsmodels.stats.multitest.multipletests()`](https://www.statsmodels.org/stable/generated/statsmodels.stats.multitest.multipletests.html#statsmodels.stats.multitest.multipletests)
    for valid options.
  * **corr_axis** ([`Literal`](https://docs.python.org/3/library/typing.html#typing.Literal)[`'interactions'`, `'clusters'`]) – 

    Axis over which to perform the FDR correction. Only used when `corr_method != None`. Valid options are:
    > - ’interactions’ - correct interactions by performing FDR correction across the clusters.
    > - ’clusters’ - correct clusters by performing FDR correction across the interactions.
  * **alpha** – Significance level for FDR correction. Only used when `corr_method != None`.
  * **copy** ([`bool`](https://docs.python.org/3/library/functions.html#bool)) – If `True`, return the result, otherwise save it to the `adata` object.
  * **key_added** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Key in [`anndata.AnnData.uns`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.uns.html#anndata.AnnData.uns) where the result is stored if `copy = False`.
    If None, `'{cluster_key}_ligrec'` will be used.
  * **numba_parallel** – Whether to use `numba.prange` or not. If None, it is determined automatically.
    For small datasets or small number of interactions, it’s recommended to set this to False.
  * **n_jobs** – Number of parallel jobs.
  * **backend** – Parallelization backend to use. See [`joblib.Parallel`](https://joblib.readthedocs.io/en/latest/generated/joblib.Parallel.html#joblib.Parallel) for available options.
  * **show_progress_bar** – Whether to show the progress bar or not.
  * **gene_symbols** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Key in [`anndata.AnnData.var`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.var.html#anndata.AnnData.var) to use instead of [`anndata.AnnData.var_names`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.var_names.html#anndata.AnnData.var_names).
* **Return type:**
  [`Mapping`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping)[[`str`](https://docs.python.org/3/library/stdtypes.html#str), [`DataFrame`](https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.html#pandas.DataFrame)] | [`None`](https://docs.python.org/3/library/constants.html#None)
* **Returns:**
  :
  If `copy = True`, returns a [`dict`](https://docs.python.org/3/library/stdtypes.html#dict) with following keys:
  > - ’means’ - [`pandas.DataFrame`](https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.html#pandas.DataFrame) containing the mean expression.
  > - ’pvalues’ - [`pandas.DataFrame`](https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.html#pandas.DataFrame) containing the possibly corrected p-values.
  > - ’metadata’ - [`pandas.DataFrame`](https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.html#pandas.DataFrame) containing interaction metadata.

  Otherwise, modifies the `adata` object with the following key:
  > - [`anndata.AnnData.uns`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.uns.html#anndata.AnnData.uns) `['{key_added}']` - the above mentioned [`dict`](https://docs.python.org/3/library/stdtypes.html#dict).

  NaN p-values mark combinations for which the mean expression of one of the interacting components was 0
  or it didn’t pass the `threshold` percentage of cells being expressed within a given cluster.
