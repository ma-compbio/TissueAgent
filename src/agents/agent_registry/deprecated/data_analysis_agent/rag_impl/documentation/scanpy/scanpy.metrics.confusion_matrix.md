## scanpy.metrics.confusion_matrix(orig, new, data=None, \*, normalize=True)
Given an original and new set of labels, create a labelled confusion matrix.

Parameters `orig` and `new` can either be entries in data or categorical arrays
of the same size.

* **Parameters:**
  **orig** 
  : Original labels.

  **new** 
  : New labels.

  **data** 
  : Optional dataframe to fill entries from.

  **normalize** 
  : Should the confusion matrix be normalized?
* **Return type:**
  [`DataFrame`](https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.html#pandas.DataFrame)

### Examples

```python
import scanpy as sc; import seaborn as sns
pbmc = sc.datasets.pbmc68k_reduced()
cmtx = sc.metrics.confusion_matrix("bulk_labels", "louvain", pbmc.obs)
sns.heatmap(cmtx)
```

![image](_build/markdown/plot_directive/api/scanpy-metrics-1.*)
