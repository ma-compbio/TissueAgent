---
name: spatial_scatter
status: enabled
description: >
  Plot spatial coordinates from an AnnData object as a scatterplot, colored by
  cluster or cell type annotations. Exports both the figure and a CSV of the
  plotted coordinates for downstream use.
---

## Inputs
- AnnData(.h5ad) with .obsm['spatial'] or obs['x','y']

## Outputs
- spatial_scatterplot.png
- spatial_points.csv

## Step Sketch
Validate coords → choose color field → render scatter → export coords table

## Evaluation Criteria
- file_exists(spatial_scatterplot.png)
- n_points > 0
- n_nan == 0
- aspect ≈ 1

## Defaults
- coord_priority: ["obsm:spatial", "obs:x,y"]
- color_key_preference: ["cluster", "cell_type", "sample_id"]
- figure size: 2400x2400 px, point_size: 3, alpha: 0.7

## Checklist
- Locate coordinates (.obsm['spatial'] or obs['x','y'])
- Choose color field (cluster/cell_type/gene); record choice in meta.json
- Render scatter (equal aspect, axis off); save spatial_points.png + thumb
- Export spatial_points.csv with [x, y, <color_key>, sample_id?]
- Run sanity checks (n>0, no NaN, aspect~1); write viz_checks.json
