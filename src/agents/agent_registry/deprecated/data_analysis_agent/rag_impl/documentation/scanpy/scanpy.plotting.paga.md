## scanpy.plotting.paga(adata, \*, threshold=None, color=None, layout=None, layout_kwds=mappingproxy({}), init_pos=None, root=0, labels=None, single_component=False, solid_edges='connectivities', dashed_edges=None, transitions=None, fontsize=None, fontweight='bold', fontoutline=None, text_kwds=mappingproxy({}), node_size_scale=1.0, node_size_power=0.5, edge_width_scale=1.0, min_edge_width=None, max_edge_width=None, arrowsize=30, title=None, left_margin=0.01, random_state=0, pos=None, normalize_to_color=False, cmap=None, cax=None, colorbar=None, cb_kwds=mappingproxy({}), frameon=None, add_pos=True, export_to_gexf=False, use_raw=True, colors=None, groups=None, plot=True, show=None, save=None, ax=None)
Plot the PAGA graph through thresholding low-connectivity edges.

Compute a coarse-grained layout of the data. Reuse this by passing
`init_pos='paga'` to `umap()` or
`draw_graph()` and obtain embeddings with more meaningful
global topology [[Wolf *et al.*, 2019](../references.md#id62)].

This uses ForceAtlas2 or igraph’s layout algorithms for most layouts [[Csárdi and Nepusz, 2006](../references.md#id13)].

* **Parameters:**
  **adata** 
  : Annotated data matrix.

  **threshold** 
  : Do not draw edges for weights below this threshold. Set to 0 if you want
    all edges. Discarding low-connectivity edges helps in getting a much
    clearer picture of the graph.

  **color** 
  : Gene name or `obs` annotation defining the node colors.
    Also plots the degree of the abstracted graph when
    passing {`'degree_dashed'`, `'degree_solid'`}.
    <br/>
    Can be also used to visualize pie chart at each node in the following form:
    `{<group name or index>: {<color>: <fraction>, ...}, ...}`. If the fractions
    do not sum to 1, a new category called `'rest'` colored grey will be created.

  **labels** 
  : The node labels. If `None`, this defaults to the group labels stored in
    the categorical for which `paga()` has been computed.

  **pos** 
  : Two-column array-like storing the x and y coordinates for drawing.
    Otherwise, path to a `.gdf` file that has been exported from Gephi or
    a similar graph visualization software.

  **layout** 
  : Plotting layout that computes positions.
    `'fa'` stands for “ForceAtlas2”,
    `'fr'` stands for “Fruchterman-Reingold”,
    `'rt'` stands for “Reingold-Tilford”,
    `'eq_tree'` stands for “eqally spaced tree”.
    All but `'fa'` and `'eq_tree'` are igraph layouts.
    All other igraph layouts are also permitted.
    See also parameter `pos` and `draw_graph()`.

  **layout_kwds** 
  : Keywords for the layout.

  **init_pos** 
  : Two-column array storing the x and y coordinates for initializing the
    layout.

  **random_state** 
  : For layouts with random initialization like `'fr'`, change this to use
    different intial states for the optimization. If `None`, the initial
    state is not reproducible.

  **root** 
  : If choosing a tree layout, this is the index of the root node or a list
    of root node indices. If this is a non-empty vector then the supplied
    node IDs are used as the roots of the trees (or a single tree if the
    graph is connected). If this is `None` or an empty list, the root
    vertices are automatically calculated based on topological sorting.

  **transitions** 
  : Key for `.uns['paga']` that specifies the matrix that stores the
    arrows, for instance `'transitions_confidence'`.

  **solid_edges** 
  : Key for `.uns['paga']` that specifies the matrix that stores the edges
    to be drawn solid black.

  **dashed_edges** 
  : Key for `.uns['paga']` that specifies the matrix that stores the edges
    to be drawn dashed grey. If `None`, no dashed edges are drawn.

  **single_component** 
  : Restrict to largest connected component.

  **fontsize** 
  : Font size for node labels.

  **fontoutline** 
  : Width of the white outline around fonts.

  **text_kwds** 
  : Keywords for [`text()`](https://matplotlib.org/stable/api/_as_gen/matplotlib.axes.Axes.text.html#matplotlib.axes.Axes.text).

  **node_size_scale** 
  : Increase or decrease the size of the nodes.

  **node_size_power** 
  : The power with which groups sizes influence the radius of the nodes.

  **edge_width_scale** 
  : Edge with scale in units of `rcParams['lines.linewidth']`.

  **min_edge_width** 
  : Min width of solid edges.

  **max_edge_width** 
  : Max width of solid and dashed edges.

  **arrowsize** 
  : For directed graphs, choose the size of the arrow head head’s length and
    width. See :py:class: `matplotlib.patches.FancyArrowPatch` for attribute
    `mutation_scale` for more info.

  **export_to_gexf** 
  : Export to gexf format to be read by graph visualization programs such as
    Gephi.

  **normalize_to_color** 
  : Whether to normalize categorical plots to `color` or the underlying
    grouping.

  **cmap** 
  : The color map.

  **cax** 
  : A matplotlib axes object for a potential colorbar.

  **cb_kwds** 
  : Keyword arguments for [`Colorbar`](https://matplotlib.org/stable/api/colorbar_api.html#matplotlib.colorbar.Colorbar),
    for instance, `ticks`.

  **add_pos** 
  : Add the positions to `adata.uns['paga']`.

  **title** 
  : Provide a title.

  **frameon** 
  : Draw a frame around the PAGA graph.

  **plot** 
  : If `False`, do not create the figure, simply compute the layout.

  **save** 
  : If `True` or a `str`, save the figure.
    A string is appended to the default filename.
    Infer the filetype if ending on {`'.pdf'`, `'.png'`, `'.svg'`}.

  **ax** 
  : A matplotlib axes object.
* **Return type:**
  [`Axes`](https://matplotlib.org/stable/api/_as_gen/matplotlib.axes.Axes.html#matplotlib.axes.Axes) | [`list`](https://docs.python.org/3/library/stdtypes.html#list)[[`Axes`](https://matplotlib.org/stable/api/_as_gen/matplotlib.axes.Axes.html#matplotlib.axes.Axes)] | [`None`](https://docs.python.org/3/library/constants.html#None)
* **Returns:**
  If `show==False`, one or more [`Axes`](https://matplotlib.org/stable/api/_as_gen/matplotlib.axes.Axes.html#matplotlib.axes.Axes) objects.
  Adds `'pos'` to `adata.uns['paga']` if `add_pos` is `True`.

### Examples

```python
import scanpy as sc
adata = sc.datasets.pbmc3k_processed()
sc.tl.paga(adata, groups='louvain')
sc.pl.paga(adata)
```

You can increase node and edge sizes by specifying additional arguments.

```python
sc.pl.paga(adata, node_size_scale=10, edge_width_scale=2)
```

### Notes

When initializing the positions, note that – for some reason – igraph
mirrors coordinates along the x axis… that is, you should increase the
`maxiter` parameter by 1 if the layout is flipped.

#### SEE ALSO
`tl.paga`, `pl.paga_compare`, `pl.paga_path`

