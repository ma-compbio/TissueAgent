## scanpy.queries.gene_coordinates(org, gene_name, \*, gene_attr='external_gene_name', chr_exclude=(), host='www.ensembl.org', use_cache=False)
Retrieve gene coordinates for specific organism through BioMart.

* **Parameters:**
  **org** 
  : Organism to query. Must be an organism in ensembl biomart. “hsapiens”,
    “mmusculus”, “drerio”, etc.

  **gene_name** 
  : The gene symbol (e.g. “hgnc_symbol” for human) for which to retrieve
    coordinates.

  **gene_attr** 
  : The biomart attribute the gene symbol should show up for.

  **chr_exclude** 
  : A list of chromosomes to exclude from query.

  **host** 
  : A valid BioMart host URL. Alternative values include archive urls (like
    “grch37.ensembl.org”) or regional mirrors (like “useast.ensembl.org”).

  **use_cache** 
  : Whether pybiomart should use a cache for requests. Will create a
    `.pybiomart.sqlite` file in current directory if used.
* **Return type:**
  [`DataFrame`](https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.html#pandas.DataFrame)
* **Returns:**
  Dataframe containing gene coordinates for the specified gene symbol.

### Examples

```pycon
>>> import scanpy as sc
>>> sc.queries.gene_coordinates("hsapiens", "MT-TF")
```

