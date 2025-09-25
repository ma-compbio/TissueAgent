# squidpy.tl.var_by_distance

### squidpy.tl.var_by_distance(adata, groups, cluster_key=None, library_key=None, library_id=None, design_matrix_key='design_matrix', covariates=None, metric='euclidean', spatial_key='spatial', copy=False)

Build a design matrix consisting of distance measurements to selected anchor point(s) for each observation.

* **Parameters:**
  * **adata** ([`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData)) – Annotated data object.
  * **groups** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`list`](https://docs.python.org/3/library/stdtypes.html#list)[[`str`](https://docs.python.org/3/library/stdtypes.html#str)] | [`ndarray`](https://numpy.org/doc/stable/reference/generated/numpy.ndarray.html#numpy.ndarray)[[`tuple`](https://docs.python.org/3/library/stdtypes.html#tuple)[[`int`](https://docs.python.org/3/library/functions.html#int), [`...`](https://docs.python.org/3/library/constants.html#Ellipsis)], [`dtype`](https://numpy.org/doc/stable/reference/generated/numpy.dtype.html#numpy.dtype)[[`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]]) – Anchor point(s) to calculate distances to. Can be a single or multiple observations as long as they are annotated in an .obs column with name given by cluster_key.
    Alternatively, a numpy array of coordinates can be passed.
  * **cluster_key** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Name of annotation column in .obs where the observation used as anchor points are located.
  * **library_key** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`None`](https://docs.python.org/3/library/constants.html#None)) – If multiple library_id, column in [`anndata.AnnData.obs`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obs.html#anndata.AnnData.obs)
    which stores mapping between `library_id` and obs.
  * **library_id** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`list`](https://docs.python.org/3/library/stdtypes.html#list)[[`str`](https://docs.python.org/3/library/stdtypes.html#str)] | [`None`](https://docs.python.org/3/library/constants.html#None)) – Name of the Z-dimension(s) that this function should be applied to.
    For not specified Z-dimensions, the identity function is applied.
  * **design_matrix_key** ([`str`](https://docs.python.org/3/library/stdtypes.html#str)) – Name of the design matrix saved to .obsm.
  * **covariates** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`list`](https://docs.python.org/3/library/stdtypes.html#list)[[`str`](https://docs.python.org/3/library/stdtypes.html#str)] | [`None`](https://docs.python.org/3/library/constants.html#None)) – Additional covariates from .obs to include in the design matrix.
  * **metric** ([`str`](https://docs.python.org/3/library/stdtypes.html#str)) – Distance metric, defaults to “euclidean”.
  * **spatial_key** ([`str`](https://docs.python.org/3/library/stdtypes.html#str)) – Key in [`anndata.AnnData.obsm`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obsm.html#anndata.AnnData.obsm) where spatial coordinates are stored.
  * **copy** ([`bool`](https://docs.python.org/3/library/functions.html#bool)) – If `True`, return the result, otherwise save it to the `adata` object.
* **Return type:**
  [`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData)
* **Returns:**
  :
  If `copy = True`, returns the design_matrix with the distances to an anchor point
  Otherwise, stores design_matrix in .obsm.
