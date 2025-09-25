## scanpy.readwrite.read_10x_mtx(path, \*, var_names='gene_symbols', make_unique=True, cache=False, cache_compression=\_empty, gex_only=True, prefix=None)
Read 10x-Genomics-formatted mtx directory.

* **Parameters:**
  **path** 
  : Path to directory for `.mtx` and `.tsv` files,
    e.g. ‘./filtered_gene_bc_matrices/hg19/’.

  **var_names** 
  : The variables index.

  **make_unique** 
  : Whether to make the variables index unique by appending ‘-1’,
    ‘-2’ etc. or not.

  **cache** 
  : If `False`, read from source, if `True`, read from fast ‘h5ad’ cache.

  **cache_compression** 
  : See the h5py [Filter pipeline](https://docs.h5py.org/en/stable/high/dataset.html#dataset-compression).
    (Default: `settings.cache_compression`)

  **gex_only** 
  : Only keep ‘Gene Expression’ data and ignore other feature types,
    e.g. ‘Antibody Capture’, ‘CRISPR Guide Capture’, or ‘Custom’

  **prefix** 
  : Any prefix before `matrix.mtx`, `genes.tsv` and `barcodes.tsv`. For instance,
    if the files are named `patientA_matrix.mtx`, `patientA_genes.tsv` and
    `patientA_barcodes.tsv` the prefix is `patientA_`.
    (Default: no prefix)
* **Return type:**
  [`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData)
* **Returns:**
  An [`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData) object

