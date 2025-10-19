## scanpy.tools.embedding_density(adata, basis='umap', \*, groupby=None, key_added=None, components=None)
Calculate the density of cells in an embedding (per condition).

Gaussian kernel density estimation is used to calculate the density of
cells in an embedded space. This can be performed per category over a
categorical cell annotation. The cell density can be plotted using the
`pl.embedding_density` function.

Note that density values are scaled to be between 0 and 1. Thus, the
density value at each cell is only comparable to densities in
the same category.

Beware that the KDE estimate used (`scipy.stats.gaussian_kde`) becomes
unreliable if you don’t have enough cells in a category.

This function was written by Sophie Tritschler and implemented into
Scanpy by Malte Luecken.

* **Parameters:**
  **adata** 
  : The annotated data matrix.

  **basis** 
  : The embedding over which the density will be calculated. This embedded
    representation is found in `adata.obsm['X_[basis]']``.

  **groupby** 
  : Key for categorical observation/cell annotation for which densities
    are calculated per category.

  **key_added** 
  : Name of the `.obs` covariate that will be added with the density
    estimates.

  **components** 
  : The embedding dimensions over which the density should be calculated.
    This is limited to two components.
* **Return type:**
  [`None`](https://docs.python.org/3/library/constants.html#None)
* **Returns:**
  Sets the following fields (`key_added` defaults to `[basis]_density_[groupby]`, where `[basis]` is one of `umap`, `diffmap`, `pca`, `tsne`, or `draw_graph_fa` and `[groupby]` denotes the parameter input):

  `adata.obs[key_added]`
  : Embedding density values for each cell.

  `adata.uns['[key_added]_params']`
  : A dict with the values for the parameters `covariate` (for the `groupby` parameter) and `components`.

### Examples

```python
import scanpy as sc
adata = sc.datasets.pbmc68k_reduced()
sc.tl.umap(adata)
sc.tl.embedding_density(adata, basis='umap', groupby='phase')
sc.pl.embedding_density(
    adata, basis='umap', key='umap_density_phase', group='G1'
)
```

![image](_build/markdown/plot_directive/api/scanpy-tools-1.*)
```python
sc.pl.embedding_density(
    adata, basis='umap', key='umap_density_phase', group='S'
)
```

![image](_build/markdown/plot_directive/api/scanpy-tools-2.*)

#### SEE ALSO
`pl.embedding_density`

