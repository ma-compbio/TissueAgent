## scanpy.read_excel(filename, sheet, dtype='float32')
Read `.xlsx` (Excel) file.

Assumes that the first columns stores the row names and the first row the
column names.

* **Parameters:**
  **filename** 
  : File name to read from.

  **sheet** 
  : Name of sheet in Excel file.
* **Return type:**
  [`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData)

