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

Inspect and resolve inputs once → choose one clustering → checkpointed batch labeling →
screen all niches and review flagged spatial subregions → validate and save the requested result.
Use this as the default niche workflow. Bundle these actions in one annotation step with the
`tissue-niche-annotation` skill and `cell_annotator_agent` when its native workflow fits.
Use labeling batches of 8, review batches of 8, at most 48 flagged review groups, and
`use_anchor_evidence=False` unless the caller explicitly overrides these settings.

## Details

- Keep the original label list and public context through delegation. Do not acquire reference
  datasets or reinterpret a niche task as cell-type annotation.
- The specialist can inspect fields and candidate radii, run UTAG and internal labeling, or label
  an existing clustering. Leave neighborhood scale, resolution, and summary breadth to its judgment
  from measured evidence. Do not add separate configuration-writing or inspection-only steps.
- Use the native bounded review tool after saving primary labels, unless the request explicitly
  asks for primary-only annotation or the legacy baseline. It screens all niches, checkpoints
  small review batches and preserves unaffected labels. Record deferred groups and keep them
  unreviewed. Add optional soft anchor evidence only when explicitly requested. A separate
  coding-agent step is needed only for justified custom computations beyond this tool.
- The specialist previews a candidate clustering before labeling it, and may inspect one justified
  alternative. This remains within the bundled annotation step. It labels only the chosen candidate
  using the existing-cluster path; no model labels are needed to choose clustering parameters.
- Use native audit filenames under the chosen output directory: `niche_evidence.tsv`,
  `annotation_parameters.json`, `validation_summary.tsv`, and `run_meta.json`. Use returned
  artifact paths for downstream steps. An explicit candidate H5AD path is allowed before review;
  keep the user's final destination for final delivery. For missing files or older plan filenames,
  use the artifact-recovery tool to validate and export existing results without relabeling.
- Correct field and path arguments using the inspector's returned evidence before changing method.
- Plan a coding-agent review only when a justified custom computation goes beyond the native
  bounded review tool, replacing rather than adding another refinement pass. Assign `tissue-niche-annotation`
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
- Report annotation availability separately from review completion. A planned spatial review that
  was not dispatched remains unfinished even if a final-named prediction file already exists.
