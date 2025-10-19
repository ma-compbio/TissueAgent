# squidpy.gr.spatial_autocorr

### squidpy.gr.spatial_autocorr(adata, connectivity_key='spatial_connectivities', genes=None, mode='moran', transformation=True, n_perms=None, two_tailed=False, corr_method='fdr_bh', attr='X', layer=None, seed=None, use_raw=False, copy=False, n_jobs=None, backend='loky', show_progress_bar=True)

Calculate Global Autocorrelation Statistic (Moran’s I  or Geary’s C).

See [[Rey and Anselin, 2010](../references.md#id15)] for reference.

* **Parameters:**
  * **adata** ([`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData) | [`SpatialData`](https://spatialdata.scverse.org/en/latest/api/SpatialData.html#spatialdata.SpatialData)) – Annotated data object.
  * **connectivity_key** ([`str`](https://docs.python.org/3/library/stdtypes.html#str)) – Key in [`anndata.AnnData.obsp`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obsp.html#anndata.AnnData.obsp) where spatial connectivities are stored.
    Default is: [`anndata.AnnData.obsp`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obsp.html#anndata.AnnData.obsp) `['spatial_connectivities']`.
  * **genes** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`int`](https://docs.python.org/3/library/functions.html#int) | [`Sequence`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Sequence)[[`str`](https://docs.python.org/3/library/stdtypes.html#str)] | [`Sequence`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Sequence)[[`int`](https://docs.python.org/3/library/functions.html#int)] | [`None`](https://docs.python.org/3/library/constants.html#None)) – 

    Depending on the `attr`:
    > - if `attr = 'X'`, it corresponds to genes stored in [`anndata.AnnData.var_names`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.var_names.html#anndata.AnnData.var_names).
    >   If None, it’s computed [`anndata.AnnData.var`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.var.html#anndata.AnnData.var) `['highly_variable']`,
    >   if present. Otherwise, it’s computed for all genes.
    > - if `attr = 'obs'`, it corresponds to a list of columns in [`anndata.AnnData.obs`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obs.html#anndata.AnnData.obs).
    >   If None, use all numerical columns.
    > - if `attr = 'obsm'`, it corresponds to indices in [`anndata.AnnData.obsm`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obsm.html#anndata.AnnData.obsm) `['{layer}']`.
    >   If None, all indices are used.
  * **mode** ([`Union`](https://docs.python.org/3/library/typing.html#typing.Union)[`SpatialAutocorr`, [`Literal`](https://docs.python.org/3/library/typing.html#typing.Literal)[`'moran'`, `'geary'`]]) – 

    Mode of score calculation:
    > - ’moran’ - [Moran’s I autocorrelation](https://en.wikipedia.org/wiki/Moran%27s_I).
    > - ’geary’ - [Geary’s C autocorrelation](https://en.wikipedia.org/wiki/Geary%27s_C).
  * **transformation** ([`bool`](https://docs.python.org/3/library/functions.html#bool)) – If True, weights in [`anndata.AnnData.obsp`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obsp.html#anndata.AnnData.obsp) `['spatial_connectivities']` are row-normalized,
    advised for analytic p-value calculation.
  * **n_perms** ([`int`](https://docs.python.org/3/library/functions.html#int) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Number of permutations for the permutation test.
    If None, only p-values under normality assumption are computed.
  * **two_tailed** ([`bool`](https://docs.python.org/3/library/functions.html#bool)) – If True, p-values are two-tailed, otherwise they are one-tailed.
  * **corr_method** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Correction method for multiple testing. See [`statsmodels.stats.multitest.multipletests()`](https://www.statsmodels.org/stable/generated/statsmodels.stats.multitest.multipletests.html#statsmodels.stats.multitest.multipletests)
    for valid options.
  * **use_raw** ([`bool`](https://docs.python.org/3/library/functions.html#bool)) – Whether to access [`anndata.AnnData.raw`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.raw.html#anndata.AnnData.raw). Only used when `attr = 'X'`.
  * **layer** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Depending on `attr`:
    Layer in [`anndata.AnnData.layers`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.layers.html#anndata.AnnData.layers) to use. If None, use [`anndata.AnnData.X`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.X.html#anndata.AnnData.X).
  * **attr** ([`Literal`](https://docs.python.org/3/library/typing.html#typing.Literal)[`'obs'`, `'X'`, `'obsm'`]) – Which attribute of [`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData) to access. See `genes` parameter for more information.
  * **seed** ([`int`](https://docs.python.org/3/library/functions.html#int) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Random seed for reproducibility.
  * **copy** ([`bool`](https://docs.python.org/3/library/functions.html#bool)) – If `True`, return the result, otherwise save it to the `adata` object.
  * **n_jobs** ([`int`](https://docs.python.org/3/library/functions.html#int) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Number of parallel jobs.
  * **backend** ([`str`](https://docs.python.org/3/library/stdtypes.html#str)) – Parallelization backend to use. See [`joblib.Parallel`](https://joblib.readthedocs.io/en/latest/generated/joblib.Parallel.html#joblib.Parallel) for available options.
  * **show_progress_bar** ([`bool`](https://docs.python.org/3/library/functions.html#bool)) – Whether to show the progress bar or not.
* **Return type:**
  [`DataFrame`](https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.html#pandas.DataFrame) | [`None`](https://docs.python.org/3/library/constants.html#None)
* **Returns:**
  :
  If `copy = True`, returns a [`pandas.DataFrame`](https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.html#pandas.DataFrame) with the following keys:
  > - ’I’ or ‘C’ - Moran’s I or Geary’s C statistic.
  > - ’pval_norm’ - p-value under normality assumption.
  > - ’var_norm’ - variance of ‘score’ under normality assumption.
  > - ’{p_val}_{corr_method}’ - the corrected p-values if `corr_method != None` .

  If `n_perms != None`, additionally returns the following columns:
  > - ’pval_z_sim’ - p-value based on standard normal approximation from permutations.
  > - ’pval_sim’ - p-value based on permutations.
  > - ’var_sim’ - variance of ‘score’ from permutations.

  Otherwise, modifies the `adata` with the following key:
  > - [`anndata.AnnData.uns`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.uns.html#anndata.AnnData.uns) `['moranI']` - the above mentioned dataframe, if `mode = 'moran'`.
  > - [`anndata.AnnData.uns`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.uns.html#anndata.AnnData.uns) `['gearyC']` - the above mentioned dataframe, if `mode = 'geary'`.
