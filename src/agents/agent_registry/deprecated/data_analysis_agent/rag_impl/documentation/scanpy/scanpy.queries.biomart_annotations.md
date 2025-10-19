## scanpy.queries.biomart_annotations(org, attrs, \*, host='www.ensembl.org', use_cache=False)
Retrieve gene annotations from ensembl biomart.

* **Parameters:**
  **org** 
  : Organism to query. Must be an organism in ensembl biomart. “hsapiens”,
    “mmusculus”, “drerio”, etc.

  **attrs** 
  : Attributes to query biomart for.

  **host** 
  : A valid BioMart host URL. Alternative values include archive urls (like
    “grch37.ensembl.org”) or regional mirrors (like “useast.ensembl.org”).

  **use_cache** 
  : Whether pybiomart should use a cache for requests. Will create a
    `.pybiomart.sqlite` file in current directory if used.
* **Return type:**
  [`DataFrame`](https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.html#pandas.DataFrame)
* **Returns:**
  Dataframe containing annotations.

### Examples

Retrieve genes coordinates and chromosomes

```pycon
>>> import scanpy as sc
>>> annot = sc.queries.biomart_annotations(
...     "hsapiens",
...     ["ensembl_gene_id", "start_position", "end_position", "chromosome_name"],
... ).set_index("ensembl_gene_id")
>>> adata.var[annot.columns] = annot
```

