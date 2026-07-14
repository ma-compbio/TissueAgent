---
name: cell_annotation
status: enabled
description: >
  Annotate cell types per cell in a single-cell-resolution spatial dataset
  (MERFISH, Xenium, CosMx, seqFISH) by transferring labels from a matched
  single-cell reference via Harmony integration. If no reference is supplied,
  first retrieve a matched one from CELLxGENE. Produces an annotated AnnData
  with predicted cell types in .obs.
---

## Inputs
- Spatial AnnData (.h5ad) file path (single-cell resolution)
- Optional: reference scRNA-seq AnnData (.h5ad) with a cell type column in .obs

## Outputs
- Annotated spatial AnnData (.h5ad) with `harmony_predicted_cell_type`, `harmony_prediction_confidence`, and `label` in .obs

## Step Sketch
(If no reference) find + download a matched CELLxGENE reference → transfer cell type labels onto the spatial cells with Harmony (2–3 steps total)

## Details
- Apply the `cell-type-annotation` skill.
- **Reference step (only if no reference is provided), agent `single_cell_agent`:**
  - `query_cellxgene_census_live_tool` — filter CELLxGENE Census to match the spatial sample (species, tissue). Set `include_cell_type_counts=True` to confirm expected cell types; pick the best match by tissue/species/`n_cells`.
  - `retrieve_cellxgene_single_cell_tool` — download the chosen `dataset_id` to `outputs/datasets/<filename>`.
- **Annotation step, agent `cell_annotator_agent`:** `harmony_transfer_tool` with `spatial_anndata_path` and `reference_anndata_path`. A CELLxGENE reference stores labels in the `cell_type` column — the tool's default `cell_type_column`, so no override needed; otherwise set it to the reference's real label column.
- Use this plan for **single-cell-resolution** platforms. For spot-based data (Visium/Slide-seq/ST) use `spatial_deconvolution` instead.

## Evaluation Criteria
- Annotated spatial AnnData written with a predicted cell type column in .obs
