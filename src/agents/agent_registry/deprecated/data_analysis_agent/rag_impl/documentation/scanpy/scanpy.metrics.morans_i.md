## scanpy.metrics.morans_i(adata, \*, vals=None, use_graph=None, layer=None, obsm=None, obsp=None, use_raw=False)
Calculate Moran’s I Global Autocorrelation Statistic.

Moran’s I is a global autocorrelation statistic for some measure on a graph. It is commonly used in
spatial data analysis to assess autocorrelation on a 2D grid. It is closely related to Geary’s C,
but not identical. More info can be found [here](https://en.wikipedia.org/wiki/Moran%27s_I).

$$
I =
    \frac{
        N \sum_{i, j} w_{i, j} z_{i} z_{j}
    }{
        S_{0} \sum_{i} z_{i}^{2}
    }
$$

* **Parameters:**
  **adata** 

  **vals** 
  : Values to calculate Moran’s I for. If this is two dimensional, should
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

Calculate Moran’s I for each components of a dimensionality reduction:

```python
import scanpy as sc, numpy as np

pbmc = sc.datasets.pbmc68k_processed()
pc_c = sc.metrics.morans_i(pbmc, obsm="X_pca")
```

It’s equivalent to call the function directly on the underlying arrays:

```python
alt = sc.metrics.morans_i(pbmc.obsp["connectivities"], pbmc.obsm["X_pca"].T)
np.testing.assert_array_equal(pc_c, alt)
```

