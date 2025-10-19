## scanpy.read_loom(filename, \*, sparse=True, cleanup=False, X_name='spliced', obs_names='CellID', obsm_names=None, var_names='Gene', varm_names=None, dtype='float32', obsm_mapping=mappingproxy({}), varm_mapping=mappingproxy({}), \*\*kwargs)
Read `.loom`-formatted hdf5 file.

This reads the whole file into memory.

Beware that you have to explicitly state when you want to read the file as
sparse data.

* **Parameters:**
  **filename** 
  : The filename.

  **sparse** 
  : Whether to read the data matrix as sparse.

  **cleanup** 
  : Whether to collapse all obs/var fields that only store
    one unique value into `.uns['loom-.']`.

  **X_name** 
  : Loompy key with which the data matrix [`X`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.X.html#anndata.AnnData.X) is initialized.

  **obs_names** 
  : Loompy key where the observation/cell names are stored.

  **obsm_mapping** 
  : Loompy keys which will be constructed into observation matrices

  **var_names** 
  : Loompy key where the variable/gene names are stored.

  **varm_mapping** 
  : Loompy keys which will be constructed into variable matrices

  **\*\*kwargs**
  : Arguments to loompy.connect
* **Return type:**
  [`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData)

### Example

```python
pbmc = anndata.io.read_loom(
    "pbmc.loom",
    sparse=True,
    X_name="lognorm",
    obs_names="cell_names",
    var_names="gene_names",
    obsm_mapping={
        "X_umap": ["umap_1", "umap_2"]
    }
)
```

