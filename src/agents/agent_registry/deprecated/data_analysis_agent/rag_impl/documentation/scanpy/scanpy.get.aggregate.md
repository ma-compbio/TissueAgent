## scanpy.get.aggregate(adata, by, func, \*, axis=None, mask=None, dof=1, layer=None, obsm=None, varm=None)
Aggregate data matrix based on some categorical grouping.

This function is useful for pseudobulking as well as plotting.

Aggregation to perform is specified by `func`, which can be a single metric or a
list of metrics. Each metric is computed over the group and results in a new layer
in the output `AnnData` object.

If none of `layer`, `obsm`, or `varm` are passed in, `X` will be used for aggregation data.

* **Parameters:**
  **adata** 
  : [`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData) to be aggregated.

  **by** 
  : Key of the column to be grouped-by.

  **func** 
  : How to aggregate.

  **axis** 
  : Axis on which to find group by column.

  **mask** 
  : Boolean mask (or key to column containing mask) to apply along the axis.

  **dof** 
  : Degrees of freedom for variance. Defaults to 1.

  **layer** 
  : If not None, key for aggregation data.

  **obsm** 
  : If not None, key for aggregation data.

  **varm** 
  : If not None, key for aggregation data.
* **Return type:**
  [`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData)
* **Returns:**
  Aggregated [`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData).

### Examples

Calculating mean expression and number of nonzero entries per cluster:

```pycon
>>> import scanpy as sc, pandas as pd
>>> pbmc = sc.datasets.pbmc3k_processed().raw.to_adata()
>>> pbmc.shape
(2638, 13714)
>>> aggregated = sc.get.aggregate(
...     pbmc, by="louvain", func=["mean", "count_nonzero"]
... )
>>> aggregated
AnnData object with n_obs × n_vars = 8 × 13714
    obs: 'louvain'
    var: 'n_cells'
    layers: 'mean', 'count_nonzero'
```

We can group over multiple columns:

```pycon
>>> pbmc.obs["percent_mito_binned"] = pd.cut(pbmc.obs["percent_mito"], bins=5)
>>> sc.get.aggregate(
...     pbmc, by=["louvain", "percent_mito_binned"], func=["mean", "count_nonzero"]
... )
AnnData object with n_obs × n_vars = 40 × 13714
    obs: 'louvain', 'percent_mito_binned'
    var: 'n_cells'
    layers: 'mean', 'count_nonzero'
```

Note that this filters out any combination of groups that wasn’t present in the original data.

