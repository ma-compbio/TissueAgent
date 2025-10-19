## scanpy.read_csv(filename, delimiter=',', first_column_names=None, dtype='float32')
Read `.csv` file.

Same as [`read_text()`](https://anndata.readthedocs.io/en/stable/generated/anndata.io.read_text.html#anndata.io.read_text) but with default delimiter `','`.

* **Parameters:**
  **filename** 
  : Data file.

  **delimiter** 
  : Delimiter that separates data within text file.
    If `None`, will split at arbitrary number of white spaces,
    which is different from enforcing splitting at single white space `' '`.

  **first_column_names** 
  : Assume the first column stores row names.

  **dtype** 
  : Numpy data type.
* **Return type:**
  [`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData)

