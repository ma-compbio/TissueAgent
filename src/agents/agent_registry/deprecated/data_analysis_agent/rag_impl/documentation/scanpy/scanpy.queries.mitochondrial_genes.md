## scanpy.queries.mitochondrial_genes(org, \*, attrname='external_gene_name', host='www.ensembl.org', use_cache=False, chromosome='MT')
Mitochondrial gene symbols for specific organism through BioMart.

* **Parameters:**
  **org** 
  : Organism to query. Must be an organism in ensembl biomart. “hsapiens”,
    “mmusculus”, “drerio”, etc.

  **attrname** 
  : Biomart attribute field to return. Possible values include
    “external_gene_name”, “ensembl_gene_id”, “hgnc_symbol”, “mgi_symbol”,
    and “zfin_id_symbol”.

  **host** 
  : A valid BioMart host URL. Alternative values include archive urls (like
    “grch37.ensembl.org”) or regional mirrors (like “useast.ensembl.org”).

  **use_cache** 
  : Whether pybiomart should use a cache for requests. Will create a
    `.pybiomart.sqlite` file in current directory if used.

  **chromosome** 
  : Mitochrondrial chromosome name used in BioMart for organism.
* **Return type:**
  [`DataFrame`](https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.html#pandas.DataFrame)
* **Returns:**
  Dataframe containing identifiers for mitochondrial genes.

### Examples

```pycon
>>> import scanpy as sc
>>> mito_gene_names = sc.queries.mitochondrial_genes("hsapiens")
>>> mito_ensembl_ids = sc.queries.mitochondrial_genes(
...     "hsapiens", attrname="ensembl_gene_id"
... )
>>> mito_gene_names_fly = sc.queries.mitochondrial_genes(
...     "dmelanogaster", chromosome="mitochondrion_genome"
... )
```
