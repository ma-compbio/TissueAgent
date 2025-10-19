# squidpy.gr.mask_graph

### squidpy.gr.mask_graph(sdata, table_key, polygon_mask, negative_mask=False, spatial_key='spatial', key_added='mask', copy=False)

Mask the graph based on a polygon mask.

Given a spatial graph stored in [`anndata.AnnData.obsp`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obsp.html#anndata.AnnData.obsp) `['{{key_added}}_{{spatial_key}}_connectivities']` and spatial coordinates stored in [`anndata.AnnData.obsp`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obsp.html#anndata.AnnData.obsp) `['{{spatial_key}}']`, it maskes the graph so that only edges fully contained in the polygons are kept.

* **Parameters:**
  * **sdata** ([`SpatialData`](https://spatialdata.scverse.org/en/latest/api/SpatialData.html#spatialdata.SpatialData)) – The spatial data object.
  * **table_key** ([`str`](https://docs.python.org/3/library/stdtypes.html#str)) – The key of the table containing the spatial data.
  * **polygon_mask** ([`Polygon`](https://shapely.readthedocs.io/en/stable/reference/shapely.Polygon.html#shapely.Polygon) | [`MultiPolygon`](https://shapely.readthedocs.io/en/stable/reference/shapely.MultiPolygon.html#shapely.MultiPolygon)) – The [`shapely.Polygon`](https://shapely.readthedocs.io/en/stable/reference/shapely.Polygon.html#shapely.Polygon) or [`shapely.MultiPolygon`](https://shapely.readthedocs.io/en/stable/reference/shapely.MultiPolygon.html#shapely.MultiPolygon) to be used as mask.
  * **negative_mask** ([`bool`](https://docs.python.org/3/library/functions.html#bool)) – Whether to keep the edges within the polygon mask or outside.
    Note that when `negative_mask = True`, only the edges fully contained in the polygon are removed.
    If edges are partially contained in the polygon, they are kept.
  * **spatial_key** ([`str`](https://docs.python.org/3/library/stdtypes.html#str)) – Key in [`anndata.AnnData.obsm`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obsm.html#anndata.AnnData.obsm) where spatial coordinates are stored.
  * **key_added** ([`str`](https://docs.python.org/3/library/stdtypes.html#str)) – Key which controls where the results are saved if `copy = False`.
  * **copy** ([`bool`](https://docs.python.org/3/library/functions.html#bool)) – If `True`, return the result, otherwise save it to the `adata` object.
* **Return type:**
  [`SpatialData`](https://spatialdata.scverse.org/en/latest/api/SpatialData.html#spatialdata.SpatialData)
* **Returns:**
  :
  If `copy = True`, returns a [`tuple`](https://docs.python.org/3/library/stdtypes.html#tuple) with the masked spatial connectivities and masked distances matrices.

  Otherwise, modifies the `adata` with the following keys:
  > - [`anndata.AnnData.obsp`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obsp.html#anndata.AnnData.obsp) `['{{key_added}}_{{spatial_key}}_connectivities']` - the spatial connectivities.
  > - [`anndata.AnnData.obsp`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obsp.html#anndata.AnnData.obsp) `['{{key_added}}_{{spatial_key}}_distances']` - the spatial distances.
  > - [`anndata.AnnData.uns`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.uns.html#anndata.AnnData.uns)  `['{{key_added}}_{{spatial_key}}']` - [`dict`](https://docs.python.org/3/library/stdtypes.html#dict) containing parameters.

### Notes

The polygon_mask must be in the same coordinate_systems of the spatial graph, but no check is performed to assess this.
