---
title: "Analyze Visium H&E data"
keywords:
  - "squidpy"
  - "visium"
  - "h&e"
  - "image-features"
  - "neighborhood-enrichment"
  - "ligand-receptor"
  - "spatial-autocorrelation"
---
# Analyze Visium H&E data

This tutorial shows how to apply Squidpy for the analysis of Visium spatial transcriptomics data.

The dataset used here consists of a Visium slide of a coronal section of the mouse brain.
The original dataset is publicly available at the
Here, we provide a pre-processed dataset, with pre-annotated clusters, in AnnData format and the


    - The pre-processing pipeline is the same as the one shown in the original
      Scanpy tutorial  .
    - The cluster annotation was performed using several resources, such as the
      Allen Brain Atlas  ,

## Import packages & data
environment.yml .


```python
import numpy as np
import pandas as pd

import anndata as ad
import scanpy as sc
import squidpy as sq

sc.logging.print_header()
print(f"squidpy=={sq.__version__}")

# load the pre-processed dataset
img = sq.datasets.visium_hne_image()
adata = sq.datasets.visium_hne_adata()
```

First, let's visualize cluster annotation in spatial context
with `squidpy.pl.spatial_scatter`.


```python
sq.pl.spatial_scatter(adata, color="cluster")
```

## Image features
Visium datasets contain high-resolution images of the tissue that was used for the gene extraction.
Using the function `squidpy.im.calculate_image_features` you can calculate image features

By extracting image features we are aiming to get both similar and complementary information to the
Similar information is for example present in the case of a tissue with two different cell types
Such cell type information is then contained in both the gene expression values and the tissue image features.

Squidpy contains several feature extractors and a flexible pipeline of calculating features
There are several detailed examples of how to use `squidpy.im.calculate_image_features`.
`../examples/image/compute_features` provides a good starting point for learning more.

Here, we will extract `summary` features at different crop sizes and scales to allow
For more information on the summary features,
also refer to `../examples/image/compute_summary_features`.


```python
# calculate features for different scales (higher value means more context)
for scale in [1.0, 2.0]:
    feature_name = f"features_summary_scale{scale}"
    sq.im.calculate_image_features(
        adata,
        img.compute(),
        features="summary",
        key_added=feature_name,
        n_jobs=4,
        scale=scale,
    )


# combine features in one dataframe
adata.obsm["features"] = pd.concat(
    [adata.obsm[f] for f in adata.obsm.keys() if "features_summary" in f],
    axis="columns",
)
# make sure that we have no duplicated feature names in the combined table
adata.obsm["features"].columns = ad.utils.make_index_unique(
    adata.obsm["features"].columns
)
```

We can use the extracted image features to compute a new cluster annotation.
This could be useful to gain insights in similarities across spots based on image morphology.


```python
# helper function returning a clustering
def cluster_features(features: pd.DataFrame, like=None) -> pd.Series:
    """
    Calculate leiden clustering of features.

    Specify filter of features using `like`.
    """
    # filter features
    if like is not None:
        features = features.filter(like=like)
    # create temporary adata to calculate the clustering
    adata = ad.AnnData(features)
    # important - feature values are not scaled, so need to scale them before PCA
    sc.pp.scale(adata)
    # calculate leiden clustering
    sc.pp.pca(adata, n_comps=min(10, features.shape[1] - 1))
    sc.pp.neighbors(adata)
    sc.tl.leiden(adata)

    return adata.obs["leiden"]


# calculate feature clusters
adata.obs["features_cluster"] = cluster_features(adata.obsm["features"], like="summary")

# compare feature and gene clusters
sq.pl.spatial_scatter(adata, color=["features_cluster", "cluster"])
```

In others, the feature clusters look different, like in the cortex,


## Spatial statistics and graph analysis
Similar to other spatial data, we can investigate spatial organization

### Neighborhood enrichment
Computing a neighborhood enrichment can help us identify spots clusters that share
We can compute such score with the following function: `squidpy.gr.nhood_enrichment`.
In short, it's an enrichment score on spatial proximity of clusters:
On the other hand, if they are far apart, and therefore are seldom a neighborhood,

Since the function works on a connectivity matrix, we need to compute that as well.
This can be done with `squidpy.gr.spatial_neighbors`.
Please see `../examples/graph/compute_spatial_neighbors` for more details

Finally, we'll directly visualize the results with `squidpy.pl.nhood_enrichment`.


```python
sq.gr.spatial_neighbors(adata)
sq.gr.nhood_enrichment(adata, cluster_key="cluster")
sq.pl.nhood_enrichment(adata, cluster_key="cluster")
```

*Pyramidal_layer_dentate_gyrus* and *Pyramidal_layer* clusters seems

### Co-occurrence across spatial dimensions
In addition to the neighbor enrichment score, we can visualize cluster co-occurrence in spatial dimensions.
This is a similar analysis of the one presented above, yet it does not operate on the connectivity matrix,


The score is computed across increasing radii size around each observation (i.e. spots here) in the tissue.

We are gonna compute such score with `squidpy.gr.co_occurrence` and set the cluster annotation
Then, we visualize the results with `squidpy.pl.co_occurrence`.


```python
sq.gr.co_occurrence(adata, cluster_key="cluster")
sq.pl.co_occurrence(
    adata,
    cluster_key="cluster",
    clusters="Hippocampus",
    figsize=(8, 4),
)
```


### Ligand-receptor interaction analysis
We are continuing the analysis showing couple of feature-level methods that are very relevant
This naturally translates in a ligand-receptor interaction analysis.
In Squidpy, we provide a fast re-implementation the popular method CellPhoneDB `cellphonedb`
You can run the analysis for all clusters pairs, and all genes (in seconds,
Furthermore, we'll directly visualize the results, filtering out lowly-expressed genes
We'll also subset the visualization for only one source group,
the *Hippocampus* cluster, and two target groups, *Pyramidal_layer_dentate_gyrus* and *Pyramidal_layer* cluster.


```python
sq.gr.ligrec(
    adata,
    n_perms=100,
    cluster_key="cluster",
)
sq.pl.ligrec(
    adata,
    cluster_key="cluster",
    source_groups="Hippocampus",
    target_groups=["Pyramidal_layer", "Pyramidal_layer_dentate_gyrus"],
    means_range=(3, np.inf),
    alpha=1e-4,
    swap_axes=True,
)
```


### Spatially variable genes with Moran's I
Finally, we might be interested in finding genes that show spatial patterns.
There are several methods that aimed at address this explicitly,

  - *SPARK* - paper _,
  - *Spatial DE*  - paper _,
  - *trendsceek* - paper _,
  - *HMRF* - paper _,

Here, we provide a simple approach based on the well-known
Moran's I statistics
The function in Squidpy is called `squidpy.gr.spatial_autocorr`, and
For time reasons, we will evaluate a subset of the highly variable genes only.


```python
genes = adata[:, adata.var.highly_variable].var_names.values[:1000]
sq.gr.spatial_autocorr(
    adata,
    mode="moran",
    genes=genes,
    n_perms=100,
    n_jobs=1,
)
```

The results are saved in ``adata.uns['moranI']`` slot.
Genes have already been sorted by Moran's I statistic.


```python
adata.uns["moranI"].head(10)
```

We can select few genes and visualize their expression levels in the tissue with `squidpy.pl.spatial_scatter`.


```python
sq.pl.spatial_scatter(adata, color=["Olfm1", "Plp1", "Itpka", "cluster"])
```
