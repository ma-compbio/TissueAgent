## scanpy.read_10x_h5(filename, \*, genome=None, gex_only=True, backup_url=None)
Read 10x-Genomics-formatted hdf5 file.

* **Parameters:**
  **filename** 
  : Path to a 10x hdf5 file.

  **genome** 
  : Filter expression to genes within this genome. For legacy 10x h5
    files, this must be provided if the data contains more than one genome.

  **gex_only** 
  : Only keep ‘Gene Expression’ data and ignore other feature types,
    e.g. ‘Antibody Capture’, ‘CRISPR Guide Capture’, or ‘Custom’

  **backup_url** 
  : Retrieve the file from an URL if not present on disk.
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

