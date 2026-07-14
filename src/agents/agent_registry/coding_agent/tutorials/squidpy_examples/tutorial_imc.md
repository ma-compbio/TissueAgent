---
title: "Analyze Imaging Mass Cytometry data"
keywords:
  - "squidpy"
  - "imc"
  - "imaging-mass-cytometry"
  - "co-occurrence"
  - "neighborhood-enrichment"
  - "centrality"
---
# Analyze Imaging Mass Cytometry data

This tutorial shows how to apply Squidpy to Imaging Mass Cytometry data.

We provide a pre-processed subset of the data, in `anndata.AnnData` format.
For details on how it was pre-processed, please refer to the original paper.


## Import packages & data
environment.yml .


```python
import squidpy as sq

print(f"squidpy=={sq.__version__}")

# load the pre-processed dataset
adata = sq.datasets.imc()
```

First, let's visualize the cluster annotation in spatial context
with `squidpy.pl.spatial_scatter`.


```python
sq.pl.spatial_scatter(adata, shape=None, color="cell type", size=10)
```

*Macrophages* and different types of *Stromal cells*. We can also

### Co-occurrence across spatial dimensions

We can visualize cluster co-occurrence in spatial dimensions using the original
The co-occurrence score is defined as:


We can compute this score with `squidpy.gr.co_occurrence`
`squidpy.pl.co_occurrence`.
We visualize the result for two conditional groups, namely
*basal CK tumor cell* and *T cells*.


```python
sq.gr.co_occurrence(adata, cluster_key="cell type")
sq.pl.co_occurrence(
    adata,
    cluster_key="cell type",
    clusters=["basal CK tumor cell", "T cells"],
    figsize=(15, 4),
)
```


### Neighborhood enrichment
A similar analysis that can inform on the neighbor structure of
You can compute such score with the following function: `squidpy.gr.nhood_enrichment`.
In short, it's an enrichment score on spatial proximity of clusters:
On the other hand, if they are far apart, the score will be low
This score is based on a permutation-based test, and you can set

Since the function works on a connectivity matrix, we need to compute that as well.
This can be done with `squidpy.gr.spatial_neighbors`.
Please see `../examples/graph/compute_spatial_neighbors` for more details

Finally, we visualize the results with `squidpy.pl.nhood_enrichment`.


```python
sq.gr.spatial_neighbors(adata)
sq.gr.nhood_enrichment(adata, cluster_key="cell type")
sq.pl.nhood_enrichment(adata, cluster_key="cell type")
```

*endothelial cells*, as well as *macrophages*. Another interesting

### Interaction matrix and network centralities
Squidpy provides other descriptive statistics of the spatial graph.
For instance, the interaction matrix, which counts the number of edges
This score can be computed with the function `squidpy.gr.interaction_matrix`.
We can visualize the results with  `squidpy.pl.interaction_matrix`.


```python
sq.gr.interaction_matrix(adata, cluster_key="cell type")
sq.pl.interaction_matrix(adata, cluster_key="cell type")
```

Finally, similar to the previous analysis,

  - degree_centrality.
  - average_clustering.
  - closeness_centrality.

Squidpy provides a convenient function for all of them:
`squidpy.gr.centrality_scores` and
`squidpy.pl.centrality_scores` for visualization.


```python
sq.gr.centrality_scores(
    adata,
    cluster_key="cell type",
)
sq.pl.centrality_scores(adata, cluster_key="cell type", figsize=(20, 5), s=500)
```
