---
name: cell-type-annotation
description: Assign one cell-type label per observation by runtime-inspected Harmony transfer from a labeled single-cell reference. Supports validated H5AD queries and queries converted first by Data Onboarding.
applies_to: [cell_annotator_agent, single_cell_agent, data_onboarding_agent, coding_agent]
status: enable
---

# Cell Type Annotation

## When to use

Use this workflow for single-cell-resolution spatial data when the user wants one transferred cell
type per observation. Spot-level mixtures require deconvolution instead.

## Inputs and paths

- Query and reference inputs resolve only from `project/uploads/`, `project/outputs/`,
  `library/datasets/`, or `library/files/`.
- H5AD queries can proceed directly. CSV directories, Seurat objects, and other formats must first
  be inspected, converted, and validated by Data Onboarding. For a format that its deterministic
  converter does not support, use the Coding Agent to create and run the conversion, then apply the
  same Data Onboarding validation to its H5AD.
- Relative outputs are written beneath `project/outputs/`; write annotated objects and their run
  metadata beneath `project/outputs/cell_annotation/` using input-derived, non-colliding names.
- A labeled reference is required. Reuse a supplied or existing compatible reference; retrieve one
  from CELLxGENE when no suitable local reference exists.

## Required workflow

1. For non-H5AD query inputs, start with `inspect_spatial_data_tool`. For a supported format, use
   `convert_spatial_data_tool` and `validate_spatial_data_tool`. If the converter does not support
   the detected format, use the Coding Agent for conversion and validate its result with
   `validate_spatial_data_tool`.
2. Call `inspect_anndata_preprocessing_tool` once with the exact validated query and reference. It
   classifies bounded matrix samples as raw-count-like or processed-continuous and returns
   `recommended_skip_preprocessing` only for a safe, compatible pair.
3. If inspection succeeds, call `harmony_transfer_tool` once and pass its exact boolean as
   `skip_preprocessing`. Choose an explicit `min_shared_genes` appropriate for the assay and gene
   panel. Stop visibly on ambiguous, invalid, or mixed preprocessing states.
4. Set `gene_mapping_species` from known organism metadata (for example `human` or `mouse`) and use
   the namespace that matches the inputs. Mapping is symmetric across query and reference.
5. Keep `preserve_all_spatial_obs=True`. The output must preserve the original observation count
   and order. Cells removed from the working transfer subset remain in the saved object with null
   predictions and explicit transfer status/reason fields.

## Output contract

The annotated H5AD contains:

- `harmony_predicted_cell_type`
- `harmony_prediction_confidence`
- `label`
- `harmony_transfer_status`
- `harmony_exclusion_reason`

The tool result and adjacent run metadata report input/output counts, transferred/excluded counts,
cell-type counts, mean confidence, shared genes, preprocessing decision, species-aware mapping,
the selected minimum shared-gene requirement, Harmony convergence warnings, and canonical
workspace-relative paths.

## Failure conditions

- Fewer shared genes than the explicit dataset-appropriate `min_shared_genes` decision
- Missing or null reference labels
- Missing or duplicate identifiers
- Ambiguous, invalid, or incompatible preprocessing states
- Output paths outside `project/outputs/`

Do not guess, silently drop observations, or rerun Harmony with alternate preprocessing. Report the
failed stage and tool evidence.
