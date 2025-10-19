## scanpy.preprocessing.filter_genes_dispersion(data, \*, flavor='seurat', min_disp=None, max_disp=None, min_mean=None, max_mean=None, n_bins=20, n_top_genes=None, log=True, subset=True, copy=False)
Extract highly variable genes [[Satija *et al.*, 2015](../references.md#id47), [Zheng *et al.*, 2017](../references.md#id64)].

#### Deprecated
Deprecated since version 1.3.6: Use `highly_variable_genes()` instead.
The new function is equivalent to the present function, except that

* the new function always expects logarithmized data
* `subset=False` in the new function, it suffices to
  merely annotate the genes, tools like `pp.pca` will
  detect the annotation
* you can now call: `sc.pl.highly_variable_genes(adata)`
* `copy` is replaced by `inplace`

If trying out parameters, pass the data matrix instead of AnnData.

Depending on `flavor`, this reproduces the R-implementations of Seurat
[[Satija *et al.*, 2015](../references.md#id47)] and Cell Ranger [[Zheng *et al.*, 2017](../references.md#id64)].

The normalized dispersion is obtained by scaling with the mean and standard
deviation of the dispersions for genes falling into a given bin for mean
expression of genes. This means that for each bin of mean expression, highly
variable genes are selected.

Use `flavor='cell_ranger'` with care and in the same way as in
`recipe_zheng17()`.

* **Parameters:**
  **data** 
  : The (annotated) data matrix of shape `n_obs` × `n_vars`. Rows correspond
    to cells and columns to genes.

  **flavor** 
  : Choose the flavor for computing normalized dispersion. If choosing
    ‘seurat’, this expects non-logarithmized data – the logarithm of mean
    and dispersion is taken internally when `log` is at its default value
    `True`. For ‘cell_ranger’, this is usually called for logarithmized data
    – in this case you should set `log` to `False`. In their default
    workflows, Seurat passes the cutoffs whereas Cell Ranger passes
    `n_top_genes`.

  **min_mean** 

  **max_mean** 

  **min_disp** 

  **max_disp** 
  : If `n_top_genes` unequals `None`, these cutoffs for the means and the
    normalized dispersions are ignored.

  **n_bins** 
  : Number of bins for binning the mean gene expression. Normalization is
    done with respect to each bin. If just a single gene falls into a bin,
    the normalized dispersion is artificially set to 1. You’ll be informed
    about this if you set `settings.verbosity = 4`.

  **n_top_genes** 
  : Number of highly-variable genes to keep.

  **log** 
  : Use the logarithm of the mean to variance ratio.

  **subset** 
  : Keep highly-variable genes only (if True) else write a bool array for h
    ighly-variable genes while keeping all genes

  **copy** 
  : If an [`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData) is passed, determines whether a copy
    is returned.
* **Return type:**
  [`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData) | [`recarray`](https://numpy.org/doc/stable/reference/generated/numpy.recarray.html#numpy.recarray) | [`None`](https://docs.python.org/3/library/constants.html#None)
* **Returns:**
  If an AnnData `adata` is passed, returns or updates `adata` depending on
  `copy`. It filters the `adata` and adds the annotations

  **means**
  : Means per gene. Logarithmized when `log` is `True`.

  **dispersions**
  : Dispersions per gene. Logarithmized when `log` is `True`.

  **dispersions_norm**
  : Normalized dispersions per gene. Logarithmized when `log` is `True`.

  If a data matrix `X` is passed, the annotation is returned as `np.recarray`
  with the same information stored in fields: `gene_subset`, `means`, `dispersions`, `dispersion_norm`.

