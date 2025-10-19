## scanpy.neighbors.neighbors(adata, n_neighbors=15, n_pcs=None, \*, use_rep=None, knn=True, method='umap', transformer=None, metric='euclidean', metric_kwds=mappingproxy({}), random_state=0, key_added=None, copy=False)
Compute the nearest neighbors distance matrix and a neighborhood graph of observations [[McInnes *et al.*, 2018](../references.md#id36)].

The neighbor search efficiency of this heavily relies on UMAP [[McInnes *et al.*, 2018](../references.md#id36)],
which also provides a method for estimating connectivities of data points -
the connectivity of the manifold (`method=='umap'`). If `method=='gauss'`,
connectivities are computed according to Coifman *et al.* [[2005](../references.md#id12)], in the adaption of
Haghverdi *et al.* [[2016](../references.md#id19)].

* **Parameters:**
  **adata** 
  : Annotated data matrix.

  **n_neighbors** 
  : The size of local neighborhood (in terms of number of neighboring data
    points) used for manifold approximation. Larger values result in more
    global views of the manifold, while smaller values result in more local
    data being preserved. In general values should be in the range 2 to 100.
    If `knn` is `True`, number of nearest neighbors to be searched. If `knn`
    is `False`, a Gaussian kernel width is set to the distance of the
    `n_neighbors` neighbor.
    <br/>
    *ignored if \`\`transformer\`\` is an instance.*

  **n_pcs** 
  : Use this many PCs. If `n_pcs==0` use `.X` if `use_rep is None`.

  **use_rep** 
  : Use the indicated representation. `'X'` or any key for `.obsm` is valid.
    If `None`, the representation is chosen automatically:
    For `.n_vars` < `N_PCS` (default: 50), `.X` is used, otherwise ‘X_pca’ is used.
    If ‘X_pca’ is not present, it’s computed with default parameters or `n_pcs` if present.

  **knn** 
  : If `True`, use a hard threshold to restrict the number of neighbors to
    `n_neighbors`, that is, consider a knn graph. Otherwise, use a Gaussian
    Kernel to assign low weights to neighbors more distant than the
    `n_neighbors` nearest neighbor.

  **method** 
  : Use ‘umap’ [[McInnes *et al.*, 2018](../references.md#id36)] or ‘gauss’ (Gauss kernel following Coifman *et al.* [[2005](../references.md#id12)]
    with adaptive width Haghverdi *et al.* [[2016](../references.md#id19)]) for computing connectivities.

  **transformer** 
  : Approximate kNN search implementation following the API of
    [`KNeighborsTransformer`](https://scikit-learn.org/stable/modules/generated/sklearn.neighbors.KNeighborsTransformer.html#sklearn.neighbors.KNeighborsTransformer).
    See /how-to/knn-transformers for more details.
    Also accepts the following known options:
    <br/>
    `None` (the default)
    : Behavior depends on data size.
      For small data, we will calculate exact kNN, otherwise we use
      [`PyNNDescentTransformer`](https://pynndescent.readthedocs.io/en/latest/api.html#pynndescent.pynndescent_.PyNNDescentTransformer)
    <br/>
    `'pynndescent'`
    : [`PyNNDescentTransformer`](https://pynndescent.readthedocs.io/en/latest/api.html#pynndescent.pynndescent_.PyNNDescentTransformer)
    <br/>
    `'rapids'`
    : A transformer based on [`cuml.neighbors.NearestNeighbors`](https://docs.rapids.ai/api/cuml/stable/api/#cuml.neighbors.NearestNeighbors).
      <br/>
      #### Deprecated
      Deprecated since version 1.10.0: Use [`rapids_singlecell.pp.neighbors()`](https://rapids-singlecell.readthedocs.io/en/latest/api/generated/rapids_singlecell.pp.neighbors.html#rapids_singlecell.pp.neighbors) instead.

  **metric** 
  : A known metric’s name or a callable that returns a distance.
    <br/>
    *ignored if \`\`transformer\`\` is an instance.*

  **metric_kwds** 
  : Options for the metric.
    <br/>
    *ignored if \`\`transformer\`\` is an instance.*

  **random_state** 
  : A numpy random seed.
    <br/>
    *ignored if \`\`transformer\`\` is an instance.*

  **key_added** 
  : If not specified, the neighbors data is stored in `.uns['neighbors']`,
    distances and connectivities are stored in `.obsp['distances']` and
    `.obsp['connectivities']` respectively.
    If specified, the neighbors data is added to .uns[key_added],
    distances are stored in `.obsp[key_added+'_distances']` and
    connectivities in `.obsp[key_added+'_connectivities']`.

  **copy** 
  : Return a copy instead of writing to adata.
* **Return type:**
  AnnData | None
* **Returns:**
  Returns `None` if `copy=False`, else returns an `AnnData` object. Sets the following fields:

  `adata.obsp['distances' | key_added+'_distances']`
  : Distance matrix of the nearest neighbors search. Each row (cell) has `n_neighbors`-1 non-zero entries. These are the distances to their `n_neighbors`-1 nearest neighbors (excluding the cell itself).

  `adata.obsp['connectivities' | key_added+'_connectivities']`
  : Weighted adjacency matrix of the neighborhood graph of data
    points. Weights should be interpreted as connectivities.

  `adata.uns['neighbors' | key_added]`
  : neighbors parameters.

### Examples

```pycon
>>> import scanpy as sc
>>> adata = sc.datasets.pbmc68k_reduced()
>>> # Basic usage
>>> sc.pp.neighbors(adata, 20, metric="cosine")
>>> # Provide your own transformer for more control and flexibility
>>> from sklearn.neighbors import KNeighborsTransformer
>>> transformer = KNeighborsTransformer(
...     n_neighbors=10, metric="manhattan", algorithm="kd_tree"
... )
>>> sc.pp.neighbors(adata, transformer=transformer)
>>> # now you can e.g. access the index: `transformer._tree`
```

#### SEE ALSO
/how-to/knn-transformers

### *class* scanpy.neighbors.FlatTree(hyperplanes, offsets, children, indices)

Bases: [`NamedTuple`](https://docs.python.org/3/library/typing.html#typing.NamedTuple)

#### hyperplanes *: [`None`](https://docs.python.org/3/library/constants.html#None)*

Alias for field number 0

#### offsets *: [`None`](https://docs.python.org/3/library/constants.html#None)*

Alias for field number 1

#### children *: [`None`](https://docs.python.org/3/library/constants.html#None)*

Alias for field number 2

#### indices *: [`None`](https://docs.python.org/3/library/constants.html#None)*

Alias for field number 3

#### getdoc() → [str](https://docs.python.org/3/library/stdtypes.html#str) | [None](https://docs.python.org/3/library/constants.html#None)

### *class* scanpy.neighbors.OnFlySymMatrix(get_row, shape, \*, DC_start=0, DC_end=-1, rows=None, restrict_array=None)

Bases: [`object`](https://docs.python.org/3/library/functions.html#object)

Emulate a matrix where elements are calculated on the fly.

#### restrict(index_array)

Generate a view restricted to a subset of indices.

#### getdoc() → [str](https://docs.python.org/3/library/stdtypes.html#str) | [None](https://docs.python.org/3/library/constants.html#None)

### *class* scanpy.neighbors.Neighbors(adata, \*, n_dcs=None, neighbors_key=None)

Bases: [`object`](https://docs.python.org/3/library/functions.html#object)

Data represented as graph of nearest neighbors.

Represent a data matrix as a graph of nearest neighbor relations (edges)
among data points (nodes).

* **Parameters:**
  **adata** 
  : Annotated data object.

  **n_dcs** 
  : Number of diffusion components to use.

  **neighbors_key** 
  : Where to look in `.uns` and `.obsp` for neighbors data

#### *property* rp_forest *: [Mapping](https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping)[[str](https://docs.python.org/3/library/stdtypes.html#str), [Mapping](https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping)[[str](https://docs.python.org/3/library/stdtypes.html#str), [ndarray](https://numpy.org/doc/stable/reference/generated/numpy.ndarray.html#numpy.ndarray)]] | [None](https://docs.python.org/3/library/constants.html#None)*

PyNNDescent index.

#### *property* distances *: np.ndarray | csr_matrix | [None](https://docs.python.org/3/library/constants.html#None)*

Distances between data points (sparse matrix).

#### *property* connectivities *: np.ndarray | csr_matrix | [None](https://docs.python.org/3/library/constants.html#None)*

Connectivities between data points (sparse matrix).

#### getdoc() → [str](https://docs.python.org/3/library/stdtypes.html#str) | [None](https://docs.python.org/3/library/constants.html#None)

#### *property* transitions *: np.ndarray | csr_matrix*

Transition matrix (sparse matrix).

Is conjugate to the symmetrized transition matrix via:

```default
self.transitions = self.Z * self.transitions_sym / self.Z
```

where `self.Z` is the diagonal matrix storing the normalization of the
underlying kernel matrix.

### Notes

This has not been tested, in contrast to `transitions_sym`.

#### *property* transitions_sym *: np.ndarray | csr_matrix | [None](https://docs.python.org/3/library/constants.html#None)*

Symmetrized transition matrix (sparse matrix).

Is conjugate to the transition matrix via:

```default
self.transitions_sym = self.Z / self.transitions * self.Z
```

where `self.Z` is the diagonal matrix storing the normalization of the
underlying kernel matrix.

#### *property* eigen_values *: [ndarray](https://numpy.org/doc/stable/reference/generated/numpy.ndarray.html#numpy.ndarray)*

Eigen values of transition matrix.

#### *property* eigen_basis *: [ndarray](https://numpy.org/doc/stable/reference/generated/numpy.ndarray.html#numpy.ndarray)*

Eigen basis of transition matrix.

#### *property* distances_dpt *: [OnFlySymMatrix](#scanpy.neighbors.OnFlySymMatrix)*

DPT distances.

This is yields [[Haghverdi *et al.*, 2016](../references.md#id19)], Eq. 15 from the supplement with the
extensions of [[Wolf *et al.*, 2019](../references.md#id62)], supplement on random-walk based distance
measures.

#### to_igraph()

Generate igraph from connectiviies.

* **Return type:**
  Graph

#### compute_neighbors(n_neighbors=30, n_pcs=None, \*, use_rep=None, knn=True, method='umap', transformer=None, metric='euclidean', metric_kwds=mappingproxy({}), random_state=0)

Compute distances and connectivities of neighbors.

* **Parameters:**
  **n_neighbors** 
  : Use this number of nearest neighbors.

  **n_pcs** 
  : Use this many PCs. If `n_pcs==0` use `.X` if `use_rep is None`.

  **use_rep** 
  : Use the indicated representation. `'X'` or any key for `.obsm` is valid.
    If `None`, the representation is chosen automatically:
    For `.n_vars` < `N_PCS` (default: 50), `.X` is used, otherwise ‘X_pca’ is used.
    If ‘X_pca’ is not present, it’s computed with default parameters or `n_pcs` if present.

  **knn** 
  : Restrict result to `n_neighbors` nearest neighbors.

  **method** 
  : See `scanpy.pp.neighbors()`.
    If `None`, skip calculating connectivities.
* **Return type:**
  None
* **Returns:**
  Writes sparse graph attributes `.distances` and,
  if `method` is not `None`, `.connectivities`.

#### compute_transitions(\*, density_normalize=True)

Compute transition matrix.

* **Parameters:**
  **density_normalize** 
  : The density rescaling of Coifman and Lafon (2006): Then only the
    geometry of the data matters, not the sampled density.
* **Returns:**
  Makes attributes `.transitions_sym` and `.transitions` available.

#### compute_eigen(n_comps=15, sym=None, sort='decrease', random_state=0)

Compute eigen decomposition of transition matrix.

* **Parameters:**
  **n_comps** 
  : Number of eigenvalues/vectors to be computed, set `n_comps = 0` if
    you need all eigenvectors.

  **sym** 
  : Instead of computing the eigendecomposition of the assymetric
    transition matrix, computed the eigendecomposition of the symmetric
    Ktilde matrix.

  **random_state** 
  : A numpy random seed
* **Returns:**
  Writes the following attributes.

  eigen_values
  : Eigenvalues of transition matrix.

  eigen_basis
  : Matrix of eigenvectors (stored in columns).  `.eigen_basis` is
    projection of data matrix on right eigenvectors, that is, the
    projection on the diffusion components.  these are simply the
    components of the right eigenvectors and can directly be used for
    plotting.
