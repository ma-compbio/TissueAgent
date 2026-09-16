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

To showcase LIANA's local functions, we will use an ischemic 10X Visium spatial slide from Kuppe et al., 2022. It is a tissue sample obtained from a patient with myocardial infarction, focusing on the ischemic zone of the heart tissue.

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


Following the initial concept of LIANA, and inspired by scHOT, we have natively re-implemented **6** local bivariate metrics, including scHOT's (default) masked Spearman & SpatialDM's local Moran's R.


### Available Local Functions


```python
li.mt.bivariate.show_functions()
```

### How do they work?

The local functions work are quite simple, as they are simply weighted versions of well-known similarity metrics. For example, the spatially-weighted version of Cosine similarity is defined as:


where for each spot **i**, we perform summation over all spots **n**, where **w**​ represents the spatial connectivity weights from spot **i** to every other spot **j**;  for variables  **x** and **y**.

### Spatial Connectivity

The way that spatially-informed methods usually work is by making use of weights based on the proximity (or spatial connectivity) between spots/cells.
These spatial connectivities are then used to calculate the metric of interest, e.g. Cosine similarity, in a spatially-informed manner.


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

We can also use Global bivariate Moran's R (or Lee's statistic) - an extension of univariate Moran's I, as proposed by Anselin 2019 and Lee and Li, 2019; implemented in SEAGAL and SpatialDM.

Bivariate Moran's R values near zero imply spatial independence, while positive or negative values reflect spatial co-clustering or spatial cross-dispersion, respectively.


```python
lrdata.var.sort_values("morans", ascending=False).head()
```


On the other hand, among most variable interactions and with with the highest global morans R is e.g. **VTN&ITGAV_ITGB5**. This interaction is thus more likely to represent biological relationships, with distinct spatial clustering patterns.

So, let's visualize both:


```python
# NOTE: reset params as plotnine seems to change them
sc.set_figure_params(dpi=80, dpi_save=300, format='png', frameon=False, transparent=True, figsize=[5,5])
```


```python
sc.pl.spatial(lrdata, color=['VTN^ITGAV_ITGB5', 'TIMP1^CD63'], size=1.4, vmax=1, cmap='magma')
```


```python
sc.pl.spatial(adata, color=['VTN', 'ITGAV', 'ITGB5',
                            'TIMP1', 'CD63'],
              size=1.4, ncols=2)
```


### Permutation-based p-values
In addition to the local scores, we also calculated permutation-based p-values based on a null distribution generated by shuffling the spot labels. Let's see how these look for the two interactions from above:


```python
sc.pl.spatial(lrdata, layer='pvals', color=['VTN^ITGAV_ITGB5', 'TIMP1^CD63'], size=1.4, cmap="magma_r")
```


### Local Categories

Did you notice that we used `mask_negatives` as a parameter when first estimating the interaction? This essentially means that we mask interactions in which both members are negative (or lowly expressed) when calculating the p-values, i.e. such which occur at places in which both members of the interaction are highly expressed. The locations at which both members are highly- expressed is defined as follows:

For each interaction, we define the category of both **x** and **y** for each spot as follows:


Then we combine the categories of **x** and **y** for each spot, such that high-high are positive (1), high-low (or low-high) are -1; and low-low are 0.
When working with non-negative values (i.e. gene expression); the features will be z-scaled (across observations).


```python
sc.pl.spatial(lrdata, layer='cats', color=['VTN^ITGAV_ITGB5', 'TIMP1^CD63'], size=1.4, cmap="coolwarm")
```


## Identify Intercellular Patterns

Now that we have estimated ligand-receptor scores, we can use non-negative matrix factorization (NMF) to identify coordinated cell-cell communication signatures.

* Basis Matrix (`W`):
        Each basis vector represents a characteristic pattern of ligand-receptor expression in the dataset.
        The values in `W` (factor score) indicate the strengths of factor in each spot; high values indicate high influence by the associated communication signature, while low values mean a weak influence.
* Coefficient Matrix (`H`):
        Each row of `H` represents the participation of the corresponding sample in the identified factor.
        The elements of each basis vector indicate the contribution of different interactions to the pattern (factor).


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


## Beyond Ligand-Receptors


So, if such diverse mechanisms are involved in cell-cell communication, why should we limit ourselves to ligand-receptor interactions?
Let's see how we can use LIANA+ to explore other types of cell-cell communication.

One simple approach would be to check relationships e.g. between transcription factors and cell type proportions.

### Extract Cell type Composition
This slide comes with estimated cell type proportions using cell2location; See Kuppe et al., 2022. Let's extract from .obsm them to an independent AnnData object.


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

While multi-omics datasets might be even more of an interest, for the sake of simplicity (and because the general lack of spatial mutli-omics data at current times), let's instead use enrichment analysis to estimate the activity of transcription factors in each spot. We will use one of decoupler-py's enrichment methods with CollectTRI to do so. Refer to this tutorial for more info.


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
