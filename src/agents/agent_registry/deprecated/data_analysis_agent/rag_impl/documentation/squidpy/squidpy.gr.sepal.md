# squidpy.gr.sepal

### squidpy.gr.sepal(adata, max_neighs, genes=None, n_iter=30000, dt=0.001, thresh=1e-08, connectivity_key='spatial_connectivities', spatial_key='spatial', layer=None, use_raw=False, copy=False, n_jobs=None, backend='loky', show_progress_bar=True)

Identify spatially variable genes with *Sepal*.

*Sepal* is a method that simulates a diffusion process to quantify spatial structure in tissue.
See [[Anderson and Lundeberg, 2021](../references.md#id2)] for reference.

* **Parameters:**
  * **adata** ([`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData) | [`SpatialData`](https://spatialdata.scverse.org/en/latest/api/SpatialData.html#spatialdata.SpatialData)) – Annotated data object.
  * **max_neighs** ([`Literal`](https://docs.python.org/3/library/typing.html#typing.Literal)[`4`, `6`]) – 

    Maximum number of neighbors of a node in the graph. Valid options are:
    > - 4 - for a square-grid (ST, Dbit-seq).
    > - 6 - for a hexagonal-grid (Visium).
  * **genes** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`Sequence`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Sequence)[[`str`](https://docs.python.org/3/library/stdtypes.html#str)] | [`None`](https://docs.python.org/3/library/constants.html#None)) – 

    List of gene names, as stored in [`anndata.AnnData.var_names`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.var_names.html#anndata.AnnData.var_names), used to compute sepal score.

    If None, it’s computed [`anndata.AnnData.var`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.var.html#anndata.AnnData.var) `['highly_variable']`, if present.
    Otherwise, it’s computed for all genes.
  * **n_iter** ([`int`](https://docs.python.org/3/library/functions.html#int) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Maximum number of iterations for the diffusion simulation.
    If `n_iter` iterations are reached, the simulation will terminate
    even though convergence has not been achieved.
  * **dt** ([`float`](https://docs.python.org/3/library/functions.html#float)) – Time step in diffusion simulation.
  * **thresh** ([`float`](https://docs.python.org/3/library/functions.html#float)) – Entropy threshold for convergence of diffusion simulation.
  * **connectivity_key** ([`str`](https://docs.python.org/3/library/stdtypes.html#str)) – Key in [`anndata.AnnData.obsp`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obsp.html#anndata.AnnData.obsp) where spatial connectivities are stored.
    Default is: [`anndata.AnnData.obsp`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obsp.html#anndata.AnnData.obsp) `['spatial_connectivities']`.
  * **spatial_key** ([`str`](https://docs.python.org/3/library/stdtypes.html#str)) – Key in [`anndata.AnnData.obsm`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obsm.html#anndata.AnnData.obsm) where spatial coordinates are stored.
  * **layer** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Layer in [`anndata.AnnData.layers`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.layers.html#anndata.AnnData.layers) to use. If None, use [`anndata.AnnData.X`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.X.html#anndata.AnnData.X).
  * **use_raw** ([`bool`](https://docs.python.org/3/library/functions.html#bool)) – Whether to access [`anndata.AnnData.raw`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.raw.html#anndata.AnnData.raw).
  * **copy** ([`bool`](https://docs.python.org/3/library/functions.html#bool)) – If `True`, return the result, otherwise save it to the `adata` object.
  * **n_jobs** ([`int`](https://docs.python.org/3/library/functions.html#int) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Number of parallel jobs.
  * **backend** ([`str`](https://docs.python.org/3/library/stdtypes.html#str)) – Parallelization backend to use. See [`joblib.Parallel`](https://joblib.readthedocs.io/en/latest/generated/joblib.Parallel.html#joblib.Parallel) for available options.
  * **show_progress_bar** ([`bool`](https://docs.python.org/3/library/functions.html#bool)) – Whether to show the progress bar or not.
* **Return type:**
  [`DataFrame`](https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.html#pandas.DataFrame) | [`None`](https://docs.python.org/3/library/constants.html#None)
* **Returns:**
  :
  If `copy = True`, returns a [`pandas.DataFrame`](https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.html#pandas.DataFrame) with the sepal scores.

  Otherwise, modifies the `adata` with the following key:
  > - [`anndata.AnnData.uns`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.uns.html#anndata.AnnData.uns) `['sepal_score']` - the sepal scores.

### Notes

If some genes in [`anndata.AnnData.uns`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.uns.html#anndata.AnnData.uns) `['sepal_score']` are NaN,
consider re-running the function with increased `n_iter`.
