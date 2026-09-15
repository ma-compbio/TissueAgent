---
name: tissue-niche-annotation
description: Assign anatomical tissue regions from expression, supplied cell types, and spatial context; review competing regional interpretations and use coding-agent analysis when spatial subdivision is warranted.
applies_to: [cell_annotator_agent, coding_agent]
status: enable
---

# Tissue Niche Annotation

## Task and evidence

Use the original biological task, public dataset context, allowed labels, and requested output
from the bound task context when available, otherwise the original user request. Preserve the label vocabulary and its order across delegation and
annotation calls. Do not substitute a missing label list or treat an omitted list as a request
to label everything Unmatched.

Use supplied cell types as evidence for region annotation. Infer new cell types only if that is
part of the user's task. A cell type can occur in multiple anatomical regions; its identity
alone does not require those cells to receive the same region label.

Use only the permitted input and public context. Do not inspect held-out region annotations,
archived predictions, or benchmark scores when choosing parameters or labels. Any additional
public label definitions used in a comparison must be available to all compared methods.

## Discover the input

Inspect the supplied file without requiring the user to name internal AnnData fields. Obtain
candidate cell-type columns, coordinate arrays, matrix state, feature identifiers, and any
section grouping from the file. Resolve an unambiguous field choice from this evidence; retain
explicit caller choices when supplied. Pass resolved field names to subsequent operations.

Input discovery must not depend on a future clustering column. Distinguish existing cluster
keys from the naming convention of a cluster that a particular backend will create.

Correct an invalid field or path argument using the returned inventory or supported-value
information. A failed validation before computation is a configuration correction, not a
completed biological analysis. Do not repeat the same failed call without new information.
Stop for genuinely invalid or missing required data and report the concrete issue.

## Choose and execute an analysis

For the annotation specialist, keep input inspection, parameter selection, native niche
discovery, and labeling together when the native workflow fits the task. The native tool
already performs clustering and labeling; do not invoke it once merely to prepare clusters
and then invoke the whole workflow again merely to attach labels.

Use a coding agent for computations that require arbitrary Python, custom graph construction,
or transformations not exposed by the specialist's tools. Explain the scientific reason for
an alternative method. A correctable tool argument is not evidence that the spatial method
is scientifically unsuitable. Execute the analysis and write its outputs; example code alone
does not complete a requested computation.

When usable clusters already exist, inspect and label those clusters with `niche_annotation_tool(utag_apply_clustering=False, niche_key=<existing column>)`.
This bypasses UTAG. Pass `dataset_context`, `allowed_labels`, and `output_path` from the task. Do not recompute them solely to satisfy an internal column-name convention.

## Choose spatial scale from measured evidence

Use a separate spatial graph for each independent section. Record coordinate units when known;
otherwise record them as unknown. Do not infer anatomical orientation from coordinate signs
unless the orientation is supplied.

Choose neighborhood scale for the requested anatomical level. Before committing, inspect the
number of non-self neighbors, isolated-cell fraction, and component-size distribution for the
candidate graph by passing `neighborhood_radii` to the inspector. Nearest-neighbor distance alone is insufficient to establish that a graph
captures tissue neighborhoods. Consider tissue boundaries, density variation, and the effect
of the selected scale on local cell composition. Choose parameters from the input evidence,
not from downstream evaluation scores.

The inspector reports each candidate separately. Compare candidates with usable diagnostics;
`resource_limit` describes computational cost, not biological suitability. If none are usable,
inspect another feasible candidate before choosing spatial scale.

Distinguish expression preprocessing from graph-weight normalization. In the native UTAG
implementation, `l1_norm` normalizes adjacency rows before aggregating expression. Log-normalized
input does not, by itself, imply that graph-weight normalization should be disabled.

Assess the resulting clusters' spatial extent and local heterogeneity. UTAG clusters are not
guaranteed to be single contiguous anatomical regions. When regional interpretations conflict,
use the spatial review below before accepting a single label for the cluster.

## Review clustering before labeling

Use `niche_annotation_tool(preview_only=True)` to inspect a candidate's cluster sizes, composition,
and spatial extent before spending model calls on labels. A preview is not a completed annotation.
Assess whether its granularity fits the requested anatomical level; the number of allowed labels
is not a required cluster count, and mixed cell types are expected in anatomical regions.
If a concrete spatial or compositional issue warrants it, preview one alternative configuration.
Choose from this measured evidence, never scores. Record the reason and keep the candidate files.

Use the selected preview's returned `labeling_arguments`, including its candidate file path.
The original query has no generated clusters; preserving that input does not mean reusing it
for labeling. Label the chosen candidate with `preview_only=False`, `utag_apply_clustering=False`, its actual
`niche_key`, and the same spatial radius used to assess it. Saved native candidates carry that selected radius
into labeling, preventing a forgotten argument from changing the spatial evidence. This reuses the
saved clustering.
The labeling operation writes the final requested H5AD. Do not label every candidate for comparison.

## Resolve competing regional interpretations

Separate recognition of a broad tissue family from selection of a more specific anatomical
region when the supplied vocabulary supports that distinction. Keep competing labels explicit
in the review; intermediate descriptions do not expand the permitted final label vocabulary.
Anatomical direction must be supported by biology or supplied orientation information, not
left/right or top/bottom positions on a plot.

At preview or initial-annotation review, look for evidence supporting different anatomical
labels within one cluster. A whole-cluster majority does not resolve whether the minority
occupies a different region. Mixed cell types, small disconnected fragments, or an unused
allowed label alone are not reasons to subdivide. Assess whether competing evidence is
spatially segregated, locally intermingled, or insufficient to decide.

The annotation specialist has no arbitrary code-execution tool. If its summaries cannot answer
that question, return a handoff to the manager describing the unresolved interpretation,
candidate labels, affected cluster IDs, saved H5AD and evidence paths, resolved input keys,
selected spatial radius and units, original vocabulary, and final destination. Request a
`coding_agent` review under this same skill. If the current plan lacks that step, state the
need for replanning; do not claim the review was executed or the ambiguity resolved.

For the coding-agent review, execute Python using the existing `python` tool. Compare local
cell-type composition, expression, and neighboring populations within the affected areas.
Report the size, location, and evidence of substantial spatial subregions, rather than only
the number of connected components or a pooled centroid. Use a sparse spatial graph per section
and bounded summaries; avoid whole-dataset dense distance matrices. Choose the analysis and
spatial scale from measured data. Do not prescribe a fixed number of regions or assume every
permitted label is present.

Use supplied cell-type identities as evidence with possible errors, not as a direct lookup
from cell type to anatomical label. Supporting cell populations belong to the region supported
by their local context. Refined regions may cross original cluster boundaries when that better
represents the tissue; retain unaffected region memberships and document the affected cells.

Return a reasoned decision to retain the grouping, propose spatial refinement, or leave the
specific region unresolved. If refinement is supported, save a derived H5AD containing all
original cells, supplied cell types, and a new region-ID column, plus a compact evidence summary.
Preserve any initial annotation columns. Report the actual file path, region key, and spatial
radius for the annotation specialist to use with `utag_apply_clustering=False`; it must not
recompute UTAG over the refined regions. The coding agent performs the spatial computation;
the existing native annotation tool assigns the permitted labels.

Check that the proposed regions respect local biological evidence and boundaries rather than
only becoming more homogeneous by cell type. Record unresolved boundary cells and uncertainty.
Use Unmatched when a final permitted label remains unsupported. Make at most one documented
refinement, retain the original result, and never compare candidates using evaluation truth
or scores.

## Assign anatomical labels

Carry the public biological context into the internal labeling call. Use cluster size,
cell-type composition, measured gene evidence, spatial extent, and relevant neighboring-region
evidence together. Choose summary breadth based on informative populations and the measured
panel; do not silently discard supplied cell types or spatial information.

For an ambiguous assignment, assess the strongest alternatives and the evidence that separates
them. Broadly distributed stromal, vascular, or immune populations alone do not establish a
unique anatomical compartment. Do not claim unmeasured functional conditions as observed
evidence. Treat a bare cluster centroid as a geometric summary, not a complete anatomical map.

Review assignments that conflict with their input-derived regional evidence using the regional
review above. Record the reason for accepting one cluster-wide label when substantial evidence
supports another region; numerical dominance alone is insufficient to dismiss that evidence.

Assign one permitted region label per cell, using Unmatched where evidence remains insufficient.
Multiple clusters may share a region label. The allowed list does not imply that every label
must be present in every section.

If a justified alternative uses marker scores, account for unequal measured marker coverage,
score scale, and specificity. Do not compare uncalibrated marker sums as if they were comparable
probabilities. Grouping all cells of the same cell type is not a substitute for spatial context.

## Deliver and validate

Save an actual annotated H5AD at the requested destination through a binary-capable writer or
copy operation. Preserve cell identifiers and supplied cell-type labels. Validate the output's
cell coverage and label vocabulary, and record the selected method, parameters, evidence,
remaining uncertainty, and artifact paths.

Record the scientific result as soon as the validated annotation file is available. A later
reporting failure must retain that artifact and its provenance while reporting the workflow
failure separately. Do not create text placeholders with `.h5ad` or image extensions.
Only list artifacts that were actually written; optional reports and plots should not require
repeating an already completed annotation.
