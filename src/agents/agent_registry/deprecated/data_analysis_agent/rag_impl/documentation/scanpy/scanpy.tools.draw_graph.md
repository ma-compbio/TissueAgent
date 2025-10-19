## scanpy.tools.draw_graph(adata, layout='fa', \*, init_pos=None, root=None, random_state=0, n_jobs=None, adjacency=None, key_added_ext=None, neighbors_key=None, obsp=None, copy=False, \*\*kwds)
Force-directed graph drawing [[Chippada, 2018](../references.md#id11), [Islam *et al.*, 2011](../references.md#id22), [Jacomy *et al.*, 2014](../references.md#id23)].

An alternative to tSNE that often preserves the topology of the data
better. This requires running `neighbors()`, first.

The default layout (‘fa’, `ForceAtlas2`, Jacomy *et al.* [[2014](../references.md#id23)]) uses the package [`fa2-modified`](https://github.com/AminAlam/fa2_modified)
[[Chippada, 2018](../references.md#id11)], which can be installed via `pip install fa2-modified`.

[Force-directed graph drawing](https://en.wikipedia.org/wiki/Force-directed_graph_drawing) describes a class of long-established
algorithms for visualizing graphs.
It was suggested for visualizing single-cell data by Islam *et al.* [[2011](../references.md#id22)].
Many other layouts as implemented in igraph [[Csárdi and Nepusz, 2006](../references.md#id13)] are available.
Similar approaches have been used by Zunder *et al.* [[2015](../references.md#id65)] or Weinreb *et al.* [[2017](../references.md#id59)].

* **Parameters:**
  **adata** 
  : Annotated data matrix.

  **layout** 
  : ‘fa’ (`ForceAtlas2`) or any valid [igraph layout](https://igraph.org/c/doc/igraph-Layout.html). Of particular interest
    are ‘fr’ (Fruchterman Reingold), ‘grid_fr’ (Grid Fruchterman Reingold,
    faster than ‘fr’), ‘kk’ (Kamadi Kawai’, slower than ‘fr’), ‘lgl’ (Large
    Graph, very fast), ‘drl’ (Distributed Recursive Layout, pretty fast) and
    ‘rt’ (Reingold Tilford tree layout).

  **root** 
  : Root for tree layouts.

  **random_state** 
  : For layouts with random initialization like ‘fr’, change this to use
    different intial states for the optimization. If `None`, no seed is set.

  **adjacency** 
  : Sparse adjacency matrix of the graph, defaults to neighbors connectivities.

  **key_added_ext** 
  : By default, append `layout`.

  **proceed**
  : Continue computation, starting off with ‘X_draw_graph_\`layout\`’.

  **init_pos** 
  : `'paga'`/`True`, `None`/`False`, or any valid 2d-`.obsm` key.
    Use precomputed coordinates for initialization.
    If `False`/`None` (the default), initialize randomly.

  **neighbors_key** 
  : If not specified, draw_graph looks at .obsp[‘connectivities’] for connectivities
    (default storage place for pp.neighbors).
    If specified, draw_graph looks at
    .obsp[.uns[neighbors_key][‘connectivities_key’]] for connectivities.

  **obsp** 
  : Use .obsp[obsp] as adjacency. You can’t specify both
    `obsp` and `neighbors_key` at the same time.

  **copy** 
  : Return a copy instead of writing to adata.

  **\*\*kwds**
  : Parameters of chosen igraph layout. See e.g.
    [`layout_fruchterman_reingold()`](https://python.igraph.org/en/stable/api/igraph.GraphBase.html#layout_fruchterman_reingold) [[Fruchterman and Reingold, 1991](../references.md#id16)].
    One of the most important ones is `maxiter`.
* **Return type:**
  [`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData) | [`None`](https://docs.python.org/3/library/constants.html#None)
* **Returns:**
  Returns `None` if `copy=False`, else returns an `AnnData` object. Sets the following fields:

  `adata.obsm['X_draw_graph_[layout | key_added_ext]']`
  : Coordinates of graph layout. E.g. for `layout='fa'` (the default),
    the field is called `'X_draw_graph_fa'`. `key_added_ext` overwrites `layout`.

  `adata.uns['draw_graph']`: [`dict`](https://docs.python.org/3/library/stdtypes.html#dict)
  : `draw_graph` parameters.

