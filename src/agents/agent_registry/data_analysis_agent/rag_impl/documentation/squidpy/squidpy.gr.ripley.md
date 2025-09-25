# squidpy.gr.ripley

### squidpy.gr.ripley(adata, cluster_key, mode='F', spatial_key='spatial', metric='euclidean', n_neigh=2, n_simulations=100, n_observations=1000, max_dist=None, n_steps=50, seed=None, copy=False)

Calculate various Ripley’s statistics for point processes.

According to the ‘mode’ argument, it calculates one of the following Ripley’s statistics:
‘F’, ‘G’ or ‘L’ statistics.

‘F’, ‘G’ are defined as:

$$
F(t),G(t)=P( d_{i,j} \le t )
$$

Where $d_{i,j}$ represents:

> - distances to a random Spatial Poisson Point Process for ‘F’.
> - distances to any other point of the dataset for ‘G’.

‘L’ we first need to compute $K(t)$, which is defined as:

$$
K(t) = \frac{1}{\lambda} \sum_{i \ne j} \frac{I(d_{i,j}<t)}{n}
$$

and then we apply a variance-stabilizing transformation:

$$
L(t) = (\frac{K(t)}{\pi})^{1/2}
$$

* **Parameters:**
  * **adata** ([`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData) | [`SpatialData`](https://spatialdata.scverse.org/en/latest/api/SpatialData.html#spatialdata.SpatialData)) – Annotated data object.
  * **cluster_key** ([`str`](https://docs.python.org/3/library/stdtypes.html#str)) – Key in [`anndata.AnnData.obs`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obs.html#anndata.AnnData.obs) where clustering is stored.
  * **mode** ([`Literal`](https://docs.python.org/3/library/typing.html#typing.Literal)[`'F'`, `'G'`, `'L'`]) – Which Ripley’s statistic to compute.
  * **spatial_key** ([`str`](https://docs.python.org/3/library/stdtypes.html#str)) – Key in [`anndata.AnnData.obsm`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obsm.html#anndata.AnnData.obsm) where spatial coordinates are stored.
  * **metric** ([`str`](https://docs.python.org/3/library/stdtypes.html#str)) – Which metric to use for computing distances.
    For available metrics, check out `sklearn.neighbors.DistanceMetric`.
  * **n_neigh** ([`int`](https://docs.python.org/3/library/functions.html#int)) – Number of neighbors to consider for the KNN graph.
  * **n_simulations** ([`int`](https://docs.python.org/3/library/functions.html#int)) – How many simulations to run for computing p-values.
  * **n_observations** ([`int`](https://docs.python.org/3/library/functions.html#int)) – How many observations to generate for the Spatial Poisson Point Process.
  * **max_dist** ([`float`](https://docs.python.org/3/library/functions.html#float) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Maximum distances for the support. If None, max_dist=$\sqrt{area \over 2}$.
  * **n_steps** ([`int`](https://docs.python.org/3/library/functions.html#int)) – Number of steps for the support.
  * **seed** ([`int`](https://docs.python.org/3/library/functions.html#int) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Random seed for reproducibility.
  * **copy** ([`bool`](https://docs.python.org/3/library/functions.html#bool)) – If `True`, return the result, otherwise save it to the `adata` object.
* **Return type:**
  [`dict`](https://docs.python.org/3/library/stdtypes.html#dict)[[`str`](https://docs.python.org/3/library/stdtypes.html#str), [`DataFrame`](https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.html#pandas.DataFrame) | [`ndarray`](https://numpy.org/doc/stable/reference/generated/numpy.ndarray.html#numpy.ndarray)[[`tuple`](https://docs.python.org/3/library/stdtypes.html#tuple)[[`int`](https://docs.python.org/3/library/functions.html#int), [`...`](https://docs.python.org/3/library/constants.html#Ellipsis)], [`dtype`](https://numpy.org/doc/stable/reference/generated/numpy.dtype.html#numpy.dtype)[[`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]]]
* **Returns:**
  :
  If `copy = True`, returns a [`dict`](https://docs.python.org/3/library/stdtypes.html#dict) with following keys:
  > - ’{mode}_stat’ - [`pandas.DataFrame`](https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.html#pandas.DataFrame) containing the statistics of choice for the real observations.
  > - ’sims_stat’ - [`pandas.DataFrame`](https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.html#pandas.DataFrame) containing the statistics of choice for the simulations.
  > - ’bins’ - [`numpy.ndarray`](https://numpy.org/doc/stable/reference/generated/numpy.ndarray.html#numpy.ndarray) containing the support.
  > - ’pvalues’ - [`numpy.ndarray`](https://numpy.org/doc/stable/reference/generated/numpy.ndarray.html#numpy.ndarray) containing the p-values for the statistics of interest.

  Otherwise, modifies the `adata` object with the following key:
  > - [`anndata.AnnData.uns`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.uns.html#anndata.AnnData.uns) `['{key_added}']` - the above mentioned [`dict`](https://docs.python.org/3/library/stdtypes.html#dict).

  Statistics and p-values are computed for each cluster [`anndata.AnnData.obs`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obs.html#anndata.AnnData.obs) `['{cluster_key}']` separately.

### References

For reference, check out
[Wikipedia](https://en.wikipedia.org/wiki/Spatial_descriptive_statistics#Ripley's_K_and_L_functions)
or [[Baddeley *et al.*, 2015](../references.md#id16)].
