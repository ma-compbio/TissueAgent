## scanpy.tools.diffmap(adata, n_comps=15, \*, neighbors_key=None, random_state=0, copy=False)
Diffusion Maps [[Coifman *et al.*, 2005](../references.md#id12), [Haghverdi *et al.*, 2015](../references.md#id18), [Wolf *et al.*, 2018](../references.md#id61)].

Diffusion maps [[Coifman *et al.*, 2005](../references.md#id12)] have been proposed for visualizing single-cell
data by Haghverdi *et al.* [[2015](../references.md#id18)]. This tool uses the adapted Gaussian kernel suggested
by Haghverdi *et al.* [[2016](../references.md#id19)] with the implementation of Wolf *et al.* [[2018](../references.md#id61)].

The width (“sigma”) of the connectivity kernel is implicitly determined by
the number of neighbors used to compute the single-cell graph in
`neighbors()`. To reproduce the original implementation
using a Gaussian kernel, use `method=='gauss'` in
`neighbors()`. To use an exponential kernel, use the default
`method=='umap'`. Differences between these options shouldn’t usually be
dramatic.

* **Parameters:**
  **adata** 
  : Annotated data matrix.

  **n_comps** 
  : The number of dimensions of the representation.

  **neighbors_key** 
  : If not specified, diffmap looks in .uns[‘neighbors’] for neighbors settings
    and .obsp[‘connectivities’] and .obsp[‘distances’] for connectivities and
    distances, respectively (default storage places for pp.neighbors).
    If specified, diffmap looks in .uns[neighbors_key] for neighbors settings and
    .obsp[.uns[neighbors_key][‘connectivities_key’]] and
    .obsp[.uns[neighbors_key][‘distances_key’]] for connectivities and distances,
    respectively.

  **random_state** 
  : A numpy random seed

  **copy** 
  : Return a copy instead of writing to adata.
* **Return type:**
  [`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData) | [`None`](https://docs.python.org/3/library/constants.html#None)
* **Returns:**
  Returns `None` if `copy=False`, else returns an `AnnData` object. Sets the following fields:

  `adata.obsm['X_diffmap']`
  : Diffusion map representation of data, which is the right eigen basis of
    the transition matrix with eigenvectors as columns.

  `adata.uns['diffmap_evals']`
  : Array of size (number of eigen vectors).
    Eigenvalues of transition matrix.

### Notes

The 0-th column in `adata.obsm["X_diffmap"]` is the steady-state solution,
which is non-informative in diffusion maps.
Therefore, the first diffusion component is at index 1,
e.g. `adata.obsm["X_diffmap"][:,1]`

