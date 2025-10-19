## scanpy.readwrite.write(filename, adata, \*, ext=None, compression='gzip', compression_opts=None)
Write [`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData) objects to file.

* **Parameters:**
  **filename** 
  : If the filename has no file extension, it is interpreted as a key for
    generating a filename via `sc.settings.writedir / (filename +
    sc.settings.file_format_data)`. This is the same behavior as in
    [`read()`](#scanpy.read).

  **adata** 
  : Annotated data matrix.

  **ext** 
  : File extension from wich to infer file format. If `None`, defaults to
    `sc.settings.file_format_data`.

  **compression** 
  : See [https://docs.h5py.org/en/latest/high/dataset.html](https://docs.h5py.org/en/latest/high/dataset.html).

  **compression_opts** 
  : See [https://docs.h5py.org/en/latest/high/dataset.html](https://docs.h5py.org/en/latest/high/dataset.html).

