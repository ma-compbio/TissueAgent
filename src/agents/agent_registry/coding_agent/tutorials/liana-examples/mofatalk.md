# Intercellular Context Factorization with MOFA

## Background

Here, we will adapt the statistical framework of multi-omics factor analysis ([MOFA](https://www.embopress.org/doi/full/10.15252/msb.20178124)) to obtain intercellular communication programmes - in the form of ligand-receptor interaction scores observed to change across samples. This application of MOFA is inspired by and is in line with the factorization proposed by Tensor-cell2cell [Armingol and Baghdassarian et al., 2022](https://www.nature.com/articles/s41467-022-31369-2) - see existing [tutorial](https://liana-py.readthedocs.io/en/latest/notebooks/liana_c2c.html). 

Such factorization approaches essentially enable us to decipher context-driven intercellular communication by simultaneously accounting for an unlimited number of “contexts” in an untargeted manner.
Similarly to Tensor-cell2cell, this application of MOFA is able to handle cell-cell communication results coming from any experimental design, regardless of its complexity. 

Simply put, we will use LIANA’s output by sample to build a multi-view structure represented by samples and interactions by cell type pairs (views). 
We will then use [MOFA+](https://genomebiology.biomedcentral.com/articles/10.1186/s13059-020-02015-1) to capture the CCC patterns across samples. To do so, we combine liana with the [MuData](https://mudata.readthedocs.io/en/latest/notebooks/quickstart_mudata.html)/[muon](https://link.springer.com/article/10.1186/s13059-021-02577-8) infrastructure.

## Load Packages

mofa, decoupler, omnipath, and marsilea can be installed via pip with the following commands:

```python
pip install "decoupler>=2.0.0"
pip install mofax
pip install muon
pip install omnipath
pip install marsilea
```


```python
import numpy as np
import pandas as pd

import scanpy as sc

import plotnine as p9

import liana as li

# load muon and mofax
import muon as mu
import mofax as mofa

import decoupler as dc
```

## Load & Prep Data

As a simple example, we will look at ~25k PBMCs from 8 pooled patient lupus samples, each before and after IFN-beta stimulation ([Kang et al., 2018](https://www.nature.com/articles/nbt.4042); [GSE96583](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE96583)). Note that by focusing on PBMCs, for the purpose of this tutorial, we assume that coordinated events occur among them.

This dataset is downloaded from a link on Figshare; preprocessed for [pertpy](https://github.com/theislab/pertpy).


```python
adata = li.testing.datasets.kang_2018()
```


```python
adata
```

Define columns of interest from `.obs`

Note that we use cell abbreviations because MOFA will use them as labels for the views.


```python
sample_key = 'sample'
condition_key = 'condition'
groupby = 'cell_abbr'
```

### Basic Preparation

Note that this data has been largely pre-processed & annotated, we refer the user to the [Quality Control](https://www.sc-best-practices.org/preprocessing_visualization/quality_control.html) and other relevant chapters from the best-practices book for information about pre-processing and annotation steps.


```python
# filter cells and genes
sc.pp.filter_cells(adata, min_genes=200)
sc.pp.filter_genes(adata, min_cells=3)
# log1p normalize the data
sc.pp.normalize_total(adata)
sc.pp.log1p(adata)
```

### Showcase the data


```python
# Show pre-computed UMAP
sc.pl.umap(adata, color=[condition_key, sample_key, 'cell_type', groupby], frameon=False, ncols=2)
```

## Ligand-Receptor Inference by Sample

Before we decompose the CCC patterns across contexts/samples with `MOFA`, we first need to run `liana` on each sample. To do so, liana provides a utility function called `by_sample` that runs each method in LIANA on each sample within the `AnnData` object, and returns a long-format `pandas.DataFrame` with the results.

In this example, we will use liana's `rank_aggregate` method, which provides a robust rank consensus that combines the predictions of multiple ligand-receptor methods. Nevertheless, any other method can be used.


```python
li.mt.rank_aggregate.by_sample(
    adata,
    groupby=groupby,
    resource_name='consensus', # NOTE: uses HUMAN gene symbols!
    sample_key=sample_key, # sample key by which we which to loop
    expr_prop = 0.1,
    use_raw=False, 
    n_perms=100, # reduce permutations for speed
    return_all_lrs=False, # we don't return all LR values to utilize MOFA's flexible views
    verbose=True, # use 'full' to show all information
    ) 
```

Check results


```python
adata.uns["liana_res"].sort_values("magnitude_rank").head()
```


```python
adata.uns["liana_res"]['source'].unique()
```

<div class="alert alert-info">

**Note**
    
<h4> by_sample </h4>

We see that in addition to the usual results, we also get `sample` as a column which corresponds to the name of the `sample_key` in the `AnnData` object.

</div>  

Now that we have obtained results by sample, we can use a dotplot by sample to visualize the ligand-receptor interactions. Let's pick arbitrarily the interactions with the highest `magnitude_rank`.


```python
(li.pl.dotplot_by_sample(adata, sample_key=sample_key,
                         colour="magnitude_rank",
                         size="specificity_rank",
                         source_labels=["CD4T", "B", "FGR3"],
                         target_labels=["CD8T", 'DCs', 'CD14'],
                         ligand_complex=["B2M"],
                         inverse_colour=True,
                         inverse_size=True,
                         receptor_complex=["KLRD1", "LILRB2", "CD3D"],
                         figure_size=(12, 8),
                         size_range=(0.5, 5),
                         ) +
    # rotate facet labels
    p9.theme(strip_text=p9.element_text(size=10, colour="black", angle=90))
 )
```

Even on a small subset interactions and cell types, we can see that interpretation becomes challenging. To overcome this, we can use MOFA to find the variable CCC patterns across contexts/samples.

## Create a Multi-View Structure

Before we can identify the variable CCC patterns across contexts/samples, we need to create a multi-view structure. 
In this case, we will use the `lrs_to_views` function from liana to create a list of views (stored in a MuData object), where each view corresponds to a pair of potentially interacting cell types.
The scores of interactions between cell type pairs represent those inferred with liana, stored by default in `adata.uns['liana_res']`. Here, we will use liana's aggregate 'magnitude_rank'.


```python
adata.write_h5ad("../../test.h5ad")
```


```python
mdata = li.multi.lrs_to_views(adata,
                              sample_key=sample_key,
                              score_key='magnitude_rank',
                              obs_keys=['patient', 'condition'], # add those to mdata.obs
                              lr_prop = 0.3, # minimum required proportion of samples to keep an LR
                              lrs_per_sample = 20, # minimum number of interactions to keep a sample in a specific view
                              lrs_per_view = 20, # minimum number of interactions to keep a view
                              samples_per_view = 5, # NOTE: minimum number of samples to keep a view
                              min_variance = 0, # minimum variance to keep an interaction
                              lr_fill = 0, # fill missing LR values across samples with this
                              verbose=True
                              )
```

The `lr_fill` parameter controls how we deal with missing interaction scores. The default is `np.nan` and in that case the scores would be imputed by MOFA.

Here, we fill the missing ligand-receptors with 0s because the ligand-receptor interaction missing here, i.e. those when `return_all_lrs=False`, are such which are not expressed above a certain proportion of cells per cell type (that is controlled via `expr_prop` when running liana).

Given the assumption that the ligand-receptor interactions occur at the across cell type level, we could thus assume that the genes that are not present in a sufficient proportion of cells are unlikely to be involved in interactions that are relevant to the cell type as a whole.

<div class="alert alert-info">

**Note**
    
<h5> View Representation </h5>

MOFA supports the flexible representation of views, where each view can represent a different type of features (e.g. genes, proteins, metabolites, etc.). In this case, we simply allow for different ligand-receptor to be used in each cell type pair (view).

</div>  


```python
mdata
```

## Fitting a MOFA model

Now that the putative ligand-receptor interactions across samples aretransformed into a multi-view representation, we can use MOFA to run an intercellular communication factor analysis.

We will attempt to capture the variability across samples and the different cell-type pairs by reducing the data into a number of factors, where each factor captures the coordinated communication events across the cell types.


```python
mu.tl.mofa(mdata, 
           use_obs='union',
           convergence_mode='medium',
           outfile='models/mofatalk.h5ad',
           n_factors=4,
           )
```

## Exploring the MOFA model

For convenience, we provide simple getter function to access the model parameters, in addition to those available via the [MuData API](https://mudata.readthedocs.io/en/latest/api/index.html) & the MOFA model itself.

### Explore Metadata Associations to the Factor Scores


```python
# Transfer to AnnData to comply with decoupler and visualise
ad = sc.AnnData(obs = mdata.obs, obsm=mdata.obsm)
```


```python
dc.tl.rankby_obsm(
    ad,
    key='X_mofa',  # Where the PCs are stored
    uns_key='rank_obsm',  # Where the results are stored
)

dc.pl.obsm(
    ad,
    key='rank_obsm',
    names = ['patient', 'condition'], # which sample annotations to plot
    titles=['Principle component scores', 'Adjusted p-values from ANOVA'],
    figsize=(7, 5),
    nvar=10
)
```


```python
# obtain the factor scores as a dataframe
factor_scores = li.ut.get_factor_scores(mdata, obsm_key='X_mofa', obs_keys=['patient', 'condition'])
factor_scores.head()
```

Let's check if any of the factors are associated with the sample condition:


```python
 # we use a paired t-test as the samples are paired
from scipy.stats import ttest_rel
```


```python
# split in control and stimulated
group1 = factor_scores[factor_scores['condition']=='ctrl']
group2 = factor_scores[factor_scores['condition']=='stim']

# get all columns that contain factor & loop
factors = [col for col in factor_scores.columns if 'Factor' in col]
for factor in factors:
    print(ttest_rel(group1[factor], group2[factor]))
    
```

We can see that the first factor is associated with the sample condition, let's plot the factor scores:


```python
# scatterplot
(p9.ggplot(factor_scores) +
 p9.aes(x='condition', colour='condition', y='Factor1') +
 p9.geom_violin() +
 p9.geom_jitter(size=4, width=0.2) +
 p9.theme_bw(base_size=16) +
 p9.theme(figure_size=(5, 4)) +
 p9.scale_colour_manual(values=['#1f77b4', '#c20019']) +
 p9.labs(x='Condition', y='Factor 1')
 )
```

#### Explore Ligand-Receptor loadings

Now that we have identified a factor that is associated with the sample condition, we can check the ligand-receptor loadings with the highest loadings:


```python
variable_loadings =  li.ut.get_variable_loadings(mdata,
                                                 varm_key='LFs',
                                                 view_sep=':',
                                                 pair_sep="&",
                                                 variable_sep="^") # get loadings for factor 1
variable_loadings.head()
```


```python
# here we will just assign the size of the dots, but this can be replace by any other statistic
variable_loadings['size'] = 4.5
```


```python
my_plot = li.pl.dotplot(liana_res = variable_loadings,
                        size='size',
                        colour='Factor1', 
                        orderby='Factor1',
                        top_n=15,
                        source_labels=['NK', 'B', 'CD4T', 'CD8T', 'CD14'],
                        orderby_ascending=False,
                        size_range=(0.1, 5),
                        figure_size=(8, 5)
                        )
# change colour, with mid as white
my_plot + p9.scale_color_gradient2(low='#1f77b4', mid='lightgray', high='#c20019')
```

Here, we can see that certain interactions from Factor 1 have high positive loadings. These are interactions that are associated with the samples with high factor scores (i.e. the stimulated samples with high scores in Factor 1).

### Explore the model

Finally, we can also explore the MOFA model itself and we will specifically check the variance explained by each pair of cell types.


```python
model = mofa.mofa_model("models/mofatalk.h5ad")
model
```


```python
# get variance explained by view and factor
rsq = model.get_r2()
factor1_rsq = rsq[rsq['Factor']=='Factor1']
# separate view column
factor1_rsq[['source', 'target']] = factor1_rsq['View'].str.split(pat='&', n=1, expand=True)
```


```python
(p9.ggplot(factor1_rsq.reset_index()) + 
 p9.aes(x='target', y='source') + 
 p9.geom_tile(p9.aes(fill='R2')) + 
 p9.scale_fill_gradient2(low='white', high='#c20019') +
 p9.theme_bw(base_size=16) +
 p9.theme(figure_size=(5, 4)) +
 p9.labs(x='Target', y='Source', fill='R²')
 )
```

Here, we can see that views that include CD14+ Monocytes have the highest variance explained both as source and as target of intercellular communication events. In particular, we see that putative autocrine interactions that occur between CD14+ Monocytes are highly explained by Factor 1.

## Pathway enrichment

Let's also perform an enrichment analysis on the ligand-receptor interactions that are associated with the factor of interest. We will use [decoupler](https://github.com/saezlab/decoupler-py) with pathway genesets from [PROGENy](https://github.com/saezlab/progeny) to look for enrichments across the cell type pairs (views).


```python
# load PROGENy pathways
net = dc.op.progeny(organism='human', top=5000, thr_padj=0.25)
# load full list of ligand-receptor pairs
lr_pairs = li.resource.select_resource('consensus')
```


```python
# generate ligand-receptor geneset
lr_progeny = li.rs.generate_lr_geneset(lr_pairs, net, lr_sep="^").rename(columns = {'interaction': 'target'})
lr_progeny.head()
```


```python
lr_loadings =  li.ut.get_variable_loadings(mdata,
                                           varm_key='LFs',
                                           view_sep=':',
                                           )
lr_loadings.set_index('variable', inplace=True)
# pivot views to wide
lr_loadings = lr_loadings.pivot(columns='view', values='Factor1')
# replace NaN with 0
lr_loadings.replace(np.nan, 0, inplace=True)
lr_loadings.head()

```


```python
# run pathway enrichment analysis
estimate, pvals =  dc.mt.mlm(lr_loadings.transpose(), lr_progeny, raw=False, tmin=5)
# pivot columns to long
estimate = (estimate.
            melt(ignore_index=False, value_name='estimate', var_name='pathway').
            reset_index().
            rename(columns={'index':'view'})
            )
```


```python
## p9 tile plot
(p9.ggplot(estimate) + 
 p9.aes(x='pathway', y='view') +
 p9.geom_tile(p9.aes(fill='estimate')) +
 p9.scale_fill_gradient2(low='#1f77b4', high='#c20019') +
 p9.theme_bw(base_size=14) +
 p9.theme(figure_size=(8, 8))
)
```

<div class="alert alert-warning">
  Some of these interactions are not expressed in the data, so we use the `lr_fill` parameter to fill them with 0s.
  This is a rather arbitrary choice, but it is a simple way to deal with missing values. Additionally, since we the views (cell type pairs) are rather sparse, it's possible that the enrichment analysis will not be very informative. Be sure to check the results carefully.
</div>

## Outlook & Further Analysis

This tutorial is just a short introduction of the use of MOFA, we thus refer the users to the available [MOFA](https://biofam.github.io/MOFA2/tutorials.html) & [muon tutorials](https://muon-tutorials.readthedocs.io/en/latest/single-cell-rna-atac/index.html) for more applications & details.

Similary, consider citing both muon & MOFA+ if you use them in your work!


```python
model.close()
```


```python

```
