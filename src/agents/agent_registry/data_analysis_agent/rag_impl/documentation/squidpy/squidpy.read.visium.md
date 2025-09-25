# squidpy.read.visium

### squidpy.read.visium(path, \*, counts_file='filtered_feature_bc_matrix.h5', library_id=None, load_images=True, source_image_path=None, \*\*kwargs)

Read *10x Genomics* Visium formatted dataset.

In addition to reading the regular *Visium* output, it looks for the *spatial* directory and loads the images,
spatial coordinates and scale factors.

#### SEE ALSO
- [Space Ranger output](https://support.10xgenomics.com/spatial-gene-expression/software/pipelines/latest/output/overview).
- [`squidpy.pl.spatial_scatter()`](squidpy.pl.spatial_scatter.md#squidpy.pl.spatial_scatter) on how to plot spatial data.

* **Parameters:**
  * **path** ([`PathLike`](https://docs.python.org/3/library/os.html#os.PathLike)[[`str`](https://docs.python.org/3/library/stdtypes.html#str)] | [`str`](https://docs.python.org/3/library/stdtypes.html#str)) – Path to the root directory containing *Visium* files.
  * **counts_file** ([`str`](https://docs.python.org/3/library/stdtypes.html#str)) – Which file in the passed directory to use as the count file. Typically either *filtered_feature_bc_matrix.h5* or
    *raw_feature_bc_matrix.h5*.
  * **library_id** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Identifier for the *Visium* library. Useful when concatenating multiple [`anndata.AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData) objects.
  * **kwargs** ([`Any`](https://docs.python.org/3/library/typing.html#typing.Any)) – Keyword arguments for [`scanpy.read_10x_h5()`](https://scanpy.readthedocs.io/en/stable/generated/scanpy.read_10x_h5.html#scanpy.read_10x_h5), `anndata.read_mtx()` or `read_text()`.
* **Return type:**
  [`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData)
* **Returns:**
  :
  Annotated data object with the following keys:
  > - [`anndata.AnnData.obsm`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obsm.html#anndata.AnnData.obsm) `['spatial']` - spatial spot coordinates.
  > - [`anndata.AnnData.uns`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.uns.html#anndata.AnnData.uns) `['spatial']['{library_id}']['images']` - *hires* and *lowres* images.
  > - [`anndata.AnnData.uns`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.uns.html#anndata.AnnData.uns) `['spatial']['{library_id}']['scalefactors']` - scale factors for the spots.
  > - [`anndata.AnnData.uns`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.uns.html#anndata.AnnData.uns) `['spatial']['{library_id}']['metadata']` - various metadata.
