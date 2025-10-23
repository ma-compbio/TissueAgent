# Neighbors enrichment analysis

This example shows how to run the neighbors enrichment analysis routine.

It calculates an enrichment score based on proximity on the connectivity graph of cell clusters.
The number of observed events is compared against $N$ permutations and a *z-score* is computed.

:::{seealso}

    See {doc}`compute_spatial_neighbors` for general usage of
    {func}`squidpy.gr.spatial_neighbors`.

:::



```python
import squidpy as sq

adata = sq.datasets.visium_fluo_adata()
adata
```

This dataset contains cell type annotations in {attr}`anndata.Anndata.obs` which are used for calculation of the
neighborhood enrichment. First, we need to compute a connectivity matrix from spatial coordinates.




```python
sq.gr.spatial_neighbors(adata)
```

Then we can calculate the neighborhood enrichment score with {func}`squidpy.gr.nhood_enrichment`.




```python
sq.gr.nhood_enrichment(adata, cluster_key="cluster")
```

And visualize the results with {func}`squidpy.pl.nhood_enrichment`.




```python
sq.pl.nhood_enrichment(adata, cluster_key="cluster")
```
