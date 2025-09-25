# squidpy.pl.extract

### squidpy.pl.extract(adata, obsm_key='img_features', prefix=None)

Create a temporary [`anndata.AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData) object for plotting.

Move columns from [`anndata.AnnData.obsm`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obsm.html#anndata.AnnData.obsm) `['{obsm_key}']` to [`anndata.AnnData.obs`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obs.html#anndata.AnnData.obs) to enable
the use of `scanpy.plotting` functions.

* **Parameters:**
  * **adata** ([`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData)) – Annotated data object.
  * **obsm_key** ([`list`](https://docs.python.org/3/library/stdtypes.html#list)[[`str`](https://docs.python.org/3/library/stdtypes.html#str)] | [`str`](https://docs.python.org/3/library/stdtypes.html#str)) – Entries in [`anndata.AnnData.obsm`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obsm.html#anndata.AnnData.obsm) that should be moved to [`anndata.AnnData.obs`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obs.html#anndata.AnnData.obs).
  * **prefix** ([`list`](https://docs.python.org/3/library/stdtypes.html#list)[[`str`](https://docs.python.org/3/library/stdtypes.html#str)] | [`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Prefix to prepend to each column name. Should be a :class;\`list\` if `obsm_key` is a [`list`](https://docs.python.org/3/library/stdtypes.html#list).
    If None, use the original column names.
* **Return type:**
  [`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData)
* **Returns:**
  :
  Temporary [`anndata.AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData) object with desired entries in [`anndata.AnnData.obs`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obs.html#anndata.AnnData.obs).
* **Raises:**
  [**ValueError**](https://docs.python.org/3/library/exceptions.html#ValueError) – If number of `prefixes` does not fit to number of `obsm_keys`.

### Notes

If [`anndata.AnnData.obs`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obs.html#anndata.AnnData.obs) `['{column}']` already exists, it will be overwritten and a warning will be issued.
