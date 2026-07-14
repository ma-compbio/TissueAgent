---
title: "Analyze 4i data"
keywords:
  - "squidpy"
  - "4i"
  - "neighborhood-enrichment"
  - "spatial-autocorrelation"
  - "moran"
  - "interaction-matrix"
---
# Analyze 4i data

This tutorial shows how to apply Squidpy for the analysis of 4i data.

We provide a pre-processed subset of the data, in `anndata.AnnData` format.
For details on how it was pre-processed, please refer to the original paper.

## Import packages & data
environment.yml .


```python
import squidpy as sq

print(f"squidpy=={sq.__version__}")

# load the pre-processed dataset
adata = sq.datasets.four_i()
```

First, let's visualize cluster annotation in spatial context
with `squidpy.pl.spatial_scatter`.


```python
sq.pl.spatial_scatter(adata, shape=None, color="cluster", size=1)
```

## Neighborhood enrichment analysis
Similar to other spatial data, we can investigate spatial organization of clusters
You can compute such score with the following function: `squidpy.gr.nhood_enrichment`.
In short, it's an enrichment score on spatial proximity of clusters:
On the other hand, if they are far apart, the score will be low
This score is based on a permutation-based test, and you can set

Since the function works on a connectivity matrix, we need to compute that as well.
This can be done with `squidpy.gr.spatial_neighbors`.
Please see `../examples/graph/compute_spatial_neighbors` for more details

Finally, we'll directly visualize the results with `squidpy.pl.nhood_enrichment`.
We'll add a dendrogram to the heatmap computed with linkage method *ward*.


```python
sq.gr.spatial_neighbors(adata, coord_type="generic")
sq.gr.nhood_enrichment(adata, cluster_key="cluster")
sq.pl.nhood_enrichment(adata, cluster_key="cluster", method="ward", vmin=-100, vmax=100)
```

A similar analysis can be performed with `squidpy.gr.interaction_matrix`.
The function computes the number of shared edges in the neighbor graph between clusters.
Please see `../examples/graph/compute_interaction_matrix` for more details
of how this function works.


```python
sq.gr.interaction_matrix(adata, cluster_key="cluster")
sq.pl.interaction_matrix(adata, cluster_key="cluster", method="ward", vmax=20000)
```

Additional analyses to gain quantitative understanding of spatial patterning of
- `../examples/graph/compute_ripley` for Ripley's statistics.
- `../examples/graph/compute_co_occurrence` for co-occurrence score.

## Spatially variable genes with spatial autocorrelation statistics
With Squidpy we can investigate spatial variability of gene expression.
This is an example of a function that only supports 2D data.
`squidpy.gr.spatial_autocorr` conveniently wraps two
They provide a score on the degree of spatial variability of gene expression.
The statistic as well as the p-value are computed for each gene, and FDR correction
See `../examples/graph/compute_moran` for more details.


```python
adata.var_names_make_unique()
sq.gr.spatial_autocorr(adata, mode="moran")
adata.uns["moranI"].head(10)
```

The results are stored in `adata.uns['moranI']` and we can visualize selected genes
with `squidpy.pl.spatial_scatter`.


```python
sq.pl.spatial_scatter(adata, shape=None, color="Yap/Taz", size=1)
```
