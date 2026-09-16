---
title: "Differential Expression Analysis for CCC & Downstream Signalling Networks"
keywords:
  - "ccc"
  - "differential expression"
  - "pseudobulk"
  - "pydeseq2"
  - "ligand-receptor"
  - "decoupler"
  - "progeny"
  - "omnipath"
  - "causal networks"
  - "corneto"
  - "carnival"
  - "gurobi"
---
# Differential Expression Analysis for CCC & Downstream Signalling Networks

## Background


For further information on pseudobulk DEA, please refer to the Differential Gene Expression chapter in the Single-cell Best Practices book, as well as Decoupler's pseudobulk vignette. These resources provide more comprehensive details on the subject.


## Load Packages

Install mofa, decoupler, and omnipath via pip with the following commands:


```python
import numpy as np
import pandas as pd
import scanpy as sc

import plotnine as p9

import liana as li
import decoupler as dc
import omnipath as op

# Import DESeq2
from pydeseq2.dds import DeseqDataSet
from pydeseq2.ds import DeseqStats
```


```python
# Obtain TF regulons
net = dc.op.collectri(organism='human', remove_complexes=False, license='academic', verbose=False)
```

## Load & Prep Data


This dataset is downloaded from a link on Figshare; preprocessed for pertpy.


```python
adata = li.testing.datasets.kang_2018()
adata
```

Define columns of interest from `.obs`

Note that we use cell abbreviations because MOFA will use them as labels for the views.


```python
sample_key = 'sample'
groupby = 'cell_abbr'
condition_key = 'condition'
```

### Basic QC

Note that this data has been largely pre-processed & annotated, we refer the user to the Quality Control and other relevant chapters from the best-practices book for information about pre-processing and annotation steps.


```python
# filter cells and genes
sc.pp.filter_cells(adata, min_genes=200)
sc.pp.filter_genes(adata, min_cells=3)
```

### Showcase the data


```python
# Show pre-computed UMAP
sc.pl.umap(adata, color=[condition_key, sample_key, 'cell_type', groupby], frameon=False, ncols=2)
```

## Differential Testing

First, we need to generate pseudobulk profiles for each cell type, and we do so using the `decoupler` package.


```python
pdata = dc.pp.pseudobulk(
    adata,
    sample_col=sample_key,
    groups_col=groupby,
    layer='counts',
    mode='sum'
)
pdata
```


```python
# filter samples based on number of cells and counts
dc.pp.filter_samples(pdata, min_cells = 10, min_counts=1000)
```

We can plot the quality control metrics for each pseudobulk sample:


```python
dc.pl.filter_samples(pdata, groupby=[sample_key, groupby], figsize=(11, 4))
```

#### Differential Expression Analysis


Here, we perform DEA on the pseudobulk profiles for each cell type, for more info check this tutorial:


```python
%%capture

dea_results = {}
quiet = True

for cell_group in pdata.obs[groupby].unique():
    # Select cell profiles
    ctdata = pdata[pdata.obs[groupby] == cell_group].copy()

    # Obtain genes that pass the edgeR-like thresholds
    # NOTE: QC thresholds might differ between cell types, consider applying them by cell type
    genes = dc.pp.filter_by_expr(ctdata,
                              group=condition_key,
                              min_count=5, # a minimum number of counts in a number of samples
                              min_total_count=10 # a minimum total number of reads across samples
                              )

    # Filter by these genes
    ctdata = ctdata[:, genes].copy()

    # Build DESeq2 object
    # NOTE: this data is actually paired, so one could consider fitting the patient label as a confounder
    dds = DeseqDataSet(
        adata=ctdata,
        design_factors=condition_key,
        ref_level=[condition_key, 'ctrl'], # set control as reference
        refit_cooks=True,
        quiet=quiet
    )

    # Compute LFCs
    dds.deseq2()
    # Contrast between stim and ctrl
    stat_res = DeseqStats(dds, contrast=[condition_key, 'stim', 'ctrl'], quiet=quiet)
    stat_res.quiet = quiet
    # Compute Wald test
    stat_res.summary()
    # Shrink LFCs
    stat_res.lfc_shrink(coeff='condition_stim_vs_ctrl') # {condition_key}_cond_vs_ref

    dea_results[cell_group] = stat_res.results_df

```


```python
# concat results across cell types
dea_df = pd.concat(dea_results)
dea_df = dea_df.reset_index().rename(columns={'level_0': groupby,'level_1':'index'}).set_index('index')
dea_df.head()
```


```python
# PyDeseq Seems to intrdoce NAs for some p-values
# NOTE: there sometimes some NaN being introduced, best to double check that, in this case it's only for a single gene, but it might be a problem.
len(dea_df[dea_df.isna().any(axis=1)])
```

## DEA to Ligand-Receptor Interactions

Now that we have DEA results per gene, we can combine them into statistics of potentially deregulated ligand-receptor interactions.

To do so, liana provides a simple function `li.multi.df_to_lr` that calculates average expression as well as proportions based on the passed `adata` object, and combines those with the DEA results and a ligand-receptor resource. Since in this case we want to focus on gene statics relevant to the condition (stim), let's subset the adata to those and normalize the counts.


```python
adata = adata[adata.obs[condition_key]=='stim'].copy()
```


```python
sc.pp.normalize_total(adata, target_sum=1e4)
sc.pp.log1p(adata)
```

Let's combine the DEA results with the ligand-receptor interactions. We need to pass the names of the statistics from the DEA table in which we are interest to `li.multi.df_to_lr`, here we will use the adjusted p-values and Wald test statistic.


```python
lr_res = li.multi.df_to_lr(adata,
                           dea_df=dea_df,
                           resource_name='consensus', # NOTE: uses HUMAN gene symbols!
                           expr_prop=0.1, # calculated for adata as passed - used to filter interactions
                           groupby=groupby,
                           stat_keys=['stat', 'pvalue', 'padj'],
                           use_raw=False,
                           complex_col='stat', # NOTE: we use the Wald Stat to deal with complexes
                           verbose=True,
                           return_all_lrs=False,
                           )
```


```python
lr_res = lr_res.sort_values("interaction_stat", ascending=False, key=abs)
lr_res.head()
```


##### Dealing with heteromeric complexes

LIANA will filter lowly-expressed interactions, i.e. those for which any of the genes are not expressed in at least **0.1** of the cells (by default) in the AnnData object. This can be adjusted with the `expr_prop` parameter.


## Visualize the Results


Moreover, by averaging the statistics across the ligand and receptor, we  are focusing on the interactions for which both the ligand and receptor are deregulated in the same direction, i.e. both up or both down. However, this might ignore interactions in which e.g. the the ligand is deregulated while the receptor is not, or such where they are deregulated in opposite directions. These could represent potential inhibitory mechanisms, but we leave this to the user to explore.


```python
# Let's visualize how this looks like for all interactions  (across all cell types)
lr_res = lr_res.sort_values("interaction_stat", ascending=False)
lr_res['interaction_stat'].hist(bins=50)
```

Now that we have covered the basics, we can visualize our interactions in a few ways.

Let's start with the top interactions according to their Wald statistic, and then plot the statistics for the ligands & receptors involved in those interactions across cell types, to do so LIANA+ provide `li.pl.tileplot`:


```python
li.pl.tileplot(liana_res=lr_res,
               fill = 'expr',
               label='padj',
               label_fun = lambda x: '*' if x < 0.05 else np.nan,
               top_n=15,
               orderby = 'interaction_stat',
               orderby_ascending = False,
               orderby_absolute = False,
               source_title='Ligand',
               target_title='Receptor',
               )
```

If you want to plot the expression values for ligand-receptor interactions without the DEA statistics, you can set the `return_all_lrs` parameter to `True` in the `li.multi.dea_to_lr` function. This will return a dataframe with all the ligand-receptor interactions, where missing DEA stats will be set as `nan`, while mean expression and proportions per cluster will be obtained via the AnnData object.

### Ligand-Receptor Plot

We can also use visualize of the stats, summarized at the level of the interaction, to prioritize the interactions, or any subunit statistics using `li.pl.dotplot`. For example, we can visualize the mean Wald statistic between the ligand & receptor, together with the pvalues for the ligand.


```python
plot = li.pl.dotplot(liana_res=lr_res,
                     colour='interaction_stat',
                     size='ligand_pvalue',
                     inverse_size=True,
                     orderby='interaction_stat',
                     orderby_ascending=False,
                     orderby_absolute=True,
                     top_n=10,
                     size_range=(0.5, 4)
                     )

# customize plot
(
    plot
    + p9.theme_bw(base_size=14)
    # fill cmap blue to red, with 0 the middle
    + p9.scale_color_cmap('RdBu_r', midpoint=0, limits=(-10, 10))
    # rotate x
    + p9.theme(axis_text_x=p9.element_text(angle=90), figure_size=(11, 6))

)
```

Now that we have identified a set of interactions that are potentially deregulated we can look into the downstream signalling events that they might be involved in.


## Intracellular Signaling Networks


Here, we will combine several tools to identify plausible signalling cascades driven by CCC events.

Our approach includes the following steps:

* Select a number of potentially deregulated ligand-receptor interactions (input nodes), in terms of summarized PyDESeq2 statistics.

* Select a number of potentially deregulated TFs (output nodes). This is done via the use of Transcription factor (TF) activity inference. Carried out on differential gene expression data using TF regulon knowledge with decoupler

* Obtain a prior knowledge network (PKNs), with signed protein-protein interactions from OmniPath.

* Generate weights for the nodes in the PKN

* Use CORNETO to identify a solution in the form of a causal (smallest sign-consistent signaling) network that explains the measured inputs and outputs


### Import OmniPath

For this part OmniPath is required.


```python
# utily function to select top n interactions
def select_top_n(d, n=None):
    d = dict(sorted(d.items(), key=lambda item: abs(item[1]), reverse=True))
    return {k: v for i, (k, v) in enumerate(d.items()) if i < n}
```

### Select Cell types of Interest

However, from dimensionality reductions on CCC, as done with Tensor-cell2cell & MOFA on the same dataset, we can see there is a potential deregulation of CCC that involve CD14 monocytes both as sources (senders) and targets (or receivers) of intecellular communication. Thus, we will focus on the interactions and downstream signalling within that cell type.


```python
source_label = 'CD14'
target_label = 'CD14'

# NOTE: We sort by the absolute value of the interaction stat
lr_stats = lr_res[lr_res['source'].isin([source_label]) & lr_res['target'].isin([target_label])].copy()
lr_stats = lr_stats.sort_values('interaction_stat', ascending=False, key=abs)
```

### Select Receptors based on interaction stats

These will be used as the input or start nodes for the network. In this case, we will use interactions potentially involved in autocrine signalling in CD14 monocytes.


```python
lr_dict = lr_stats.set_index('receptor')['interaction_stat'].to_dict()
input_scores = select_top_n(lr_dict, n=10)
```


```python
input_scores
```

### Select Transcription Factors of interest

Before we select the transcription factors, we need to infer their activity. We will do so using decoupler with CollecTri regulons. Specifically, we will estimate TF activities using the Wald statistics (from PyDESeq2) for the genes in the regulons.


```python
# First, let's transform the DEA statistics into a DF
# we will use these to estimate deregulated TF activity
dea_wide = dea_df[[groupby, 'stat']].reset_index(names='genes').pivot(index=groupby, columns='genes', values='stat')
dea_wide = dea_wide.fillna(0)
dea_wide
```


```python
# Run Enrichment Analysis
estimates, pvals = dc.mt.ulm(mat=dea_wide, net=net)
estimates.T.sort_values(target_label, key=abs, ascending=False).head()
```

### Select top TFs

Now that we have the potentially deregulated TFs, we focus on the top 10 TFs, based on their enrichment scores. In this case, we will look specifically at the top TFs deregulated in CD14 monocytes.


```python
tf_data = estimates.copy()
tf_dict = tf_data.loc[target_label].to_dict()
output_scores = select_top_n(tf_dict, n=5)
```

### Generate a Prior Knowledge Network

Now we will obtain protein-protein interactions from OmniPath, filter them according to curation effort to ensure we only keep those that are of high quality, and convert them into a knowledge graph.


```python
# obtain ppi network
ppis = op.interactions.OmniPath().get(genesymbols = True)

ppis['mor'] = ppis['is_stimulation'].astype(int) - ppis['is_inhibition'].astype(int)
ppis = ppis[(ppis['mor'] != 0) & (ppis['curation_effort'] >= 5) & ppis['consensus_direction']]

input_pkn = ppis[['source_genesymbol', 'mor', 'target_genesymbol']]
input_pkn.columns = ['source', 'mor', 'target']
input_pkn.head()
```


```python
# convert the PPI network into a knowledge graph
prior_graph = li.mt.build_prior_network(input_pkn, input_scores, output_scores, verbose=True)
```


### Calculate Node weights

Calculate gene expression proportions within the target cell type; we will use those as node weights in the network.


```python
temp = adata[adata.obs[groupby] == target_label].copy()
```


```python
node_weights = pd.DataFrame(temp.X.getnnz(axis=0) / temp.n_obs, index=temp.var_names)
node_weights = node_weights.rename(columns={0: 'props'})
node_weights = node_weights['props'].to_dict()
```

### Find Causal Network


To run CORNETO, we need to first install it; it's very lightweight and can be installed via pip:


```python
import corneto as cn
cn.info()
```


```python
df_res, problem = li.mt.find_causalnet(
    prior_graph,
    input_scores,
    output_scores,
    node_weights,
    # penalize (max_penalty) nodes with counts in less than 0.1 of the cells
    node_cutoff=0.1,
    max_penalty=1,
    # the penaly of those in > 0.1 prop of cells set to:
    min_penalty=0.01,
    edge_penalty=0.1,
    verbose=False,
    max_runs=50, # NOTE that this repeats the solving either until the max runs are reached
    stable_runs=10, # or until X number of consequitive stable runs are reached (i.e. no new edges are added)
    solver='gurobi' # 'scipy' is available by default, but often results in suboptimal solutions
    )
```

### Visualize the Inferred Network

Now that the solution has been found, we can visualize it using the `cn.methods.carnival.visualize_network` function.


```python
cn.methods.carnival.visualize_network(df_res)
```


### Describe Results

Let's examine the result of the subnetwork search - it provides information about the predicted signs of nodes and edges.


```python
df_res.head()
```

#### Nodes
- **target**: target nodes in the PPI network, with suffixes similar to the source node.

- **source_type (unmeasured, input)**:
  - **input**: start nodes (provided by the users, here receptors).
  - **output**: end nodes (provides by the user, here transcription factors).
  - **unmeasured**: Nodes that are neither input nor output - i.e. those that predicted by the algorithm.
- **source_weight** and **target_weight**: Inputs to the causal net method, indicating the influence of "measured" nodes within the network. Only the sign is taken into account.
- **source_pred_val (1, 0, -1)**: Regulatory state of the node:
  - **1**: Upregulated
  - **0**: No differential expression
  - **-1**: Downregulated
- **target_pred_val (1, -1)**: Regulatory state of the target node:
  - **1**: Upregulated
  - **-1**: Downregulated

#### Edges (interaction)
- **edge_type (1, -1, 0)**: Type of interaction from prior knowledge:
  - **1**: Activating interaction (e.g., A -> B)
  - **-1**: Inhibitory interaction
- **edge_pred_val (1, -1)**: Predicted effect of the interaction on the target node:
  - **1**: Upregulation
  - **-1**: Downregulation
