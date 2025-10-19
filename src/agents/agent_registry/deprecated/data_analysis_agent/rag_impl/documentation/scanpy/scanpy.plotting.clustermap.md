## scanpy.plotting.clustermap(adata, obs_keys=None, \*, use_raw=None, show=None, save=None, \*\*kwds)
Hierarchically-clustered heatmap.

Wraps [`seaborn.clustermap()`](https://seaborn.pydata.org/generated/seaborn.clustermap.html#seaborn.clustermap) for [`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData).

* **Parameters:**
  **adata** 
  : Annotated data matrix.

  **obs_keys** 
  : Categorical annotation to plot with a different color map.
    Currently, only a single key is supported.

  **use_raw** 
  : Whether to use `raw` attribute of `adata`. Defaults to `True` if `.raw` is present.

  **show** 
  : Show the plot, do not return axis.

  **save** 
  : If `True` or a `str`, save the figure.
    A string is appended to the default filename.
    Infer the filetype if ending on {`'.pdf'`, `'.png'`, `'.svg'`}.

  **ax**
  : A matplotlib axes object. Only works if plotting a single component.

  **\*\*kwds**
  : Keyword arguments passed to [`clustermap()`](https://seaborn.pydata.org/generated/seaborn.clustermap.html#seaborn.clustermap).
* **Return type:**
  `ClusterGrid` | [`None`](https://docs.python.org/3/library/constants.html#None)
* **Returns:**
  If `show` is `False`, a `ClusterGrid` object
  (see [`clustermap()`](https://seaborn.pydata.org/generated/seaborn.clustermap.html#seaborn.clustermap)).

### Examples

```python
import scanpy as sc
adata = sc.datasets.krumsiek11()
sc.pl.clustermap(adata)
```

![image](_build/markdown/plot_directive/api/scanpy-plotting-1.*)
```python
sc.pl.clustermap(adata, obs_keys='cell_type')
```

![image](_build/markdown/plot_directive/api/scanpy-plotting-2.*)

