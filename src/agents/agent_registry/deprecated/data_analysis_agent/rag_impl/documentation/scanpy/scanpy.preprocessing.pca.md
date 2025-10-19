## scanpy.preprocessing.pca(data, n_comps=None, \*, layer=None, zero_center=True, svd_solver=None, random_state=0, return_info=False, mask_var=\_empty, use_highly_variable=None, dtype='float32', chunked=False, chunk_size=None, key_added=None, copy=False)
Principal component analysis [[Pedregosa *et al.*, 2011](../references.md#id44)].

Computes PCA coordinates, loadings and variance decomposition.
Uses the implementation of *scikit-learn* [[Pedregosa *et al.*, 2011](../references.md#id44)].

#### Versionchanged
Changed in version 1.5.0: In previous versions, computing a PCA on a sparse matrix would make
a dense copy of the array for mean centering.
As of scanpy 1.5.0, mean centering is implicit.
While results are extremely similar, they are not exactly the same.
If you would like to reproduce the old results, pass a dense array.

* **Parameters:**
  **data** 
  : The (annotated) data matrix of shape `n_obs` × `n_vars`.
    Rows correspond to cells and columns to genes.

  **n_comps** 
  : Number of principal components to compute. Defaults to 50, or 1 - minimum
    dimension size of selected representation.

  **layer** 
  : If provided, which element of layers to use for PCA.

  **zero_center** 
  : If `True`, compute standard PCA from covariance matrix.
    If `False`, omit zero-centering variables
    (uses *scikit-learn* [`TruncatedSVD`](https://scikit-learn.org/stable/modules/generated/sklearn.decomposition.TruncatedSVD.html#sklearn.decomposition.TruncatedSVD) or
    *dask-ml* [`TruncatedSVD`](https://ml.dask.org/modules/generated/dask_ml.decomposition.TruncatedSVD.html#dask_ml.decomposition.TruncatedSVD)),
    which allows to handle sparse input efficiently.
    Passing `None` decides automatically based on sparseness of the data.

  **svd_solver** 
  : SVD solver to use:
    <br/>
    `None`
    : See `chunked` and `zero_center` descriptions to determine which class will be used.
      Depending on the class and the type of X different values for default will be set.
      For sparse *dask* arrays, will use `'covariance_eigh'`.
      If *scikit-learn* [`PCA`](https://scikit-learn.org/stable/modules/generated/sklearn.decomposition.PCA.html#sklearn.decomposition.PCA) is used, will give `'arpack'`,
      if *scikit-learn* [`TruncatedSVD`](https://scikit-learn.org/stable/modules/generated/sklearn.decomposition.TruncatedSVD.html#sklearn.decomposition.TruncatedSVD) is used, will give `'randomized'`,
      if *dask-ml* [`PCA`](https://ml.dask.org/modules/generated/dask_ml.decomposition.PCA.html#dask_ml.decomposition.PCA) or [`IncrementalPCA`](https://ml.dask.org/modules/generated/dask_ml.decomposition.IncrementalPCA.html#dask_ml.decomposition.IncrementalPCA) is used, will give `'auto'`,
      if *dask-ml* [`TruncatedSVD`](https://ml.dask.org/modules/generated/dask_ml.decomposition.TruncatedSVD.html#dask_ml.decomposition.TruncatedSVD) is used, will give `'tsqr'`
    <br/>
    `'arpack'`
    : for the ARPACK wrapper in SciPy ([`svds()`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.sparse.linalg.svds.html#scipy.sparse.linalg.svds))
      Not available with *dask* arrays.
    <br/>
    `'covariance_eigh'`
    : Classic eigendecomposition of the covariance matrix, suited for tall-and-skinny matrices.
      With dask, array must be CSR or dense and chunked as (N, adata.shape[1]).
    <br/>
    `'randomized'`
    : for the randomized algorithm due to Halko (2009). For *dask* arrays,
      this will use [`svd_compressed()`](https://docs.dask.org/en/stable/generated/dask.array.linalg.svd_compressed.html#dask.array.linalg.svd_compressed).
    <br/>
    `'auto'`
    : chooses automatically depending on the size of the problem.
    <br/>
    `'tsqr'`
    : Only available with dense *dask* arrays. “tsqr”
      algorithm from Benson et. al. (2013).
    <br/>
    #### Versionchanged
    Changed in version 1.9.3: Default value changed from `'arpack'` to None.
    <br/>
    #### Versionchanged
    Changed in version 1.4.5: Default value changed from `'auto'` to `'arpack'`.
    <br/>
    Efficient computation of the principal components of a sparse matrix
    currently only works with the `'arpack`’ or `'covariance_eigh`’ solver.
    <br/>
    If X is a sparse *dask* array, a custom `'covariance_eigh'` solver will be used.
    If X is a dense *dask* array, *dask-ml* classes [`PCA`](https://ml.dask.org/modules/generated/dask_ml.decomposition.PCA.html#dask_ml.decomposition.PCA),
    [`IncrementalPCA`](https://ml.dask.org/modules/generated/dask_ml.decomposition.IncrementalPCA.html#dask_ml.decomposition.IncrementalPCA), or
    [`TruncatedSVD`](https://ml.dask.org/modules/generated/dask_ml.decomposition.TruncatedSVD.html#dask_ml.decomposition.TruncatedSVD) will be used.
    Otherwise their *scikit-learn* counterparts [`PCA`](https://scikit-learn.org/stable/modules/generated/sklearn.decomposition.PCA.html#sklearn.decomposition.PCA),
    [`IncrementalPCA`](https://scikit-learn.org/stable/modules/generated/sklearn.decomposition.IncrementalPCA.html#sklearn.decomposition.IncrementalPCA), or
    [`TruncatedSVD`](https://scikit-learn.org/stable/modules/generated/sklearn.decomposition.TruncatedSVD.html#sklearn.decomposition.TruncatedSVD) will be used.

  **random_state** 
  : Change to use different initial states for the optimization.

  **return_info** 
  : Only relevant when not passing an [`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData):
    see “Returns”.

  **mask_var** 
  : To run only on a certain set of genes given by a boolean array
    or a string referring to an array in [`var`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.var.html#anndata.AnnData.var).
    By default, uses `.var['highly_variable']` if available, else everything.

  **use_highly_variable** 
  : Whether to use highly variable genes only, stored in
    `.var['highly_variable']`.
    By default uses them if they have been determined beforehand.
    <br/>
    #### Deprecated
    Deprecated since version 1.10.0: Use `mask_var` instead

  **layer**
  : Layer of `adata` to use as expression values.

  **dtype** 
  : Numpy data type string to which to convert the result.

  **chunked** 
  : If `True`, perform an incremental PCA on segments of `chunk_size`.
    The incremental PCA automatically zero centers and ignores settings of
    `random_seed` and `svd_solver`. Uses sklearn [`IncrementalPCA`](https://scikit-learn.org/stable/modules/generated/sklearn.decomposition.IncrementalPCA.html#sklearn.decomposition.IncrementalPCA) or
    *dask-ml* [`IncrementalPCA`](https://ml.dask.org/modules/generated/dask_ml.decomposition.IncrementalPCA.html#dask_ml.decomposition.IncrementalPCA). If `False`, perform a full PCA and
    use sklearn [`PCA`](https://scikit-learn.org/stable/modules/generated/sklearn.decomposition.PCA.html#sklearn.decomposition.PCA) or
    *dask-ml* [`PCA`](https://ml.dask.org/modules/generated/dask_ml.decomposition.PCA.html#dask_ml.decomposition.PCA)

  **chunk_size** 
  : Number of observations to include in each chunk.
    Required if `chunked=True` was passed.

  **key_added** 
  : If not specified, the embedding is stored as
    [`obsm`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obsm.html#anndata.AnnData.obsm)`['X_pca']`, the loadings as
    [`varm`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.varm.html#anndata.AnnData.varm)`['PCs']`, and the the parameters in
    [`uns`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.uns.html#anndata.AnnData.uns)`['pca']`.
    If specified, the embedding is stored as
    [`obsm`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obsm.html#anndata.AnnData.obsm)`[key_added]`, the loadings as
    [`varm`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.varm.html#anndata.AnnData.varm)`[key_added]`, and the the parameters in
    [`uns`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.uns.html#anndata.AnnData.uns)`[key_added]`.

  **copy** 
  : If an [`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData) is passed, determines whether a copy
    is returned. Is ignored otherwise.
* **Return type:**
  AnnData | np.ndarray | \_CSMatrix | None
* **Returns:**
  If `data` is array-like and `return_info=False` was passed,
  this function returns the PCA representation of `data` as an
  array of the same type as the input array.

  Otherwise, it returns `None` if `copy=False`, else an updated `AnnData` object.
  Sets the following fields:

  `.obsm['X_pca' | key_added]`
  : PCA representation of data.

  `.varm['PCs' | key_added]`
  : The principal components containing the loadings.

  `.uns['pca' | key_added]['variance_ratio']`
  : Ratio of explained variance.

  `.uns['pca' | key_added]['variance']`
  : Explained variance, equivalent to the eigenvalues of the
    covariance matrix.

