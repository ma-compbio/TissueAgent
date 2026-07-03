---
name: spatial_deconvolution
status: enabled
description: >
  Estimate per-spot cell type composition on spot-based spatial data
  (10x Visium, Slide-seq, ST) by mapping a scRNA-seq reference with
  cell2location. If no reference is supplied, first retrieve a matched one
  from CELLxGENE. Produces per-spot cell type abundance tables and an
  annotated AnnData.
---

## Inputs
- Spatial AnnData (.h5ad) with raw integer counts (Visium / spot-based)
- Optional: reference scRNA-seq AnnData (.h5ad) with raw counts and a cell type column in .obs

## Outputs
- q05_cell_abundance_w_sf.csv (5% quantile abundance per spot × cell type)
- means_cell_abundance_w_sf.csv (posterior mean abundance per spot × cell type)
- visium_with_cell2location.h5ad (spatial AnnData with abundances in .obsm)

## Step Sketch
(If no reference) find + download a matched CELLxGENE reference → cell2location deconvolution to estimate per-spot cell type abundances (2–3 steps total)

## Details
- Apply the `cell-type-deconvolution` skill.
- **Reference step (only if no reference is provided), agent `single_cell_agent`:**
  - `query_cellxgene_census_live_tool` — filter CELLxGENE Census to match the spatial sample (species, tissue), `include_cell_type_counts=True`; pick the best match.
  - `retrieve_cellxgene_single_cell_tool` — download the chosen `dataset_id` to `outputs/datasets/<filename>`.
- **Deconvolution step, agent `spot_agent` (or `single_cell_agent`):** `cell2location_visium_deconvolution_tool` with `visium_h5ad_path` and `reference_h5ad_path`.
  - Requires **raw integer counts** in both objects (the tool auto-falls back to `.raw`).
  - **Set `cell_type_column` explicitly** — defaults to `leiden`. For a CELLxGENE reference use `cell_type_column="cell_type"`.
  - Tune `n_cells_per_location` to the tissue; raise `regression_max_epochs`/`spatial_max_epochs` for production-quality fits.
- Use this plan for **spot-based** platforms. For single-cell-resolution data (MERFISH/Xenium/CosMx/seqFISH) use `cell_annotation` instead.

## Evaluation Criteria
- file_exists(q05_cell_abundance_w_sf.csv)
- file_exists(visium_with_cell2location.h5ad)
