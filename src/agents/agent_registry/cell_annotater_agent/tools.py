"""Tool definitions for the Cell Annotater Agent."""

from __future__ import annotations

from typing import Any

from langchain_core.tools import StructuredTool

from agents.agent_registry.cell_annotater_agent.tools_impl.niche_artifacts import (
    recover_niche_annotation_artifacts_tool,
)
from agents.agent_registry.cell_annotater_agent.tools_impl.niche_review import (
    review_tissue_niches_tool,
)
from agents.agent_registry.cell_annotater_agent.tools_impl.annotation_review import (
    inspect_annotation_evidence_tool,
    refine_cell_annotations_tool,
)
from agents.agent_registry.cell_annotater_agent.tools_impl.selective_annotation_review import (
    refine_cell_annotations_selective_tool,
)
from agents.agent_registry.cell_annotater_agent.tools_impl.requested_celltypist import (
    run_requested_celltypist_tool,
)

from agents.agent_registry.cell_annotater_agent.tools_impl.celltypist_annotation import (
    celltypist_annotation_tool as _celltypist_annotation_impl,
)
from agents.agent_registry.cell_annotater_agent.tools_impl.gptcelltype_annotation import (
    gptcelltype_annotation_tool as _gptcelltype_annotation_impl,
)
from agents.agent_registry.cell_annotater_agent.tools_impl.harmony_transfer import (
    harmony_transfer_tool as _harmony_transfer_impl,
    inspect_anndata_preprocessing_tool,
)
from agents.agent_registry.cell_annotater_agent.tools_impl.method_selection import (
    inspect_cell_annotation_methods_tool,
    list_celltypist_model_catalog_tool,
)
from agents.agent_registry.cell_annotater_agent.tools_impl.niche_annotation import (
    inspect_tissue_niche_input_tool,
    niche_annotation_tool,
)
from agents.agent_registry.cell_annotater_agent.tools_impl.selection_contract import (
    CELLTYPIST_PARAMETER_POLICY_VERSION,
    GPTCELLTYPE_PARAMETER_POLICY_VERSION,
    HARMONY_PARAMETER_POLICY_VERSION,
    authorize_backend_execution,
    validate_cell_annotation_selection_tool,
)


def harmony_transfer_tool(
    spatial_anndata_path: str,
    reference_anndata_path: str,
    selection_execution_token: str,
    configuration_sha256: str,
    output_dir: str = "cell_annotation",
    output_path: str | None = None,
    output_filename: str | None = None,
    cell_type_column: str = "cell_type",
    skip_preprocessing: bool | None = None,
    preprocess_spatial: bool | None = None,
    preprocess_reference: bool | None = None,
    preserve_all_spatial_obs: bool = True,
    reference_min_genes: int | None = None,
    min_cells: int = 10,
    target_sum: float = 1e4,
    n_top_genes: int = 2000,
    feature_scaling: str = "none",
    n_pcs: int = 30,
    min_shared_genes: int | None = None,
    harmony_key: str = "batch",
    harmony_max_iter: int = 20,
    mlp_hidden_layers: tuple = (100, 50),
    mlp_max_iter: int = 500,
    mlp_random_state: int = 42,
    classifier: str = "mlp",
    knn_neighbors: int = 51,
    map_spatial_gene_names: bool = True,
    gene_mapping_species: str = "auto",
    gene_mapping_target: str = "symbol",
) -> dict[str, Any]:
    """Authorize and run Harmony reference transfer."""
    scientific_configuration = {
        "skip_preprocessing": skip_preprocessing,
        "preprocess_spatial": preprocess_spatial,
        "preprocess_reference": preprocess_reference,
        "preserve_all_spatial_obs": preserve_all_spatial_obs,
        "reference_min_genes": reference_min_genes,
        "min_cells": min_cells,
        "target_sum": target_sum,
        "n_top_genes": n_top_genes,
        "feature_scaling": feature_scaling,
        "n_pcs": n_pcs,
        "min_shared_genes": min_shared_genes,
        "harmony_key": harmony_key,
        "harmony_max_iter": harmony_max_iter,
        "mlp_hidden_layers": mlp_hidden_layers,
        "mlp_max_iter": mlp_max_iter,
        "mlp_random_state": mlp_random_state,
        "classifier": classifier,
        "knn_neighbors": knn_neighbors,
        "map_spatial_gene_names": map_spatial_gene_names,
        "gene_mapping_species": gene_mapping_species,
        "gene_mapping_target": gene_mapping_target,
    }
    operational_configuration = {
        "output_dir": output_dir,
        "output_filename": output_filename,
    }
    authorization = authorize_backend_execution(
        selection_execution_token=selection_execution_token,
        selected_method="harmony",
        spatial_anndata_path=spatial_anndata_path,
        output_path=output_path,
        reference_anndata_path=reference_anndata_path,
        reference_cell_type_column=cell_type_column,
        scientific_configuration=scientific_configuration,
        operational_configuration=operational_configuration,
        parameter_policy_version=HARMONY_PARAMETER_POLICY_VERSION,
        configuration_sha256=configuration_sha256,
    )
    if authorization.get("status") != "success":
        return authorization
    return _harmony_transfer_impl(
        spatial_anndata_path=spatial_anndata_path,
        reference_anndata_path=reference_anndata_path,
        output_dir=output_dir,
        output_path=output_path,
        output_filename=output_filename,
        cell_type_column=cell_type_column,
        skip_preprocessing=skip_preprocessing,
        preprocess_spatial=preprocess_spatial,
        preprocess_reference=preprocess_reference,
        preserve_all_spatial_obs=preserve_all_spatial_obs,
        reference_min_genes=reference_min_genes,
        min_cells=min_cells,
        target_sum=target_sum,
        n_top_genes=n_top_genes,
        feature_scaling=feature_scaling,
        n_pcs=n_pcs,
        min_shared_genes=min_shared_genes,
        harmony_key=harmony_key,
        harmony_max_iter=harmony_max_iter,
        mlp_hidden_layers=mlp_hidden_layers,
        mlp_max_iter=mlp_max_iter,
        mlp_random_state=mlp_random_state,
        classifier=classifier,
        knn_neighbors=knn_neighbors,
        map_spatial_gene_names=map_spatial_gene_names,
        gene_mapping_species=gene_mapping_species,
        gene_mapping_target=gene_mapping_target,
        selection_rationale=authorization["validated_selection_rationale"],
        execution_contract={
            "selection_contract_id": authorization["selection_contract_id"],
            **authorization["configuration_contract"],
        },
    )


def celltypist_annotation_tool(
    spatial_anndata_path: str,
    output_path: str,
    selection_execution_token: str,
    configuration_sha256: str,
    model_name: str,
    majority_voting: bool = False,
    mode: str = "best match",
    p_thres: float = 0.5,
    n_jobs: int = 1,
    min_feature_overlap: int = 50,
) -> dict[str, Any]:
    """Authorize and run CellTypist annotation."""
    scientific_configuration = {
        "majority_voting": majority_voting,
        "mode": mode,
        "p_thres": p_thres,
        "min_feature_overlap": min_feature_overlap,
    }
    operational_configuration = {"n_jobs": n_jobs}
    authorization = authorize_backend_execution(
        selection_execution_token=selection_execution_token,
        selected_method="celltypist",
        spatial_anndata_path=spatial_anndata_path,
        output_path=output_path,
        celltypist_model_name=model_name,
        celltypist_majority_voting=majority_voting,
        scientific_configuration=scientific_configuration,
        operational_configuration=operational_configuration,
        parameter_policy_version=CELLTYPIST_PARAMETER_POLICY_VERSION,
        configuration_sha256=configuration_sha256,
    )
    if authorization.get("status") != "success":
        return authorization
    return _celltypist_annotation_impl(
        spatial_anndata_path=spatial_anndata_path,
        output_path=output_path,
        selection_rationale=authorization["validated_selection_rationale"],
        model_name=model_name,
        majority_voting=majority_voting,
        mode=mode,
        p_thres=p_thres,
        n_jobs=n_jobs,
        min_feature_overlap=min_feature_overlap,
        execution_contract={
            "selection_contract_id": authorization["selection_contract_id"],
            **authorization["configuration_contract"],
        },
    )


def gptcelltype_annotation_tool(
    spatial_anndata_path: str,
    output_path: str,
    species: str,
    tissue: str,
    selection_execution_token: str,
    configuration_sha256: str,
    cluster_column: str | None = None,
    resolution: float = 1.0,
    top_marker_genes: int = 10,
    api_batch_size: int = 25,
    max_api_attempts_per_batch: int = 3,
    api_timeout_seconds: int = 120,
) -> dict[str, Any]:
    """Authorize and run GPTCellType annotation."""
    scientific_configuration = {
        "cluster_column": cluster_column,
        "resolution": resolution,
        "top_marker_genes": top_marker_genes,
    }
    operational_configuration = {
        "api_batch_size": api_batch_size,
        "max_api_attempts_per_batch": max_api_attempts_per_batch,
        "api_timeout_seconds": api_timeout_seconds,
    }
    authorization = authorize_backend_execution(
        selection_execution_token=selection_execution_token,
        selected_method="gptcelltype",
        spatial_anndata_path=spatial_anndata_path,
        output_path=output_path,
        species=species,
        tissue=tissue,
        scientific_configuration=scientific_configuration,
        operational_configuration=operational_configuration,
        parameter_policy_version=GPTCELLTYPE_PARAMETER_POLICY_VERSION,
        configuration_sha256=configuration_sha256,
    )
    if authorization.get("status") != "success":
        return authorization
    return _gptcelltype_annotation_impl(
        spatial_anndata_path=spatial_anndata_path,
        output_path=output_path,
        species=species,
        tissue=tissue,
        selection_rationale=authorization["validated_selection_rationale"],
        cluster_column=cluster_column,
        resolution=resolution,
        top_marker_genes=top_marker_genes,
        api_batch_size=api_batch_size,
        max_api_attempts_per_batch=max_api_attempts_per_batch,
        api_timeout_seconds=api_timeout_seconds,
        execution_contract={
            "selection_contract_id": authorization["selection_contract_id"],
            **authorization["configuration_contract"],
        },
    )


CellAnnotaterTools: list[StructuredTool] = [
    StructuredTool.from_function(
        func=run_requested_celltypist_tool,
        name="run_requested_celltypist_tool",
        description=(
            "Run an explicit original-user CellTypist execution request bound by the manager. "
            "No arguments: query/reference hashes, training label column, output path, seed "
            "and normal majority voting are fixed by that original request. Trains a fresh "
            "reference model and predicts all query cells; preserves raw/voted labels. "
            "Use only when celltypist_execution_request is present in the bound context. "
            "Replaces automatic catalog/method selection for this user-selected experiment; "
            "does not change default adaptive policy. Follow with requested evidence review."
        ),
    ),
    StructuredTool.from_function(
        func=refine_cell_annotations_selective_tool,
        name="refine_cell_annotations_selective_tool",
        description=(
            "Opt-in selective review after inspect_annotation_evidence_tool. Pass its exact "
            "evidence_path, evidence_sha256, a new final output_path and the caller's declared "
            "max_review_groups (default 48). Screen all clusters and select only specific "
            "marker-supported conflicts, rather than every subgroup in a mixed cluster. "
            "Retain original fine predictions otherwise; preserve rare populations and cell "
            "states. Budget-deferred groups retain primary predictions and are explicitly "
            "flagged, never described as fully reviewed. Does not change backend selection."
        ),
    ),
    StructuredTool.from_function(
        func=inspect_annotation_evidence_tool,
        name="inspect_annotation_evidence_tool",
        description=(
            "After one successful primary backend, build deterministic expression-cluster and "
            "primary-label-group evidence. Preserve original predictions. Pass original species, "
            "tissue, disease and developmental context, an unused output_prefix, and the exact "
            "run random_state (default 42). Returns "
            "evidence_path and its binding SHA-256. It carries unique reference Cell Ontology "
            "IDs, binds a versioned ontology snapshot when available, and records non-destructive "
            "doublet/ambient QC or explicit not_assessable reasons. Never supply truth or "
            "benchmark mappings."
        ),
    ),
    StructuredTool.from_function(
        func=refine_cell_annotations_tool,
        name="refine_cell_annotations_tool",
        description=(
            "After evidence inspection, pass its exact evidence_path and evidence_sha256 and a "
            "new final output_path. Internally screen marker/prediction conflicts then review "
            "disputed groups with the worker model. Keep, revise, broaden or mark unresolved; "
            "validate ontology-aware broadening, keep optional cell state separate from cell type, "
            "and preserve minority evidence, primary predictions, QC flags and full audit. "
            "No new primary backend or reference selection is performed."
        ),
    ),
    StructuredTool.from_function(
        func=list_celltypist_model_catalog_tool,
        name="list_celltypist_model_catalog_tool",
        description=(
            "List the verified official CellTypist model catalog without ranking or selecting a "
            "model. Call exactly once before method inspection, review all compact model cards, "
            "and shortlist one to three exact filenames from biological context, requested label "
            "coverage, training provenance, and catalog descriptions. Pass the returned catalog "
            "SHA-256 and shortlist verbatim to inspect_cell_annotation_methods_tool."
        ),
    ),
    StructuredTool.from_function(
        func=inspect_cell_annotation_methods_tool,
        name="inspect_cell_annotation_methods_tool",
        description=(
            "Required input-preserving decision context for cell-type annotation. Inspect the "
            "query and optional Harmony candidate reference exactly once before choosing a "
            "backend. It reports supervised method-scoped evidence: Harmony-only candidate-"
            "reference query-panel separability plus "
            "label/source coherence, exact feature, label-inventory, and retained-coefficient "
            "support for every agent-shortlisted official CellTypist model. Query-only "
            "GPTCellType readiness runs only for an orchestrator-bound explicit legacy-primary "
            "request. It preserves raw evidence and emits categorical assessments plus "
            "supervised-first selection-policy v7: suitable Harmony, otherwise suitable "
            "CellTypist, otherwise abstain. Its structured rationale guard marks unknown "
            "candidates as best_supported_unresolved and requires exact disclosure codes for "
            "observed reference placeholder prevalence and context heterogeneity. It does not "
            "rank or select a CellTypist model. It emits the exact query-only "
            "CellTypist majority-voting recommendation that must be passed "
            "to the backend and registers a short-lived selection contract that must be validated "
            "before execution. Supervised "
            "preflights privately inspect query .var identifiers only and "
            "return no gene names or predictions; GPTCellType readiness uses bounded expression "
            "but returns no marker names, cluster assignments, or observation metadata. The tool "
            "may populate only the controlled official CellTypist model cache. It never uses "
            "query annotations, benchmark identities, held-out truth, mappings, or historical "
            "scores. Candidate-reference evidence must not affect CellTypist suitability or model "
            "selection, or GPTCellType suitability; the returned method_evidence_scopes records "
            "and the selection contract binds that boundary. When the caller supplies an "
            "annotation scope and context SHA-256, every context value is immutable and the tool "
            "rejects any rewritten or omitted value. The Cell Annotater must follow the ordered "
            "authorized candidates and choose the first non-low-suitability method or abstain."
        ),
    ),
    StructuredTool.from_function(
        func=validate_cell_annotation_selection_tool,
        name="validate_cell_annotation_selection_tool",
        description=(
            "Required authorization boundary after method inspection and, for selected Harmony, "
            "after pair preprocessing inspection. Pass the inspector's contract ID, one selected "
            "method, exact output, comparative rationale, qualitative high/moderate/low "
            "suitability confidences and evidence-scoped rationales for all three methods. Copy "
            "selection_contract.method_evidence_scopes.method_inputs exactly into "
            "method_evidence_sources so the evidence boundary is structurally auditable. When "
            "built-in CellTypist is "
            "selected, the exact inspected model filename, comparative model rationale, and "
            "high/moderate/low suitability for every shortlisted model, plus a complete structured "
            "scope assessment for each candidate. Primary-scope coverage is the first decision "
            "criterion, followed by requested-output coverage and technical compatibility; "
            "secondary breadth cannot override weaker primary coverage. Pass the exact returned "
            "parameter-policy "
            "version, and complete scientific and operational mappings containing every field "
            "listed for that method. It rejects partial configurations, parameter drift, input "
            "mutation, unsupported GPTCellType readiness profiles, and methods outside the "
            "ordered supervised-first authorization list; "
            "structurally retains required unresolved-status language, reference disclosures, "
            "adverse reason codes, and the Harmony-only candidate-reference scope. It never "
            "authorizes the Harmony candidate as a CellTypist training source. Pass its one-time "
            "execution token "
            "and configuration SHA-256 "
            "to a backend invoked with exactly the same parameters."
        ),
    ),
    StructuredTool.from_function(
        func=inspect_anndata_preprocessing_tool,
        name="inspect_anndata_preprocessing_tool",
        description=(
            "Read-only inspection of spatial and reference AnnData expression matrices before "
            "Harmony transfer. Deterministically samples bounded rows/genes and reports dtype, "
            "integer-like fraction, negative/non-finite values, log1p metadata, and an explicit "
            "raw-count-like versus processed-continuous classification for each input. Also "
            "reports detected-gene quantiles so the agent can choose reference_min_genes. "
            "Returns explicit preprocess_spatial and preprocess_reference booleans, including "
            "when exactly one input is raw-count-like and must be normalized on its own working "
            "copy. Returns a visible error for ambiguous, invalid, or incompatibly processed "
            "states. Call this before every Harmony transfer; the general "
            "method-inspection tool's expression summary does not replace this pair inspection."
        ),
    ),
    StructuredTool.from_function(
        func=harmony_transfer_tool,
        name="harmony_transfer_tool",
        description=(
            "Transfers reference cell-type labels to spatial observations with Harmony and an "
            "explicit MLP or distance-weighted KNN classifier. Call "
            "inspect_anndata_preprocessing_tool first and pass its exact per-input "
            "preprocess_spatial and preprocess_reference booleans. The backend independently "
            "repeats the bounded "
            "preflight and rejects a mismatch before full loading. Choose and pass "
            "min_shared_genes explicitly for the "
            "assay and panel. When preprocessing a raw reference, choose and pass "
            "reference_min_genes from the inspection evidence; it filters reference cells only. "
            "Query observations are "
            "never filtered by detected-gene count. Both decisions are recorded in run metadata. "
            "Set feature_scaling explicitly: unit_variance is intended for independently "
            "normalized query/reference inputs, while none requires compatible existing scale. "
            "Gene mapping is symmetric and species-aware. The output keeps every query row and "
            "records explicit transfer status and exclusion reason columns. Bounded truth-blind "
            "embedding-distance, entropy, and predicted-prior diagnostics are recorded, with a "
            "separate support-calibrated confidence that never changes the raw transferred label. "
            "Predictions, raw confidence, support-calibrated confidence, and label are written "
            "to .obs. Relative outputs must be beneath "
            "project/outputs; existing outputs "
            "are never overwritten. Pass the one-time selection_execution_token and exact "
            "configuration_sha256 returned by validate_cell_annotation_selection_tool."
        ),
    ),
    StructuredTool.from_function(
        func=celltypist_annotation_tool,
        name="celltypist_annotation_tool",
        description=(
            "Annotate every query observation with the official CellTypist API, using exactly one "
            "explicitly selected pretrained model. Candidate-reference evidence is scoped only "
            "to Harmony and cannot authorize CellTypist training or model selection. "
            "Use only after inspect_cell_annotation_methods_tool supports the choice. It validates "
            "expression state and model-feature overlap, normalizes raw data on working copies, "
            "uses a controlled project cache, preserves query rows and order, and writes both "
            "CellTypist-specific and method-neutral prediction columns plus reproducible model "
            "metadata. Pass the inspector's majority_voting recommendation exactly; when true it "
            "uses transcriptomic overclustering only, never a spatial graph. Existing outputs are "
            "never overwritten. Pass the exact model, majority_voting value, one-time "
            "selection_execution_token, and configuration_sha256 returned by the validator."
        ),
    ),
    StructuredTool.from_function(
        func=gptcelltype_annotation_tool,
        name="gptcelltype_annotation_tool",
        description=(
            "Run the published GPTCellType marker-list strategy natively with Scanpy and "
            "TissueAgent's configured worker model. Use only after "
            "inspect_cell_annotation_methods_tool supports a reference-free choice. It creates or "
            "uses transcriptomic clusters, computes top positive Wilcoxon markers, sends only "
            "broad species/tissue context and marker names in bounded audited batches, maps one "
            "free-text label back to every query row, and preserves the original observation "
            "order. GPTCellType is cluster-level and does not produce calibrated confidence. The "
            "current readiness profile authorizes only generated clusters at resolution 1.0 with "
            "ten markers. Pass the validator's one-time token and exact configuration_sha256."
        ),
    ),
    StructuredTool.from_function(
        func=inspect_tissue_niche_input_tool,
        name="inspect_tissue_niche_input_tool",
        description=(
            "Read-only preflight for tissue-niche annotation. Inspect the truth-blinded query "
            "before choosing niche parameters. Explicit or auto cell-type/spatial keys are "
            "accepted; no future clustering key is required. Optional neighborhood_radii report "
            "sparse graph connectivity for candidate scales. Feasible diagnostics are retained "
            "when another candidate exceeds the resource limit. If none are usable, inspect "
            "another candidate before choosing a scale. It reports slide-key candidates, cell-type "
            "coverage, bounded expression-state diagnostics, coordinate extents, and within-slide "
            "nearest-neighbor distance quantiles. It does not read held-out niche labels, "
            "historical predictions, benchmark scores, or recommend a final configuration."
        ),
    ),
    StructuredTool.from_function(
        func=niche_annotation_tool,
        name="niche_annotation_tool",
        description=(
            "Runs UTAG tissue-niche discovery and internal LLM labeling on one spatial AnnData. "
            "It uses cell-type composition when available, otherwise marker and spatial summaries. "
            "Call it after inspect_tissue_niche_input_tool with an explicit evidence-backed "
            "configuration, parameter rationale, and preflight SHA-256. It writes annotated H5AD "
            "at output_path and JSON evidence/prompt/result artifacts. Pass dataset_context and "
            "the original allowed_labels. Set preview_only=True to save clustering and return its "
            "spatial/composition evidence without model labeling. Then label the chosen candidate "
            "with preview_only=False. To label existing clusters, set utag_apply_clustering=False "
            "and their actual niche_key; this skips UTAG. It performs no external reference "
            "acquisition. Explicit output_path is honored for a candidate; when omitted, the "
            "bound final destination is used. Returns niche_evidence_tsv, annotation_parameters_json, "
            "validation_summary_tsv and run_meta_json. For missing audit files or a filename "
            "mismatch after annotation, use recover_niche_annotation_artifacts_tool instead of "
            "repeating clustering or labeling. A completed annotation does not certify review."
            " Native labeling uses batches of 8 by default and checkpoints each completed batch; "
            "set label_run_id for an independent replicate and reuse the same evidence/output "
            "directory to resume interrupted labeling."
        ),
    ),
    StructuredTool.from_function(
        func=review_tissue_niches_tool,
        name="review_tissue_niches_tool",
        description=(
            "Screen every annotated niche for measured spatial conflicts, then review only "
            "flagged spatial subregions in small checkpointed batches. Uses an annotated_h5ad "
            "from the native niche tool and writes a NEW output_path; preserves primary labels "
            "and changes only regions supported by measured gene and local spatial evidence. "
            "No UTAG or whole-dataset relabeling. max_review_groups defaults to 48; deferred groups "
            "keep primary labels and are reported explicitly. At most one refinement pass. "
            "Optional use_anchor_evidence=True adds soft evidence from explicitly regional "
            "supplied cell-type names; it never directly assigns final labels. Use that option "
            "only when requested. Report n_groups_screened/reviewed/deferred and n_cells_changed."
        ),
    ),
    StructuredTool.from_function(
        func=recover_niche_annotation_artifacts_tool,
        name="recover_niche_annotation_artifacts_tool",
        description=(
            "Validate an existing niche-annotated H5AD and restore evidence, parameter and "
            "validation files from its saved receipt without clustering or model calls. "
            "Use for missing audit files or output filename mismatches. Pass annotated_h5ad "
            "and output_dir; optional output_path copies the unchanged binary to an exact "
            "destination. Optional evidence_path, parameters_path, validation_path and metadata_path "
            "satisfy exact plan filenames. It preserves predictions and does not execute or "
            "certify a separate spatial review."
        ),
    ),
]
