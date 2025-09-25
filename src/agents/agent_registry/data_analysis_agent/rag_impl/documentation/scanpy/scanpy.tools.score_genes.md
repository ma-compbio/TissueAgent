## scanpy.tools.score_genes(adata, gene_list, \*, ctrl_as_ref=True, ctrl_size=50, gene_pool=None, n_bins=25, score_name='score', random_state=0, copy=False, use_raw=None, layer=None)
Score a set of genes [[Satija *et al.*, 2015](../references.md#id47)].

The score is the average expression of a set of genes after subtraction by
the average expression of a reference set of genes. The reference set is
randomly sampled from the `gene_pool` for each binned expression value.

This reproduces the approach in Seurat [[Satija *et al.*, 2015](../references.md#id47)] and has been implemented
for Scanpy by Davide Cittaro.

* **Parameters:**
  **adata**
  : The annotated data matrix.

  **gene_list**
  : The list of gene names used for score calculation.

  **ctrl_as_ref** 
  : Allow the algorithm to use the control genes as reference.
    Will be changed to `False` in scanpy 2.0.

  **ctrl_size** 
  : Number of reference genes to be sampled from each bin. If `len(gene_list)` is not too
    low, you can set `ctrl_size=len(gene_list)`.

  **gene_pool** 
  : Genes for sampling the reference set. Default is all genes.

  **n_bins** 
  : Number of expression level bins for sampling.

  **score_name** 
  : Name of the field to be added in `.obs`.

  **random_state** 
  : The random seed for sampling.

  **copy** 
  : Copy `adata` or modify it inplace.

  **use_raw** 
  : Whether to use `raw` attribute of `adata`. Defaults to `True` if `.raw` is present.
    <br/>
    #### Versionchanged
    Changed in version 1.4.5: Default value changed from `False` to `None`.

  **layer** 
  : Key from `adata.layers` whose value will be used to perform tests on.
* **Returns:**
  Returns `None` if `copy=False`, else returns an `AnnData` object. Sets the following field:

  `adata.obs[score_name]`
  : Scores of each cell.

### Examples

See this [notebook](https://github.com/scverse/scanpy_usage/tree/master/180209_cell_cycle).

