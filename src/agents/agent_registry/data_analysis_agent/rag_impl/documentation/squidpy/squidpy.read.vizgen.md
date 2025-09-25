# squidpy.read.vizgen

### squidpy.read.vizgen(path, \*, counts_file, meta_file, transformation_file=None, library_id='library', \*\*kwargs)

Read *Vizgen* formatted dataset.

In addition to reading the regular *Vizgen* output, it loads the metadata file and optionally loads
the transformation matrix.

#### SEE ALSO
- [Vizgen data release program](https://vizgen.com/data-release-program/).
- [`squidpy.pl.spatial_scatter()`](squidpy.pl.spatial_scatter.md#squidpy.pl.spatial_scatter) on how to plot spatial data.

* **Parameters:**
  * **path** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`Path`](https://docs.python.org/3/library/pathlib.html#pathlib.Path)) – Path to the root directory containing *Vizgen* files.
  * **counts_file** ([`str`](https://docs.python.org/3/library/stdtypes.html#str)) – File containing the counts. Typically ends with  *\_cell_by_gene.csv*.
  * **meta_file** ([`str`](https://docs.python.org/3/library/stdtypes.html#str)) – File containing the spatial coordinates and additional cell-level metadata.
  * **transformation_file** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Transformation matrix file for converting micron coordinates into pixels in images.
  * **library_id** ([`str`](https://docs.python.org/3/library/stdtypes.html#str)) – Identifier for the *Vizgen* library. Useful when concatenating multiple [`anndata.AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData) objects.
* **Return type:**
  [`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData)
* **Returns:**
  :
  Annotated data object with the following keys:
  > - [`anndata.AnnData.obsm`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obsm.html#anndata.AnnData.obsm) `['spatial']` - spatial spot coordinates in microns.
  > - [`anndata.AnnData.obsm`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obsm.html#anndata.AnnData.obsm) `['blank_genes']` - blank genes from Vizgen platform.
  > - [`anndata.AnnData.uns`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.uns.html#anndata.AnnData.uns) `['spatial']['{library_id}']['scalefactors']['transformation_matrix']` -
  >   transformation matrix for converting micron coordinates to pixels.
  >   Only present if `transformation_file != None`.
