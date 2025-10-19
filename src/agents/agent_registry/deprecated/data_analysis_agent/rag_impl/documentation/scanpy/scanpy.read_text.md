## scanpy.read_text(filename, delimiter=None, first_column_names=None, dtype='float32')
Read `.txt`, `.tab`, `.data` (text) file.

Same as [`read_csv()`](https://anndata.readthedocs.io/en/stable/generated/anndata.io.read_csv.html#anndata.io.read_csv) but with default delimiter `None`.

* **Parameters:**
  **filename** 
  : Data file, filename or stream.

  **delimiter** 
  : Delimiter that separates data within text file. If `None`, will split at
    arbitrary number of white spaces, which is different from enforcing
    splitting at single white space `' '`.

  **first_column_names** 
  : Assume the first column stores row names.

  **dtype** 
  : Numpy data type.
* **Return type:**
  [`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData)

