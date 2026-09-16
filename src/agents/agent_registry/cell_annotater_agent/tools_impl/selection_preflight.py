"""Bounded, leakage-safe preflights for cell-annotation method selection."""

from __future__ import annotations

import hashlib
import os
import re
import time
import unicodedata
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

import anndata as ad
import numpy as np
import pandas as pd
import requests
from scipy import sparse
from sklearn.metrics import balanced_accuracy_score, f1_score
from sklearn.model_selection import GroupKFold, StratifiedKFold

from agents.agent_registry.cell_annotater_agent.tools_impl.harmony_transfer import (
    GENE_ID_COLUMNS,
    GENE_SYMBOL_COLUMNS,
)


MAX_REFERENCE_CELLS = 8192
MAX_REFERENCE_FEATURES = 2048
MAX_REFERENCE_LABELS = 128
MAX_CELLS_PER_LABEL = 128
REFERENCE_CV_FOLDS = 3
REFERENCE_GROUP_FOLDS = 3
PREFLIGHT_RANDOM_STATE = 42
MAX_LABEL_EXAMPLES = 20
MAX_LEXICAL_HIERARCHY_LABELS = 512
MAX_CELLTYPIST_MODEL_BYTES = 512 * 1024 * 1024
CELLTYPIST_CONNECT_TIMEOUT_SECONDS = 5
CELLTYPIST_READ_TIMEOUT_SECONDS = 15
CELLTYPIST_TOTAL_DOWNLOAD_SECONDS = 60
CELLTYPIST_OFFICIAL_HOST = "celltypist.cog.sanger.ac.uk"
CELLTYPIST_BACKEND_MIN_FEATURE_OVERLAP = 50
METHOD_ASSESSMENT_VERSION = "cell_annotation_method_assessment_v1"
SELECTION_POLICY_VERSION = "cell_annotation_selection_policy_v6"
RATIONALE_GUARD_VERSION = "cell_annotation_rationale_guard_v1"
STRUCTURAL_MAJORITY_FRACTION = 0.5
GENERALIZATION_COLLAPSE_RATIO = 0.5
METHOD_ORDER = ("harmony", "celltypist", "gptcelltype")

_ONTOLOGY_ID_RE = re.compile(r"^CL:\d{7}$")
_PLACEHOLDER_LABELS = {
    "cell",
    "cells",
    "n/a",
    "na",
    "not applicable",
    "other",
    "unassigned",
    "unknown",
}
_SOURCE_COLUMNS = ("dataset_id", "source_dataset_id")
_ONTOLOGY_COLUMNS = ("cell_type_ontology_term_id",)


def _bounded_fraction(value: Any) -> float | None:
    """Return a finite fraction without coercing booleans or invalid values."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(numeric) or numeric < 0.0 or numeric > 1.0:
        return None
    return numeric


def _categorical_assessment(
    *,
    prerequisites: str,
    evidence_tier: str,
    risk_tier: str,
    supporting_codes: Sequence[str] = (),
    adverse_codes: Sequence[str] = (),
    unresolved_codes: Sequence[str] = (),
    evidence_annotations: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one stable categorical method assessment."""
    supporting = list(dict.fromkeys(supporting_codes))
    adverse = list(dict.fromkeys(adverse_codes))
    unresolved = list(dict.fromkeys(unresolved_codes))
    return {
        "version": METHOD_ASSESSMENT_VERSION,
        "prerequisites": prerequisites,
        "evidence_tier": evidence_tier,
        "risk_tier": risk_tier,
        "reason_codes": [*supporting, *adverse],
        "supporting_codes": supporting,
        "adverse_codes": adverse,
        "unresolved_codes": unresolved,
        "evidence_annotations": dict(evidence_annotations or {}),
    }


def assess_harmony_selection_evidence(
    reference_preflight: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Categorize Harmony evidence without query labels or outcome calibration."""
    if not isinstance(reference_preflight, Mapping):
        return _categorical_assessment(
            prerequisites="unknown",
            evidence_tier="unknown",
            risk_tier="unknown",
            unresolved_codes=("reference_preflight_unavailable",),
        )
    if reference_preflight.get("status") not in {"success", "partial"}:
        return _categorical_assessment(
            prerequisites="unknown",
            evidence_tier="unknown",
            risk_tier="unknown",
            unresolved_codes=("reference_preflight_not_assessable",),
        )

    feature_compatibility = reference_preflight.get("feature_compatibility", {})
    label_coherence = reference_preflight.get("label_coherence", {})
    n_matched_features = feature_compatibility.get("n_matched_features")
    n_labels = label_coherence.get("n_raw_labels")
    if (
        not isinstance(n_matched_features, int)
        or n_matched_features < 2
        or not isinstance(n_labels, int)
        or n_labels < 2
    ):
        return _categorical_assessment(
            prerequisites="not_met",
            evidence_tier="adverse",
            risk_tier="high",
            adverse_codes=("reference_panel_prerequisites_not_met",),
        )

    source = label_coherence.get("source_dependence", {})
    source_status = source.get("status")
    label_exclusive = _bounded_fraction(source.get("single_source_label_fraction"))
    cell_exclusive = _bounded_fraction(source.get("cell_fraction_in_single_source_labels"))
    source_exclusivity = [
        value for value in (label_exclusive, cell_exclusive) if value is not None
    ]
    any_source_exclusivity = bool(source_exclusivity and max(source_exclusivity) > 0.0)
    majority_source_exclusivity = bool(
        source_exclusivity
        and max(source_exclusivity) >= STRUCTURAL_MAJORITY_FRACTION
    )

    discriminability = reference_preflight.get(
        "reference_only_panel_discriminability",
        {},
    )
    stratified = discriminability.get("stratified_cv", {})
    grouped = discriminability.get("source_grouped_cv", {})
    grouped_status = grouped.get("status")
    scorable_label_fraction = _bounded_fraction(grouped.get("scorable_label_fraction"))
    scorable_observation_fraction = _bounded_fraction(
        grouped.get("scorable_observation_fraction")
    )
    grouped_coverages = [
        value
        for value in (scorable_label_fraction, scorable_observation_fraction)
        if value is not None
    ]
    minimum_grouped_coverage = min(grouped_coverages) if grouped_coverages else None
    minority_grouped_coverage = bool(
        minimum_grouped_coverage is not None
        and minimum_grouped_coverage < STRUCTURAL_MAJORITY_FRACTION
    )

    stratified_macro_f1 = _bounded_fraction(stratified.get("macro_f1"))
    grouped_macro_f1 = _bounded_fraction(grouped.get("macro_f1"))
    generalization_ratio = None
    if (
        stratified_macro_f1 is not None
        and grouped_macro_f1 is not None
        and stratified_macro_f1 > 0.0
    ):
        generalization_ratio = grouped_macro_f1 / stratified_macro_f1
    twofold_generalization_collapse = bool(
        generalization_ratio is not None
        and generalization_ratio < GENERALIZATION_COLLAPSE_RATIO
    )
    high_source_confounded_risk = bool(
        source_status == "success"
        and majority_source_exclusivity
        and (minority_grouped_coverage or twofold_generalization_collapse)
    )

    annotations = {
        "stratified_cv": {
            "source_confounded": bool(
                source_status == "success" and any_source_exclusivity
            ),
            "affirmative_for_selection": not (
                source_status == "success" and any_source_exclusivity
            ),
            "reason": (
                "Within-reference stratification cannot distinguish labels from source when "
                "any labels occur in only one source."
                if source_status == "success" and any_source_exclusivity
                else "No label-source exclusivity was detected in the bounded reference sample."
            ),
        },
        "source_grouped_cv": {
            "status": grouped_status,
            "conditional_on_scorable_subset": grouped_status == "success",
            "scorable_label_fraction": scorable_label_fraction,
            "scorable_observation_fraction": scorable_observation_fraction,
            "minimum_coverage_fraction": minimum_grouped_coverage,
            "macro_f1_relative_to_stratified": generalization_ratio,
            "affirmative_for_selection": bool(
                grouped_status == "success"
                and not minority_grouped_coverage
                and not twofold_generalization_collapse
            ),
        },
        "fixed_guardrails": {
            "structural_majority_fraction": STRUCTURAL_MAJORITY_FRACTION,
            "generalization_collapse_ratio": GENERALIZATION_COLLAPSE_RATIO,
        },
    }
    supporting = ["reference_query_panel_prerequisites_met"]
    adverse: list[str] = []
    unresolved = ["query_population_coverage_unverified"]
    if label_exclusive is not None and label_exclusive >= STRUCTURAL_MAJORITY_FRACTION:
        adverse.append("majority_reference_labels_source_exclusive")
    if cell_exclusive is not None and cell_exclusive >= STRUCTURAL_MAJORITY_FRACTION:
        adverse.append("majority_reference_cells_in_source_exclusive_labels")
    if minority_grouped_coverage:
        adverse.append("source_grouped_cv_minority_coverage")
    if twofold_generalization_collapse:
        adverse.append("source_generalization_twofold_collapse")

    if high_source_confounded_risk:
        return _categorical_assessment(
            prerequisites="met",
            evidence_tier="adverse",
            risk_tier="high",
            supporting_codes=supporting,
            adverse_codes=adverse,
            unresolved_codes=unresolved,
            evidence_annotations=annotations,
        )

    if source_status == "success":
        if any_source_exclusivity or minority_grouped_coverage or twofold_generalization_collapse:
            if any_source_exclusivity:
                adverse.append("reference_label_source_exclusivity_present")
            return _categorical_assessment(
                prerequisites="met",
                evidence_tier="conditional",
                risk_tier="moderate",
                supporting_codes=supporting,
                adverse_codes=adverse,
                unresolved_codes=unresolved,
                evidence_annotations=annotations,
            )
        supporting.append("source_grouped_reference_generalization_supported")
        return _categorical_assessment(
            prerequisites="met",
            evidence_tier="strong",
            risk_tier="low",
            supporting_codes=supporting,
            unresolved_codes=unresolved,
            evidence_annotations=annotations,
        )

    if source_status == "not_applicable_single_source":
        unresolved.append("source_generalization_not_testable_single_source")
        return _categorical_assessment(
            prerequisites="met",
            evidence_tier="conditional",
            risk_tier="moderate",
            supporting_codes=supporting,
            unresolved_codes=unresolved,
            evidence_annotations=annotations,
        )

    unresolved.append("reference_source_structure_unavailable")
    return _categorical_assessment(
        prerequisites="met",
        evidence_tier="conditional",
        risk_tier="unknown",
        supporting_codes=supporting,
        unresolved_codes=unresolved,
        evidence_annotations=annotations,
    )


def _celltypist_query_expression_prerequisite(
    query_matrix: Mapping[str, Any] | None,
) -> tuple[str, list[str], list[str], list[str], dict[str, Any]]:
    """Classify whether the inspected query expression can enter CellTypist."""
    if not isinstance(query_matrix, Mapping):
        return (
            "unknown",
            [],
            [],
            ["celltypist_query_expression_state_unavailable"],
            {},
        )

    state = query_matrix.get("expression_state")
    processed_state = query_matrix.get("processed_expression_state")
    log1p_metadata_present = query_matrix.get("log1p_metadata_present")
    annotation = {
        "expression_state": state,
        "processed_expression_state": processed_state,
        "log1p_metadata_present": log1p_metadata_present,
    }
    shape = query_matrix.get("shape")
    empty_shape = (
        isinstance(shape, Sequence)
        and not isinstance(shape, (str, bytes))
        and len(shape) == 2
        and any(value == 0 for value in shape)
    )
    sampled_nonzero = query_matrix.get("sampled_nonzero_values")

    if state == "invalid":
        return (
            "not_met",
            [],
            ["celltypist_query_expression_invalid"],
            [],
            annotation,
        )
    if state == "empty" or empty_shape or (
        state == "ambiguous" and sampled_nonzero == 0
    ):
        return (
            "not_met",
            [],
            ["celltypist_query_expression_empty"],
            [],
            annotation,
        )
    if state == "raw_count_like":
        return (
            "met",
            ["celltypist_query_raw_counts_compatible"],
            [],
            [],
            annotation,
        )
    if state == "processed_continuous":
        if (
            log1p_metadata_present is True
            and processed_state == "log1p_normalized"
        ):
            return (
                "met",
                ["celltypist_query_explicit_log1p_compatible"],
                [],
                ["celltypist_query_log1p_target_sum_unverified"],
                annotation,
            )
        if log1p_metadata_present is not True:
            adverse_code = (
                "celltypist_query_processed_expression_missing_explicit_log1p"
            )
        else:
            adverse_code = "celltypist_query_processed_expression_incompatible"
        return ("not_met", [], [adverse_code], [], annotation)
    return (
        "unknown",
        [],
        [],
        ["celltypist_query_expression_state_unavailable"],
        annotation,
    )


def assess_celltypist_selection_evidence(
    model_preflight: Mapping[str, Any] | None,
    query_matrix: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Categorize CellTypist model and query-expression compatibility."""
    (
        expression_prerequisite,
        expression_supporting,
        expression_adverse,
        expression_unresolved,
        expression_annotation,
    ) = _celltypist_query_expression_prerequisite(query_matrix)
    expression_annotations = (
        {"query_expression": expression_annotation}
        if expression_annotation
        else {}
    )
    if expression_prerequisite == "not_met":
        return _categorical_assessment(
            prerequisites="not_met",
            evidence_tier="adverse",
            risk_tier="high",
            adverse_codes=expression_adverse,
            evidence_annotations=expression_annotations,
        )
    if expression_prerequisite == "unknown":
        return _categorical_assessment(
            prerequisites="unknown",
            evidence_tier="unknown",
            risk_tier="unknown",
            unresolved_codes=expression_unresolved,
            evidence_annotations=expression_annotations,
        )

    if not isinstance(model_preflight, Mapping) or model_preflight.get("status") != "success":
        return _categorical_assessment(
            prerequisites="unknown",
            evidence_tier="unknown",
            risk_tier="unknown",
            supporting_codes=expression_supporting,
            unresolved_codes=(
                *expression_unresolved,
                "celltypist_model_preflight_not_assessable",
            ),
            evidence_annotations=expression_annotations,
        )

    compatibility = model_preflight.get("feature_compatibility", {})
    if compatibility.get("meets_backend_min_feature_overlap") is not True:
        return _categorical_assessment(
            prerequisites="not_met",
            evidence_tier="adverse",
            risk_tier="high",
            supporting_codes=expression_supporting,
            adverse_codes=("celltypist_backend_feature_minimum_not_met",),
            unresolved_codes=expression_unresolved,
            evidence_annotations=expression_annotations,
        )

    model = model_preflight.get("model", {})
    context_mismatches = model.get("context_mismatches")
    context_mismatches = context_mismatches if isinstance(context_mismatches, list) else []
    matched_terms = model.get("matched_context_terms")
    matched_terms = matched_terms if isinstance(matched_terms, list) else []
    matched_fields = {
        item.get("field")
        for item in matched_terms
        if isinstance(item, Mapping) and isinstance(item.get("field"), str)
    }
    exact_species_tissue_context = {"species", "tissue"}.issubset(matched_fields)

    coefficient_support = model_preflight.get("coefficient_support", {})
    retained = coefficient_support.get("retained_absolute_weight_fraction", {})
    retained_p95 = _bounded_fraction(retained.get("p95"))
    zero_weight_rows = coefficient_support.get("n_zero_total_weight_rows")
    zero_weight_rows = zero_weight_rows if isinstance(zero_weight_rows, int) else None
    minority_classifier_signal = bool(
        retained_p95 is not None
        and retained_p95 < STRUCTURAL_MAJORITY_FRACTION
    )

    annotations = {
        **expression_annotations,
        "feature_compatibility": {
            "backend_runnable": True,
            "n_matched_features": compatibility.get("n_matched_features"),
        },
        "coefficient_support": {
            "retained_absolute_weight_fraction_p95": retained_p95,
            "majority_fraction_guardrail": STRUCTURAL_MAJORITY_FRACTION,
            "majority_signal_retained_for_at_least_five_percent_of_rows": bool(
                retained_p95 is not None
                and retained_p95 >= STRUCTURAL_MAJORITY_FRACTION
            ),
        },
        "biological_context": {
            "matched_fields": sorted(matched_fields),
            "context_mismatch_count": len(context_mismatches),
            "exact_species_tissue_context": exact_species_tissue_context,
        },
    }
    supporting = [*expression_supporting, "celltypist_backend_feature_minimum_met"]
    adverse: list[str] = []
    unresolved = [
        *expression_unresolved,
        "celltypist_query_population_coverage_unverified",
        "celltypist_query_training_independence_unknown",
    ]
    if exact_species_tissue_context and not context_mismatches:
        supporting.append("celltypist_species_tissue_context_matched")
    else:
        unresolved.append("celltypist_species_tissue_context_not_fully_matched")
    if context_mismatches:
        adverse.append("celltypist_context_mismatch_present")
    if zero_weight_rows is not None and zero_weight_rows > 0:
        adverse.append("celltypist_zero_weight_classifier_rows")
    if minority_classifier_signal:
        adverse.append("celltypist_minority_classifier_signal_retained")
    elif retained_p95 is None:
        unresolved.append("celltypist_coefficient_support_unknown")
    else:
        supporting.append("celltypist_majority_classifier_signal_retained")

    if context_mismatches or minority_classifier_signal or (
        zero_weight_rows is not None and zero_weight_rows > 0
    ):
        return _categorical_assessment(
            prerequisites="met",
            evidence_tier="adverse",
            risk_tier="high",
            supporting_codes=supporting,
            adverse_codes=adverse,
            unresolved_codes=unresolved,
            evidence_annotations=annotations,
        )
    if exact_species_tissue_context and retained_p95 is not None:
        return _categorical_assessment(
            prerequisites="met",
            evidence_tier="strong",
            risk_tier="moderate",
            supporting_codes=supporting,
            unresolved_codes=unresolved,
            evidence_annotations=annotations,
        )
    return _categorical_assessment(
        prerequisites="met",
        evidence_tier="conditional",
        risk_tier="unknown",
        supporting_codes=supporting,
        unresolved_codes=unresolved,
        evidence_annotations=annotations,
    )


def assess_gptcelltype_selection_evidence(
    readiness: Mapping[str, Any] | None,
    worker_llm: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Categorize GPTCellType readiness while keeping unavailable evidence neutral."""
    credential = (
        worker_llm.get("credential_available")
        if isinstance(worker_llm, Mapping)
        else None
    )
    if credential is False:
        return _categorical_assessment(
            prerequisites="not_met",
            evidence_tier="adverse",
            risk_tier="high",
            adverse_codes=("gptcelltype_worker_llm_unavailable",),
        )
    if not isinstance(readiness, Mapping) or readiness.get("status") != "success":
        unresolved = ["gptcelltype_readiness_not_assessable"]
        if credential is not True:
            unresolved.append("gptcelltype_worker_llm_availability_unknown")
        return _categorical_assessment(
            prerequisites="unknown",
            evidence_tier="unknown",
            risk_tier="unknown",
            unresolved_codes=unresolved,
        )

    readiness_grade = readiness.get("assessment")
    if readiness_grade not in {"strong", "moderate", "weak"}:
        return _categorical_assessment(
            prerequisites="unknown",
            evidence_tier="unknown",
            risk_tier="unknown",
            unresolved_codes=("gptcelltype_readiness_grade_unknown",),
        )
    if credential is not True:
        return _categorical_assessment(
            prerequisites="unknown",
            evidence_tier=readiness_grade if readiness_grade != "moderate" else "conditional",
            risk_tier="unknown",
            supporting_codes=(f"gptcelltype_{readiness_grade}_query_readiness",),
            unresolved_codes=("gptcelltype_worker_llm_availability_unknown",),
        )

    annotations = {
        "readiness": {
            "assessment": readiness_grade,
            "component_grades": readiness.get("component_grades"),
        }
    }
    unresolved = ["gptcelltype_cluster_identity_not_biological_guarantee"]
    if readiness_grade == "strong":
        return _categorical_assessment(
            prerequisites="met",
            evidence_tier="strong",
            risk_tier="moderate",
            supporting_codes=("gptcelltype_strong_query_readiness",),
            unresolved_codes=unresolved,
            evidence_annotations=annotations,
        )
    if readiness_grade == "moderate":
        return _categorical_assessment(
            prerequisites="met",
            evidence_tier="conditional",
            risk_tier="moderate",
            supporting_codes=("gptcelltype_moderate_query_readiness",),
            unresolved_codes=unresolved,
            evidence_annotations=annotations,
        )
    return _categorical_assessment(
        prerequisites="met",
        evidence_tier="adverse",
        risk_tier="high",
        adverse_codes=("gptcelltype_weak_query_readiness",),
        unresolved_codes=unresolved,
        evidence_annotations=annotations,
    )


def build_method_selection_policy(
    method_assessments: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Apply categorical dominance without learning from benchmark outcomes."""
    assessments = {
        method: method_assessments.get(method, {})
        for method in METHOD_ORDER
    }
    eligible_non_high = {
        method: assessment
        for method, assessment in assessments.items()
        if assessment.get("prerequisites") == "met"
        and assessment.get("risk_tier") != "high"
    }
    strong = [
        method
        for method in METHOD_ORDER
        if eligible_non_high.get(method, {}).get("evidence_tier") == "strong"
    ]
    conditional = [
        method
        for method in METHOD_ORDER
        if eligible_non_high.get(method, {}).get("evidence_tier") == "conditional"
    ]
    if strong:
        default_candidates = strong
        dominant_evidence_tier = "strong"
    elif conditional:
        default_candidates = conditional
        dominant_evidence_tier = "conditional"
    else:
        default_candidates = []
        dominant_evidence_tier = None

    fallback_candidates = [
        method
        for method in METHOD_ORDER
        if assessments[method].get("prerequisites") == "met"
        and method not in default_candidates
    ]
    unknown_candidates = [
        method
        for method in METHOD_ORDER
        if assessments[method].get("prerequisites") == "unknown"
    ]
    excluded_methods = [
        method
        for method in METHOD_ORDER
        if assessments[method].get("prerequisites") == "not_met"
    ]
    high_risk_methods = [
        method
        for method in METHOD_ORDER
        if assessments[method].get("risk_tier") == "high"
    ]
    status = (
        "policy_resolved"
        if len(default_candidates) == 1
        else "requires_agent_reasoning"
    )
    claim_status_by_method = {
        method: (
            "affirmative_candidate"
            if method in default_candidates
            else "fallback_only"
            if method in fallback_candidates
            else "best_supported_unresolved"
            if method in unknown_candidates
            else "ineligible"
        )
        for method in METHOD_ORDER
    }
    return {
        "version": SELECTION_POLICY_VERSION,
        "status": status,
        "default_candidates": default_candidates,
        "fallback_candidates": fallback_candidates,
        "unknown_candidates": unknown_candidates,
        "excluded_methods": excluded_methods,
        "high_risk_methods": high_risk_methods,
        "dominant_evidence_tier": dominant_evidence_tier,
        "tie_requires_agent_reasoning": len(default_candidates) != 1,
        "selection_rule": (
            "Choose from the strongest non-high-risk affirmative tier. High-risk methods are "
            "fallbacks only when no non-high-risk affirmative method exists or the user "
            "explicitly requests an otherwise runnable method."
        ),
        "unknown_evidence_rule": (
            "Unknown evidence is neutral: it is neither affirmative nor adverse and never "
            "satisfies a prerequisite by itself."
        ),
        "rationale_guard": {
            "version": RATIONALE_GUARD_VERSION,
            "claim_status_by_method": claim_status_by_method,
            "required_exact_phrase_by_claim_status": {
                "best_supported_unresolved": "best-supported unresolved option",
            },
            "required_disclosure_codes": [],
            "reference_disclosures": [],
            "rule": (
                "Describe an unknown selected candidate only as the best-supported unresolved "
                "option, and include every required disclosure code verbatim. Do not turn "
                "unavailable evidence into an affirmative superiority claim."
            ),
        },
        "fixed_guardrails": {
            "structural_majority_fraction": STRUCTURAL_MAJORITY_FRACTION,
            "generalization_collapse_ratio": GENERALIZATION_COLLAPSE_RATIO,
            "basis": [
                "A majority boundary identifies when most labels, cells, or learned weight are "
                "affected.",
                "A twofold relative collapse flags source generalization far below ordinary "
                "within-reference separation.",
                "No query labels, benchmark identities, historical outcomes, or fitted selection "
                "scores are used.",
            ],
        },
    }


def _unknown_result(stage: str, reason: str, exc: Exception | None = None) -> dict[str, Any]:
    """Return a structured unknown result without interpreting failure as poor suitability."""
    result: dict[str, Any] = {
        "status": "not_assessable" if exc is None else "error",
        "assessment": "unknown",
        "stage": stage,
        "reason": reason,
    }
    if exc is not None:
        result["error_type"] = type(exc).__name__
        result["message"] = str(exc)
    return result


def _normalize_label(value: str) -> str:
    """Normalize a label for structural comparisons without changing biological meaning."""
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _bounded_examples(values: Sequence[Any]) -> list[Any]:
    """Return deterministic bounded examples."""
    return list(values[:MAX_LABEL_EXAMPLES])


def _lexical_hierarchy_candidates(labels: Sequence[str]) -> dict[str, Any]:
    """Find heuristic token-containment pairs that may indicate mixed label granularity."""
    if len(labels) > MAX_LEXICAL_HIERARCHY_LABELS:
        return {
            "status": "not_assessable",
            "reason": (
                f"{len(labels)} labels exceed the lexical-hierarchy bound of "
                f"{MAX_LEXICAL_HIERARCHY_LABELS}."
            ),
            "n_candidate_pairs": None,
            "examples": [],
        }
    tokenized = {
        label: frozenset(re.findall(r"[a-z0-9]+", _normalize_label(label)))
        for label in labels
    }
    candidates: list[dict[str, str]] = []
    ordered = sorted(labels, key=lambda value: (_normalize_label(value), value))
    for index, parent in enumerate(ordered):
        parent_tokens = tokenized[parent]
        if not parent_tokens:
            continue
        for child in ordered[index + 1 :]:
            child_tokens = tokenized[child]
            if parent_tokens < child_tokens:
                candidates.append({"broader_candidate": parent, "narrower_candidate": child})
            elif child_tokens < parent_tokens:
                candidates.append({"broader_candidate": child, "narrower_candidate": parent})
    unique = {
        (item["broader_candidate"], item["narrower_candidate"]): item
        for item in candidates
    }
    ordered_candidates = [
        unique[key]
        for key in sorted(
            unique,
            key=lambda pair: (
                _normalize_label(pair[0]),
                _normalize_label(pair[1]),
                pair,
            ),
        )
    ]
    return {
        "status": "heuristic_only",
        "n_candidate_pairs": int(len(ordered_candidates)),
        "examples": _bounded_examples(ordered_candidates),
        "limitation": "Token containment is not a Cell Ontology ancestor assertion.",
    }


def summarize_label_coherence(
    labels: Sequence[Any],
    *,
    sources: Sequence[Any] | None = None,
    ontology_ids: Sequence[Any] | None = None,
) -> dict[str, Any]:
    """Summarize label consistency, granularity warnings, and source exclusivity."""
    labels_series = pd.Series(labels, dtype="string")
    cleaned = labels_series.fillna("").str.strip()
    valid_mask = cleaned.ne("")
    valid = cleaned[valid_mask].astype(str)
    raw_labels = sorted(set(valid), key=lambda value: (_normalize_label(value), value))

    normalized_to_raw: dict[str, set[str]] = {}
    for label in raw_labels:
        normalized_to_raw.setdefault(_normalize_label(label), set()).add(label)
    collision_groups = [
        sorted(values, key=lambda value: (_normalize_label(value), value))
        for values in normalized_to_raw.values()
        if len(values) > 1
    ]
    collision_groups.sort(key=lambda values: tuple(_normalize_label(value) for value in values))
    placeholders = [
        label for label in raw_labels if _normalize_label(label) in _PLACEHOLDER_LABELS
    ]
    placeholder_value_mask = valid.map(
        lambda label: _normalize_label(label) in _PLACEHOLDER_LABELS
    )
    n_placeholder_values = int(placeholder_value_mask.sum())

    ontology: dict[str, Any]
    if ontology_ids is None:
        ontology = {
            "status": "not_available",
            "n_labels_with_ontology_id": 0,
            "n_invalid_ontology_ids": 0,
            "n_labels_with_multiple_ids": 0,
            "n_ids_with_multiple_labels": 0,
            "hierarchy_status": "not_assessable_without_ontology_graph",
        }
    else:
        ontology_series = pd.Series(ontology_ids, dtype="string")
        if len(ontology_series) != len(labels_series):
            return _unknown_result(
                "summarize_label_coherence",
                "ontology_ids must have the same length as labels.",
            )
        pairs = pd.DataFrame(
            {
                "label": cleaned,
                "ontology_id": ontology_series.fillna("").str.strip(),
            }
        )
        pairs = pairs[(pairs["label"] != "") & (pairs["ontology_id"] != "")]
        invalid_ids = sorted(
            {
                value
                for value in pairs["ontology_id"].astype(str)
                if not _ONTOLOGY_ID_RE.fullmatch(value)
            }
        )
        valid_pairs = pairs[
            pairs["ontology_id"]
            .astype(str)
            .map(lambda value: bool(_ONTOLOGY_ID_RE.fullmatch(value)))
        ]
        label_to_ids = valid_pairs.groupby("label")["ontology_id"].nunique()
        id_to_labels = valid_pairs.groupby("ontology_id")["label"].nunique()
        ontology = {
            "status": "provided_ids_only",
            "n_labels_with_ontology_id": int(valid_pairs["label"].nunique()),
            "n_invalid_ontology_ids": int(len(invalid_ids)),
            "invalid_ontology_id_examples": _bounded_examples(invalid_ids),
            "n_labels_with_multiple_ids": int((label_to_ids > 1).sum()),
            "n_ids_with_multiple_labels": int((id_to_labels > 1).sum()),
            "hierarchy_status": "not_assessable_without_ontology_graph",
        }

    source_dependence: dict[str, Any]
    if sources is None:
        source_dependence = {"status": "not_available"}
    else:
        sources_series = pd.Series(sources, dtype="string")
        if len(sources_series) != len(labels_series):
            return _unknown_result(
                "summarize_label_coherence",
                "sources must have the same length as labels.",
            )
        source_frame = pd.DataFrame(
            {
                "label": cleaned,
                "source": sources_series.fillna("").str.strip(),
            }
        )
        source_frame = source_frame[
            (source_frame["label"] != "") & (source_frame["source"] != "")
        ]
        n_sources = int(source_frame["source"].nunique())
        if n_sources < 2:
            source_dependence = {
                "status": "not_applicable_single_source",
                "n_sources": n_sources,
            }
        else:
            source_counts = source_frame.groupby("label")["source"].nunique()
            single_source_labels = set(source_counts[source_counts == 1].index.astype(str))
            source_dependence = {
                "status": "success",
                "n_sources": n_sources,
                "n_labels_with_source": int(len(source_counts)),
                "n_single_source_labels": int(len(single_source_labels)),
                "single_source_label_fraction": float(
                    len(single_source_labels) / max(1, len(source_counts))
                ),
                "cell_fraction_in_single_source_labels": float(
                    source_frame["label"].isin(single_source_labels).mean()
                ),
                "single_source_label_examples": _bounded_examples(
                    sorted(
                        single_source_labels,
                        key=lambda value: (_normalize_label(value), value),
                    )
                ),
            }

    return {
        "status": "success",
        "n_values": int(len(labels_series)),
        "n_missing_or_empty": int((~valid_mask).sum()),
        "n_raw_labels": int(len(raw_labels)),
        "n_normalized_labels": int(len(normalized_to_raw)),
        "n_normalization_collision_groups": int(len(collision_groups)),
        "normalization_collision_examples": _bounded_examples(collision_groups),
        "n_placeholder_labels": int(len(placeholders)),
        "placeholder_label_examples": _bounded_examples(placeholders),
        "n_placeholder_labeled_observations": n_placeholder_values,
        "placeholder_labeled_observation_fraction": float(
            n_placeholder_values / max(1, len(valid))
        ),
        "lexical_hierarchy_candidates": _lexical_hierarchy_candidates(raw_labels),
        "ontology": ontology,
        "source_dependence": source_dependence,
    }


def _clean_feature_representations(
    representations: Mapping[str, Sequence[Any]],
) -> dict[str, list[str]]:
    """Normalize feature representations while preserving deterministic order."""
    cleaned: dict[str, list[str]] = {}
    for name, values in sorted(representations.items()):
        seen: set[str] = set()
        retained: list[str] = []
        for value in values:
            text = str(value).strip()
            if not text or text.casefold() in {"na", "nan", "none"} or text in seen:
                continue
            seen.add(text)
            retained.append(text)
        if retained:
            cleaned[str(name)] = retained
    return cleaned


def _candidate_feature_representations(dataset: ad.AnnData) -> dict[str, list[str]]:
    """Return allowed feature representations and their original row order."""
    representations = {"var_names": [str(value).strip() for value in dataset.var_names]}
    for column in (*GENE_SYMBOL_COLUMNS, *GENE_ID_COLUMNS):
        if column in dataset.var:
            representations[f"var['{column}']"] = [
                str(value).strip() for value in dataset.var[column]
            ]
    return representations


def _match_feature_representations(
    query_representations: Mapping[str, Sequence[Any]],
    candidate_representations: Mapping[str, Sequence[Any]],
) -> dict[str, Any]:
    """Find the strongest unique case-insensitive feature match without returning names."""
    query_clean = _clean_feature_representations(query_representations)
    best: dict[str, Any] | None = None
    for query_name, query_values in query_clean.items():
        query_folded: dict[str, list[str]] = {}
        for value in query_values:
            query_folded.setdefault(value.casefold(), []).append(value)
        for candidate_name, candidate_values_raw in sorted(candidate_representations.items()):
            candidate_values = [str(value).strip() for value in candidate_values_raw]
            candidate_folded: dict[str, list[int]] = {}
            for index, value in enumerate(candidate_values):
                if value:
                    candidate_folded.setdefault(value.casefold(), []).append(index)
            matched_indices: list[int] = []
            case_aligned = 0
            ambiguous = 0
            for folded, originals in query_folded.items():
                candidates = candidate_folded.get(folded, [])
                if len(originals) != 1 or len(candidates) != 1:
                    if candidates:
                        ambiguous += 1
                    continue
                candidate_index = candidates[0]
                matched_indices.append(candidate_index)
                if originals[0] != candidate_values[candidate_index]:
                    case_aligned += 1
            matched_indices = sorted(set(matched_indices))
            result = {
                "query_representation": query_name,
                "candidate_representation": candidate_name,
                "n_query_features": int(len(query_values)),
                "n_candidate_features": int(len(candidate_values)),
                "n_matched_features": int(len(matched_indices)),
                "query_feature_fraction": float(
                    len(matched_indices) / max(1, len(query_values))
                ),
                "candidate_feature_fraction": float(
                    len(matched_indices) / max(1, len(candidate_values))
                ),
                "n_case_aligned_features": int(case_aligned),
                "n_ambiguous_casefold_matches": int(ambiguous),
                "_matched_candidate_indices": matched_indices,
                "_candidate_values": candidate_values,
            }
            key = (
                result["n_matched_features"],
                -result["n_ambiguous_casefold_matches"],
                query_name == "var_names",
                candidate_name == "var_names",
                query_name,
                candidate_name,
            )
            if best is None or key > best["_selection_key"]:
                result["_selection_key"] = key
                best = result
    if best is None:
        return {
            "query_representation": None,
            "candidate_representation": None,
            "n_query_features": 0,
            "n_candidate_features": 0,
            "n_matched_features": 0,
            "query_feature_fraction": 0.0,
            "candidate_feature_fraction": 0.0,
            "n_case_aligned_features": 0,
            "n_ambiguous_casefold_matches": 0,
            "_matched_candidate_indices": [],
            "_candidate_values": [],
        }
    best.pop("_selection_key")
    return best


def _distribution(values: np.ndarray) -> dict[str, float | None]:
    """Return stable quantiles for a finite numeric vector."""
    finite = np.asarray(values, dtype=float)
    finite = finite[np.isfinite(finite)]
    if finite.size == 0:
        return {
            "minimum": None,
            "p05": None,
            "median": None,
            "p95": None,
            "maximum": None,
        }
    return {
        "minimum": float(np.min(finite)),
        "p05": float(np.quantile(finite, 0.05)),
        "median": float(np.median(finite)),
        "p95": float(np.quantile(finite, 0.95)),
        "maximum": float(np.max(finite)),
    }


def _sha256(path: Path) -> str:
    """Hash an artifact without loading it into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _bounded_celltypist_model_loader(
    model_record: Mapping[str, Any],
    cache_root: Path,
) -> tuple[Any, dict[str, Any]]:
    """Load one official CellTypist artifact through a bounded download."""
    model_name = str(model_record.get("model") or "").strip()
    url = str(model_record.get("url") or "").strip()
    if Path(model_name).name != model_name or not model_name.endswith(".pkl"):
        raise ValueError("CellTypist preflight requires an exact catalog .pkl filename.")
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != CELLTYPIST_OFFICIAL_HOST:
        raise ValueError("CellTypist preflight only accepts the official HTTPS model host.")

    model_dir = cache_root / "data" / "models"
    model_dir.mkdir(parents=True, exist_ok=True)
    model_path = model_dir / model_name
    cache_populated = False
    if not model_path.exists():
        temporary_path = model_dir / f".{model_name}.{uuid4().hex}.tmp"
        started = time.monotonic()
        size = 0
        try:
            with requests.get(
                url,
                stream=True,
                timeout=(
                    CELLTYPIST_CONNECT_TIMEOUT_SECONDS,
                    CELLTYPIST_READ_TIMEOUT_SECONDS,
                ),
            ) as response:
                response.raise_for_status()
                final_url = urlparse(response.url)
                if (
                    final_url.scheme != "https"
                    or final_url.hostname != CELLTYPIST_OFFICIAL_HOST
                ):
                    raise ValueError("CellTypist model download redirected off the official host.")
                content_length = response.headers.get("Content-Length")
                if (
                    content_length is not None
                    and int(content_length) > MAX_CELLTYPIST_MODEL_BYTES
                ):
                    raise ValueError("CellTypist model exceeds the preflight artifact-size bound.")
                with temporary_path.open("xb") as handle:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if not chunk:
                            continue
                        size += len(chunk)
                        if size > MAX_CELLTYPIST_MODEL_BYTES:
                            raise ValueError(
                                "CellTypist model exceeds the preflight artifact-size bound."
                            )
                        if time.monotonic() - started > CELLTYPIST_TOTAL_DOWNLOAD_SECONDS:
                            raise TimeoutError("CellTypist model download exceeded its deadline.")
                        handle.write(chunk)
            if size == 0:
                raise ValueError("CellTypist model download was empty.")
            os.replace(temporary_path, model_path)
            cache_populated = True
        finally:
            temporary_path.unlink(missing_ok=True)

    size_bytes = model_path.stat().st_size
    if size_bytes == 0 or size_bytes > MAX_CELLTYPIST_MODEL_BYTES:
        raise ValueError("Cached CellTypist model is empty or exceeds the artifact-size bound.")
    from agents.agent_registry.cell_annotater_agent.tools_impl.celltypist_annotation import (
        _load_celltypist,
    )

    _, models, restore_configuration = _load_celltypist(cache_root)
    try:
        model = models.Model.load(str(model_path.resolve()))
    finally:
        restore_configuration()
    return model, {
        "sha256": _sha256(model_path),
        "size_bytes": int(size_bytes),
        "cache_populated": cache_populated,
    }


def preflight_celltypist_model(
    query_features: Mapping[str, Sequence[Any]],
    model_records: Sequence[Mapping[str, Any]],
    cache_root: Path,
    *,
    model_loader: Callable[
        [Mapping[str, Any], Path], tuple[Any, dict[str, Any]]
    ] = _bounded_celltypist_model_loader,
) -> dict[str, Any]:
    """Inspect one exact CellTypist candidate without query expression or inference."""
    if len(model_records) != 1:
        return _unknown_result(
            "select_candidate_model",
            "Exactly one verified CellTypist candidate is required per preflight.",
        )
    model_record = dict(model_records[0])
    try:
        model, artifact = model_loader(model_record, cache_root)
        model_features = np.asarray(model.features, dtype=str)
        cell_types = np.asarray(model.cell_types, dtype=str)
        if len(model_features) == 0 or len(cell_types) < 2:
            raise ValueError("The selected CellTypist model has invalid features or classes.")
        if len(set(model_features)) != len(model_features):
            raise ValueError("The selected CellTypist model has duplicate features.")
        overlap = _match_feature_representations(
            query_features,
            {"model.features": model_features},
        )
        matched_indices = np.asarray(overlap.pop("_matched_candidate_indices"), dtype=int)
        overlap.pop("_candidate_values")
        overlap["n_model_features"] = overlap.pop("n_candidate_features")
        overlap["model_feature_fraction"] = overlap.pop("candidate_feature_fraction")
        overlap["backend_min_feature_overlap"] = CELLTYPIST_BACKEND_MIN_FEATURE_OVERLAP
        overlap["meets_backend_min_feature_overlap"] = bool(
            overlap["n_matched_features"] >= CELLTYPIST_BACKEND_MIN_FEATURE_OVERLAP
        )

        coefficients = np.asarray(model.classifier.coef_, dtype=float)
        if coefficients.ndim != 2 or coefficients.shape[1] != len(model_features):
            raise ValueError("CellTypist classifier coefficients do not match model features.")
        absolute = np.abs(coefficients)
        totals = absolute.sum(axis=1)
        retained = (
            absolute[:, matched_indices].sum(axis=1)
            if matched_indices.size
            else np.zeros(coefficients.shape[0], dtype=float)
        )
        valid_totals = totals > 0
        retained_fraction = np.full(len(totals), np.nan, dtype=float)
        retained_fraction[valid_totals] = retained[valid_totals] / totals[valid_totals]
        matched_nonzero = (
            np.count_nonzero(coefficients[:, matched_indices], axis=1)
            if matched_indices.size
            else np.zeros(coefficients.shape[0], dtype=int)
        )

        safe_model = {
            key: model_record[key]
            for key in (
                "model",
                "description",
                "default",
                "source",
                "url",
                "version",
                "date",
                "n_cell_types",
            )
            if key in model_record
        }
        return {
            "status": "success",
            "assessment": "requires_agent_reasoning",
            "model": safe_model,
            "artifact": artifact,
            "feature_compatibility": overlap,
            "coefficient_support": {
                "status": "success",
                "n_classifier_rows": int(coefficients.shape[0]),
                "n_zero_total_weight_rows": int((~valid_totals).sum()),
                "retained_absolute_weight_fraction": _distribution(retained_fraction),
                "matched_nonzero_features_per_row": _distribution(matched_nonzero),
            },
            "label_coherence": summarize_label_coherence(cell_types),
            "label_inventory": {
                "labels": sorted(str(value) for value in cell_types),
                "n_labels": int(len(cell_types)),
                "truncated": False,
            },
            "provenance": {
                "training_source": model_record.get("source"),
                "query_training_overlap_status": "unknown",
                "limitation": (
                    "Model/query study independence cannot be inferred from feature overlap."
                ),
            },
            "bounds": {
                "models_loaded": 1,
                "maximum_models": 1,
                "maximum_artifact_bytes": MAX_CELLTYPIST_MODEL_BYTES,
                "download_deadline_seconds": CELLTYPIST_TOTAL_DOWNLOAD_SECONDS,
            },
            "limitations": [
                "No query expression or CellTypist predictions were computed.",
                "Feature and coefficient support do not establish query population coverage.",
            ],
            "leakage_safety": {
                "query_expression_read": False,
                "query_obs_read": False,
                "query_feature_names_returned": False,
                "query_predictions_computed": False,
            },
        }
    except Exception as exc:
        result = _unknown_result(
            "preflight_celltypist_model",
            "The selected CellTypist candidate could not be inspected safely.",
            exc,
        )
        result["model"] = {
            "model": model_record.get("model"),
        }
        result["leakage_safety"] = {
            "query_expression_read": False,
            "query_obs_read": False,
            "query_feature_names_returned": False,
            "query_predictions_computed": False,
        }
        return result


def _stable_feature_subset(
    indices: Sequence[int],
    values: Sequence[str],
) -> list[int]:
    """Select a deterministic bounded feature subset without labels or expression."""
    pairs = list(zip(indices, values, strict=True))
    pairs.sort(
        key=lambda pair: (
            hashlib.sha256(pair[1].casefold().encode("utf-8")).hexdigest(),
            pair[0],
        )
    )
    return sorted(pair[0] for pair in pairs[:MAX_REFERENCE_FEATURES])


def _stratified_reference_sample(
    labels: pd.Series,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Select a deterministic bounded reference sample from evaluable labels."""
    counts = labels.value_counts()
    eligible = sorted(
        [str(label) for label, count in counts.items() if count >= REFERENCE_CV_FOLDS],
        key=lambda value: (_normalize_label(value), value),
    )
    if len(eligible) < 2:
        return np.array([], dtype=int), {
            "n_labels_total": int(len(counts)),
            "n_labels_evaluable": int(len(eligible)),
            "n_labels_too_small_for_cv": int(len(counts) - len(eligible)),
        }
    allocation = min(
        MAX_CELLS_PER_LABEL,
        max(REFERENCE_CV_FOLDS, MAX_REFERENCE_CELLS // len(eligible)),
    )
    rng = np.random.default_rng(PREFLIGHT_RANDOM_STATE)
    selected: list[int] = []
    values = labels.to_numpy(dtype=str)
    for label in eligible:
        positions = np.flatnonzero(values == label)
        if len(positions) > allocation:
            positions = np.sort(rng.choice(positions, size=allocation, replace=False))
        selected.extend(positions.tolist())
    selected_array = np.asarray(sorted(selected), dtype=int)
    return selected_array, {
        "n_labels_total": int(len(counts)),
        "n_labels_evaluable": int(len(eligible)),
        "n_labels_too_small_for_cv": int(len(counts) - len(eligible)),
        "maximum_cells_per_label": int(allocation),
    }


def _prepare_reference_matrix(matrix: Any, expression_state: str) -> np.ndarray:
    """Prepare a bounded reference-only matrix for geometric discriminability."""
    if sparse.issparse(matrix):
        working = matrix.tocsr().astype(np.float32)
        values = working.data
    else:
        working = np.asarray(matrix, dtype=np.float32)
        values = working.ravel()
    if values.size and (not np.isfinite(values).all() or np.any(values < 0)):
        raise ValueError("Reference panel preflight requires finite nonnegative expression.")
    if expression_state == "raw_count_like":
        totals = np.asarray(working.sum(axis=1)).ravel()
        nonzero = totals > 0
        if not np.all(nonzero):
            raise ValueError("Reference panel sample contains zero-expression observations.")
        scales = 10_000.0 / totals
        if sparse.issparse(working):
            working = working.multiply(scales[:, None]).tocsr()
            working.data = np.log1p(working.data)
        else:
            working = np.log1p(working * scales[:, None])
    elif expression_state != "log1p_normalized":
        raise ValueError(
            f"Reference expression state {expression_state!r} is not safely assessable."
        )
    return working.toarray() if sparse.issparse(working) else np.asarray(working)


def _read_bounded_backed_matrix(
    dataset: ad.AnnData,
    row_indices: np.ndarray,
    column_indices: Sequence[int],
) -> Any:
    """Read only bounded rows and columns despite backed dense indexing limits."""
    matrix = dataset.X
    columns = np.asarray(sorted(column_indices), dtype=int)
    if getattr(matrix, "format", None) in {"csr", "csc"}:
        return matrix[row_indices, columns]

    runs: list[tuple[int, int]] = []
    run_start = int(columns[0])
    previous = run_start
    for column in columns[1:]:
        current = int(column)
        if current != previous + 1:
            runs.append((run_start, previous + 1))
            run_start = current
        previous = current
    runs.append((run_start, previous + 1))
    parts = [np.asarray(matrix[row_indices, start:stop]) for start, stop in runs]
    return parts[0] if len(parts) == 1 else np.concatenate(parts, axis=1)


def _nearest_centroid_predictions(
    matrix: np.ndarray,
    labels: np.ndarray,
    train_indices: np.ndarray,
    test_indices: np.ndarray,
) -> np.ndarray:
    """Fit a deterministic fold-local standardized nearest-centroid classifier."""
    train = matrix[train_indices]
    test = matrix[test_indices]
    means = train.mean(axis=0)
    scales = train.std(axis=0)
    scales[scales == 0] = 1.0
    train_scaled = (train - means) / scales
    test_scaled = (test - means) / scales
    train_labels = labels[train_indices]
    classes = np.unique(train_labels)
    centroids = np.vstack(
        [train_scaled[train_labels == label].mean(axis=0) for label in classes]
    )
    distances = np.sum((test_scaled[:, None, :] - centroids[None, :, :]) ** 2, axis=2)
    return classes[np.argmin(distances, axis=1)].astype(str)


def _score_predictions(labels: np.ndarray, predictions: np.ndarray) -> dict[str, float]:
    """Score bounded reference-only predictions with class-balanced summaries."""
    return {
        "macro_recall": float(balanced_accuracy_score(labels, predictions)),
        "macro_f1": float(f1_score(labels, predictions, average="macro", zero_division=0)),
    }


def _reference_discriminability(
    matrix: np.ndarray,
    labels: np.ndarray,
    sources: np.ndarray | None,
) -> dict[str, Any]:
    """Measure bounded reference-only panel separability and source generalization."""
    stratified = StratifiedKFold(
        n_splits=REFERENCE_CV_FOLDS,
        shuffle=True,
        random_state=PREFLIGHT_RANDOM_STATE,
    )
    stratified_truth: list[np.ndarray] = []
    stratified_predictions: list[np.ndarray] = []
    for train, test in stratified.split(matrix, labels):
        stratified_truth.append(labels[test])
        stratified_predictions.append(
            _nearest_centroid_predictions(matrix, labels, train, test)
        )
    truth = np.concatenate(stratified_truth)
    predictions = np.concatenate(stratified_predictions)
    result: dict[str, Any] = {
        "protocol": "bounded_reference_only_nearest_centroid_v1",
        "stratified_cv": {
            "status": "success",
            "n_folds": REFERENCE_CV_FOLDS,
            **_score_predictions(truth, predictions),
            "label_coverage_fraction": 1.0,
            "observation_coverage_fraction": 1.0,
        },
    }

    if sources is None:
        result["source_grouped_cv"] = {
            "status": "not_available",
            "reason": "Reference source identifiers are unavailable.",
        }
        return result
    if len(set(sources)) < 2:
        result["source_grouped_cv"] = {
            "status": "not_applicable_single_source",
            "reason": "Source-grouped validation does not apply to one reference source.",
        }
        return result

    n_splits = min(REFERENCE_GROUP_FOLDS, len(set(sources)))
    grouped = GroupKFold(n_splits=n_splits)
    grouped_truth: list[np.ndarray] = []
    grouped_predictions: list[np.ndarray] = []
    scorable_observations = 0
    scorable_labels: set[str] = set()
    all_labels = set(labels)
    for train, test in grouped.split(matrix, labels, groups=sources):
        train_labels = set(labels[train])
        mask = np.asarray([label in train_labels for label in labels[test]])
        scorable_test = test[mask]
        if not len(scorable_test):
            continue
        fold_truth = labels[scorable_test]
        grouped_truth.append(fold_truth)
        grouped_predictions.append(
            _nearest_centroid_predictions(matrix, labels, train, scorable_test)
        )
        scorable_observations += len(scorable_test)
        scorable_labels.update(fold_truth)
    if not grouped_truth:
        result["source_grouped_cv"] = {
            "status": "not_assessable",
            "reason": "No held-out source observations had labels represented in training.",
            "n_folds": n_splits,
            "scorable_label_fraction": 0.0,
            "scorable_observation_fraction": 0.0,
        }
        return result
    truth = np.concatenate(grouped_truth)
    predictions = np.concatenate(grouped_predictions)
    result["source_grouped_cv"] = {
        "status": "success",
        "n_folds": n_splits,
        **_score_predictions(truth, predictions),
        "scorable_label_fraction": float(len(scorable_labels) / max(1, len(all_labels))),
        "scorable_observation_fraction": float(
            scorable_observations / max(1, len(labels))
        ),
    }
    return result


def preflight_reference_query_panel(
    query_features: Mapping[str, Sequence[Any]],
    reference_path: Path,
    label_column: str,
    reference_expression_state: str,
) -> dict[str, Any]:
    """Assess reference labels using query features without reading query expression or obs."""
    reference = None
    try:
        reference = ad.read_h5ad(reference_path, backed="r")
        if label_column not in reference.obs:
            return _unknown_result(
                "validate_reference_labels",
                f"Reference is missing .obs[{label_column!r}].",
            )
        labels_raw = reference.obs[label_column].astype("string")
        labels_clean = labels_raw.fillna("").str.strip()
        source_column = next(
            (column for column in _SOURCE_COLUMNS if column in reference.obs),
            None,
        )
        sources_raw = reference.obs[source_column] if source_column else None
        ontology_column = next(
            (column for column in _ONTOLOGY_COLUMNS if column in reference.obs),
            None,
        )
        ontology_raw = reference.obs[ontology_column] if ontology_column else None
        coherence = summarize_label_coherence(
            labels_raw,
            sources=sources_raw,
            ontology_ids=ontology_raw,
        )

        candidate_representations = _candidate_feature_representations(reference)
        overlap = _match_feature_representations(
            query_features,
            candidate_representations,
        )
        matched_indices = overlap.pop("_matched_candidate_indices")
        candidate_values = overlap.pop("_candidate_values")
        n_reference_features = overlap.pop("n_candidate_features")
        reference_feature_fraction = overlap.pop("candidate_feature_fraction")
        feature_compatibility = {
            **overlap,
            "n_reference_features": n_reference_features,
            "reference_feature_fraction": reference_feature_fraction,
        }

        valid_labels = labels_clean[labels_clean != ""]
        n_labels = int(valid_labels.nunique())
        base = {
            "feature_compatibility": feature_compatibility,
            "label_coherence": coherence,
            "provenance": {
                "exact_query_reference_obs_overlap": None,
                "independence_status": "provenance_unknown",
                "limitation": (
                    "This helper receives query features only and cannot infer study independence."
                ),
            },
            "bounds": {
                "maximum_reference_cells": MAX_REFERENCE_CELLS,
                "maximum_reference_features": MAX_REFERENCE_FEATURES,
                "maximum_reference_labels": MAX_REFERENCE_LABELS,
                "maximum_cells_per_label": MAX_CELLS_PER_LABEL,
                "stratified_folds": REFERENCE_CV_FOLDS,
                "source_group_folds": REFERENCE_GROUP_FOLDS,
                "random_state": PREFLIGHT_RANDOM_STATE,
            },
            "leakage_safety": {
                "query_expression_read": False,
                "query_obs_read": False,
                "query_feature_names_returned": False,
                "reference_labels_used": True,
                "held_out_query_labels_used": False,
            },
        }
        if reference_expression_state not in {"raw_count_like", "log1p_normalized"}:
            return {
                "status": "not_assessable",
                "assessment": "unknown",
                "stage": "validate_reference_expression_state",
                "reason": (
                    "Reference panel diagnostics require raw-count-like or explicitly "
                    "log1p-normalized expression; other states remain unknown."
                ),
                **base,
            }
        if n_labels > MAX_REFERENCE_LABELS:
            return {
                "status": "not_assessable",
                "assessment": "unknown",
                "stage": "enforce_label_bound",
                "reason": (
                    f"Reference has {n_labels} labels, exceeding the bound of "
                    f"{MAX_REFERENCE_LABELS}; no favorable subset was scored."
                ),
                **base,
            }
        if n_labels < 2:
            return {
                "status": "not_assessable",
                "assessment": "unknown",
                "stage": "validate_reference_labels",
                "reason": "Reference panel discriminability requires at least two labels.",
                **base,
            }
        if len(matched_indices) < 2:
            return {
                "status": "not_assessable",
                "assessment": "unknown",
                "stage": "validate_shared_features",
                "reason": "Reference panel discriminability requires at least two shared features.",
                **base,
            }

        valid_positions = np.flatnonzero(labels_clean.to_numpy(dtype=str) != "")
        valid_series = labels_clean.iloc[valid_positions].reset_index(drop=True)
        sampled_relative, sampling = _stratified_reference_sample(valid_series)
        if len(sampled_relative) == 0:
            return {
                "status": "not_assessable",
                "assessment": "unknown",
                "stage": "sample_reference",
                "reason": "Fewer than two labels have enough cells for bounded cross-validation.",
                "sampling": sampling,
                **base,
            }
        sampled_positions = valid_positions[sampled_relative]
        selected_features = _stable_feature_subset(
            matched_indices,
            [candidate_values[index] for index in matched_indices],
        )
        bounded_matrix = _read_bounded_backed_matrix(
            reference,
            sampled_positions,
            selected_features,
        )
        matrix = _prepare_reference_matrix(bounded_matrix, reference_expression_state)
        sampled_labels = labels_clean.iloc[sampled_positions].astype(str).to_numpy()
        sampled_sources = None
        if source_column is not None:
            sampled_sources_series = (
                reference.obs[source_column]
                .iloc[sampled_positions]
                .astype("string")
                .fillna("")
                .str.strip()
            )
            if sampled_sources_series.ne("").all():
                sampled_sources = sampled_sources_series.astype(str).to_numpy()
        diagnostics = _reference_discriminability(
            matrix,
            sampled_labels,
            sampled_sources,
        )
        sampling.update(
            {
                "n_reference_cells": int(reference.n_obs),
                "n_sampled_cells": int(len(sampled_positions)),
                "n_features_used": int(len(selected_features)),
                "feature_selection": (
                    "all_unique_shared_features"
                    if len(matched_indices) <= MAX_REFERENCE_FEATURES
                    else "stable_hash_bounded_shared_subset"
                ),
            }
        )
        grouped_status = diagnostics["source_grouped_cv"]["status"]
        status = (
            "partial"
            if sampling["n_labels_too_small_for_cv"]
            or grouped_status in {"not_available", "not_assessable"}
            else "success"
        )
        return {
            "status": status,
            "assessment": "requires_agent_reasoning",
            **base,
            "sampling": sampling,
            "reference_only_panel_discriminability": diagnostics,
            "limitations": [
                "Diagnostics use independent reference labels, never query outcomes.",
                "Reference-only separability does not establish query population coverage.",
                "No performance threshold is applied to these diagnostics.",
            ],
        }
    except Exception as exc:
        result = _unknown_result(
            "preflight_reference_query_panel",
            "The supplied reference could not be assessed safely within fixed bounds.",
            exc,
        )
        result["leakage_safety"] = {
            "query_expression_read": False,
            "query_obs_read": False,
            "query_feature_names_returned": False,
            "reference_labels_used": True,
            "held_out_query_labels_used": False,
        }
        return result
    finally:
        if reference is not None:
            reference.file.close()
