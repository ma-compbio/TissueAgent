---
id: squidpy.pl.spatial_scatter
aliases: []
tags: []
---

# squidpy.pl.spatial_scatter

### squidpy.pl.spatial_scatter(adata, shape=None, color=None, groups=None, library_id=None, library_key=None, spatial_key='spatial', img=True, img_res_key='hires', img_alpha=None, img_cmap=None, img_channel=None, use_raw=None, layer=None, alt_var=None, size=None, size_key='spot_diameter_fullres', scale_factor=None, crop_coord=None, cmap=None, palette=None, alpha=1.0, norm=None, na_color=(0, 0, 0, 0), connectivity_key=None, edges_width=1.0, edges_color='grey', library_first=True, frameon=None, wspace=None, hspace=0.25, ncols=4, outline=False, outline_color=('black', 'white'), outline_width=(0.3, 0.05), legend_loc='right margin', legend_fontsize=None, legend_fontweight='bold', legend_fontoutline=None, legend_na=True, colorbar=True, scalebar_dx=None, scalebar_units=None, title=None, axis_label=None, fig=None, ax=None, return_ax=False, figsize=None, dpi=None, save=None, scalebar_kwargs=mappingproxy({}), edges_kwargs=mappingproxy({}), \*\*kwargs)

Plot spatial omics data with data overlayed on top.

The plotted shapes (circles, squares or hexagons) have a real “size” with respect to their
coordinate space, which can be specified via the `size` or `size_key` argument.

> - Use `img_key` to display the image in the background.
> - Use `library_id` to select the image. By default, `'hires'` is attempted.
> - Use `img_alpha`, `img_cmap` and `img_channel` to control how it is displayed.
> - Use `size` to scale the size of the shapes plotted on top.

If no image is plotted, it defaults to a scatter plot, see [`matplotlib.axes.Axes.scatter()`](https://matplotlib.org/stable/api/_as_gen/matplotlib.axes.Axes.scatter.html#matplotlib.axes.Axes.scatter).

Use `library_id` to select the image. If multiple `library_id` are available, use `library_key` in
[`anndata.AnnData.obs`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obs.html#anndata.AnnData.obs) to plot the subsets.
Use `crop_coord` to crop the spatial plot based on coordinate boundaries.

This function has few key assumptions about how coordinates and libraries are handled:

> - If spatial shapes are not available (e.g. in adata[`spatial`], pass `shape=None`)
> - The arguments `library_key` and `library_id` control which dataset is plotted.
>   If multiple libraries are present, specifying solely `library_key` will suffice, and all unique libraries
>   will be plotted sequentially. To select specific libraries, use the `library_id` argument.
> - The argument `color` controls which features in obs/var are plotted. They are plotted for all
>   available/specified libraries. The argument `groups` can be used to select categories to be plotted.
>   This is valid only for categorical features in [`anndata.AnnData.obs`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obs.html#anndata.AnnData.obs).
> - If multiple `library_id` are available, arguments such as `size` and `crop_coord` accept lists to
>   selectively customize different `library_id` plots. This requires that the length of such lists matches
>   the number of unique libraries in the dataset.
> - Coordinates are in the pixel space of the source image, so an equal aspect ratio is assumed.
> - The origin  *(0, 0)* is on the top left, as is common convention with image data.
> - The plotted points (dots) do not have a real “size” but it is relative to their coordinate/pixel space.
>   This does not hold if no image is plotted, then the size corresponds to points size passed to
>   [`matplotlib.axes.Axes.scatter()`](https://matplotlib.org/stable/api/_as_gen/matplotlib.axes.Axes.scatter.html#matplotlib.axes.Axes.scatter).

If [`anndata.AnnData.uns`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.uns.html#anndata.AnnData.uns) `['spatial']` is present, use `img_key`, `seg_key` and
`size_key` arguments to find values for `img`, `seg` and `size`.
Alternatively, these values can be passed directly via `img`.

#### SEE ALSO
- [`squidpy.pl.spatial_segment()`](squidpy.pl.spatial_segment.md#squidpy.pl.spatial_segment) on how to plot spatial data with segmentation masks on top.

* **Parameters:**
  * **adata** ([`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData)) – Annotated data object.
  * **shape** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`Literal`](https://docs.python.org/3/library/typing.html#typing.Literal)[`'circle'`, `'square'`, `'hex'`]]) – Whether to plot scatter plot of points or regular polygons.
  * **color** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`Sequence`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Sequence)[[`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`None`](https://docs.python.org/3/library/constants.html#None)] | [`None`](https://docs.python.org/3/library/constants.html#None)) – Key for annotations in [`anndata.AnnData.obs`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obs.html#anndata.AnnData.obs) or variables/genes.
  * **groups** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`Sequence`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Sequence)[[`str`](https://docs.python.org/3/library/stdtypes.html#str)] | [`None`](https://docs.python.org/3/library/constants.html#None)) – For discrete annotation in `color`, select which values to plot (other values are set to NAs).
  * **library_id** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`Sequence`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Sequence)[[`str`](https://docs.python.org/3/library/stdtypes.html#str)] | [`None`](https://docs.python.org/3/library/constants.html#None)) – Name of the Z-dimension(s) that this function should be applied to.
    For not specified Z-dimensions, the identity function is applied.
  * **library_key** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`None`](https://docs.python.org/3/library/constants.html#None)) – If multiple library_id, column in [`anndata.AnnData.obs`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obs.html#anndata.AnnData.obs)
    which stores mapping between `library_id` and obs.
  * **spatial_key** ([`str`](https://docs.python.org/3/library/stdtypes.html#str)) – Key in [`anndata.AnnData.obsm`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obsm.html#anndata.AnnData.obsm) where spatial coordinates are stored.
  * **img** ([`bool`](https://docs.python.org/3/library/functions.html#bool) | [`ndarray`](https://numpy.org/doc/stable/reference/generated/numpy.ndarray.html#numpy.ndarray)[[`tuple`](https://docs.python.org/3/library/stdtypes.html#tuple)[[`int`](https://docs.python.org/3/library/functions.html#int), [`...`](https://docs.python.org/3/library/constants.html#Ellipsis)], [`dtype`](https://numpy.org/doc/stable/reference/generated/numpy.dtype.html#numpy.dtype)[[`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]] | [`Sequence`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Sequence)[[`ndarray`](https://numpy.org/doc/stable/reference/generated/numpy.ndarray.html#numpy.ndarray)[[`tuple`](https://docs.python.org/3/library/stdtypes.html#tuple)[[`int`](https://docs.python.org/3/library/functions.html#int), [`...`](https://docs.python.org/3/library/constants.html#Ellipsis)], [`dtype`](https://numpy.org/doc/stable/reference/generated/numpy.dtype.html#numpy.dtype)[[`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]]] | [`None`](https://docs.python.org/3/library/constants.html#None)) – Whether to plot the image. One (or more) [`numpy.ndarray`](https://numpy.org/doc/stable/reference/generated/numpy.ndarray.html#numpy.ndarray) can also be
    passed for plotting.
  * **img_res_key** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Key for image resolution, used to get `img` and `scale_factor` from `'images'`
    and `'scalefactors'` entries for this library.
  * **img_alpha** ([`float`](https://docs.python.org/3/library/functions.html#float) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Alpha value for the underlying image.
  * **image_cmap** – Colormap for the image, see [`matplotlib.colors.Colormap`](https://matplotlib.org/stable/api/_as_gen/matplotlib.colors.Colormap.html#matplotlib.colors.Colormap).
  * **img_channel** ([`int`](https://docs.python.org/3/library/functions.html#int) | [`list`](https://docs.python.org/3/library/stdtypes.html#list)[[`int`](https://docs.python.org/3/library/functions.html#int)] | [`None`](https://docs.python.org/3/library/constants.html#None)) – To select which channel to plot (all by default).
  * **use_raw** ([`bool`](https://docs.python.org/3/library/functions.html#bool) | [`None`](https://docs.python.org/3/library/constants.html#None)) – If True, use [`anndata.AnnData.raw`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.raw.html#anndata.AnnData.raw).
  * **layer** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Key in [`anndata.AnnData.layers`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.layers.html#anndata.AnnData.layers) or None for [`anndata.AnnData.X`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.X.html#anndata.AnnData.X).
  * **alt_var** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Which column to use in [`anndata.AnnData.var`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.var.html#anndata.AnnData.var) to select alternative `var_name`.
  * **size** ([`float`](https://docs.python.org/3/library/functions.html#float) | [`Sequence`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Sequence)[[`float`](https://docs.python.org/3/library/functions.html#float)] | [`None`](https://docs.python.org/3/library/constants.html#None)) – Size of the scatter point/shape. In case of `spatial_shape` it represents to the
    scaling factor for shape (accessed via `size_key`). In case of `spatial_point`,
    it represents the `size` argument in [`matplotlib.pyplot.scatter()`](https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.scatter.html#matplotlib.pyplot.scatter).
  * **size_key** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Key of of pixel size of shapes to be plotted, stored in [`anndata.AnnData.uns`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.uns.html#anndata.AnnData.uns).
    Only needed for `spatial_shape`.
  * **scale_factor** ([`float`](https://docs.python.org/3/library/functions.html#float) | [`Sequence`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Sequence)[[`float`](https://docs.python.org/3/library/functions.html#float)] | [`None`](https://docs.python.org/3/library/constants.html#None)) – Scaling factor used to map from coordinate space to pixel space.
    Found by default if `library_id` and `img_key` can be resolved.
    Otherwise, defaults to 1.
  * **crop_coord** ([`tuple`](https://docs.python.org/3/library/stdtypes.html#tuple)[[`int`](https://docs.python.org/3/library/functions.html#int), [`int`](https://docs.python.org/3/library/functions.html#int), [`int`](https://docs.python.org/3/library/functions.html#int), [`int`](https://docs.python.org/3/library/functions.html#int)] | [`Sequence`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Sequence)[[`tuple`](https://docs.python.org/3/library/stdtypes.html#tuple)[[`int`](https://docs.python.org/3/library/functions.html#int), [`int`](https://docs.python.org/3/library/functions.html#int), [`int`](https://docs.python.org/3/library/functions.html#int), [`int`](https://docs.python.org/3/library/functions.html#int)]] | [`None`](https://docs.python.org/3/library/constants.html#None)) – Coordinates to use for cropping the image (left, right, top, bottom).
    These coordinates are expected to be in pixel space (same as `spatial`)
    and will be transformed by `scale_factor`.
    If not provided, image is automatically cropped to bounds of `spatial`,
    plus a border.
  * **cmap** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`Colormap`](https://matplotlib.org/stable/api/_as_gen/matplotlib.colors.Colormap.html#matplotlib.colors.Colormap) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Colormap for continuous annotations, see [`matplotlib.colors.Colormap`](https://matplotlib.org/stable/api/_as_gen/matplotlib.colors.Colormap.html#matplotlib.colors.Colormap).
  * **palette** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`ListedColormap`](https://matplotlib.org/stable/api/_as_gen/matplotlib.colors.ListedColormap.html#matplotlib.colors.ListedColormap) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Palette for discrete annotations, see [`matplotlib.colors.Colormap`](https://matplotlib.org/stable/api/_as_gen/matplotlib.colors.Colormap.html#matplotlib.colors.Colormap).
  * **alpha** ([`float`](https://docs.python.org/3/library/functions.html#float)) – Alpha value for scatter point/shape.
  * **norm** ([`Normalize`](https://matplotlib.org/stable/api/_as_gen/matplotlib.colors.Normalize.html#matplotlib.colors.Normalize) | [`Sequence`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Sequence)[[`Normalize`](https://matplotlib.org/stable/api/_as_gen/matplotlib.colors.Normalize.html#matplotlib.colors.Normalize)] | [`None`](https://docs.python.org/3/library/constants.html#None)) – Colormap normalization for continuous annotations, see [`matplotlib.colors.Normalize`](https://matplotlib.org/stable/api/_as_gen/matplotlib.colors.Normalize.html#matplotlib.colors.Normalize).
  * **na_color** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`tuple`](https://docs.python.org/3/library/stdtypes.html#tuple)[[`float`](https://docs.python.org/3/library/functions.html#float), [`...`](https://docs.python.org/3/library/constants.html#Ellipsis)]) – Color to be used for NAs values, if present.
  * **connectivity_key** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Key for neighbors graph to plot. Default is: [`anndata.AnnData.obsp`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.obsp.html#anndata.AnnData.obsp) `['spatial_connectivities']`.
  * **edges_width** ([`float`](https://docs.python.org/3/library/functions.html#float)) – Width of the edges. Only used when `connectivity_key != None` .
  * **edges_color** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`Sequence`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Sequence)[[`str`](https://docs.python.org/3/library/stdtypes.html#str)] | [`Sequence`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Sequence)[[`float`](https://docs.python.org/3/library/functions.html#float)]) – Color of the edges.
  * **library_first** ([`bool`](https://docs.python.org/3/library/functions.html#bool)) – If multiple libraries are plotted, set the plotting order with respect to `color`.
  * **frameon** ([`bool`](https://docs.python.org/3/library/functions.html#bool) | [`None`](https://docs.python.org/3/library/constants.html#None)) – If True, draw a frame around the panels.
  * **wspace** ([`float`](https://docs.python.org/3/library/functions.html#float) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Width space between panels.
  * **hspace** ([`float`](https://docs.python.org/3/library/functions.html#float)) – Height space between panels.
  * **ncols** ([`int`](https://docs.python.org/3/library/functions.html#int)) – Number of panels per row.
  * **outline** ([`bool`](https://docs.python.org/3/library/functions.html#bool)) – If True, a thin border around points/shapes is plotted.
  * **outline_color** ([`tuple`](https://docs.python.org/3/library/stdtypes.html#tuple)[[`str`](https://docs.python.org/3/library/stdtypes.html#str), [`str`](https://docs.python.org/3/library/stdtypes.html#str)]) – Color of the border.
  * **outline_width** ([`tuple`](https://docs.python.org/3/library/stdtypes.html#tuple)[[`float`](https://docs.python.org/3/library/functions.html#float), [`float`](https://docs.python.org/3/library/functions.html#float)]) – Width of the border.
  * **legend_loc** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Location of the legend, see [`matplotlib.legend.Legend`](https://matplotlib.org/stable/api/legend_api.html#matplotlib.legend.Legend).
  * **legend_fontsize** ([`Union`](https://docs.python.org/3/library/typing.html#typing.Union)[[`int`](https://docs.python.org/3/library/functions.html#int), [`float`](https://docs.python.org/3/library/functions.html#float), [`Literal`](https://docs.python.org/3/library/typing.html#typing.Literal)[`'xx-small'`, `'x-small'`, `'small'`, `'medium'`, `'large'`, `'x-large'`, `'xx-large'`], [`None`](https://docs.python.org/3/library/constants.html#None)]) – Font size of the legend, see [`matplotlib.text.Text.set_fontsize()`](https://matplotlib.org/stable/api/text_api.html#matplotlib.text.Text.set_fontsize).
  * **legend_fontweight** ([`Union`](https://docs.python.org/3/library/typing.html#typing.Union)[[`int`](https://docs.python.org/3/library/functions.html#int), [`Literal`](https://docs.python.org/3/library/typing.html#typing.Literal)[`'light'`, `'normal'`, `'medium'`, `'semibold'`, `'bold'`, `'heavy'`, `'black'`]]) – Font weight of the legend, see [`matplotlib.text.Text.set_fontweight()`](https://matplotlib.org/stable/api/text_api.html#matplotlib.text.Text.set_fontweight).
  * **legend_fontoutline** ([`int`](https://docs.python.org/3/library/functions.html#int) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Font outline of the legend, see [`matplotlib.patheffects.withStroke`](https://matplotlib.org/stable/api/patheffects_api.html#matplotlib.patheffects.withStroke).
  * **legend_na** ([`bool`](https://docs.python.org/3/library/functions.html#bool)) – Whether to show NA values in the legend.
  * **colorbar** ([`bool`](https://docs.python.org/3/library/functions.html#bool)) – Whether to show the colorbar, see [`matplotlib.pyplot.colorbar()`](https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.colorbar.html#matplotlib.pyplot.colorbar).
  * **scalebar_dx** ([`float`](https://docs.python.org/3/library/functions.html#float) | [`Sequence`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Sequence)[[`float`](https://docs.python.org/3/library/functions.html#float)] | [`None`](https://docs.python.org/3/library/constants.html#None)) – Size of one pixel in units specified by `scalebar_units`.
  * **scalebar_units** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`Sequence`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Sequence)[[`str`](https://docs.python.org/3/library/stdtypes.html#str)] | [`None`](https://docs.python.org/3/library/constants.html#None)) – Units of `scalebar_dx`.
  * **title** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`Sequence`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Sequence)[[`str`](https://docs.python.org/3/library/stdtypes.html#str)] | [`None`](https://docs.python.org/3/library/constants.html#None)) – Panel titles.
  * **axis_label** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`Sequence`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Sequence)[[`str`](https://docs.python.org/3/library/stdtypes.html#str)] | [`None`](https://docs.python.org/3/library/constants.html#None)) – Panel axis labels.
  * **fig** ([`Figure`](https://matplotlib.org/stable/api/_as_gen/matplotlib.figure.Figure.html#matplotlib.figure.Figure) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Optional [`matplotlib.figure.Figure`](https://matplotlib.org/stable/api/_as_gen/matplotlib.figure.Figure.html#matplotlib.figure.Figure) to use.
  * **ax** ([`Axes`](https://matplotlib.org/stable/api/_as_gen/matplotlib.axes.Axes.html#matplotlib.axes.Axes) | [`Sequence`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Sequence)[[`Axes`](https://matplotlib.org/stable/api/_as_gen/matplotlib.axes.Axes.html#matplotlib.axes.Axes)] | [`None`](https://docs.python.org/3/library/constants.html#None)) – Optional [`matplotlib.axes.Axes`](https://matplotlib.org/stable/api/_as_gen/matplotlib.axes.Axes.html#matplotlib.axes.Axes) to use.
  * **return_ax** ([`bool`](https://docs.python.org/3/library/functions.html#bool)) – Whether to return [`matplotlib.axes.Axes`](https://matplotlib.org/stable/api/_as_gen/matplotlib.axes.Axes.html#matplotlib.axes.Axes) object(s).
  * **figsize** ([`tuple`](https://docs.python.org/3/library/stdtypes.html#tuple)[[`float`](https://docs.python.org/3/library/functions.html#float), [`float`](https://docs.python.org/3/library/functions.html#float)] | [`None`](https://docs.python.org/3/library/constants.html#None)) – Size of the figure in inches.
  * **dpi** ([`int`](https://docs.python.org/3/library/functions.html#int) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Dots per inch.
  * **save** ([`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`Path`](https://docs.python.org/3/library/pathlib.html#pathlib.Path) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Whether to save the plot.
  * **scalebar_kwargs** ([`Mapping`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping)[[`str`](https://docs.python.org/3/library/stdtypes.html#str), [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]) – Keyword arguments for `matplotlib_scalebar.ScaleBar()`.
  * **edges_kwargs** ([`Mapping`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping)[[`str`](https://docs.python.org/3/library/stdtypes.html#str), [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)]) – Keyword arguments for `networkx.draw_networkx_edges()`.
  * **kwargs** ([`Any`](https://docs.python.org/3/library/typing.html#typing.Any)) – Keyword arguments for [`matplotlib.pyplot.scatter()`](https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.scatter.html#matplotlib.pyplot.scatter) or [`matplotlib.pyplot.imshow()`](https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.imshow.html#matplotlib.pyplot.imshow).
* **Return type:**
  [`Axes`](https://matplotlib.org/stable/api/_as_gen/matplotlib.axes.Axes.html#matplotlib.axes.Axes) | [`Sequence`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Sequence)[[`Axes`](https://matplotlib.org/stable/api/_as_gen/matplotlib.axes.Axes.html#matplotlib.axes.Axes)] | [`None`](https://docs.python.org/3/library/constants.html#None)
* **Returns:**
  :
  Nothing, just plots the figure and optionally saves the plot.
