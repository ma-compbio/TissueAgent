## scanpy.read_hdf(filename, key)
Read `.h5` (hdf5) file.

Note: Also looks for fields `row_names` and `col_names`.

* **Parameters:**
  **filename** 
  : Filename of data file.

  **key** 
  : Name of dataset in the file.
* **Return type:**
  [`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData)

