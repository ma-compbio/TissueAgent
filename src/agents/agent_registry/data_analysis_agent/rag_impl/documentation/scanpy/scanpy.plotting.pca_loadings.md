## scanpy.plotting.pca_loadings(adata, components=None, \*, include_lowest=True, n_points=None, show=None, save=None)
Rank genes according to contributions to PCs.

* **Parameters:**
  **adata** 
  : Annotated data matrix.

  **components** 
  : For example, `'1,2,3'` means `[1, 2, 3]`, first, second, third
    principal component.

  **include_lowest** 
  : Whether to show the variables with both highest and lowest loadings.

  **show** 
  : Show the plot, do not return axis.

  **n_points** 
  : Number of variables to plot for each component.

  **save** 
  : If `True` or a `str`, save the figure.
    A string is appended to the default filename.
    Infer the filetype if ending on {`'.pdf'`, `'.png'`, `'.svg'`}.

### Examples

```python
import scanpy as sc
adata = sc.datasets.pbmc3k_processed()
```

Show first 3 components loadings

```python
sc.pl.pca_loadings(adata, components = '1,2,3')
```

![image](_build/markdown/plot_directive/api/scanpy-plotting-30.*)

