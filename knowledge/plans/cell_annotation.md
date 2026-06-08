---
name: cell_annotation
status: enabled
description: >
  Annotate cell types in a spatial transcriptomics dataset using harmony
  integration with a matched single-cell reference atlas. Produces an updated
  AnnData file with a cell_type column in .obs.
---

## Inputs
- Spatial AnnData(.h5ad) file path

## Outputs
- Updated spatial AnnData(.h5ad) file with cell_type column in .obs

## Step Sketch
Find reference dataset → use harmony transfer to infer cell types in spatial dataset
