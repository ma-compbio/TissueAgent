---
name: tissue_niche_annotation
status: enabled
description: Annotate anatomical tissue regions using expression, supplied cell types, and spatial context within a requested label vocabulary.
---

## Inputs

- Spatial AnnData with expression, cell-type labels, and coordinates.
- Public biological context, allowed region labels, and the desired annotated output.
- Optional explicit cell-type, spatial, and output annotation keys.

## Outputs

- A readable annotated H5AD at the requested destination, preserving every cell and supplied cell type.
- Saved niche evidence, model prompts/responses, and selected parameters alongside the result.

## Step sketch

Inspect and resolve inputs → choose and execute spatial niche discovery and annotation → validate
and save the requested result. Bundle these actions in one annotation step with the
`tissue-niche-annotation` skill and `cell_annotator_agent` when its native workflow fits.
When distinguishing related anatomical labels requires a local spatial review, include a
`coding_agent` review step followed by annotation of the reviewed regions when needed.

## Details

- Keep the original label list and public context through delegation. Do not acquire reference
  datasets or reinterpret a niche task as cell-type annotation.
- The specialist can inspect fields and candidate radii, run UTAG and internal labeling, or label
  an existing clustering. Leave neighborhood scale, resolution, and summary breadth to its judgment
  from measured evidence. Do not add separate configuration-writing or inspection-only steps.
- The specialist previews a candidate clustering before labeling it, and may inspect one justified
  alternative. This remains within the bundled annotation step. It labels only the chosen candidate
  using the existing-cluster path; no model labels are needed to choose clustering parameters.
- Correct field and path arguments using the inspector's returned evidence before changing method.
- Plan a coding-agent review when the task or previous evidence indicates competing regional
  interpretations that pooled cluster summaries cannot resolve. Assign `tissue-niche-annotation`
  to both the coding and annotation steps. If this need emerges during execution, preserve the
  existing outputs and carry the specialist's handoff into replanning.
- The coding agent uses its existing Python tool to examine spatial subregions and returns a
  retain/refine/unresolved decision with measured evidence. Only a supported refinement requires
  a derived H5AD with all cells and an explicit region key. Carry its actual path, keys, radius,
  vocabulary and final destination into the next annotation step. When no refinement is needed,
  retain the existing result; do not force another clustering or labeling pass.
- Let the annotation specialist label refined regions with `utag_apply_clustering=False`.
  The review may span original cluster boundaries; the original grouping is not an anatomical
  constraint. Require executed analysis, not example code or a claim that a review took place.
- Mixed cell types or disconnected fragments alone do not require subdivision. Refine only when
  local evidence supports different anatomical contexts. Retain initial labels and document the
  reason for at most one refinement. Neither truth nor benchmark scores are analysis inputs.
- Report the validated annotation once available. The normal reporter handles the final response;
  an additional overview, reference search, or plotting step is not required by this task.
