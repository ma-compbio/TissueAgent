## scanpy.preprocessing.scrublet_simulate_doublets(adata, \*, layer=None, sim_doublet_ratio=2.0, synthetic_doublet_umi_subsampling=1.0, random_seed=0)
Simulate doublets by adding the counts of random observed transcriptome pairs.

* **Parameters:**
  **adata** 
  : The annotated data matrix of shape `n_obs` × `n_vars`. Rows
    correspond to cells and columns to genes. Genes should have been
    filtered for expression and variability, and the object should contain
    raw expression of the same dimensions.

  **layer** 
  : Layer of adata where raw values are stored, or ‘X’ if values are in .X.

  **sim_doublet_ratio** 
  : Number of doublets to simulate relative to the number of observed
    transcriptomes. If `None`, self.sim_doublet_ratio is used.

  **synthetic_doublet_umi_subsampling** 
  : Rate for sampling UMIs when creating synthetic doublets. If 1.0,
    each doublet is created by simply adding the UMIs from two randomly
    sampled observed transcriptomes. For values less than 1, the
    UMI counts are added and then randomly sampled at the specified
    rate.
* **Return type:**
  [`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData)
* **Returns:**
  adata : anndata.AnnData with simulated doublets in .X
  Adds fields to `adata`:

  `.obsm['scrublet']['doublet_parents']`
  : Pairs of `.obs_names` used to generate each simulated doublet transcriptome

  `.uns['scrublet']['parameters']`
  : Dictionary of Scrublet parameters

#### SEE ALSO
`scrublet()`
: Main way of running Scrublet, runs preprocessing, doublet simulation (this function) and calling.

`scrublet_score_distribution()`
: Plot histogram of doublet scores for observed transcriptomes and simulated doublets.

