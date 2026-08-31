# Plot-family decisions

Read only the section matching the target. In every family, derive order, labels,
colors, ranges, and layout from the target specification rather than library
defaults.

## Scatter, embedding, and spatial maps

Confirm two coordinate fields and the encoded value. Use equal aspect for physical
coordinates unless measurement disproves it. Test image-convention y inversion,
axis swapping, and mirroring against a distinctive feature. Match marker area,
alpha, edges, density, and z-order. Preserve histology or image underlays and their
registration. A coordinate-only panel must not gain an invented underlay.

## Heatmaps and dot plots

Confirm the exact matrix, row and column order, transformations, clustering, and
dendrogram presence. For dot plots, color and size are separate encodings: reproduce
both scales and both legends. Match continuous color limits and direction.

## Bar, line, box, and violin plots

Confirm the displayed subset, categorical order, aggregation, interval definition,
and whether raw observations are overlaid. Match baselines, error bars, line and
marker styles, tick text, units, and clipping. Never recompute an undocumented
summary merely because it resembles the target.

## Multipanel figures

Treat each panel as an independently measured plot and the page as a layout. Record
panel boxes and shared legends before rendering. Preserve shared axes, panel letters,
alignment, whitespace, and reading order. Compare the assembled figure as well as
any panel whose error is hidden by the full-page scale.

## Continuous encoding

Measure the colorbar endpoints, ticks, label, normalization, and direction. Use the
actual colormap samples when a named map is ambiguous or unavailable. Record value
limits in the plotted-data artifact or specification.
