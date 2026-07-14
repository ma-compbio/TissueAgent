---
name: lr_analysis
status: enabled
description: >
  Perform steady-state ligand-receptor analysis on spatial transcriptomics data
  using LIANA+. Produces interaction dotplots and a results table summarizing
  significant ligand-receptor pairs across cell types.
---

## Inputs
- AnnData(.h5ad) with .obsm['spatial'] or obs['x','y']

## Outputs
- lr_dotplot.png
- lr_results.csv

## Step Sketch
Preprocess and clean spatial data → ligand-receptor analysis with LIANA+ and export results/dotplot (2 steps total)

## Details
- Use `li.mt.show_methods()` to show available ligand-receptor methods (e.g. CellPhoneDB, CellChat, etc.)
- Use `li.mt.rank_aggregate(adata, groupby='bulk_labels', resource_name='consensus', expr_prop=0.1, verbose=True)` to get a consensus of ligand-receptor interactions.
- Use "consensus" resource for human gene symbols (default) or "mouseconsensus" for mice.
- Plot using `li.pl.dotplot`

## Evaluation Criteria
- file_exists(lr_dotplot.png)
- file_exists(lr_results.csv)
