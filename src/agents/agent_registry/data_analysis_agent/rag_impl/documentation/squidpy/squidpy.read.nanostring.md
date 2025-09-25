# squidpy.read.nanostring

### squidpy.read.nanostring(path, \*, counts_file, meta_file, fov_file=None)

Read *Nanostring* formatted dataset.

In addition to reading the regular *Nanostring* output, it loads the metadata file, if present *CellComposite* and *CellLabels*
directories containing the images and optionally the field of view file.

#### SEE ALSO
- [Nanostring Spatial Molecular Imager](https://nanostring.com/products/cosmx-spatial-molecular-imager/).
- [`squidpy.pl.spatial_scatter()`](squidpy.pl.spatial_scatter.md#squidpy.pl.spatial_scatter) on how to plot spatial data.

* **Parameters:**
  * **path** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`Path`](https://docs.python.org/3/library/pathlib.html#pathlib.Path)) – Path to the root directory containing *Nanostring* files.
  * **counts_file** ([`str`](https://docs.python.org/3/library/stdtypes.html#str)) – File containing the counts. Typically ends with  *\_exprMat_file.csv*.
  * **meta_file** ([`str`](https://docs.python.org/3/library/stdtypes.html#str)) – File containing the spatial coordinates and additional cell-level metadata.
    Typically ends with  *\_metadata_file.csv*.
  * **fov_file** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`None`](https://docs.python.org/3/library/constants.html#None)) – File containing the coordinates of all the fields of view.
* **Return type:**
  [`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData)
* **Returns:**
  :
  Annotated data object with the following keys:
  > - [`anndata.AnnData.obsm`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obsm.html#anndata.AnnData.obsm) `['spatial']` -  local coordinates of the centers of cells.
  > - [`anndata.AnnData.obsm`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obsm.html#anndata.AnnData.obsm) `['spatial_fov']` - global coordinates of the centers of cells in the
  >   field of view.
  > - [`anndata.AnnData.uns`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.uns.html#anndata.AnnData.uns) `['spatial']['{fov}']['images']` - *hires* and *segmentation* images.
  > - [`anndata.AnnData.uns`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.uns.html#anndata.AnnData.uns) `['spatial']['{fov}']['metadata']]['{x,y}_global_px']` - coordinates of the field of view.
  >   Only present if `fov_file != None`.
