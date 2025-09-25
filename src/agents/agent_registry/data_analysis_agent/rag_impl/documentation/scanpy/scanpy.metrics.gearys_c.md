## scanpy.metrics.gearys_c(adata, \*, vals=None, use_graph=None, layer=None, obsm=None, obsp=None, use_raw=False)
Calculate [Geary’s C](https://en.wikipedia.org/wiki/Geary's_C).

Specifically as used by [VISION](https://doi.org/10.1038/s41467-019-12235-0).

Geary’s C is a measure of autocorrelation for some measure on a graph. This
can be to whether measures are correlated between neighboring cells. Lower
values indicate greater correlation.

$$
C =
\frac{
    (N - 1)\sum_{i,j} w_{i,j} (x_i - x_j)^2
}{
    2W \sum_i (x_i - \bar{x})^2
}
$$

* **Parameters:**
  **adata** 

  **vals** 
  : Values to calculate Geary’s C for. If this is two dimensional, should
    be of shape `(n_features, n_cells)`. Otherwise should be of shape
    `(n_cells,)`. This matrix can be selected from elements of the anndata
    object by using key word arguments: `layer`, `obsm`, `obsp`, or
    `use_raw`.

  **use_graph** 
  : Key to use for graph in anndata object. If not provided, default
    neighbors connectivities will be used instead.

  **layer** 
  : Key for `adata.layers` to choose `vals`.

  **obsm** 
  : Key for `adata.obsm` to choose `vals`.

  **obsp** 
  : Key for `adata.obsp` to choose `vals`.

  **use_raw** 
  : Whether to use `adata.raw.X` for `vals`.

This function can also be called on the graph and values directly. In this case
the signature looks like:

* **Parameters:**
  **g**
  : The graph

  **vals**
  : The values

See the examples for more info.

* **Return type:**
  [`ndarray`](https://numpy.org/doc/stable/reference/generated/numpy.ndarray.html#numpy.ndarray) | [`float`](https://docs.python.org/3/library/functions.html#float)
* **Returns:**
  If vals is two dimensional, returns a 1 dimensional ndarray array. Returns
  a scalar if `vals` is 1d.

### Examples

Calculate Geary’s C for each components of a dimensionality reduction:

```python
import scanpy as sc, numpy as np

pbmc = sc.datasets.pbmc68k_processed()
pc_c = sc.metrics.gearys_c(pbmc, obsm="X_pca")
```

It’s equivalent to call the function directly on the underlying arrays:

```python
alt = sc.metrics.gearys_c(pbmc.obsp["connectivities"], pbmc.obsm["X_pca"].T)
np.testing.assert_array_equal(pc_c, alt)
```

