## scanpy.tools.rank_genes_groups(adata, groupby, \*, mask_var=None, use_raw=None, groups='all', reference='rest', n_genes=None, rankby_abs=False, pts=False, key_added=None, copy=False, method=None, corr_method='benjamini-hochberg', tie_correct=False, layer=None, \*\*kwds)
Rank genes for characterizing groups.

Expects logarithmized data.

* **Parameters:**
  **adata** 
  : Annotated data matrix.

  **groupby** 
  : The key of the observations grouping to consider.

  **mask_var** 
  : Select subset of genes to use in statistical tests.

  **use_raw** 
  : Use `raw` attribute of `adata` if present. The default behavior is to use `raw` if present.

  **layer** 
  : Key from `adata.layers` whose value will be used to perform tests on.

  **groups** 
  : Subset of groups, e.g. [`'g1'`, `'g2'`, `'g3'`], to which comparison
    shall be restricted, or `'all'` (default), for all groups. Note that if
    `reference='rest'` all groups will still be used as the reference, not
    just those specified in `groups`.

  **reference** 
  : If `'rest'`, compare each group to the union of the rest of the group.
    If a group identifier, compare with respect to this group.

  **n_genes** 
  : The number of genes that appear in the returned tables.
    Defaults to all genes.

  **method** 
  : The default method is `'t-test'`,
    `'t-test_overestim_var'` overestimates variance of each group,
    `'wilcoxon'` uses Wilcoxon rank-sum,
    `'logreg'` uses logistic regression. See Ntranos *et al.* [[2019](../references.md#id41)],
    [here](https://github.com/scverse/scanpy/issues/95) and [here](https://www.nxn.se/valent/2018/3/5/actionable-scrna-seq-clusters),
    for why this is meaningful.

  **corr_method** 
  : p-value correction method.
    Used only for `'t-test'`, `'t-test_overestim_var'`, and `'wilcoxon'`.

  **tie_correct** 
  : Use tie correction for `'wilcoxon'` scores.
    Used only for `'wilcoxon'`.

  **rankby_abs** 
  : Rank genes by the absolute value of the score, not by the
    score. The returned scores are never the absolute values.

  **pts** 
  : Compute the fraction of cells expressing the genes.

  **key_added** 
  : The key in `adata.uns` information is saved to.

  **copy** 
  : Whether to copy `adata` or modify it inplace.

  **kwds**
  : Are passed to test methods. Currently this affects only parameters that
    are passed to [`sklearn.linear_model.LogisticRegression`](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LogisticRegression.html#sklearn.linear_model.LogisticRegression).
    For instance, you can pass `penalty='l1'` to try to come up with a
    minimal set of genes that are good predictors (sparse solution meaning
    few non-zero fitted coefficients).
* **Return type:**
  [`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData) | [`None`](https://docs.python.org/3/library/constants.html#None)
* **Returns:**
  Returns `None` if `copy=False`, else returns an `AnnData` object. Sets the following fields:

  `adata.uns['rank_genes_groups' | key_added]['names']`
  : Structured array to be indexed by group id storing the gene
    names. Ordered according to scores.

  `adata.uns['rank_genes_groups' | key_added]['scores']`
  : Structured array to be indexed by group id storing the z-score
    underlying the computation of a p-value for each gene for each
    group. Ordered according to scores.

  `adata.uns['rank_genes_groups' | key_added]['logfoldchanges']`
  : Structured array to be indexed by group id storing the log2
    fold change for each gene for each group. Ordered according to
    scores. Only provided if method is ‘t-test’ like.
    Note: this is an approximation calculated from mean-log values.

  `adata.uns['rank_genes_groups' | key_added]['pvals']`
  : p-values.

  `adata.uns['rank_genes_groups' | key_added]['pvals_adj']`
  : Corrected p-values.

  `adata.uns['rank_genes_groups' | key_added]['pts']`
  : Fraction of cells expressing the genes for each group.

  `adata.uns['rank_genes_groups' | key_added]['pts_rest']`
  : Only if `reference` is set to `'rest'`.
    Fraction of cells from the union of the rest of each group
    expressing the genes.

### Notes

There are slight inconsistencies depending on whether sparse
or dense data are passed. See [here](https://github.com/scverse/scanpy/blob/main/tests/test_rank_genes_groups.py).

### Examples

```pycon
>>> import scanpy as sc
>>> adata = sc.datasets.pbmc68k_reduced()
>>> sc.tl.rank_genes_groups(adata, "bulk_labels", method="wilcoxon")
>>> # to visualize the results
>>> sc.pl.rank_genes_groups(adata)
```

