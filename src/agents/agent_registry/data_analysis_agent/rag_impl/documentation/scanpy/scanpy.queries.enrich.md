## scanpy.queries.enrich(container, \*, org='hsapiens', gprofiler_kwargs=mappingproxy({}))
Get enrichment for DE results.

This is a thin convenience wrapper around the very useful [gprofiler](https://pypi.org/project/gprofiler-official/#description).

This method dispatches on the first argument, leading to the following two
signatures:

```default
enrich(container, ...)
enrich(adata: AnnData, group, key: str, ...)
```

Where:

```default
enrich(adata, group, key, ...) = enrich(adata.uns[key]["names"][group], ...)
```

* **Parameters:**
  **container** 
  : Contains list of genes you’d like to search. If container is a `dict` all
    enrichment queries are made at once.

  **adata**
  : AnnData object whose group will be looked for.

  **group**
  : The group whose genes should be used for enrichment.

  **key**
  : Key in `uns` to find group under.

  **org** 
  : Organism to query. Must be an organism in ensembl biomart. “hsapiens”,
    “mmusculus”, “drerio”, etc.

  **gprofiler_kwargs** 
  : Keyword arguments to pass to `GProfiler.profile`, see [gprofiler](https://pypi.org/project/gprofiler-official/#description). Some
    useful options are `no_evidences=False` which reports gene intersections,
    `sources=['GO:BP']` which limits gene sets to only GO biological processes and
    `all_results=True` which returns all results including the non-significant ones.

  **\*\*kwargs**
  : All other keyword arguments are passed to `sc.get.rank_genes_groups_df`. E.g.
    pval_cutoff, log2fc_min.
* **Return type:**
  [`DataFrame`](https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.html#pandas.DataFrame)
* **Returns:**
  Dataframe of enrichment results.

### Examples

Using `sc.queries.enrich` on a list of genes:

```pycon
>>> import scanpy as sc
>>> sc.queries.enrich(["KLF4", "PAX5", "SOX2", "NANOG"], org="hsapiens")
>>> sc.queries.enrich(
...     {"set1": ["KLF4", "PAX5"], "set2": ["SOX2", "NANOG"]}, org="hsapiens"
... )
```

Using `sc.queries.enrich` on an [`anndata.AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData) object:

```pycon
>>> pbmcs = sc.datasets.pbmc68k_reduced()
>>> sc.tl.rank_genes_groups(pbmcs, "bulk_labels")
>>> sc.queries.enrich(pbmcs, "CD34+")
```

