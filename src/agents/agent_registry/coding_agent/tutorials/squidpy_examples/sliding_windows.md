# Analyse your spatial data using sliding windows

This example shows how to use {func}`squidpy.tl.sliding_window` to divide the 
obs of an {attr}`anndata.AnnData` object into adjecent, potentially overlapping,
windows.


```python
import matplotlib.pyplot as plt

import squidpy as sq
```

First, let's download the MIBI-TOF dataset.


```python
adata = sq.datasets.mibitof()
```

This data set contains a cell type annotation in {attr}`anndata.AnnData.obs["Cluster"]`
and a slide annotation in {attr}`anndata.AnnData.obs["library_id"]`


```python
adata.obs
```

Stratified by library, we now want to assign each cell to a sliding window of a given size.


```python
sq.tl.sliding_window(
    adata=adata,
    library_key="library_id",  # to stratify by sample
    window_size=300,
    overlap=0,
    copy=False,  # we modify in place
)
```

Let's inspect the column that the function has added to our data.


```python
adata.obs["sliding_window_assignment"]
```

We see that each observation has been assigned to a window, which is defined by the `sliding_window_assignment` column. We can visualise this using {func}`squidpy.pl.spatial_scatter`.


```python
sq.pl.spatial_scatter(
    adata, color="sliding_window_assignment", library_key="library_id", figsize=(10, 10)
)
```

Optionally, we can also look at a specific sample:


```python
sq.pl.spatial_scatter(
    adata,
    color="sliding_window_assignment",
    library_key="library_id",
    library_id=["point8"],
    figsize=(10, 10),
)
```

We see that the function has created 16 windows, this is based on the `window_size` of 200 and an `overlap` of 0. The behaviour of the function changes when we use an overlap, since then observations will be assigned to multiple windows. This information can no longer be stored in a single column. Let's try this out.


```python
adata = sq.datasets.mibitof()  # fresh copy

sq.tl.sliding_window(
    adata=adata,
    library_key="library_id",  # to stratify by sample
    window_size=300,
    overlap=50,
    copy=False,  # we modify in place
)
```

When now inspecting the {attr}`anndata.AnnData.obs`, we see that several columns have been added, each indicating whether an observation is a member of a specific window, stratified by `library_key`.

Due to the overlapping assignments, we now have more "true" assignments than observations. This is because each observation can be a member of multiple windows.


```python
total_cells = 0
for lib_key in ["point8", "point16", "point23"]:
    cols_in_lib = adata.obs.columns[adata.obs.columns.str.contains(lib_key)]
    total_cells_in_lib = sum(adata.obs[col].sum() for col in cols_in_lib)
    total_cells += total_cells_in_lib
    print(f"Total cells in {lib_key}: {total_cells_in_lib}")

print(f"Total cells: {total_cells}")
```

We can also illustrate these overlapping windows.


```python
adata_point8 = adata[adata.obs["library_id"] == "point8"]
cols = adata.obs.columns[adata.obs.columns.str.contains("point8")]

# convert True/False to category so we can vizualize it
adata_point8.obs[cols] = adata_point8.obs[cols].astype("category")

sq.pl.spatial_scatter(
    adata_point8,
    color=cols,
    library_key="library_id",
    library_id="point8",
    legend_loc=None,
)
plt.tight_layout()
```

Finally, we see that these specific parameters result in tiny windows with very few cells at the bottom and right corner. We can drop these with the parameter `drop_partial_windows`. 


```python
adata = sq.datasets.mibitof()  # fresh copy

sq.tl.sliding_window(
    adata=adata,
    library_key="library_id",  # to stratify by sample
    window_size=300,
    overlap=50,
    copy=False,  # we modify in place
    drop_partial_windows=True,
)

adata_point8 = adata[adata.obs["library_id"] == "point8"]
cols = adata.obs.columns[adata.obs.columns.str.contains("point8")]

# convert True/False to category so we can vizualize it
adata_point8.obs[cols] = adata_point8.obs[cols].astype("category")

sq.pl.spatial_scatter(
    adata_point8,
    color=cols,
    library_key="library_id",
    library_id="point8",
    legend_loc=None,
)
plt.tight_layout()
```

If desired, in-place modifications can be avoided by using `copy=True`. This then returns a {attr}`pandas.DataFrame` with the assignments.


```python
adata = sq.datasets.mibitof()  # fresh copy

assignment = sq.tl.sliding_window(
    adata=adata,
    library_key="library_id",  # to stratify by sample
    window_size=300,
    overlap=50,
    copy=True,  # we modify in place
    drop_partial_windows=True,
)

assignment
```

## For reproducibility


```python
import spatialdata

import numpy
import pandas

import matplotlib

import scanpy
import squidpy

%load_ext watermark
```


```python
%watermark -v -m -p numpy,pandas,matplotlib,scanpy,squidpy,spatialdata
```
