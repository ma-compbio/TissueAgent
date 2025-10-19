## scanpy.tools.umap(adata, \*, min_dist=0.5, spread=1.0, n_components=2, maxiter=None, alpha=1.0, gamma=1.0, negative_sample_rate=5, init_pos='spectral', random_state=0, a=None, b=None, method='umap', key_added=None, neighbors_key='neighbors', copy=False)
Embed the neighborhood graph using UMAP [[McInnes *et al.*, 2018](../references.md#id36)].

UMAP (Uniform Manifold Approximation and Projection) is a manifold learning
technique suitable for visualizing high-dimensional data. Besides tending to
be faster than tSNE, it optimizes the embedding such that it best reflects
the topology of the data, which we represent throughout Scanpy using a
neighborhood graph. tSNE, by contrast, optimizes the distribution of
nearest-neighbor distances in the embedding such that these best match the
distribution of distances in the high-dimensional space.
We use the implementation of [umap-learn](https://github.com/lmcinnes/umap) [[McInnes *et al.*, 2018](../references.md#id36)].
For a few comparisons of UMAP with tSNE, see Becht *et al.* [[2018](../references.md#id6)].

* **Parameters:**
  **adata** 
  : Annotated data matrix.

  **min_dist** 
  : The effective minimum distance between embedded points. Smaller values
    will result in a more clustered/clumped embedding where nearby points on
    the manifold are drawn closer together, while larger values will result
    on a more even dispersal of points. The value should be set relative to
    the `spread` value, which determines the scale at which embedded
    points will be spread out. The default of in the `umap-learn` package is
    0.1.

  **spread** 
  : The effective scale of embedded points. In combination with `min_dist`
    this determines how clustered/clumped the embedded points are.

  **n_components** 
  : The number of dimensions of the embedding.

  **maxiter** 
  : The number of iterations (epochs) of the optimization. Called `n_epochs`
    in the original UMAP.

  **alpha** 
  : The initial learning rate for the embedding optimization.

  **gamma** 
  : Weighting applied to negative samples in low dimensional embedding
    optimization. Values higher than one will result in greater weight
    being given to negative samples.

  **negative_sample_rate** 
  : The number of negative edge/1-simplex samples to use per positive
    edge/1-simplex sample in optimizing the low dimensional embedding.

  **init_pos** 
  : How to initialize the low dimensional embedding. Called `init` in the
    original UMAP. Options are:
    * Any key for `adata.obsm`.
    * ’paga’: positions from `paga()`.
    * ’spectral’: use a spectral embedding of the graph.
    * ’random’: assign initial embedding positions at random.
    * A numpy array of initial embedding positions.

  **random_state** 
  : If `int`, `random_state` is the seed used by the random number generator;
    If `RandomState` or `Generator`, `random_state` is the random number generator;
    If `None`, the random number generator is the `RandomState` instance used
    by `np.random`.

  **a** 
  : More specific parameters controlling the embedding. If `None` these
    values are set automatically as determined by `min_dist` and
    `spread`.

  **b** 
  : More specific parameters controlling the embedding. If `None` these
    values are set automatically as determined by `min_dist` and
    `spread`.

  **method** 
  : Chosen implementation.
    <br/>
    `'umap'`
    : Umap’s simplical set embedding.
    <br/>
    `'rapids'`
    : GPU accelerated implementation.
      <br/>
      #### Deprecated
      Deprecated since version 1.10.0: Use [`rapids_singlecell.tl.umap()`](https://rapids-singlecell.readthedocs.io/en/latest/api/generated/rapids_singlecell.tl.umap.html#rapids_singlecell.tl.umap) instead.

  **key_added** 
  : If not specified, the embedding is stored as
    [`obsm`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obsm.html#anndata.AnnData.obsm)`['X_umap']` and the the parameters in
    [`uns`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.uns.html#anndata.AnnData.uns)`['umap']`.
    If specified, the embedding is stored as
    [`obsm`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obsm.html#anndata.AnnData.obsm)`[key_added]` and the the parameters in
    [`uns`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.uns.html#anndata.AnnData.uns)`[key_added]`.

  **neighbors_key** 
  : Umap looks in
    [`uns`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.uns.html#anndata.AnnData.uns)`[neighbors_key]` for neighbors settings and
    [`obsp`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obsp.html#anndata.AnnData.obsp)`[.uns[neighbors_key]['connectivities_key']]` for connectivities.

  **copy** 
  : Return a copy instead of writing to adata.
* **Return type:**
  [`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData) | [`None`](https://docs.python.org/3/library/constants.html#None)
* **Returns:**
  Returns `None` if `copy=False`, else returns an `AnnData` object. Sets the following fields:

  `adata.obsm['X_umap' | key_added]`
  : UMAP coordinates of data.

  `adata.uns['umap' | key_added]`
  : UMAP parameters.
