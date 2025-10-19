---
id: scanpy.tools.dendrogram
aliases: []
tags: []
---

## scanpy.tools.dendrogram(adata, groupby, \*, n_pcs=None, use_rep=None, var_names=None, use_raw=None, cor_method='pearson', linkage_method='complete', optimal_ordering=False, key_added=None, inplace=True)
Compute a hierarchical clustering for the given `groupby` categories.

By default, the PCA representation is used unless `.X`
has less than 50 variables.

Alternatively, a list of `var_names` (e.g. genes) can be given.

Average values of either `var_names` or components are used
to compute a correlation matrix.

The hierarchical clustering can be visualized using
`scanpy.pl.dendrogram()` or multiple other visualizations
that can include a dendrogram: `matrixplot()`,
`heatmap()`, `dotplot()`,
and `stacked_violin()`.

#### NOTE
The computation of the hierarchical clustering is based on predefined
groups and not per cell. The correlation matrix is computed using by
default pearson but other methods are available.

* **Parameters:**
  **adata**
  : Annotated data matrix

  **n_pcs**
  : Use this many PCs. If `n_pcs==0` use `.X` if `use_rep is None`.

  **use_rep**
  : Use the indicated representation. `'X'` or any key for `.obsm` is valid.
    If `None`, the representation is chosen automatically:
    For `.n_vars` < `N_PCS` (default: 50), `.X` is used, otherwise ‘X_pca’ is used.
    If ‘X_pca’ is not present, it’s computed with default parameters or `n_pcs` if present.

  **var_names**
  : List of var_names to use for computing the hierarchical clustering.
    If `var_names` is given, then `use_rep` and `n_pcs` are ignored.

  **use_raw**
  : Only when `var_names` is not None.
    Use `raw` attribute of `adata` if present.

  **cor_method**
  : Correlation method to use.
    Options are ‘pearson’, ‘kendall’, and ‘spearman’

  **linkage_method**
  : Linkage method to use. See [`scipy.cluster.hierarchy.linkage()`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.cluster.hierarchy.linkage.html#scipy.cluster.hierarchy.linkage)
    for more information.

  **optimal_ordering**
  : Same as the optimal_ordering argument of [`scipy.cluster.hierarchy.linkage()`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.cluster.hierarchy.linkage.html#scipy.cluster.hierarchy.linkage)
    which reorders the linkage matrix so that the distance between successive
    leaves is minimal.

  **key_added**
  : By default, the dendrogram information is added to
    `.uns[f'dendrogram_{groupby}']`.
    Notice that the `groupby` information is added to the dendrogram.

  **inplace**
  : If `True`, adds dendrogram information to `adata.uns[key_added]`,
    else this function returns the information.
* **Return type:**
  [`dict`](https://docs.python.org/3/library/stdtypes.html#dict)[[`str`](https://docs.python.org/3/library/stdtypes.html#str), [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)] | [`None`](https://docs.python.org/3/library/constants.html#None)
* **Returns:**
  Returns `None` if `inplace=True`, else returns a `dict` with dendrogram information. Sets the following field if `inplace=True`:

  `adata.uns[f'dendrogram_{group_by}' | key_added]`
  : Dendrogram information.

### Examples

```pycon
>>> import scanpy as sc
>>> adata = sc.datasets.pbmc68k_reduced()
>>> sc.tl.dendrogram(adata, groupby="bulk_labels")
>>> sc.pl.dendrogram(adata, groupby="bulk_labels")
<Axes: >
>>> markers = ["C1QA", "PSAP", "CD79A", "CD79B", "CST3", "LYZ"]
>>> sc.pl.dotplot(adata, markers, groupby="bulk_labels", dendrogram=True)
