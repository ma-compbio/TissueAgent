## scanpy.readwrite.read(filename, backed=None, \*, sheet=None, ext=None, delimiter=None, first_column_names=False, backup_url=None, cache=False, cache_compression=\_empty, \*\*kwargs)
Read file and return [`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData) object.

To speed up reading, consider passing `cache=True`, which creates an hdf5
cache file.

* **Parameters:**
  **filename** 
  : If the filename has no file extension, it is interpreted as a key for
    generating a filename via `sc.settings.writedir / (filename +
    sc.settings.file_format_data)`.  This is the same behavior as in
    `sc.read(filename, ...)`.

  **backed** 
  : If `'r'`, load [`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData) in `backed` mode instead
    of fully loading it into memory (`memory` mode). If you want to modify
    backed attributes of the AnnData object, you need to choose `'r+'`.

  **sheet** 
  : Name of sheet/table in hdf5 or Excel file.

  **ext** 
  : Extension that indicates the file type. If `None`, uses extension of
    filename.

  **delimiter** 
  : Delimiter that separates data within text file. If `None`, will split at
    arbitrary number of white spaces, which is different from enforcing
    splitting at any single white space `' '`.

  **first_column_names** 
  : Assume the first column stores row names. This is only necessary if
    these are not strings: strings in the first column are automatically
    assumed to be row names.

  **backup_url** 
  : Retrieve the file from an URL if not present on disk.

  **cache** 
  : If `False`, read from source, if `True`, read from fast ‘h5ad’ cache.

  **cache_compression** 
  : See the h5py [Filter pipeline](https://docs.h5py.org/en/stable/high/dataset.html#dataset-compression).
    (Default: `settings.cache_compression`)

  **kwargs**
  : Parameters passed to [`read_loom()`](https://anndata.readthedocs.io/en/stable/generated/anndata.io.read_loom.html#anndata.io.read_loom).
* **Return type:**
  [`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData)
* **Returns:**
  An [`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData) object

