---
title: "Analyze Merfish data"
keywords:
  - "squidpy"
  - "merfish"
  - "3d-spatial"
  - "neighborhood-enrichment"
  - "spatial-autocorrelation"
  - "differential-expression"
---
# Analyze Merfish data

This tutorial shows how to apply Squidpy for the analysis of Merfish data.

We provide a pre-processed subset of the data, in `anndata.AnnData` format.
For details on how it was pre-processed, please refer to the original paper.


## Import packages & data
environment.yml .


```python
import scanpy as sc
import squidpy as sq

sc.logging.print_header()
print(f"squidpy=={sq.__version__}")

# load the pre-processed dataset
adata = sq.datasets.merfish()
adata
```

It represents an interesting example of how to work with 3D spatial data in Squidpy.
Let's start with visualization: we can either visualize the 3D stack of slides
using `scanpy.pl.embedding`:


```python
sc.pl.embedding(adata, basis="spatial3d", projection="3d", color="Cell_class")
```

Or visualize a single slide with `squidpy.pl.spatial_scatter`. Here the slide identifier
is stored in `adata.obs["Bregma"]`, see original paper for definition.


```python
sq.pl.spatial_scatter(
    adata[adata.obs.Bregma == -9], shape=None, color="Cell_class", size=1
)
```

## Neighborhood enrichment analysis in 3D
It is important to consider whether the analysis should be performed on the 3D
Let's start with the neighborhood enrichment score. You can read more on the function
First, we need to compute a neighbor graph with `squidpy.gr.spatial_neighbors`.
If we want to compute the neighbor graph on the 3D coordinate space,
Then we can use `squidpy.gr.nhood_enrichment` to compute the score, and visualize
it with `squidpy.pl.nhood_enrichment`.


```python
sq.gr.spatial_neighbors(adata, coord_type="generic", spatial_key="spatial3d")
sq.gr.nhood_enrichment(adata, cluster_key="Cell_class")
sq.pl.nhood_enrichment(
    adata, cluster_key="Cell_class", method="single", cmap="inferno", vmin=-50, vmax=100
)
```

We can visualize some of the co-enriched clusters with `scanpy.pl.embedding`.
We will set `na_colors=(1,1,1,0)` to make transparent the other observations,
in order to better visualize the clusters of interests across z-stacks.


```python
sc.pl.embedding(
    adata,
    basis="spatial3d",
    groups=["OD Mature 1", "OD Mature 2", "OD Mature 4"],
    na_color=(1, 1, 1, 0),
    projection="3d",
    color="Cell_class",
)
```

We can also visualize gene expression in 3D coordinates. Let's perform differential
expression testing with `scanpy.tl.rank_genes_groups` and visualize the results


```python
sc.tl.rank_genes_groups(adata, groupby="Cell_class")
sc.pl.rank_genes_groups(adata, groupby="Cell_class")
```

and the expression in 3D.


```python
sc.pl.embedding(adata, basis="spatial3d", projection="3d", color=["Gad1", "Mlc1"])
```

If the same analysis should be performed on a single slice, then it is advisable to
a standard 2D spatial data object.


```python
adata_slice = adata[adata.obs.Bregma == -9].copy()
sq.gr.spatial_neighbors(adata_slice, coord_type="generic")
sq.gr.nhood_enrichment(adata, cluster_key="Cell_class")
sq.pl.spatial_scatter(
    adata_slice,
    color="Cell_class",
    shape=None,
    groups=[
        "Ependymal",
        "Pericytes",
        "Endothelial 2",
    ],
    size=10,
)
```

## Spatially variable genes with spatial autocorrelation statistics
With Squidpy we can investigate spatial variability of gene expression.
This is an example of a function that only supports 2D data.
`squidpy.gr.spatial_autocorr` conveniently wraps two
They provide a score on the degree of spatial variability of gene expression.
The statistic as well as the p-value are computed for each gene, and FDR correction
The results are stored in `adata.uns['moranI']` and we can visualize selected genes
with `squidpy.pl.spatial_scatter`.


```python
sq.gr.spatial_autocorr(adata_slice, mode="moran")
adata_slice.uns["moranI"].head()
sq.pl.spatial_scatter(
    adata_slice, shape=None, color=["Cd24a", "Necab1", "Mlc1"], size=3
)
```
