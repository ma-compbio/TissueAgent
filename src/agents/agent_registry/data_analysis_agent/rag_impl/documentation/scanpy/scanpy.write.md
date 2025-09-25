## scanpy.write(filename, adata, \*, ext=None, compression='gzip', compression_opts=None)
Write [`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData) objects to file.

* **Parameters:**
  **filename** 
  : If the filename has no file extension, it is interpreted as a key for
    generating a filename via `sc.settings.writedir / (filename +
    sc.settings.file_format_data)`. This is the same behavior as in
    [`read()`](#scanpy.read).

  **adata** 
  : Annotated data matrix.

  **ext** 
  : File extension from wich to infer file format. If `None`, defaults to
    `sc.settings.file_format_data`.

  **compression** 
  : See [https://docs.h5py.org/en/latest/high/dataset.html](https://docs.h5py.org/en/latest/high/dataset.html).

  **compression_opts** 
  : See [https://docs.h5py.org/en/latest/high/dataset.html](https://docs.h5py.org/en/latest/high/dataset.html).

### *class* scanpy.Verbosity(value, names=<not given>, \*values, module=None, qualname=None, type=None, start=1, boundary=None)

Bases: [`IntEnum`](https://docs.python.org/3/library/enum.html#enum.IntEnum)

Logging verbosity levels.

#### error *= 0*

#### warning *= 1*

#### info *= 2*

#### hint *= 3*

#### debug *= 4*

#### *property* level *: [int](https://docs.python.org/3/library/functions.html#int)*

#### override(verbosity)

Temporarily override verbosity.

* **Return type:**
  [`Generator`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Generator)[[`Verbosity`](#scanpy.Verbosity), [`None`](https://docs.python.org/3/library/constants.html#None), [`None`](https://docs.python.org/3/library/constants.html#None)]

#### warn *= 1*

#### getdoc() → [str](https://docs.python.org/3/library/stdtypes.html#str) | [None](https://docs.python.org/3/library/constants.html#None)

### *class* scanpy.Neighbors(adata, \*, n_dcs=None, neighbors_key=None)

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

#### *property* distances_dpt *: [OnFlySymMatrix](scanpy.neighbors.md#scanpy.neighbors.OnFlySymMatrix)*

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

