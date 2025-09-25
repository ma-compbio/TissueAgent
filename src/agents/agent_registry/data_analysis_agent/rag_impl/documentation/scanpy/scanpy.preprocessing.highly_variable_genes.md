## scanpy.preprocessing.highly_variable_genes(adata, \*, layer=None, n_top_genes=None, min_disp=0.5, max_disp=inf, min_mean=0.0125, max_mean=3, span=0.3, n_bins=20, flavor='seurat', subset=False, inplace=True, batch_key=None, check_values=True)
Annotate highly variable genes [[Satija *et al.*, 2015](../references.md#id47), [Stuart *et al.*, 2019](../references.md#id52), [Zheng *et al.*, 2017](../references.md#id64)].

Expects logarithmized data, except when `flavor='seurat_v3'`/`'seurat_v3_paper'`, in which count
data is expected.

Depending on `flavor`, this reproduces the R-implementations of Seurat
[[Satija *et al.*, 2015](../references.md#id47)], Cell Ranger [[Zheng *et al.*, 2017](../references.md#id64)], and Seurat v3 [[Stuart *et al.*, 2019](../references.md#id52)].

`'seurat_v3'`/`'seurat_v3_paper'` requires `scikit-misc` package. If you plan to use this flavor, consider
installing `scanpy` with this optional dependency: `scanpy[skmisc]`.

For the dispersion-based methods (`flavor='seurat'` Satija *et al.* [[2015](../references.md#id47)] and
`flavor='cell_ranger'` Zheng *et al.* [[2017](../references.md#id64)]), the normalized dispersion is obtained
by scaling with the mean and standard deviation of the dispersions for genes
falling into a given bin for mean expression of genes. This means that for each
bin of mean expression, highly variable genes are selected.

For `flavor='seurat_v3'`/`'seurat_v3_paper'` [[Stuart *et al.*, 2019](../references.md#id52)], a normalized variance for each gene
is computed. First, the data are standardized (i.e., z-score normalization
per feature) with a regularized standard deviation. Next, the normalized variance
is computed as the variance of each gene after the transformation. Genes are ranked
by the normalized variance.
Only if `batch_key` is not `None`, the two flavors differ: For `flavor='seurat_v3'`, genes are first sorted by the median (across batches) rank, with ties broken by the number of batches a gene is a HVG.
For `flavor='seurat_v3_paper'`, genes are first sorted by the number of batches a gene is a HVG, with ties broken by the median (across batches) rank.

The following may help when comparing to Seurat’s naming:
If `batch_key=None` and `flavor='seurat'`, this mimics Seurat’s `FindVariableFeatures(…, method='mean.var.plot')`.
If `batch_key=None` and `flavor='seurat_v3'`/`flavor='seurat_v3_paper'`, this mimics Seurat’s `FindVariableFeatures(..., method='vst')`.
If `batch_key` is not `None` and `flavor='seurat_v3_paper'`, this mimics Seurat’s `SelectIntegrationFeatures`.

See also `scanpy.experimental.pp._highly_variable_genes` for additional flavors
(e.g. Pearson residuals).

* **Parameters:**
  **adata** 
  : The annotated data matrix of shape `n_obs` × `n_vars`. Rows correspond
    to cells and columns to genes.

  **layer** 
  : If provided, use `adata.layers[layer]` for expression values instead of `adata.X`.

  **n_top_genes** 
  : Number of highly-variable genes to keep. Mandatory if `flavor='seurat_v3'`.

  **min_mean** 
  : If `n_top_genes` unequals `None`, this and all other cutoffs for the means and the
    normalized dispersions are ignored. Ignored if `flavor='seurat_v3'`.

  **max_mean** 
  : If `n_top_genes` unequals `None`, this and all other cutoffs for the means and the
    normalized dispersions are ignored. Ignored if `flavor='seurat_v3'`.

  **min_disp** 
  : If `n_top_genes` unequals `None`, this and all other cutoffs for the means and the
    normalized dispersions are ignored. Ignored if `flavor='seurat_v3'`.

  **max_disp** 
  : If `n_top_genes` unequals `None`, this and all other cutoffs for the means and the
    normalized dispersions are ignored. Ignored if `flavor='seurat_v3'`.

  **span** 
  : The fraction of the data (cells) used when estimating the variance in the loess
    model fit if `flavor='seurat_v3'`.

  **n_bins** 
  : Number of bins for binning the mean gene expression. Normalization is
    done with respect to each bin. If just a single gene falls into a bin,
    the normalized dispersion is artificially set to 1. You’ll be informed
    about this if you set `settings.verbosity = 4`.

  **flavor** 
  : Choose the flavor for identifying highly variable genes. For the dispersion
    based methods in their default workflows, Seurat passes the cutoffs whereas
    Cell Ranger passes `n_top_genes`.

  **subset** 
  : Inplace subset to highly-variable genes if `True` otherwise merely indicate
    highly variable genes.

  **inplace** 
  : Whether to place calculated metrics in `.var` or return them.

  **batch_key** 
  : If specified, highly-variable genes are selected within each batch separately and merged.
    This simple process avoids the selection of batch-specific genes and acts as a
    lightweight batch correction method. For all flavors, except `seurat_v3`, genes are first sorted
    by how many batches they are a HVG. For dispersion-based flavors ties are broken
    by normalized dispersion. For `flavor = 'seurat_v3_paper'`, ties are broken by the median
    (across batches) rank based on within-batch normalized variance.

  **check_values** 
  : Check if counts in selected layer are integers. A Warning is returned if set to True.
    Only used if `flavor='seurat_v3'`/`'seurat_v3_paper'`.
* **Return type:**
  [`DataFrame`](https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.html#pandas.DataFrame) | [`None`](https://docs.python.org/3/library/constants.html#None)
* **Returns:**
  Returns a [`pandas.DataFrame`](https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.html#pandas.DataFrame) with calculated metrics if `inplace=False`, else returns an `AnnData` object where it sets the following field:

  `adata.var['highly_variable']`
  : boolean indicator of highly-variable genes

  `adata.var['means']`
  : means per gene

  `adata.var['dispersions']`
  : For dispersion-based flavors, dispersions per gene

  `adata.var['dispersions_norm']`
  : For dispersion-based flavors, normalized dispersions per gene

  `adata.var['variances']`
  : For `flavor='seurat_v3'`/`'seurat_v3_paper'`, variance per gene

  `adata.var['variances_norm']`/`'seurat_v3_paper'`
  : For `flavor='seurat_v3'`/`'seurat_v3_paper'`, normalized variance per gene, averaged in
    the case of multiple batches

  `adata.var['highly_variable_rank']`
  : For `flavor='seurat_v3'`/`'seurat_v3_paper'`, rank of the gene according to normalized
    variance, in case of multiple batches description above

  `adata.var['highly_variable_nbatches']`
  : If `batch_key` is given, this denotes in how many batches genes are detected as HVG

  `adata.var['highly_variable_intersection']`
  : If `batch_key` is given, this denotes the genes that are highly variable in all batches

### Notes

This function replaces `filter_genes_dispersion()`.

