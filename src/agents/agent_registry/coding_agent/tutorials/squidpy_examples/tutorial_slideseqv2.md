---
title: "Analyze Slide-seqV2 data"
keywords:
  - "squidpy"
  - "slide-seqv2"
  - "neighborhood-enrichment"
  - "ripley"
  - "ligand-receptor"
  - "spatial-autocorrelation"
---
# Analyze Slide-seqV2 data

This tutorial shows how to apply Squidpy for the analysis of Slide-seqV2 data.

We provide a pre-processed subset of the data, in `anndata.AnnData` format.
We would like to thank @tudaga for providing cell-type level annotation.
For details on how it was pre-processed, please refer to the original paper.

## Import packages & data
environment.yml .


```python
import squidpy as sq

print(f"squidpy=={sq.__version__}")

# load the pre-processed dataset
adata = sq.datasets.slideseqv2()
adata
```

First, let's visualize cluster annotation in spatial context
with `squidpy.pl.spatial_scatter`.


```python
sq.pl.spatial_scatter(adata, color="cluster", size=1, shape=None)
```

## Neighborhood enrichment analysis
Similar to other spatial data, we can investigate spatial organization of clusters
You can compute such score with the following function: `squidpy.gr.nhood_enrichment`.
In short, it's an enrichment score on spatial proximity of clusters:
On the other hand, if they are far apart, the score will be low
This score is based on a permutation-based test, and you can set

Since the function works on a connectivity matrix, we need to compute that as well.
This can be done with `squidpy.gr.spatial_neighbors`.
Please see `../examples/graph/compute_spatial_neighbors` and
`../examples/graph/compute_nhood_enrichment` for more details

Finally, we'll directly visualize the results with `squidpy.pl.nhood_enrichment`.
We'll add a dendrogram to the heatmap computed with linkage method *ward*.


```python
sq.gr.spatial_neighbors(adata, coord_type="generic")
sq.gr.nhood_enrichment(adata, cluster_key="cluster")
sq.pl.nhood_enrichment(
    adata, cluster_key="cluster", method="single", cmap="inferno", vmin=-50, vmax=100
)
```

For this, we'll use `squidpy.pl.spatial_scatter` again.


```python
sq.pl.spatial_scatter(
    adata,
    shape=None,
    color="cluster",
    groups=["Endothelial_Tip", "Ependymal", "Oligodendrocytes", "Polydendrocytes"],
    size=3,
)
```

## Ripley's statistics
In addition to the neighbor enrichment score, we can further investigate spatial
Ripley's statistics allow analyst to evaluate whether a discrete annotation (e.g. cell-type)
In Squidpy, we implement three closely related Ripley's statistics, that can be
We'll visualize the results with `squidpy.pl.ripley`.
Check `../examples/graph/compute_ripley` for more details.


```python
mode = "L"
sq.gr.ripley(adata, cluster_key="cluster", mode=mode, max_dist=500)
sq.pl.ripley(adata, cluster_key="cluster", mode=mode)
```

selectively visualize again their spatial organization.


```python
sq.pl.spatial_scatter(
    adata,
    color="cluster",
    groups=["Mural", "CA1_CA2_CA3_Subiculum"],
    size=3,
    shape=None,
)
```

## Ligand-receptor interaction analysis
The analysis showed above has provided us with quantitative information on
We might be interested in getting a list of potential candidates that might be driving
This naturally translates in doing a ligand-receptor interaction analysis.
In Squidpy, we provide a fast re-implementation the popular method CellPhoneDB `cellphonedb`
You can run the analysis for all clusters pairs, and all genes (in seconds,

Let's perform the analysis and visualize the result for three clusters of
For the visualization, we will filter out annotations
Check `../examples/graph/compute_ligrec` for more details.


```python
sq.gr.ligrec(
    adata,
    n_perms=100,
    cluster_key="cluster",
    clusters=["Polydendrocytes", "Oligodendrocytes"],
)
sq.pl.ligrec(
    adata,
    cluster_key="cluster",
    source_groups="Oligodendrocytes",
    target_groups=["Polydendrocytes"],
    pvalue_threshold=0.05,
    swap_axes=True,
)
```


## Spatially variable genes with spatial autocorrelation statistics
Lastly, with Squidpy we can investigate spatial variability of gene expression.
`squidpy.gr.spatial_autocorr` conveniently wraps two
They provide a score on the degree of spatial variability of gene expression.
The statistic as well as the p-value are computed for each gene, and FDR correction
See `../examples/graph/compute_moran` for more details.


```python
sq.gr.spatial_autocorr(adata, mode="moran")
adata.uns["moranI"].head(10)
```

The results are stored in `adata.uns["moranI"]` and we can visualize selected genes
with `squidpy.pl.spatial_scatter`.


```python
sq.pl.spatial_scatter(
    adata,
    shape=None,
    color=["Ttr", "Plp1", "Mbp", "Hpca", "Enpp2"],
    size=0.1,
)
```
