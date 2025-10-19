## scanpy.tools.louvain(adata, resolution=None, \*, random_state=0, restrict_to=None, key_added='louvain', adjacency=None, flavor='vtraag', directed=True, use_weights=False, partition_type=None, partition_kwargs=mappingproxy({}), neighbors_key=None, obsp=None, copy=False)
Cluster cells into subgroups [[Blondel *et al.*, 2008](../references.md#id8), [Levine *et al.*, 2015](../references.md#id32), [Traag, 2015](../references.md#id54)].

Cluster cells using the Louvain algorithm [[Blondel *et al.*, 2008](../references.md#id8)] in the implementation
of Traag [[2015](../references.md#id54)]. The Louvain algorithm was proposed for single-cell
analysis by Levine *et al.* [[2015](../references.md#id32)].

This requires having run `neighbors()` or
[`bbknn()`](scanpy.external.pp.md#scanpy.external.pp.bbknn) first,
or explicitly passing a `adjacency` matrix.

* **Parameters:**
  **adata** 
  : The annotated data matrix.

  **resolution** 
  : For the default flavor (`'vtraag'`) or for ``RAPIDS``, you can provide a
    resolution (higher resolution means finding more and smaller clusters),
    which defaults to 1.0.
    See “Time as a resolution parameter” in Lambiotte *et al.* [[2014](../references.md#id29)].

  **random_state** 
  : Change the initialization of the optimization.

  **restrict_to** 
  : Restrict the clustering to the categories within the key for sample
    annotation, tuple needs to contain `(obs_key, list_of_categories)`.

  **key_added** 
  : Key under which to add the cluster labels. (default: `'louvain'`)

  **adjacency** 
  : Sparse adjacency matrix of the graph, defaults to neighbors connectivities.

  **flavor** 
  : Choose between to packages for computing the clustering.
    <br/>
    `'vtraag'`
    : Much more powerful than `'igraph'`, and the default.
    <br/>
    `'igraph'`
    : Built in `igraph` method.
    <br/>
    `'rapids'`
    : GPU accelerated implementation.
      <br/>
      #### Deprecated
      Deprecated since version 1.10.0: Use [`rapids_singlecell.tl.louvain()`](https://rapids-singlecell.readthedocs.io/en/latest/api/generated/rapids_singlecell.tl.louvain.html#rapids_singlecell.tl.louvain) instead.

  **directed** 
  : Interpret the `adjacency` matrix as directed graph?

  **use_weights** 
  : Use weights from knn graph.

  **partition_type** 
  : Type of partition to use.
    Only a valid argument if `flavor` is `'vtraag'`.

  **partition_kwargs** 
  : Key word arguments to pass to partitioning,
    if `vtraag` method is being used.

  **neighbors_key** 
  : Use neighbors connectivities as adjacency.
    If not specified, louvain looks .obsp[‘connectivities’] for connectivities
    (default storage place for pp.neighbors).
    If specified, louvain looks
    .obsp[.uns[neighbors_key][‘connectivities_key’]] for connectivities.

  **obsp** 
  : Use .obsp[obsp] as adjacency. You can’t specify both
    `obsp` and `neighbors_key` at the same time.

  **copy** 
  : Copy adata or modify it inplace.
* **Return type:**
  [`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData) | [`None`](https://docs.python.org/3/library/constants.html#None)
* **Returns:**
  Returns `None` if `copy=False`, else returns an `AnnData` object. Sets the following fields:

  `adata.obs['louvain' | key_added]`
  : Array of dim (number of samples) that stores the subgroup id
    (`'0'`, `'1'`, …) for each cell.

  `adata.uns['louvain' | key_added]['params']`
  : A dict with the values for the parameters `resolution`, `random_state`,
    and `n_iterations`.

