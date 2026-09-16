---
title: "Intercellular Context Factorization with Tensor-Cell2cell"
keywords:
  - "liana"
  - "tensor-cell2cell"
  - "tensor decomposition"
  - "parafac"
  - "multi-context"
  - "pbmcs"
  - "ifn-beta"
  - "rank aggregate"
  - "enrichment"
  - "progeny"
  - "decoupler"
---
# Intercellular Context Factorization with Tensor-Cell2cell


## Background


We will combine LIANA with tensor_cell2cell to decipher potential ligand-receptor interaction changes.

Extensive tutorials combining LIANA & Tensor-cell2cell are available here.

## Load Packages

Install required packages via pip with the following command:


```python
import pandas as pd
import scanpy as sc
import plotnine as p9

import liana as li
import cell2cell as c2c
import decoupler as dc # needed for pathway enrichment

import warnings
warnings.filterwarnings('ignore')
from collections import defaultdict

%matplotlib inline
```


```python
# NOTE: to use CPU instead of GPU, set use_gpu = False
use_gpu = True

if use_gpu:
    import torch
    import tensorly as tl

    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cuda":
        tl.set_backend('pytorch')
else:
    device = "cpu"

device
```

## Load & Prep Data


This dataset is downloaded from a link on Figshare; preprocessed for pertpy.


```python
# load data as from CCC chapter
adata = li.testing.datasets.kang_2018()
```

#### Showcase anndata object


```python
adata
```


```python
adata.obs.head()
```


```python
adata.obs["cell_type"].cat.categories
```


```python
sample_key = 'sample'
condition_key = 'condition'
groupby = 'cell_type'
```

#### Basic QC

Note that this data has been largely pre-processed & annotated, we refer the user to the Quality Control and other relevant chapters from the best-practices book for information about pre-processing and annotation steps.


```python
# filter cells and genes
sc.pp.filter_cells(adata, min_genes=200)
sc.pp.filter_genes(adata, min_cells=3)
# log1p normalize the data
sc.pp.normalize_total(adata)
sc.pp.log1p(adata)
```

In addition to the basic QC steps, one needs to ensure that the cell groups on which they run the analysis are well defined, and stable across samples.

#### Show pre-computed UMAP


```python
sc.pl.umap(adata, color=[condition_key, groupby], frameon=False)
```

## Ligand-Receptor Inference by Sample


In this example, we will use liana's rank_aggregate method, which provides a robust rank consensus that combines the predictions of multiple ligand-receptor methods. Nevertheless, any other method can be used.


```python
li.mt.rank_aggregate.by_sample(
    adata,
    groupby=groupby,
    resource_name='consensus', # NOTE: uses human gene symbols!
    sample_key=sample_key, # sample key by which we which to loop
    use_raw=False,
    verbose=True, # use 'full' to show all verbose information
    n_perms=None, # exclude permutations for speed
    return_all_lrs=True, # return all LR values
    )
```

Check results


```python
adata.uns["liana_res"].sort_values("magnitude_rank").head(10)
```

Even on a small subset interactions and cell types, the  interpretation becomes challenging. To overcome this, we can use Tensor-cell2cell to find the variable CCC patterns across contexts/samples.

## Building a Tensor


Note that the way that we build the tensor can impact the results that we obtain. This is largely controlled by the `how`, `lr_fill`, and `cell_fill` parameters, but these are out of the scope of this tutorial. For more information, please refer to the tensor_cell2cell documentation, as well as the `c2c.tensor.external_scores.dataframes_to_tensor` function.


```python
tensor = li.multi.to_tensor_c2c(adata,
                                sample_key=sample_key,
                                score_key='magnitude_rank', # can be any score from liana
                                how='outer_cells' # how to join the samples
                                )
```

We can check the shape of the tensor, represented as (Contexts, Interactions, Senders, Receivers).


```python
tensor.tensor.shape
```

One can save the tensor to disk, by using the `c2c.io.export_variable_with_pickle` function


```python
c2c.io.export_variable_with_pickle(tensor, "tensor_tutorial.pkl")
```

Build Metadata


```python
context_dict = adata.obs[[sample_key, condition_key]].drop_duplicates()
context_dict = dict(zip(context_dict[sample_key], context_dict[condition_key]))
context_dict = defaultdict(lambda: 'Unknown', context_dict)

tensor_meta = c2c.tensor.generate_tensor_metadata(interaction_tensor=tensor,
                                                  metadata_dicts=[context_dict, None, None, None],
                                                  fill_with_order_elements=True
                                                  )
```

#### Running Tensor-cell2cell

Let's now run the Tensor decomposition pipeline of Tensor-cell2cell. This function includes optimal rank estimation, as well as PARAFAC decomposition of the tensor. For more information, please refer to the Tensor-cell2cell manuscript.


```python
tensor = c2c.analysis.run_tensor_cell2cell_pipeline(tensor,
                                                    tensor_meta,
                                                    copy_tensor=True, # Whether to output a new tensor or modifying the original
                                                    rank=6, # Number of factors to perform the factorization. If None, it is automatically determined by an elbow analysis. Here, it was precomuputed.
                                                    tf_optimization='regular', # To define how robust we want the analysis to be.
                                                    random_state=0, # Random seed for reproducibility
                                                    device=device, # Device to use. If using GPU and PyTorch, use 'cuda'. For CPU use 'cpu'
                                                    elbow_metric='error', # Metric to use in the elbow analysis.
                                                    smooth_elbow=False, # Whether smoothing the metric of the elbow analysis.
                                                    upper_rank=20, # Max number of factors to try in the elbow analysis
                                                    tf_init='random', # Initialization method of the tensor factorization
                                                    tf_svd='numpy_svd', # Type of SVD to use if the initialization is 'svd'
                                                    cmaps=None, # Color palettes to use in color each of the dimensions. Must be a list of palettes.
                                                    sample_col='Element', # Columns containing the elements in the tensor metadata
                                                    group_col='Category', # Columns containing the major groups in the tensor metadata
                                                    output_fig=False, # Whether to output the figures. If False, figures won't be saved a files if a folder was passed in output_folder.
                                                    )
```

Plot Tensor Decomposition results


```python
factors, axes = c2c.plotting.tensor_factors_plot(interaction_tensor=tensor,
                                                 metadata = tensor_meta, # This is the metadata for each dimension
                                                 sample_col='Element',
                                                 group_col='Category',
                                                 meta_cmaps = ['viridis', 'Dark2_r', 'tab20', 'tab20'],
                                                 fontsize=10, # Font size of the figures generated
                                                 )
```

## Factorization Results

To get a more detailed look we can access the factors and loadings of the decomposition. As expected, for each factor we get four vectors, one for each dimension of the tensor. We can access those as follows:


```python
factors = tensor.factors
```


```python
factors.keys()
```


```python
_ = c2c.plotting.context_boxplot(context_loadings=factors['Contexts'],
                                 metadict=context_dict,
                                 nrows=2,
                                 figsize=(8, 6),
                                 statistical_test='t-test_ind',
                                 pval_correction='fdr_bh',
                                 cmap='plasma',
                                 verbose=False,
                                )
```

The cell types associated with Factors of interest, in this case Factor 6 are CD14+ Monocytes, FCGR3A+ Monocytes, and Dendritic cells:


```python
c2c.plotting.ccc_networks_plot(factors,
                               included_factors=['Factor 6'],
                               network_layout='circular',
                               ccc_threshold=0.05, # Only important communication
                               nrows=1,
                               panel_size=(8, 8), # This changes the size of each figure panel.
                              )
```

We can also check the loadings of each factor, which are the weights assigned to each interaction, sender, and receiver cell type.
So, let's check the ligand-receptor interactions with the highest loadings in `Factor 6`.


```python
lr_loadings = factors['Ligand-Receptor Pairs']
lr_loadings.sort_values("Factor 6", ascending=False).head(10)
```


## Downstream Analysis

Let's also perform a basic enrichment analysis on the results above. We will use decoupler with pathway genesets from PROGENy.


```python
# load PROGENy pathways
net = dc.op.progeny(organism='human', top=5000)
```


```python
# load full list of ligand-receptor pairs
lr_pairs = li.resource.select_resource('consensus')
```


```python
# generate ligand-receptor geneset
lr_progeny = li.rs.generate_lr_geneset(lr_pairs, net, lr_sep="^").rename(columns = {"interaction": "target"})
lr_progeny.head()
```


```python
# run enrichment analysis
estimate, pvals = dc.mt.ulm(lr_loadings.transpose(), lr_progeny, raw=False)
```

Check Enrichment results for Factor 5


```python
dc.pl.barplot(estimate, 'Factor 6', vertical=True, cmap='coolwarm', vmin=-7, vmax=7)
```
