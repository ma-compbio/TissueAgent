# squidpy.gr.spatial_neighbors

### squidpy.gr.spatial_neighbors(adata, spatial_key='spatial', elements_to_coordinate_systems=None, table_key=None, library_key=None, coord_type=None, n_neighs=6, radius=None, delaunay=False, n_rings=1, percentile=None, transform=None, set_diag=False, key_added='spatial', copy=False)

Create a graph from spatial coordinates.

* **Parameters:**
  * **adata** ([`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData) | [`SpatialData`](https://spatialdata.scverse.org/en/latest/api/SpatialData.html#spatialdata.SpatialData)) – Annotated data object.
  * **spatial_key** ([`str`](https://docs.python.org/3/library/stdtypes.html#str)) – Key in [`anndata.AnnData.obsm`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obsm.html#anndata.AnnData.obsm) where spatial coordinates are stored.
    If adata is a [`spatialdata.SpatialData`](https://spatialdata.scverse.org/en/latest/api/SpatialData.html#spatialdata.SpatialData), the coordinates of the centroids will be stored in the
    adata with this key.
  * **elements_to_coordinate_systems** ([`dict`](https://docs.python.org/3/library/stdtypes.html#dict)[[`str`](https://docs.python.org/3/library/stdtypes.html#str), [`str`](https://docs.python.org/3/library/stdtypes.html#str)] | [`None`](https://docs.python.org/3/library/constants.html#None)) – A dictionary mapping element names of the SpatialData object to coordinate systems.
    The elements can be either Shapes or Labels. For compatibility, the spatialdata table must annotate
    all regions keys. Must not be None if adata is a [`spatialdata.SpatialData`](https://spatialdata.scverse.org/en/latest/api/SpatialData.html#spatialdata.SpatialData).
  * **table_key** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Key in [`spatialdata.SpatialData.tables`](https://spatialdata.scverse.org/en/latest/api/SpatialData.html#spatialdata.SpatialData.tables) where the spatialdata table is stored. Must not be None if
    adata is a [`spatialdata.SpatialData`](https://spatialdata.scverse.org/en/latest/api/SpatialData.html#spatialdata.SpatialData).
  * **mask_polygon** – The Polygon or MultiPolygon element.
  * **library_key** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`None`](https://docs.python.org/3/library/constants.html#None)) – If multiple library_id, column in [`anndata.AnnData.obs`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obs.html#anndata.AnnData.obs)
    which stores mapping between `library_id` and obs.
  * **coord_type** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | `CoordType` | [`None`](https://docs.python.org/3/library/constants.html#None)) – 

    Type of coordinate system. Valid options are:
    > - ’grid’ - grid coordinates.
    > - ’generic’ - generic coordinates.
    > - None - ‘grid’ if `spatial_key` is in [`anndata.AnnData.uns`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.uns.html#anndata.AnnData.uns)
    >   with `n_neighs = 6` (Visium), otherwise use ‘generic’.
  * **n_neighs** ([`int`](https://docs.python.org/3/library/functions.html#int)) – 

    Depending on the `coord_type`:
    > - ’grid’ - number of neighboring tiles.
    > - ’generic’ - number of neighborhoods for non-grid data. Only used when `delaunay = False`.
  * **radius** ([`float`](https://docs.python.org/3/library/functions.html#float) | [`tuple`](https://docs.python.org/3/library/stdtypes.html#tuple)[[`float`](https://docs.python.org/3/library/functions.html#float), [`float`](https://docs.python.org/3/library/functions.html#float)] | [`None`](https://docs.python.org/3/library/constants.html#None)) – 

    Only available when `coord_type = 'generic'`. Depending on the type:
    > - [`float`](https://docs.python.org/3/library/functions.html#float) - compute the graph based on neighborhood radius.
    > - [`tuple`](https://docs.python.org/3/library/stdtypes.html#tuple) - prune the final graph to only contain edges in interval [min(radius), max(radius)].
  * **delaunay** ([`bool`](https://docs.python.org/3/library/functions.html#bool)) – Whether to compute the graph from Delaunay triangulation. Only used when `coord_type = 'generic'`.
  * **n_rings** ([`int`](https://docs.python.org/3/library/functions.html#int)) – Number of rings of neighbors for grid data. Only used when `coord_type = 'grid'`.
  * **percentile** ([`float`](https://docs.python.org/3/library/functions.html#float) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Percentile of the distances to use as threshold. Only used when `coord_type = 'generic'`.
  * **transform** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | `Transform` | [`None`](https://docs.python.org/3/library/constants.html#None)) – 

    Type of adjacency matrix transform. Valid options are:
    > - ’spectral’ - spectral transformation of the adjacency matrix.
    > - ’cosine’ - cosine transformation of the adjacency matrix.
    > - None - no transformation of the adjacency matrix.
  * **set_diag** ([`bool`](https://docs.python.org/3/library/functions.html#bool)) – Whether to set the diagonal of the spatial connectivities to 1.0.
  * **key_added** ([`str`](https://docs.python.org/3/library/stdtypes.html#str)) – Key which controls where the results are saved if `copy = False`.
  * **copy** ([`bool`](https://docs.python.org/3/library/functions.html#bool)) – If `True`, return the result, otherwise save it to the `adata` object.
* **Return type:**
  [`tuple`](https://docs.python.org/3/library/stdtypes.html#tuple)[[`csr_matrix`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.sparse.csr_matrix.html#scipy.sparse.csr_matrix), [`csr_matrix`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.sparse.csr_matrix.html#scipy.sparse.csr_matrix)] | [`None`](https://docs.python.org/3/library/constants.html#None)
* **Returns:**
  :
  If `copy = True`, returns a [`tuple`](https://docs.python.org/3/library/stdtypes.html#tuple) with the spatial connectivities and distances matrices.

  Otherwise, modifies the `adata` with the following keys:
  > - [`anndata.AnnData.obsp`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obsp.html#anndata.AnnData.obsp) `['{key_added}_connectivities']` - the spatial connectivities.
  > - [`anndata.AnnData.obsp`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obsp.html#anndata.AnnData.obsp) `['{key_added}_distances']` - the spatial distances.
  > - [`anndata.AnnData.uns`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.uns.html#anndata.AnnData.uns)  `['{key_added}']` - [`dict`](https://docs.python.org/3/library/stdtypes.html#dict) containing parameters.
