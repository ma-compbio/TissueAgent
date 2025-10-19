# squidpy.gr.nhood_enrichment

### squidpy.gr.nhood_enrichment(adata, cluster_key, library_key=None, connectivity_key=None, n_perms=1000, numba_parallel=False, seed=None, copy=False, n_jobs=None, backend='loky', show_progress_bar=True)

Compute neighborhood enrichment by permutation test.

* **Parameters:**
  * **adata** ([`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData) | [`SpatialData`](https://spatialdata.scverse.org/en/latest/api/SpatialData.html#spatialdata.SpatialData)) – Annotated data object.
  * **cluster_key** ([`str`](https://docs.python.org/3/library/stdtypes.html#str)) – Key in [`anndata.AnnData.obs`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obs.html#anndata.AnnData.obs) where clustering is stored.
  * **library_key** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`None`](https://docs.python.org/3/library/constants.html#None)) – If multiple library_id, column in [`anndata.AnnData.obs`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obs.html#anndata.AnnData.obs)
    which stores mapping between `library_id` and obs.
  * **connectivity_key** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Key in [`anndata.AnnData.obsp`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obsp.html#anndata.AnnData.obsp) where spatial connectivities are stored.
    Default is: [`anndata.AnnData.obsp`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obsp.html#anndata.AnnData.obsp) `['spatial_connectivities']`.
  * **n_perms** ([`int`](https://docs.python.org/3/library/functions.html#int)) – Number of permutations for the permutation test.
  * **numba_parallel** ([`bool`](https://docs.python.org/3/library/functions.html#bool)) – Whether to use `numba.prange` or not. If None, it is determined automatically.
    For small datasets or small number of interactions, it’s recommended to set this to False.
  * **seed** ([`int`](https://docs.python.org/3/library/functions.html#int) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Random seed for reproducibility.
  * **copy** ([`bool`](https://docs.python.org/3/library/functions.html#bool)) – If `True`, return the result, otherwise save it to the `adata` object.
  * **n_jobs** ([`int`](https://docs.python.org/3/library/functions.html#int) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Number of parallel jobs.
  * **backend** ([`str`](https://docs.python.org/3/library/stdtypes.html#str)) – Parallelization backend to use. See [`joblib.Parallel`](https://joblib.readthedocs.io/en/latest/generated/joblib.Parallel.html#joblib.Parallel) for available options.
  * **show_progress_bar** ([`bool`](https://docs.python.org/3/library/functions.html#bool)) – Whether to show the progress bar or not.
* **Return type:**
  [`tuple`](https://docs.python.org/3/library/stdtypes.html#tuple)[[`ndarray`](https://numpy.org/doc/stable/reference/generated/numpy.ndarray.html#numpy.ndarray)[[`tuple`](https://docs.python.org/3/library/stdtypes.html#tuple)[[`int`](https://docs.python.org/3/library/functions.html#int), [`...`](https://docs.python.org/3/library/constants.html#Ellipsis)], [`dtype`](https://numpy.org/doc/stable/reference/generated/numpy.dtype.html#numpy.dtype)[[`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]], [`ndarray`](https://numpy.org/doc/stable/reference/generated/numpy.ndarray.html#numpy.ndarray)[[`tuple`](https://docs.python.org/3/library/stdtypes.html#tuple)[[`int`](https://docs.python.org/3/library/functions.html#int), [`...`](https://docs.python.org/3/library/constants.html#Ellipsis)], [`dtype`](https://numpy.org/doc/stable/reference/generated/numpy.dtype.html#numpy.dtype)[[`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]]] | [`None`](https://docs.python.org/3/library/constants.html#None)
* **Returns:**
  :
  If `copy = True`, returns a [`tuple`](https://docs.python.org/3/library/stdtypes.html#tuple) with the z-score and the enrichment count.

  Otherwise, modifies the `adata` with the following keys:
  > - [`anndata.AnnData.uns`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.uns.html#anndata.AnnData.uns) `['{cluster_key}_nhood_enrichment']['zscore']` - the enrichment z-score.
  > - [`anndata.AnnData.uns`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.uns.html#anndata.AnnData.uns) `['{cluster_key}_nhood_enrichment']['count']` - the enrichment count.
