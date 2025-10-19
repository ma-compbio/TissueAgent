## scanpy.plotting.dendrogram(adata, groupby, \*, dendrogram_key=None, orientation='top', remove_labels=False, show=None, save=None, ax=None)
Plot a dendrogram of the categories defined in `groupby`.

See `dendrogram()`.

* **Parameters:**
  **adata** 
  : Annotated data matrix.

  **groupby** 
  : Categorical data column used to create the dendrogram

  **dendrogram_key** 
  : Key under with the dendrogram information was stored.
    By default the dendrogram information is stored under
    `.uns[f'dendrogram_{groupby}']`.

  **orientation** 
  : Origin of the tree. Will grow into the opposite direction.

  **remove_labels** 
  : Don’t draw labels. Used e.g. by `scanpy.pl.matrixplot()`
    to annotate matrix columns/rows.

  **show** 
  : Show the plot, do not return axis.

  **save** 
  : If `True` or a `str`, save the figure.
    A string is appended to the default filename.
    Infer the filetype if ending on {`'.pdf'`, `'.png'`, `'.svg'`}.

  **ax** 
  : A matplotlib axes object. Only works if plotting a single component.
* **Return type:**
  [`Axes`](https://matplotlib.org/stable/api/_as_gen/matplotlib.axes.Axes.html#matplotlib.axes.Axes)
* **Returns:**
  [`matplotlib.axes.Axes`](https://matplotlib.org/stable/api/_as_gen/matplotlib.axes.Axes.html#matplotlib.axes.Axes)

### Examples

```python
import scanpy as sc
adata = sc.datasets.pbmc68k_reduced()
sc.tl.dendrogram(adata, 'bulk_labels')
sc.pl.dendrogram(adata, 'bulk_labels')
```

![image](_build/markdown/plot_directive/api/scanpy-plotting-3.*)

