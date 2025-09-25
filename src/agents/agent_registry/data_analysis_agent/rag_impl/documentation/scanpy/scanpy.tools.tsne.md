## scanpy.tools.tsne(adata, n_pcs=None, \*, use_rep=None, perplexity=30, metric='euclidean', early_exaggeration=12, learning_rate=1000, random_state=0, use_fast_tsne=False, n_jobs=None, key_added=None, copy=False)
t-SNE [[Amir *et al.*, 2013](../references.md#id3), [Pedregosa *et al.*, 2011](../references.md#id44), [van der Maaten and Hinton, 2008](../references.md#id66)].

t-distributed stochastic neighborhood embedding (tSNE, van der Maaten and Hinton [[2008](../references.md#id66)]) was
proposed for visualizating single-cell data by Amir *et al.* [[2013](../references.md#id3)]. Here, by default,
we use the implementation of *scikit-learn* [[Pedregosa *et al.*, 2011](../references.md#id44)]. You can achieve
a huge speedup and better convergence if you install [Multicore-tSNE](https://github.com/DmitryUlyanov/Multicore-TSNE)
by Ulyanov [[2016](../references.md#id56)], which will be automatically detected by Scanpy.

* **Parameters:**
  **adata** 
  : Annotated data matrix.

  **n_pcs** 
  : Use this many PCs. If `n_pcs==0` use `.X` if `use_rep is None`.

  **use_rep** 
  : Use the indicated representation. `'X'` or any key for `.obsm` is valid.
    If `None`, the representation is chosen automatically:
    For `.n_vars` < `N_PCS` (default: 50), `.X` is used, otherwise ‘X_pca’ is used.
    If ‘X_pca’ is not present, it’s computed with default parameters or `n_pcs` if present.

  **perplexity** 
  : The perplexity is related to the number of nearest neighbors that
    is used in other manifold learning algorithms. Larger datasets
    usually require a larger perplexity. Consider selecting a value
    between 5 and 50. The choice is not extremely critical since t-SNE
    is quite insensitive to this parameter.

  **metric** 
  : Distance metric calculate neighbors on.

  **early_exaggeration** 
  : Controls how tight natural clusters in the original space are in the
    embedded space and how much space will be between them. For larger
    values, the space between natural clusters will be larger in the
    embedded space. Again, the choice of this parameter is not very
    critical. If the cost function increases during initial optimization,
    the early exaggeration factor or the learning rate might be too high.

  **learning_rate** 
  : Note that the R-package “Rtsne” uses a default of 200.
    The learning rate can be a critical parameter. It should be
    between 100 and 1000. If the cost function increases during initial
    optimization, the early exaggeration factor or the learning rate
    might be too high. If the cost function gets stuck in a bad local
    minimum increasing the learning rate helps sometimes.

  **random_state** 
  : Change this to use different intial states for the optimization.
    If `None`, the initial state is not reproducible.

  **n_jobs** 
  : Number of jobs for parallel computation.
    `None` means using `scanpy._settings.ScanpyConfig.n_jobs`.

  **key_added** 
  : If not specified, the embedding is stored as
    [`obsm`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obsm.html#anndata.AnnData.obsm)`['X_tsne']` and the the parameters in
    [`uns`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.uns.html#anndata.AnnData.uns)`['tsne']`.
    If specified, the embedding is stored as
    [`obsm`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obsm.html#anndata.AnnData.obsm)`[key_added]` and the the parameters in
    [`uns`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.uns.html#anndata.AnnData.uns)`[key_added]`.

  **copy** 
  : Return a copy instead of writing to `adata`.
* **Return type:**
  [`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData) | [`None`](https://docs.python.org/3/library/constants.html#None)
* **Returns:**
  Returns `None` if `copy=False`, else returns an `AnnData` object. Sets the following fields:

  `adata.obsm['X_tsne' | key_added]`
  : tSNE coordinates of data.

  `adata.uns['tsne' | key_added]`
  : tSNE parameters.

