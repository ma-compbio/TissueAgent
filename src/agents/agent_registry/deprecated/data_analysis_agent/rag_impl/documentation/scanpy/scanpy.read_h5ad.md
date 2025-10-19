## scanpy.read_h5ad(filename, backed=None, \*, as_sparse=(), as_sparse_fmt=<class 'scipy.sparse._csr.csr_matrix'>, chunk_size=6000)
Read `.h5ad`-formatted hdf5 file.

* **Parameters:**
  **filename** 
  : File name of data file.

  **backed** 
  : If `'r'`, load [`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData) in `backed` mode
    instead of fully loading it into memory (`memory` mode).
    If you want to modify backed attributes of the AnnData object,
    you need to choose `'r+'`.
    <br/>
    Currently, `backed` only support updates to `X`. That means any
    changes to other slots like `obs` will not be written to disk in
    `backed` mode. If you would like save changes made to these slots
    of a `backed` [`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData), write them to a new file
    (see [`write()`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.write.html#anndata.AnnData.write)). For an example, see
    [Partial reading of large data](https://anndata.readthedocs.io/en/stable/tutorials/notebooks/getting-started.html#read-partial).

  **as_sparse** 
  : If an array was saved as dense, passing its name here will read it as
    a sparse_matrix, by chunk of size `chunk_size`.

  **as_sparse_fmt** 
  : Sparse format class to read elements from `as_sparse` in as.

  **chunk_size** 
  : Used only when loading sparse dataset that is stored as dense.
    Loading iterates through chunks of the dataset of this row size
    until it reads the whole dataset.
    Higher size means higher memory consumption and higher (to a point)
    loading speed.
* **Return type:**
  [`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData)

