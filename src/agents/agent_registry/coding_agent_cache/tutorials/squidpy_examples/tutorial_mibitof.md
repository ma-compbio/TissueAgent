---
title: "Analyze MIBI-TOF image data"
keywords:
  - "squidpy"
  - "mibitof"
  - "image-container"
  - "segmentation"
  - "feature-extraction"
  - "cmyk"
---
# Analyze MIBI-TOF image data

This tutorial shows how to apply Squidpy to MIBI-TOF data.

We provide a pre-processed subset of the data, in `anndata.AnnData` format.
For details on how it was pre-processed, please refer to the original paper.


## Import packages & data
environment.yml .


```python
import numpy as np

import matplotlib.pyplot as plt

import squidpy as sq

adata = sq.datasets.mibitof()
```

As imaging information, we included three raw image channels:

  - `145_CD45` - a immune cell marker (cyan).
  - `174_CK` - a tumor marker (magenta).
  - `113_vimentin` - a mesenchymal cell marker (yellow).


The `adata` object contains three different libraries, one for each biopsy.
The images are contained in ``adata.uns['spatial'][<library_id>]['images']``.
Let us visualize the cluster annotations for each library using `squidpy.pl.spatial_scatter`.


```python
sq.pl.spatial_segment(
    adata, color="Cluster", library_key="library_id", seg_cell_id="cell_id"
)
```

Let us create an ImageContainer from the images contained in `adata`.
As all three biopsies are already joined in `adata`, let us also create one ImageContainer for
For more information on how to use `ImageContainer` with z-stacks, also have a look at
`tutorial_image_container_zstacks`.


```python
imgs = []
for library_id in adata.uns["spatial"].keys():
    img = sq.im.ImageContainer(
        adata.uns["spatial"][library_id]["images"]["hires"], library_id=library_id
    )
    img.add_img(
        adata.uns["spatial"][library_id]["images"]["segmentation"],
        library_id=library_id,
        layer="segmentation",
    )
    img["segmentation"].attrs["segmentation"] = True
    imgs.append(img)
img = sq.im.ImageContainer.concat(imgs)
```

Note that we also added the segmentation as an additional layer to `img`, and set the
`segmentation` attribute in the ImageContainer.
This allows visualization of the segmentation layer as a `labels` layer in Napari.


```python
img
```

If you have Napari installed, you can have a look at the data using the interactive viewer:
Note that you can load the segmentation layer as an overlay over the image.

Let us also statically visualize the data in `img`, using `squidpy.im.ImageCntainer.show`:


```python
img.show("image")
img.show("image", segmentation_layer="segmentation")
```

In the following we show how to use Squidpy to extract cellular mean intensity information using raw images
In the present case, `adata` of course already contains the post-processed cellular mean intensity
The aim of this tutorial, however, is to showcase how the extraction of such features is possible using Squidpy.
As Squidpy is backed by `dask` and supports chunked image processing,

## Convert image to CMYK
As already mentioned, the images contain information from three raw channels, `145_CD45`,
`174_CK`, and `113_vimentin`.
As the channel information is encoded in CMYK space, we first need to convert the RGB images to CMYK.

For this, we can use `squidpy.im.ImageContainer.apply`.


```python
def rgb2cmyk(arr):
    """Convert arr from RGB to CMYK color space."""
    R = arr[..., 0] / 255
    G = arr[..., 1] / 255
    B = arr[..., 2] / 255
    K = 1 - (np.max(arr, axis=-1) / 255)
    C = (1 - R - K) / (1 - K + np.finfo(float).eps)  # avoid division by 0
    M = (1 - G - K) / (1 - K + np.finfo(float).eps)
    Y = (1 - B - K) / (1 - K + np.finfo(float).eps)
    return np.stack([C, M, Y, K], axis=3)


img.apply(rgb2cmyk, layer="image", new_layer="image_cmyk", copy=False)
img.show("image_cmyk", channelwise=True)
```

## Extract per-cell mean intensity
Now that we have disentangled the individual channels, let use use the provided segmentation mask

By default, the `segmentation` feature extractor extracts information using all segments (cells)
As we would like to only get information of the segment (cell) in the center of the current crop,

Fist, define a custom feature extraction function. This function needs to get the segmentation mask
We will achieve this by passing an ``additional_layers`` argument to the `custom` feature extractor.
This special argument will pass the values of every layer in `additional_layers`
to the custom feature extraction function.


```python
def segmentation_image_intensity(arr, image_cmyk):
    """
    Calculate per-channel mean intensity of the center segment.

    arr: the segmentation
    image_cmyk: the raw image values
    """
    import skimage.measure

    # the center of the segmentation mask contains the current label
    # use that to calculate the mask
    s = arr.shape[0]
    mask = (arr == arr[s // 2, s // 2, 0, 0]).astype(int)
    # use skimage.measure.regionprops to get the intensity per channel
    features = []
    for c in range(image_cmyk.shape[-1]):
        feature = skimage.measure.regionprops_table(
            np.squeeze(mask),  # skimage needs 3d or 2d images, so squeeze excess dims
            intensity_image=np.squeeze(image_cmyk[:, :, :, c]),
            properties=["mean_intensity"],
        )["mean_intensity"][0]
        features.append(feature)
    return features
```

Now, use `squidpy.im.calculate_image_features` with the `custom` feature extractor,
We will use ``spot_scale = 10`` to ensure that we also cover big segments fully by one crop.


```python
sq.im.calculate_image_features(
    adata,
    img,
    library_id="library_id",
    features="custom",
    spot_scale=10,
    layer="segmentation",
    features_kwargs={
        "custom": {
            "func": segmentation_image_intensity,
            "additional_layers": ["image_cmyk"],
        }
    },
)
```

The resulting features are stored in ``adata.obs['img_features']``,
with channel 0 representing `145_CD45`, channel 1 `174_CK`, and channel 2 `113_vimentin`.


```python
adata.obsm["img_features"]
```

As described in `hartmann2020multiplexed`, let us transformed using an
the computed mean intensities with the values contained in `adata`.


```python
adata.obsm["img_features_transformed"] = np.arcsinh(adata.obsm["img_features"] / 0.05)
```

Now, let's visualize the result:


```python
channels = ["CD45", "CK", "vimentin"]

fig, axes = plt.subplots(1, 3, figsize=(15, 3))
for i, ax in enumerate(axes):
    X = np.array(adata[:, channels[i]].X.todense())[:, 0]
    Y = adata.obsm["img_features_transformed"][f"segmentation_image_intensity_{i}"]
    ax.scatter(X, Y)
    ax.set_xlabel("true value in adata.X")
    ax.set_ylabel("computed mean intensity")
    corr = np.corrcoef(X, Y)[1, 0]
    ax.set_title(f"{channels[i]}, corr: {corr:.2f}")
```


`squidpy.gr` module to MIBI-TOF data.
For examples of this, please see our other Analysis tutorials, e.g.
`tutorial_seqfish`.
