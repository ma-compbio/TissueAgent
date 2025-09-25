## scanpy.readwrite.read_visium(path, genome=None, \*, count_file='filtered_feature_bc_matrix.h5', library_id=None, load_images=True, source_image_path=None)
Read 10x-Genomics-formatted visum dataset.

#### Deprecated
Deprecated since version 1.11.0: Use `squidpy.read.visium()` instead.

In addition to reading regular 10x output,
this looks for the `spatial` folder and loads images,
coordinates and scale factors.
Based on the [Space Ranger output docs](<https://support.10xgenomics.com/spatial-gene-expression/software/pipelines/latest/output/overview>).

See `spatial()` for a compatible plotting function.

* **Parameters:**
  **path** 
  : Path to directory for visium datafiles.

  **genome** 
  : Filter expression to genes within this genome.

  **count_file** 
  : Which file in the passed directory to use as the count file. Typically would be one of:
    ‘filtered_feature_bc_matrix.h5’ or ‘raw_feature_bc_matrix.h5’.

  **library_id** 
  : Identifier for the visium library. Can be modified when concatenating multiple adata objects.

  **source_image_path** 
  : Path to the high-resolution tissue image. Path will be included in
    `.uns["spatial"][library_id]["metadata"]["source_image_path"]`.
* **Return type:**
  [`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData)
* **Returns:**
  Annotated data matrix, where observations/cells are named by their
  barcode and variables/genes by gene name. Stores the following information:

  [`X`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.X.html#anndata.AnnData.X)
  : The data matrix is stored

  [`obs_names`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obs_names.html#anndata.AnnData.obs_names)
  : Cell names

  [`var_names`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.var_names.html#anndata.AnnData.var_names)
  : Gene names for a feature barcode matrix, probe names for a probe bc matrix

  [`var`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.var.html#anndata.AnnData.var)`['gene_ids']`
  : Gene IDs

  [`var`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.var.html#anndata.AnnData.var)`['feature_types']`
  : Feature types

  [`obs`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obs.html#anndata.AnnData.obs)`[filtered_barcodes]`
  : filtered barcodes if present in the matrix

  [`var`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.var.html#anndata.AnnData.var)
  : Any additional metadata present in /matrix/features is read in.

  [`uns`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.uns.html#anndata.AnnData.uns)`['spatial']`
  : Dict of spaceranger output files with ‘library_id’ as key

  [`uns`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.uns.html#anndata.AnnData.uns)`['spatial'][library_id]['images']`
  : Dict of images (`'hires'` and `'lowres'`)

  [`uns`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.uns.html#anndata.AnnData.uns)`['spatial'][library_id]['scalefactors']`
  : Scale factors for the spots

  [`uns`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.uns.html#anndata.AnnData.uns)`['spatial'][library_id]['metadata']`
  : Files metadata: ‘chemistry_description’, ‘software_version’, ‘source_image_path’

  [`obsm`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obsm.html#anndata.AnnData.obsm)`['spatial']`
  : Spatial spot coordinates, usable as `basis` by `embedding()`.

