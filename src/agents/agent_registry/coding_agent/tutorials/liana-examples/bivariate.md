---
title: "Spatially-informed Bivariate Metrics"
keywords:
  - "liana+"
  - "spatial"
  - "bivariate"
  - "moran's r"
  - "cosine similarity"
  - "jaccard"
  - "spearman"
  - "permutation"
  - "visium"
  - "nmf"
  - "transcription factors"
  - "cell type compositions"
---
# Spatially-informed Bivariate Metrics

This tutorial provides an overview of the local scores implemented in LIANA+. These scores are used to identify spatially co-expressed ligand-receptor pairs. However, there also applicable to other types of spatially-informed bivariate analyses.

It provides brief explanations of the mathematical formulations of the scores; these include adaptation of bivariate Moran's R, Pearson correlation, Spearman correlation, weighted Jaccard similarity, and Cosine similarity. The tutorial also showcases interaction categories (masks) and significance testing. 

## Environement Setup


```python
import pandas as pd
import scanpy as sc
import decoupler as dc
import liana as li
from matplotlib import pyplot as plt
# set dpi to 50, to make the notebook smaller
plt.rcParams['figure.dpi'] = 50

from mudata import MuData
```

## Load and Normalize Data

To showcase LIANA's local functions, we will use an ischemic 10X Visium spatial slide from [Kuppe et al., 2022](https://www.nature.com/articles/s41586-022-05060-x). It is a tissue sample obtained from a patient with myocardial infarction, focusing on the ischemic zone of the heart tissue. 

The slide provides spatially-resolved information about the cellular composition and gene expression patterns within the tissue.


```python
adata = sc.read("kuppe_heart19.h5ad", backup_url='https://figshare.com/ndownloader/files/41501073?private_link=4744950f8768d5c8f68c')
adata.layers['counts'] = adata.X.copy()
sc.pp.normalize_total(adata, target_sum=1e4)
sc.pp.log1p(adata)
```


```python
adata.obs.head()
```

Spot clusters


```python
sc.pl.spatial(adata, color=[None, 'celltype_niche'], size=1.3, palette='Set1')
```

## Background

Here, we will demonstrate how to use the spatially-informed bivariate metrics to assess the spatial relationship between two variables. Specifically, we focus on local bivariate similarity metrics. In contrast to other spatial Methods, including [Misty](https://liana-py.readthedocs.io/en/latest/notebooks/misty.html); focusing on local spatial relationships enables us to pinpoint the exact location of spatial relationships, and to identify spatial relationships that might occur only in a specific sub-region of our samples.

Following the initial concept of LIANA, and inspired by [scHOT](https://www.nature.com/articles/s41592-020-0885-x), we have natively re-implemented **6** local bivariate metrics, including scHOT's (default) masked Spearman & [SpatialDM's](https://www.biorxiv.org/content/10.1101/2022.08.19.504616v1.full) local Moran's R.

As part of the [LIANA+ manuscript](https://www.biorxiv.org/content/10.1101/2023.08.19.553863v1.full), we performed two distinct tasks to evaluate the ability of these metrics to preserve biological information, and saw that on average when used to identify local ligand-receptor relationships, spatially-weighted Cosine similarity did best. Thus, we will focus on it throughout this tutorial. However, we expect that other scoring functions might be better suited for other tasks, e.g. Spatially-weighted Jaccard Similarity should be well suited for categorical data; thus we encourage you to explore them.

### Available Local Functions


```python
li.mt.bivariate.show_functions()
```

### How do they work?

The local functions work are quite simple, as they are simply weighted versions of well-known similarity metrics. For example, the spatially-weighted version of Cosine similarity is defined as:

$$ \text{wCosine}_i = \frac{\sum_{j=1}^n w_{ij} x_j y_j}{\sqrt{\sum_{j=1}^n w_{ij} x_j^2} \sqrt{\sum_{j=1}^n w_{ij} y_j^2}}$$

where for each spot **i**, we perform summation over all spots **n**, where **w**​ represents the spatial connectivity weights from spot **i** to every other spot **j**;  for variables  **x** and **y**.

### Spatial Connectivity

The way that spatially-informed methods usually work is by making use of weights based on the proximity (or spatial connectivity) between spots/cells.
These spatial connectivities are then used to calculate the metric of interest, e.g. Cosine similarity, in a spatially-informed manner.

The spatial weights in LIANA+ are by default defined as a family of radial kernels that use the inverse Euclidean distance between cells/spots to bind the weights between 0 and 1, with spots that are closest having the highest spatial connectivity to one another (1), while those that are thought to be too far to be in contact are assigned 0.

Key parameters of spatial_neighbors include:
- `bandwidth` controls the radius of the spatial connectivities where higher values will result in a broader area being considered (controls the radius relative to the coordinates stored in `adata.obsm['spatial']`)
- `cutoff` controls the minimum value that will be considered to have a spatial relationship (anything lower than the `cutoff` is set to 0).
- `kernel` controls the distribution (shape) of the weights ('gaussian' by default)
- `set_diag` sets the diagonal (i.e. the weight for each spot to itself) to 1 if True. **NOTE**: Here we set it to True as we expect many cells to be neighbors of themselves within a visium spot

As choosing an optimal bandwidith can be tricky, we provide the ``query_bandwidth`` function which uses a set of coordinates to provide an estimate of how many cell or spot neighbors are being considered for each spot over a range of bandwidths. 


```python
plot, _ = li.ut.query_bandwidth(coordinates=adata.obsm['spatial'], start=0, end=500, interval_n=20)
plot
```

Here, we can see that a bandwidth of 150-200 (pixels) roughly includes 6 neighbours i.e. the first ring of neighbours in the hexagonal grid of 10x Visium. So, we will build the spatial graph with a bandwidth of 200.


```python
li.ut.spatial_neighbors(adata, bandwidth=200, cutoff=0.1, kernel='gaussian', set_diag=True)
```

Let's visualize the spatial weights for a single spot to all other spots in the dataset:


```python
li.pl.connectivity(adata, idx=0, size=1.3, figure_size=(6, 5))
```

<div class="alert alert-success">

LIANA's connectivities are flexible and can be defined in any way that fits the user. We have thus aligned LIANA's `spatial_neighbors` function to [Squidpy](https://github.com/scverse/squidpy)'s `spatial_neighbors` function.
A perfectly viable solution would be to use Squidpy's nearest neighbors graph, which one can use to easily replace LIANA's radial kernel connecitivies.

</div>

## Bivariate Ligand-Receptor Relationships

Now that we have covered the basics, let's see how these scores look for potential ligand-receptor interactions on our 10X Visium Slide.
Note that LIANA+ will take the presence of heteromeric complexes into account at the individual spot-level!


```python
lrdata = li.mt.bivariate(adata,
                resource_name='consensus', # NOTE: uses HUMAN gene symbols!
                local_name='cosine', # Name of the function
                global_name="morans", # Name global function
                n_perms=100, # Number of permutations to calculate a p-value
                mask_negatives=False, # Whether to mask LowLow/NegativeNegative interactions
                add_categories=True, # Whether to add local categories to the results
                nz_prop=0.2, # Minimum expr. proportion for ligands/receptors and their subunits
                use_raw=False,
                verbose=True
                )
```

#### Global Summaries

In addition to the local bivariate scores, we can also get the "global" scores for each pair of variables, which we can choose the best pairs of variables to visualize:



```python
lrdata.var.sort_values("mean", ascending=False).head(3)
```


```python
lrdata.var.sort_values("std", ascending=False).head(3)
```

We can also use Global bivariate Moran's R (or [Lee's statistic](https://onlinelibrary.wiley.com/doi/full/10.1111/gean.12106)) - an extension of univariate Moran's I, as proposed by [Anselin 2019](https://onlinelibrary.wiley.com/doi/full/10.1111/gean.12164) and [Lee and Li, 2019](https://onlinelibrary.wiley.com/doi/full/10.1111/gean.12106); implemented in [SEAGAL](https://academic.oup.com/bioinformatics/article/39/7/btad431/7223197) and [SpatialDM](https://github.com/StatBiomed/SpatialDM).

Bivariate Moran's R values near zero imply spatial independence, while positive or negative values reflect spatial co-clustering or spatial cross-dispersion, respectively.


```python
lrdata.var.sort_values("morans", ascending=False).head()
```

From these Global summaries, we see that the average Cosine similarity largely represents **coverage** - e.g. *TIMP1 & CD63* is ubiquoutesly and uniformly distributed across the slide. 

On the other hand, among most variable interactions and with with the highest global morans R is e.g. **VTN&ITGAV_ITGB5**. This interaction is thus more likely to represent biological relationships, with distinct spatial clustering patterns.

So, let's visualize both:


```python
# NOTE: reset params as plotnine seems to change them
sc.set_figure_params(dpi=80, dpi_save=300, format='png', frameon=False, transparent=True, figsize=[5,5])
```


```python
sc.pl.spatial(lrdata, color=['VTN^ITGAV_ITGB5', 'TIMP1^CD63'], size=1.4, vmax=1, cmap='magma')
```

As expected, we see that the **TIMP1 & CD63** interaction is uniformly distributed across the slide, while **VTN&ITGAV_ITGB5** shows a clear spatial pattern.

We can also see that this is the case when we look at the individual genes:


```python
sc.pl.spatial(adata, color=['VTN', 'ITGAV', 'ITGB5', 
                            'TIMP1', 'CD63'],
              size=1.4, ncols=2)
```

<div class="alert alert-info">
  While Moran's R provides a sound summary of spatial clustering, it is limited to two variables at a time and is thus not fit for complex, or non-linear, spatial relationships between variables. Thus, we also encourage the user to explore <a href="https://liana-py.readthedocs.io/en/latest/notebooks/misty.html">LIANA+'s re-implementation of MISTy</a>.
</div>




### Permutation-based p-values
In addition to the local scores, we also calculated permutation-based p-values based on a null distribution generated by shuffling the spot labels. Let's see how these look for the two interactions from above: 


```python
sc.pl.spatial(lrdata, layer='pvals', color=['VTN^ITGAV_ITGB5', 'TIMP1^CD63'], size=1.4, cmap="magma_r")
```

These largely agree with what we saw above for *VTN&ITGAV_ITGB1* as appears to be specific to a certain region.

### Local Categories

Did you notice that we used `mask_negatives` as a parameter when first estimating the interaction? This essentially means that we mask interactions in which both members are negative (or lowly expressed) when calculating the p-values, i.e. such which occur at places in which both members of the interaction are highly expressed. The locations at which both members are highly- expressed is defined as follows:

For each interaction, we define the category of both **x** and **y** for each spot as follows:

$$ Category_i(x) = \begin{cases} \text{positive} & \text{if } \sum_{i,j} (x_i \cdot w_{ij}) > 0 \\ \text{negative} & \text{if } \sum_{i,j} (x_i \cdot w_{ij}) < 0 \\ \text{neither} & \text{otherwise} \end{cases}$$

Then we combine the categories of **x** and **y** for each spot, such that high-high are positive (1), high-low (or low-high) are -1; and low-low are 0.
When working with non-negative values (i.e. gene expression); the features will be z-scaled (across observations).


```python
sc.pl.spatial(lrdata, layer='cats', color=['VTN^ITGAV_ITGB5', 'TIMP1^CD63'], size=1.4, cmap="coolwarm")
```

Here, we can distinguish areas in which the interaction between interaction members is positive (high-high) in Red (1), while interactions in which one is high the other is low or negative (High-low) are in Blue (-1). We also see that some interactions are neither, these are predominantly interactions in which both members are lowly-expressed (i.e. low-low); we see those in white (0).

When set to `mask_negatives=False`, we also return interactions that are not between necessarily positive/high magnitude genes ; when set to `mask_negatives=True`, we mask interactions that are negative (low-low) or uncategorized; for both the p-values and the local scores.

## Identify Intercellular Patterns

Now that we have estimated ligand-receptor scores, we can use non-negative matrix factorization (NMF) to identify coordinated cell-cell communication signatures.
This would ultimately decompose the ligand-receptor scores into a basis matrix (`W`) and a coefficient matrix (`H`). We will use a very simple utility function (around sklearn's NMF implementation) to do so, along with a simple `k` (component number) selection procedure.

* Basis Matrix (`W`):
        Each basis vector represents a characteristic pattern of ligand-receptor expression in the dataset.
        The values in `W` (factor score) indicate the strengths of factor in each spot; high values indicate high influence by the associated communication signature, while low values mean a weak influence.
* Coefficient Matrix (`H`):
        Each row of `H` represents the participation of the corresponding sample in the identified factor.
        The elements of each basis vector indicate the contribution of different interactions to the pattern (factor).

<img src="nmf.png" width=700 />


By decomposing the ligand-receptor interactions into W and H, NMF can potentially identify underlying CCC processes, with additive and non-negative relationships between the features. This property aligns well with the biological intuition that genes work together in a coordinated manner, but assumes linearity and only captures additive effects. Thus, alternative decomposition or clustering approaches can be used to a similar end. 

In this particular scenario, we chose NMF as it is a well-established method for decomposition of non-negative matrices, it is fast, and it is easy to interpret. Also, in our case the ligand-receptor local scores already encode the spatial relationships between the features, so we don't necessarily need to use a spatial-aware decomposition methods (e.g. [SpatialDE](https://www.nature.com/articles/nmeth.4636), [Spatial NMF](https://www.nature.com/articles/s41592-022-01687-w), [Chrysalis](https://github.com/rockdeme/chrysalis), or [MEFISTO](https://www.nature.com/articles/s41592-021-01343-9)).

One limitation of NMF is that it requires the number of components (factors) to be specified - a somewhat an arbitrary choice. To aid the selection of `n_components`, we provide a simple function that estimates an elbow based on reconstruction error.  Another limitation is that it only accepts non-negative values, so it won't work with metrics that can be negative (e.g. Pearson correlation). In this case, we use Cosine similarity with non-negative values, which results also in non-negative local scores.


```python
li.multi.nmf(lrdata, n_components=None, inplace=True, random_state=0, max_iter=200, verbose=True)
```


```python
# Extract the variable loadings
lr_loadings = li.ut.get_variable_loadings(lrdata, varm_key='NMF_H').set_index('index')
```


```python
# Extract the factor scores
factor_scores = li.ut.get_factor_scores(lrdata, obsm_key='NMF_W')
```

Convert NMF Factor scores to an AnnData object for plotting


```python
nmf = sc.AnnData(X=lrdata.obsm['NMF_W'],
                 obs=lrdata.obs,
                 var=pd.DataFrame(index=lr_loadings.columns),
                 uns=lrdata.uns,
                 obsm=lrdata.obsm)
```


```python
sc.pl.spatial(nmf, color=[*nmf.var.index, None], size=1.4, ncols=2)
```

Wee see that Factor 2 is largely covering the ischemic areas of the side, let's check the interactions contributing the most to it:


```python
lr_loadings.sort_values("Factor2", ascending=False).head(10)
```

<div class="alert alert-info">
  From here on, one can estimate pathway activities or look for downstream effects of these interactions, plot the interactions, etc. These utility functions in liana are covered in other tutorials, but also applicable here.
</div>

## Beyond Ligand-Receptors

While protein-mediated ligand-receptor interactions are interesting, cell-cell communication is not limited to those alone. Rather it is a complex process that involves a variety of different mechanisms such as signalling pathways, metabolite-mediated signalling, and distinct cell types.

So, if such diverse mechanisms are involved in cell-cell communication, why should we limit ourselves to ligand-receptor interactions?
Let's see how we can use LIANA+ to explore other types of cell-cell communication.

One simple approach would be to check relationships e.g. between transcription factors and cell type proportions.

### Extract Cell type Composition
This slide comes with estimated cell type proportions using cell2location; See [Kuppe et al., 2022](https://www.nature.com/articles/s41586-022-05060-x). Let's extract from .obsm them to an independent AnnData object.


```python
# let's extract those
comps = li.ut.obsm_to_adata(adata, 'compositions')
# check key cell types
sc.pl.spatial(comps, color=['vSMCs','CM', 'Endo', 'Fib'], size=1.3, ncols=2)
```

### Estimate Transcription Factor Activity


```python
# Get transcription factor resource
net = dc.op.collectri(organism='human', remove_complexes=False, license='academic', verbose=False)
```

While multi-omics datasets might be even more of an interest, for the sake of simplicity (and because the general lack of spatial mutli-omics data at current times), let's instead use enrichment analysis to estimate the activity of transcription factors in each spot. We will use one of [decoupler-py's](https://decoupler-py.readthedocs.io/en/latest/index.html) enrichment methods with [CollectTRI](https://www.biorxiv.org/content/10.1101/2023.03.30.534849v1.abstract) to do so. Refer to this [tutorial](https://decoupler-py.readthedocs.io/en/latest/notebooks/dorothea.html) for more info.


```python
# run enrichment
dc.mt.ulm(adata, net=net, raw=False, verbose=True)
```

#### Extract highly-variable TF activities
To reduce the number of TFs for the sake of computational speed, we will only focus on the top 50 most variable TFs.

Note we will use the simple coefficient of variation to identify the most variable TFs, but one can also use more sophisticated or spatially-informed methods to extract those (light-weight suggestions are welcome).



```python
est = li.ut.obsm_to_adata(adata, 'score_ulm')
est.var['cv'] =  est.X.std(axis=0) / est.X.mean(axis=0)
top_tfs = est.var.sort_values('cv', ascending=False, key=abs).head(50).index

```

Create MuData object with TF activities and cell type proportions, and transfer spatial connectivities and other information from the original AnnData object.


```python
mdata = MuData({"tf":est, "comps":comps})
mdata.obsp = adata.obsp
mdata.uns = adata.uns
mdata.obsm = adata.obsm
```

Define Interactions of interest:


```python
from itertools import product
```


```python
interactions = list(product(comps.var.index, top_tfs))
```

### Estimate Cosine Similarity


```python
bdata = li.mt.bivariate(mdata,
                        x_mod="comps",
                        y_mod="tf",
                        x_transform=sc.pp.scale,
                        y_transform=sc.pp.scale,
                        local_name="cosine", 
                        interactions=interactions,
                        mask_negatives=True, 
                        add_categories=True,
                        x_use_raw=False,
                        y_use_raw=False,
                        xy_sep="<->",
                        x_name='celltype',
                        y_name='tf'
                        )
```

<div class="alert alert-info">

To make the distributions comparable, we simply z-scale the TF activities and cell type proportions via the `x_transform` & `y_transform` parameters.

The type of transformation will affect the interpretation of the results, and different types of transformation might be more appropriate for different types of data. We provide zero-inflated minmax `zi_minmax` & `neg_to_zero` transformation functions via `li.fun.transform`.

One can explore how different transformations affect the results, to also get a better feeling how these local metrics work.

</div>


```python
bdata.var.sort_values("mean", ascending=False).head(5)
```

#### Let's plot the results


```python
sc.pl.spatial(bdata, color=['Myeloid<->SNAI2', 'CM<->HAND1'], size=1.4, cmap="coolwarm", vmax=1, vmin=-1)
```

Plot categories


```python
sc.pl.spatial(bdata, layer='cats', color=['Myeloid<->SNAI2', 'CM<->HAND1'], cmap='coolwarm')
```

Plot variables (without transformations)


```python
sc.pl.spatial(mdata.mod['tf'], color=['SNAI2', 'HAND1'], cmap='coolwarm', size=1.4, vcenter=0)
```


```python
sc.pl.spatial(mdata.mod['comps'], color=['Myeloid', 'CM'], cmap='viridis', size=1.4)
```


```python

```
