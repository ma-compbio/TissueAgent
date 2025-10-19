## scanpy.preprocessing.combat(adata, key='batch', \*, covariates=None, inplace=True)
ComBat function for batch effect correction [[Johnson *et al.*, 2006](../references.md#id24), [Leek *et al.*, 2017](../references.md#id31), [Pedersen, 2012](../references.md#id43)].

Corrects for batch effects by fitting linear models, gains statistical power
via an EB framework where information is borrowed across genes.
This uses the implementation [combat.py](https://github.com/brentp/combat.py) [[Pedersen, 2012](../references.md#id43)].

* **Parameters:**
  **adata** 
  : Annotated data matrix

  **key** 
  : Key to a categorical annotation from [`obs`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obs.html#anndata.AnnData.obs)
    that will be used for batch effect removal.

  **covariates** 
  : Additional covariates besides the batch variable such as adjustment
    variables or biological condition. This parameter refers to the design
    matrix `X` in Equation 2.1 in Johnson *et al.* [[2006](../references.md#id24)] and to the `mod` argument in
    the original combat function in the sva R package.
    Note that not including covariates may introduce bias or lead to the
    removal of biological signal in unbalanced designs.

  **inplace** 
  : Whether to replace adata.X or to return the corrected data
* **Return type:**
  [`ndarray`](https://numpy.org/doc/stable/reference/generated/numpy.ndarray.html#numpy.ndarray) | [`None`](https://docs.python.org/3/library/constants.html#None)
* **Returns:**
  Returns [`numpy.ndarray`](https://numpy.org/doc/stable/reference/generated/numpy.ndarray.html#numpy.ndarray) if `inplace=False`, else returns `None` and sets the following field in the `adata` object:

  `adata.X`
  : Corrected data matrix.

