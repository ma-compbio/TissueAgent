---
name: cell_annotation
status: enabled
description: >
  Annotate cell types in a single-cell-resolution spatial transcriptomics dataset by
  onboarding it when needed, then transferring labels from a required matched
  single-cell reference through runtime-inspected Harmony integration.
---

## Inputs

- A spatial transcriptomics dataset, for example H5AD, one or more CSV files, or a Seurat object
- A required labeled single-cell reference AnnData; an existing matching reference should be reused

## Outputs

- An annotated `.h5ad` with an input-derived, non-colliding name in
  `project/outputs/cell_annotation/`
- Conversion/validation provenance when onboarding was required
- A corresponding `.run_meta.json` in `project/outputs/cell_annotation/`

## Step Sketch

Onboard the query if needed → reuse or retrieve the required reference → inspect both matrices
→ run Harmony transfer once with explicit inspection and shared-gene decisions

## Details

- Apply the `cell-type-annotation` skill.
- **Query routing:**
  - An existing H5AD proceeds to `cell_annotator_agent`.
  - CSV files, Seurat objects, and other non-H5AD sources first go to
    `data_onboarding_agent`: inspect → convert → validate. Pass the validated
    `project/outputs/...h5ad` onward.
  - If inspection finds a format that the deterministic converter does not support, use
    `coding_agent` to create and run a format-appropriate conversion, then send the resulting H5AD
    back to `data_onboarding_agent` for the same validation checks before annotation.
- **Reference routing:** every annotation run requires a labeled reference. Reuse a supplied or
  existing matching H5AD from project outputs or approved library directories. If none was supplied
  or found, use `single_cell_agent` to query CELLxGENE and retrieve one into
  `project/outputs/references/` before annotation.
- **Annotation step, agent `cell_annotator_agent`:** call
  `inspect_anndata_preprocessing_tool` exactly once on the exact query/reference pair. If it
  returns a successful boolean recommendation, pass that exact boolean to one
  `harmony_transfer_tool` call. Choose and pass an explicit `min_shared_genes` appropriate for the
  assay and panel; the decision and observed shared-gene count must appear in run metadata. Do not
  guess on ambiguous or mixed preprocessing states.
- Set species-aware gene mapping from known sample metadata. Preserve all original query
  observations; cells excluded during preprocessing must retain null predictions plus explicit
  `harmony_transfer_status` and `harmony_exclusion_reason` values.
- Use this plan for single-cell-resolution platforms. Route spot mixtures to
  `spatial_deconvolution`.
- Keep the execution plan minimal:
  - Do not add standalone query-inspection, query-QC, preprocessing-configuration, shared-gene,
    integrity-check, or report steps. Do not request intermediate tables/configs/preprocessed H5ADs
    from Cell Annotator or Data Onboarding. Their deterministic tool results, provenance JSON, final
    H5AD, and run metadata are the artifacts.
  - With an existing query H5AD and reference, create exactly one Cell Annotator step containing
    both preprocessing inspection and Harmony transfer.
  - With an existing query H5AD but no reference, create exactly two steps: one Single Cell Agent
    reference-retrieval step, then one bundled Cell Annotator step. Do not route the valid H5AD
    through Data Onboarding and do not copy/convert it before annotation.
  - With a supported non-H5AD query and existing reference, create exactly two steps: one Data
    Onboarding step (inspect, convert, validate), then one Cell Annotator step (inspect, Harmony).
  - For an unsupported format, insert a Coding Agent conversion step and a Data Onboarding
    validation step before Cell Annotation.
  - Add a separate reference-retrieval step when no compatible reference was supplied or found.
- Do not create separate configuration, matrix-summary, inspection-decision, integrity-check, or
  warning-report steps. The deterministic tool results, conversion provenance, Harmony run metadata,
  plan, and captured transcript are the audit record.

## Evaluation Criteria

- The final H5AD has the same observation count and order as the validated query.
- `.obs` contains `harmony_predicted_cell_type`, `harmony_prediction_confidence`, `label`,
  `harmony_transfer_status`, and `harmony_exclusion_reason`.
- The inspection decision, Harmony warnings, mapping metadata, and all artifact paths are visible,
  and every written artifact is beneath `project/outputs/`.
