---
title: "Analyze Visium fluorescence data"
keywords:
  - "squidpy"
  - "visium"
  - "fluorescence"
  - "segmentation"
  - "image-features"
  - "clustering"
---
# Analyze Visium fluorescence data

This tutorial shows how to apply Squidpy image analysis features for the analysis of Visium data.

For a tutorial using Visium data that includes the graph analysis functions, have a look at
`tutorial_visium_hne`.
The dataset used here consists of a Visium slide of a coronal section of the mouse brain.
The original dataset is publicly available at the
Here, we provide a pre-processed dataset, with pre-annotated clusters, in `anndata.AnnData` format and the


    - The pre-processing pipeline is the same as the one shown in the original
      Scanpy tutorial  .
    - The cluster annotation was performed using several resources, such as the
      Allen Brain Atlas  ,

## Import packages & data
environment.yml .


```python
import pandas as pd

import matplotlib.pyplot as plt

import anndata as ad
import scanpy as sc
import squidpy as sq

sc.logging.print_header()
print(f"squidpy=={sq.__version__}")

# load the pre-processed dataset
img = sq.datasets.visium_fluo_image_crop()
adata = sq.datasets.visium_fluo_adata_crop()
```

First, let's visualize the cluster annotation in the spatial context

We provide this crop to make the execution time of this tutorial a bit shorter.


```python
sq.pl.spatial_scatter(adata, color="cluster")
```

The fluorescence image provided with this dataset has three channels:
*DAPI* (specific to DNA), *anti-NEUN* (specific to neurons), *anti-GFAP* (specific to Glial cells).
We can directly visualize the channels with the method `squidpy.im.ImageContainer.show`.


```python
img.show(channelwise=True)
```

Visium datasets contain high-resolution images of the tissue.
Using the function `squidpy.im.calculate_image_features` you can calculate image features

By extracting image features we are aiming to get both similar and complementary information to the
Similar information is for example present in the case of a tissue with two different cell types
Such cell type information is then contained in both the gene expression values and the tissue image features.
Complementary or additional information is present in the fact that we can use a nucleus segmentation

Squidpy contains several feature extractors and a flexible pipeline of calculating features
There are several detailed examples of how to use `squidpy.im.calculate_image_features`.
`../examples/image/compute_features` provides a good starting point for learning more.

Here, we will extract `summary`, `histogram`, `segmentation`, and `texture` features.
To provide more context and allow the calculation of multi-scale features, we will additionally calculate
`summary` and `histogram` features at different crop sizes and scales.

## Image segmentation
To calculate `segmentation` features, we first need to segment the tissue image using `squidpy.im.segment`.
But even before that, it's best practice to pre-process the image by e.g. smoothing it using
We will then use the *DAPI* channel of the fluorescence image (``channel_id s= 0``).
Please refer to `../examples/image/compute_segment_fluo`
for more details on how to calculate a segmented image.


```python
sq.im.process(
    img=img,
    layer="image",
    method="smooth",
)

sq.im.segment(img=img, layer="image_smooth", method="watershed", channel=0, chunks=1000)

# plot the resulting segmentation
fig, ax = plt.subplots(1, 2)
img_crop = img.crop_corner(2000, 2000, size=500)
img_crop.show(layer="image", channel=0, ax=ax[0])
img_crop.show(
    layer="segmented_watershed",
    channel=0,
    ax=ax[1],
)
```

The result of `squidpy.im.segment` is saved in ``img['segmented_watershed']`` by default.
It is a label image where each segmented object is annotated with a different integer number.

## Segmentation features
We can now use the segmentation to calculate segmentation features.
These include morphological features of the segmented objects and channel-wise image
In particular, we can count the segmented objects within each Visium spot to get an
In addition, we can calculate the mean intensity of each fluorescence channel within the segmented objects.
Depending on the fluorescence channels, this can give us e.g., an estimation of the cell type.
For more details on how the segmentation features, you can have a look at
`../examples/image/compute_segmentation_features`.


```python
# define image layer to use for segmentation
features_kwargs = {"segmentation": {"label_layer": "segmented_watershed"}}
# calculate segmentation features
sq.im.calculate_image_features(
    adata,
    img,
    features="segmentation",
    layer="image",
    key_added="features_segmentation",
    n_jobs=1,
    features_kwargs=features_kwargs,
)
# plot results and compare with gene-space clustering
sq.pl.spatial_scatter(
    sq.pl.extract(adata, "features_segmentation"),
    color=[
        "segmentation_label",
        "cluster",
        "segmentation_ch-0_mean_intensity_mean",
        "segmentation_ch-1_mean_intensity_mean",
    ],
    frameon=False,
    ncols=2,
)
```

Such method is particularly useful for plotting purpose, as shown above.

This fine-grained view of the Hippocampus is not visible in the gene clusters where

*Cortex_3* have a higher intensity of channel 1, *anti-NEUN* (lower left).
This means that these areas have more neurons that the remaining areas in this crop.
In addition, cluster *Fiber_tracts* and *lateral ventricles* seems to be enriched with *Glial cells*,

## Extract and cluster features
Now we will calculate summary, histogram, and texture features.
These features provide a useful compressed summary of the tissue image.
For more information on these features, refer to:

  - `../examples/image/compute_summary_features`.
  - `../examples/image/compute_histogram_features`.
  - `../examples/image/compute_texture_features`.


```python
# define different feature calculation combinations
params = {
    # all features, corresponding only to tissue underneath spot
    "features_orig": {
        "features": ["summary", "texture", "histogram"],
        "scale": 1.0,
        "mask_circle": True,
    },
    # summary and histogram features with a bit more context, original resolution
    "features_context": {"features": ["summary", "histogram"], "scale": 1.0},
    # summary and histogram features with more context and at lower resolution
    "features_lowres": {"features": ["summary", "histogram"], "scale": 0.25},
}

for feature_name, cur_params in params.items():
    # features will be saved in `adata.obsm[feature_name]`
    sq.im.calculate_image_features(
        adata, img, layer="image", key_added=feature_name, n_jobs=1, **cur_params
    )

# combine features in one dataframe
adata.obsm["features"] = pd.concat(
    [adata.obsm[f] for f in params.keys()], axis="columns"
)

# make sure that we have no duplicated feature names in the combined table
adata.obsm["features"].columns = ad.utils.make_index_unique(
    adata.obsm["features"].columns
)
```

We can use the extracted image features to compute a new cluster annotation.
This could be useful to gain insights in similarities across spots based on image morphology.

For this, we first define a helper function to cluster features.


```python
def cluster_features(features: pd.DataFrame, like=None):
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
```

Then, we calculate feature clusters using different features and compare them to gene clusters:


```python
adata.obs["features_summary_cluster"] = cluster_features(
    adata.obsm["features"], like="summary"
)
adata.obs["features_histogram_cluster"] = cluster_features(
    adata.obsm["features"], like="histogram"
)
adata.obs["features_texture_cluster"] = cluster_features(
    adata.obsm["features"], like="texture"
)

sc.set_figure_params(facecolor="white", figsize=(8, 8))
sq.pl.spatial_scatter(
    adata,
    color=[
        "features_summary_cluster",
        "features_histogram_cluster",
        "features_texture_cluster",
        "cluster",
    ],
    ncols=3,
)
```


This is a higher level of detail than the gene-space clustering provides with only one cluster for the Hippocampus.

It might be possible to re-cluster the gene expression counts with a higher resolution to also get
