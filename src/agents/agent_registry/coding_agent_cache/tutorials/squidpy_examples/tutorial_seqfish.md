---
title: "Analyze seqFISH data"
keywords:
  - "squidpy"
  - "seqfish"
  - "neighborhood-enrichment"
  - "co-occurrence"
  - "ligand-receptor"
  - "spatial"
---
# Analyze seqFISH data

This tutorial shows how to apply Squidpy for the analysis of seqFISH data.

We provide a pre-processed subset of the data, in `anndata.AnnData` format.
For details on how it was pre-processed, please refer to the original paper.

## Import packages & data
environment.yml .


```python
import numpy as np

import scanpy as sc
import squidpy as sq

sc.logging.print_header()
print(f"squidpy=={sq.__version__}")

# load the pre-processed dataset
adata = sq.datasets.seqfish()
```

First, let's visualize cluster annotation in spatial context
with `squidpy.pl.spatial_scatter`.


```python
sq.pl.spatial_scatter(
    adata, color="celltype_mapped_refined", shape=None, figsize=(10, 10)
)
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
sq.gr.nhood_enrichment(adata, cluster_key="celltype_mapped_refined")
sq.pl.nhood_enrichment(adata, cluster_key="celltype_mapped_refined", method="ward")
```

For instance, there seems to be an enrichment between the *Lateral plate mesoderm*,
As in the original publication, there also seems to be an association between the *Endothelium* and

  - the construction of the neighbors graph (which in our case is
  - the number of permutation of the neighborhood enrichment

We can also visualize the spatial organization of cells again,
For this, we'll use `squidpy.pl.spatial_scatter` again.


```python
sq.pl.spatial_scatter(
    adata,
    color="celltype_mapped_refined",
    groups=[
        "Endothelium",
        "Haematoendothelial progenitors",
        "Allantois",
        "Lateral plate mesoderm",
        "Intermediate mesoderm",
        "Presomitic mesoderm",
    ],
    shape=None,
    size=2,
)
```

## Co-occurrence across spatial dimensions
In addition to the neighbor enrichment score, we can visualize cluster co-occurrence
This is a similar analysis of the one presented above,
The co-occurrence score is defined as:


We can compute this score with `squidpy.gr.co_occurrence`
`squidpy.pl.co_occurrence`.


```python
sq.gr.co_occurrence(adata, cluster_key="celltype_mapped_refined")
sq.pl.co_occurrence(
    adata,
    cluster_key="celltype_mapped_refined",
    clusters="Lateral plate mesoderm",
    figsize=(10, 5),
)
```

*Intermediate mesoderm* and *Allantois*.
It also seems that at longer distances, there is a co-occurrence of cells belonging to

## Ligand-receptor interaction analysis
The analysis showed above has provided us with quantitative information on
We might be interested in getting a list of potential candidates that might be driving
This naturally translates in doing a ligand-receptor interaction analysis.
In Squidpy, we provide a fast re-implementation the popular method CellPhoneDB `cellphonedb`
You can run the analysis for all clusters pairs, and all genes (in seconds,

Let's perform the analysis and visualize the result for three clusters of
*Intermediate mesoderm* and *Allantois*. For the visualization, we will
and decreasing the threshold for the adjusted p-value (with the ``alpha`` argument).


```python
sq.gr.ligrec(
    adata,
    n_perms=100,
    cluster_key="celltype_mapped_refined",
)
sq.pl.ligrec(
    adata,
    cluster_key="celltype_mapped_refined",
    source_groups="Lateral plate mesoderm",
    target_groups=["Intermediate mesoderm", "Allantois"],
    means_range=(0.3, np.inf),
    alpha=1e-4,
    swap_axes=True,
)
```
