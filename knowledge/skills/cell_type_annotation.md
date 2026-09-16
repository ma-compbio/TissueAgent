---
name: cell-type-annotation
description: Assign one cell-type label per observation by evidence-backed selection among Harmony reference transfer, CellTypist, and GPTCellType. Supports validated H5AD queries and queries converted first by Data Onboarding.
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
- A labeled reference is required only for Harmony; it is not evidence for CellTypist or
  GPTCellType. Reuse a supplied compatible reference. Unless a
  reference-free method was explicitly requested, retrieve a bounded CELLxGENE candidate when none
  exists so method selection can compare real biological coverage and provenance.

## Required workflow

1. For non-H5AD query inputs, start with `inspect_spatial_data_tool`. For a supported format, use
   `convert_spatial_data_tool` and `validate_spatial_data_tool`. If the converter does not support
   the detected format, use the Coding Agent for conversion and validate its result with
   `validate_spatial_data_tool`.
2. Inside the single Cell Annotator plan step, call `list_celltypist_model_catalog_tool` exactly once.
   Review the complete verified catalog against the known query biology and shortlist one to three
   exact filenames; no code-generated model rank is provided. Treat the immutable
   `annotation_scope.primary_scope` as the dominant objective; secondary coverage and a tissue-name
   match cannot compensate for weak primary-scope coverage. Then call
   `inspect_cell_annotation_methods_tool` exactly once with the catalog SHA-256, exact shortlist,
   validated query, optional Harmony candidate reference and label column, and known
   species/tissue/disease/developmental context plus the caller's exact `annotation_scope` and
   `annotation_context_sha256`. In TissueAgent, the manager binds these original values around the
   delegated call and the inspector treats that binding as authoritative; generated argument drift
   is recorded but cannot alter the executed context. The inspector must verify the canonical context hash. Follow
   `method_evidence_scopes`: use
   `reference.query_panel_preflight` only for Harmony, use every
   `celltypist.candidate_model_preflights` entry with query context only for CellTypist, and use
   `query.gptcelltype_readiness` only for GPTCellType. The supervised
   preflights use query feature identifiers only; they do not read query expression or observations.
   The CellTypist assessment separately uses the returned query matrix-state summary to require raw
   counts or explicit nonnegative log1p state, with target-sum validation unresolved until backend
   execution. The tool preserves those raw diagnostics and also returns versioned
   `method_assessments` and categorical selection policy v6. Not-assessable evidence is unknown,
   not adverse. Do not inspect query annotation-like columns, benchmark identities, held-out
   labels, mappings, or historical scores.
3. Choose exactly one backend from `selection_policy.default_candidates` when that list is
   nonempty. If one default remains, use it; if several remain, reason over their
   biological/provenance evidence. If there is no default, choose only from the reported
   `fallback_candidates` and `unknown_candidates`, explicitly explain the adverse-versus-unknown
   tradeoff, and never choose an excluded method. Follow the selection-policy v6
   `rationale_guard`: describe a selected method whose claim status is
   `best_supported_unresolved` with the exact phrase `best-supported unresolved option`, and
   include every required disclosure code for observed reference placeholder prevalence or
   context heterogeneity verbatim. Prioritize a specific supplied
   disease/developmental match over generic tissue-only evidence; an official catalog default is
   only a final model tie-break. Assign `high`, `moderate`, or `low` suitability confidence to all
   three methods before choosing, pass the exact mapping as `method_suitability_confidences`, add
   one evidence-scoped explanation per method in `method_suitability_rationales` with candidate-
   reference evidence confined to Harmony, and
   never choose a method rated below another runnable method. Harmony suitability means how well
   this specific reference matches the supplied species, tissue or compartment, disease,
   developmental stage, and needed population or label inventory, followed by technical
   compatibility. Shared genes, reference-only separability, and single-source status cannot
   upgrade weak biological coverage. A disease-specific query with a normal-only reference or a
   different explicit disease family has low Harmony suitability, and reference availability does
   not imply that the caller prefers Harmony. Pass a
   comparative `selection_rationale` that names the strongest alternative, includes the exact
   sentence `Candidate reference evidence was used only to assess Harmony.` when a reference was
   inspected, cites relevant adverse
   policy reason codes, and lists supporting, adverse, and unresolved evidence for all three:
   - **Harmony** for a well-matched labeled same-species reference with appropriate tissue/state and
     coherent labels plus source-aware query-panel discriminability when batch correction is
     valuable. For a composite reference, inspect every source. A jointly matched source is
     strongest, but distinct same-species sources can provide
     defensible complementary tissue-resident and disease-associated lineages when their labels
     are explicit, gene overlap is strong, and source-confounding risk is disclosed; aggregate
     keywords alone are insufficient. For a composite reference, majority source-exclusive labels
     make stratified CV non-affirmative; source-grouped minority coverage or at least twofold
     generalization collapse makes Harmony high-risk while a supported lower-risk alternative
     exists. Zero exact observation-ID overlap does not prove study, donor, or sample independence.
     Then call `inspect_anndata_preprocessing_tool` exactly once before selection validation. The
     general method inspector's expression summary does not replace this pair inspection. Put its
     exact safe boolean, the evidence-derived thresholds, and every other Harmony argument into the
     configuration contract, then pass identical values to one `harmony_transfer_tool` call. The
     backend verifies the preprocessing decision again before full loading. Set
     `gene_mapping_species`, select reference-only `reference_min_genes` when raw preprocessing is
     required, and select assay-appropriate `min_shared_genes`.
   - **CellTypist** after semantically comparing every shortlisted model's disease or population
     coverage, tissue, developmental stage, label inventory, training provenance, and technical
     preflight. Choose a built-in model only when the match is convincing and its bounded query
     expression prerequisite, exact feature overlap, and retained-coefficient support are adequate;
     otherwise lower CellTypist relative to a stronger method. Do not infer biological suitability
     from feature overlap or prefer a tissue-name match over explicit population evidence. Do not
     use candidate-reference identity, anatomy, disease, labels, provenance, or feature overlap in
     CellTypist reasoning. Provide the selected built-in `model_name` and a structured assessment
     for every candidate containing primary-scope, secondary-scope, requested-output, and technical
     coverage plus evidence and unsupported populations. Rank primary scope first, requested output
     second, and technical compatibility third; secondary breadth is never a reason to override a
     stronger primary match. Processed continuous
     expression without explicit log1p metadata is incompatible; explicit log1p target-sum
     compatibility remains unresolved until backend validation. Passing the backend feature minimum
     means feature-runnable, not supported: retained coefficient mass below the majority boundary is
     high panel risk. Pass `celltypist.majority_voting_recommendation.recommended` exactly as
     `majority_voting`; it is true only with met CellTypist prerequisites, successful readiness,
     strong disjoint-view coherence, and at least 51 sampled nonzero cells.
   - **GPTCellType** when query-only readiness provides affirmative evidence for coherent clusters
     and held-out positive markers. Strong readiness can outweigh supervised candidates with
     adverse or unresolved evidence and is not merely a fallback. Moderate readiness requires
     caution, weak readiness is adverse, and not-assessable or errored readiness is unknown. Provide
     broad species and tissue context only. It is cluster-level, free-text, reference-free, and has
     no calibrated confidence. The current readiness profile authorizes only generated clusters at
     resolution 1.0 with ten markers; other cluster configurations require a separate readiness
     profile and must not be executed under this inspection result.
4. Call `validate_cell_annotation_selection_tool` exactly once with the inspector's
   `selection_contract.contract_id`, the selected method, comparative rationale,
   `method_suitability_confidences`, `method_suitability_rationales`, and
   `method_evidence_sources` copied exactly from `method_evidence_scopes.method_inputs`, plus the
   exact output path and exact method
   `parameter_policy_version`, and
   complete `scientific_configuration` and
   `operational_configuration` mappings. For built-in CellTypist, also pass the exact selected
   candidate filename, a rationale naming and comparing every technically eligible candidate, and
   one `high`, `moderate`, or `low` suitability rating per candidate. For selected Harmony, do this after preprocessing
   inspection; for other methods, do it immediately after selection. The validator binds input
   identities, choice, model/context, and the complete canonical configuration, then returns a
   one-time execution token and `configuration_sha256`. Pass both to exactly one backend invoked
   with identical arguments. Copy every validated scientific and operational value verbatim; an
   explicit Harmony `output_path` does not authorize changing its validated `output_dir` or
   `output_filename`. For CellTypist, use the exact majority-voting value and the
   contract-authorized agent-selected built-in model.
5. Never choose from benchmark/dataset identity or held-out truth, compare backend prediction
   confidence values across methods, silently run several methods, or calibrate preflight thresholds
   to benchmark outcomes.
   The fixed majority and twofold rules are structural validation guardrails, not performance
   estimates. Method selection is an evidence-backed hypothesis, not an oracle guarantee.
6. Preserve the original query observation count and order. A successful backend must assign a
   prediction to every query observation or surface exclusions explicitly.

## Output contract

Every annotated H5AD contains:

- `cell_annotation_predicted_cell_type`
- `cell_annotation_prediction_confidence` (`NaN` for methods without calibrated confidence)
- `cell_annotation_method`
- `cell_annotation_status`
- `cell_annotation_exclusion_reason`
- `label`

Backend-specific aliases remain available. Harmony writes `harmony_*`; CellTypist writes
`celltypist_*`; GPTCellType writes `gptcelltype_*`.

The tool result and adjacent run metadata report the selected method, selection rationale,
raw-label source, input/output counts, cell-type counts, relevant confidence, model/reference
provenance, warnings, and canonical workspace-relative paths. The compact
`.uns['tissueagent_cell_annotation']` provenance includes the selection-contract ID, parameter-policy
version, configuration SHA-256, and the full canonical execution contract as deterministic JSON.
Harmony also records preprocessing, mapping, shared genes, batches, and convergence. CellTypist
records model metadata/hash and feature overlap. GPTCellType records clusters, markers, prompts, raw
responses, worker model, and bounded retry counts.

## Failure conditions

- No eligible backend after method inspection
- Selection validation failure or an invalid, expired, replayed, or mismatched execution token
- Missing or incompatible CellTypist model/reference, weak feature overlap, or invalid expression
- GPTCellType without broad species/tissue context, reliable clusters/markers, or a worker LLM key
- Harmony with too few shared genes, unsafe preprocessing evidence, or invalid reference labels
- Missing or duplicate identifiers
- Output paths outside `project/outputs/`

Do not guess, silently drop observations, switch methods after a backend error, or use held-out truth.
Report the failed stage and tool evidence.
