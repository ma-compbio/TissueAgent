---
name: cell_annotation
status: enabled
description: >
  Annotate cell types in a single-cell-resolution spatial transcriptomics dataset by
  onboarding it when needed, inspecting method suitability, and choosing one evidence-backed
  backend from Harmony reference transfer, CellTypist, or GPTCellType.
---

## Inputs

- A spatial transcriptomics dataset, for example H5AD, one or more CSV files, or a Seurat object
- Known species and broad tissue context
- An optional labeled single-cell reference AnnData used only to assess and run Harmony

## Outputs

- An annotated `.h5ad` with an input-derived, non-colliding name in
  `project/outputs/cell_annotation/`
- Conversion/validation provenance when onboarding was required
- A corresponding `.run_meta.json` in `project/outputs/cell_annotation/`

## Step Sketch

Onboard the query if needed → reuse or retrieve a candidate reference when appropriate → inspect
method suitability inside Cell Annotater → validate one selection → run exactly one annotation
backend

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
- **Reference routing:** reuse a supplied or existing matching labeled H5AD. Unless the user
  explicitly requests a reference-free method, use `single_cell_agent` to query CELLxGENE and
  retrieve a bounded candidate reference into `project/outputs/references/` when none is available.
  This gives Cell Annotater actual source, tissue, disease, assay, label-count, and shared-gene
  evidence for assessing Harmony only. Candidate-reference evidence must not affect CellTypist
  suitability or model selection, or GPTCellType suitability. Reference acquisition remains outside
  Cell Annotater.
- **Annotation step, agent `cell_annotator_agent`:** keep method inspection, reasoning, and execution
  in one bundled plan step. First call `list_celltypist_model_catalog_tool` exactly once, review the
  complete verified catalog against the supplied query biology, and shortlist one to three exact
  model filenames without a code-generated rank. Preserve any caller-provided annotation scope as
  an immutable primary scope, secondary scope, sampling context, and requested output. Then call `inspect_cell_annotation_methods_tool`
  exactly once on the validated query and optional Harmony candidate reference, passing that
  shortlist, catalog SHA-256, exact annotation scope, and annotation-context SHA-256. TissueAgent
  binds the original context around delegation so generated argument drift cannot alter it. The inspector
  must reject a rewritten, omitted, or rehashed context. Follow `method_evidence_scopes`: use
  `reference.query_panel_preflight` only for Harmony, every
  `celltypist.candidate_model_preflights` entry only with query context for CellTypist, and
  `query.gptcelltype_readiness` only for GPTCellType. The supervised
  preflights privately use full query feature identifiers only and return no gene names or query
  predictions; the CellTypist assessment separately uses the returned matrix-state summary to
  require raw counts or explicit nonnegative log1p state, with target-sum validation unresolved
  until backend execution. GPTCellType readiness uses bounded query expression without observation
  metadata.
  Not-assessable evidence is unknown rather than adverse. The inspector also returns versioned
  categorical method assessments and selection policy v6. The agent chooses exactly one backend from
  `selection_policy.default_candidates` when nonempty. If no default exists, it chooses only from
  the reported fallback and unknown candidates, explicitly explains the adverse-versus-unknown
  tradeoff, and never chooses an excluded method. It follows the selection-policy v6
  `rationale_guard`: an unknown selected candidate has claim status
  `best_supported_unresolved` and must be described with the exact phrase
  `best-supported unresolved option`; every required disclosure code for observed reference
  placeholder prevalence or context heterogeneity must appear verbatim. Ties are resolved from raw
  evidence, with specific supplied disease/developmental coverage ahead of generic tissue-only
  evidence. Before choosing, the agent assigns `high`, `moderate`, or `low` suitability confidence
  to all three methods. Harmony confidence specifically measures how well the selected reference
  matches the supplied species, tissue or compartment, disease, developmental stage, and needed
  population or label inventory, followed by technical compatibility. Shared genes,
  reference-only separability, and single-source status cannot upgrade weak biological coverage.
  A disease-specific query with a normal-only reference or a different explicit disease family is
  a disease-context mismatch and cannot receive high Harmony suitability. Reference availability
  does not imply that the caller prefers Harmony. Reference identity, anatomy, disease, labels,
  provenance, and feature overlap may not raise or lower CellTypist, a CellTypist model, or
  GPTCellType.
  The agent passes all three values as `method_suitability_confidences` and one scoped explanation
  per method as `method_suitability_rationales`; only Harmony's explanation may use the candidate
  reference. It also copies `method_evidence_scopes.method_inputs` exactly into
  `method_evidence_sources` so the allowed evidence is contract-validated without brittle wording
  checks. It may not select a method rated below another runnable method. The agent also passes a
  comparative `selection_rationale` that keeps reference details in the Harmony explanation and
  names the strongest alternative, including the exact
  sentence `Candidate reference evidence was used only to assess Harmony.` when a reference was
  inspected, cites relevant adverse
  policy reason codes, and records supporting, adverse, and unresolved evidence for all three
  methods. For composite references,
  inspect every source. Co-occurrence of
  tissue, disease, and decisive labels in one suitable source is strongest, but distinct
  same-species sources may provide complementary tissue-resident and disease-associated lineages
  when those labels are explicit, gene overlap is strong, and source-confounding risk is disclosed.
  Aggregate tissue/disease keywords alone do not establish coverage. When most reference labels or
  cells are source-exclusive, stratified CV is not affirmative evidence; source-grouped minority
  coverage or a twofold generalization collapse makes Harmony high-risk while a supported
  lower-risk alternative exists.
- **Selection authorization:** call `validate_cell_annotation_selection_tool` exactly once with the
  inspector's `selection_contract.contract_id`, the selected method, comparative rationale,
  `method_suitability_confidences`, `method_suitability_rationales`, exact
  `method_evidence_sources`, and exact final output path.
  Also pass the selected method's
  exact `parameter_policy_version` and
  complete `scientific_configuration` and `operational_configuration` mappings listed in
  `selection_contract.backend_configuration_requirements`; those values must exactly match the
  backend invocation. For built-in CellTypist, also provide the selected exact candidate filename,
  a rationale that compares every technically eligible shortlisted model, and a `high`, `moderate`,
  or `low` suitability value for every candidate. Also provide a structured model-scope assessment
  for every candidate with primary, secondary, requested-output, and technical coverage plus cited
  evidence and unsupported populations. The validator ranks primary coverage first,
  requested-output coverage second, and technical compatibility third; secondary breadth cannot
  override weaker primary coverage. It validates policy membership and canonically retains required unresolved
  language, reference disclosures, and adverse reason codes, and returns a one-time execution
  token plus `configuration_sha256`. No annotation backend may run before it succeeds. For selected
  Harmony, run the required pair preprocessing inspection first so its decision and derived
  thresholds can be included in the contract. The token binds input identities, method, output,
  context, label source, every exposed backend parameter, parameter-policy version, and—in
  GPTCellType—the worker-model and readiness/execution profile identities.
- **Harmony:** select it for a strongly matched labeled reference when label coherence,
  source-aware query-panel discriminability, and the need for batch correction are compelling.
  Zero exact observation-ID overlap does not prove study/sample independence. Before selection
  validation, call `inspect_anndata_preprocessing_tool` once on the exact pair; the method
  inspector's expression summary does not replace this call. Include its exact per-input
  `preprocess_spatial` and `preprocess_reference` booleans and all other Harmony arguments in the
  configuration contract, then call `harmony_transfer_tool` once with the same values, token, and
  configuration hash. A raw/processed pair preprocesses only the raw input on a working copy; the
  backend verifies both decisions with the same bounded preflight before full loading. If the
  exact output path is supplied, still copy the validated `output_dir` and `output_filename`
  verbatim into the backend call; do not replace them with values derived from the output path. If the
  reference is preprocessed, choose `reference_min_genes` from reference detected-gene evidence; it
  must never filter query observations. Choose an explicit assay-appropriate `min_shared_genes`.
  When the caller supplies human or mouse context, pass that exact known species as
  `gene_mapping_species`; use `auto` only when species is genuinely unresolved.
- **CellTypist:** semantically compare every shortlisted official model's population or disease
  coverage, tissue, developmental stage, label inventory, training provenance, and technical
  preflight. Select a built-in model only when that evidence is convincing and the query expression
  prerequisite plus exact feature and retained-coefficient support are adequate; otherwise lower
  CellTypist's suitability relative to a stronger method. The inspector verifies and preflights the
  shortlist but intentionally supplies no model rank. Choose from the built-in shortlist without
  using any candidate-reference evidence, and pass the selected `model_name`. Processed continuous expression without
  explicit log1p metadata is incompatible; explicit log1p target-sum compatibility remains
  unresolved until backend validation. Passing the backend feature-count minimum establishes
  feature runnability, not panel support; retaining less than the majority of coefficient mass is
  high panel risk. Pass `celltypist.majority_voting_recommendation.recommended` exactly as
  `majority_voting`. That query-only recommendation is true only when CellTypist prerequisites are
  met, readiness succeeds, disjoint-view coherence is strong, and at least 51 sampled nonzero cells
  support transcriptomic overclustering. Do not compare CellTypist probabilities numerically with
  Harmony confidence.
- **GPTCellType:** treat strong readiness as affirmative independent evidence rather than merely a
  fallback. Moderate readiness requires caution, weak readiness is adverse, and not-assessable or
  errored readiness is unknown. Supply broad species/tissue context only. Treat it as cluster-level
  free-text annotation with no calibrated confidence; avoid it when its marker-readiness evidence
  is weak. The current readiness profile authorizes only generated Leiden clusters at resolution
  1.0 with ten markers. A supplied cluster column, another resolution, or another marker count
  requires a separately implemented readiness profile and is rejected by selection validation.
- Never route by benchmark/dataset identity, inspect held-out labels or mappings, or run several
  methods and use truth to choose. Do not calibrate selection thresholds against benchmark outcomes;
  the fixed majority and twofold policy rules are structural guardrails. Preserve all original query
  observations and their order for every backend.
- Use this plan for single-cell-resolution platforms. Route spot mixtures to
  `spatial_deconvolution`.
- Keep the execution plan minimal:
  - Repeat the exact workspace-relative query, reference, and final output paths in the Cell
    Annotator step description and every dispatched task instruction. Never replace them with
    shortened aliases such as `spatial_query.h5ad` or `reference.h5ad`.
  - Do not add standalone query-inspection, query-QC, preprocessing-configuration, shared-gene,
    integrity-check, or report steps. Do not request intermediate tables/configs/preprocessed H5ADs
    from Cell Annotator or Data Onboarding. Their deterministic tool results, provenance JSON, final
    H5AD, and run metadata are the artifacts.
  - With an existing query H5AD and reference, create exactly one Cell Annotator step containing
    method inspection, selection reasoning, and one backend.
  - With an existing query H5AD but no reference, create exactly two steps: one Single Cell Agent
    candidate-reference retrieval step, then one bundled Cell Annotator step, unless the user
    explicitly requests a reference-free method. Do not route the valid H5AD through Data Onboarding
    and do not copy/convert it before annotation.
  - With a supported non-H5AD query and existing reference, create exactly two steps: one Data
    Onboarding step (inspect, convert, validate), then one adaptive Cell Annotator step.
  - For an unsupported format, insert a Coding Agent conversion step and a Data Onboarding
    validation step before Cell Annotation.
  - Add a separate reference-retrieval step when no compatible reference was supplied or found.
- Do not create separate configuration, matrix-summary, method-selection, preprocessing-decision,
  integrity-check, or warning-report steps. Deterministic tool results, conversion/reference
  provenance, backend run metadata, plan, and captured transcript are the audit record.

## Evaluation Criteria

- The final H5AD has the same observation count and order as the validated query.
- `.obs` contains `cell_annotation_predicted_cell_type`,
  `cell_annotation_prediction_confidence`, `cell_annotation_method`, `cell_annotation_status`,
  `cell_annotation_exclusion_reason`, and `label`, plus backend-specific columns.
- Run metadata records the selected backend, evidence-based rationale, raw-label source, input/output
  counts, model/reference provenance, method-specific warnings, and all artifact paths.
- Harmony additionally records preprocessing/shared-gene decisions and reference filtering;
  CellTypist records model identity/hash and feature overlap; GPTCellType records clusters, markers,
  prompts, raw responses, worker model, and bounded retry counts.
- Every backend records the selection-contract ID, parameter-policy version, full canonical
  execution configuration, and configuration SHA-256.
- Every written artifact is beneath `project/outputs/` and no existing artifact is overwritten.
