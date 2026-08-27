"""Tool definitions for the Cell Annotater Agent."""

from __future__ import annotations

from typing import Any

from langchain.tools import StructuredTool

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
            "backend. It reports three method-scoped evidence branches: Harmony-only candidate-"
            "reference query-panel separability plus "
            "label/source coherence, exact feature, label-inventory, and retained-coefficient "
            "support for every agent-shortlisted official CellTypist model, and query-only "
            "GPTCellType cluster/marker "
            "readiness. It preserves the raw evidence and emits versioned categorical method "
            "assessments plus selection-policy v6 default candidates using fixed majority and "
            "twofold structural guardrails. Its structured rationale guard marks unknown "
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
            "rejects any rewritten or omitted value. The Cell Annotater must compare all "
            "three method-scoped assessments and explain the final choice."
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
            "mutation, unsupported GPTCellType readiness profiles, methods outside policy, and "
            "a selected method rated below another runnable method; "
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
            "Gene mapping is symmetric and species-aware. The output keeps every query row and "
            "records explicit transfer status and exclusion reason columns. Predictions, "
            "confidence, and label are written to .obs. Relative outputs must be beneath "
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
        func=niche_annotation_tool,
        name="niche_annotation_tool",
        description=(
            "Runs UTAG tissue-niche discovery and internal LLM labeling on one spatial AnnData. "
            "It uses cell-type composition when available, otherwise marker and spatial summaries. "
            "It writes annotated H5AD and JSON prompt/result artifacts without CELLxGENE, Harmony, "
            "or external reference acquisition."
        ),
    ),
]
