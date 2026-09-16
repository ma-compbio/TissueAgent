"""Pre-execution contracts for adaptive cell-annotation routing."""

from __future__ import annotations

import hashlib
import json
import math
import secrets
import threading
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from agents.workspace_paths import resolve_project_output, resolve_workspace_input
from models import get_model_seed


SELECTION_CONTRACT_VERSION = "cell_annotation_selection_contract_v7"
ANNOTATION_CONTEXT_CONTRACT_VERSION = "cell_annotation_context_contract_v1"
CONFIGURATION_CONTRACT_VERSION = "cell_annotation_scientific_configuration_contract_v2"
CONFIGURATION_EXECUTION_TOKEN_VERSION = "cell_annotation_execution_token_v2"
INPUT_IDENTITY_VERSION = "resolved_file_stat_and_bounded_content_identity_v1"
HARMONY_PARAMETER_POLICY_VERSION = "harmony_execution_parameter_policy_v1"
CELLTYPIST_PARAMETER_POLICY_VERSION = "celltypist_execution_parameter_policy_v1"
GPTCELLTYPE_PARAMETER_POLICY_VERSION = "gptcelltype_execution_parameter_policy_v1"
_INPUT_IDENTITY_SAMPLE_BYTES = 64 * 1024
_CONTRACT_TTL_SECONDS = 2 * 60 * 60
_MAX_LIVE_RECORDS = 128
_MAX_AGENT_RATIONALE_CHARACTERS = 20_000
_MAX_BACKEND_RATIONALE_CHARACTERS = 4_000
_MAX_PARAMETER_POLICY_VERSION_CHARACTERS = 200
_METHODS = ("harmony", "celltypist", "gptcelltype")
_SUITABILITY_LEVELS = {"low": 0, "moderate": 1, "high": 2}
_SCOPE_COVERAGE_LEVELS = {"unknown": 0, "inadequate": 1, "partial": 2, "adequate": 3}
_CELLTYPIST_MODEL_SCOPE_FIELDS = {
    "primary_scope_coverage",
    "secondary_scope_coverage",
    "requested_output_coverage",
    "technical_compatibility",
    "evidence",
    "unsupported_populations",
}
REFERENCE_EVIDENCE_SCOPE_PHRASE = (
    "Candidate reference evidence was used only to assess Harmony."
)
_PARAMETER_POLICY_VERSION_BY_METHOD = {
    "harmony": HARMONY_PARAMETER_POLICY_VERSION,
    "celltypist": CELLTYPIST_PARAMETER_POLICY_VERSION,
    "gptcelltype": GPTCELLTYPE_PARAMETER_POLICY_VERSION,
}
_SCIENTIFIC_CONFIGURATION_FIELDS = {
    "harmony": {
        "skip_preprocessing",
        "preprocess_spatial",
        "preprocess_reference",
        "preserve_all_spatial_obs",
        "reference_min_genes",
        "min_cells",
        "target_sum",
        "n_top_genes",
        "n_pcs",
        "min_shared_genes",
        "harmony_key",
        "harmony_max_iter",
        "mlp_hidden_layers",
        "mlp_max_iter",
        "mlp_random_state",
        "classifier",
        "knn_neighbors",
        "map_spatial_gene_names",
        "gene_mapping_species",
        "gene_mapping_target",
    },
    "celltypist": {
        "majority_voting",
        "mode",
        "p_thres",
        "min_feature_overlap",
    },
    "gptcelltype": {
        "cluster_column",
        "resolution",
        "top_marker_genes",
    },
}
_OPERATIONAL_CONFIGURATION_FIELDS = {
    "harmony": {"output_dir", "output_filename"},
    "celltypist": {"n_jobs"},
    "gptcelltype": {
        "api_batch_size",
        "max_api_attempts_per_batch",
        "api_timeout_seconds",
    },
}
_LOCK = threading.RLock()
_CONTRACTS: dict[str, dict[str, Any]] = {}
_EXECUTION_TOKENS: dict[str, dict[str, Any]] = {}


def method_evidence_scopes(*, reference_provided: bool) -> dict[str, Any]:
    """Return the auditable evidence boundary for each annotation method."""
    return {
        "version": "cell_annotation_method_evidence_scope_v1",
        "candidate_reference": {
            "provided": reference_provided,
            "allowed_use": "harmony_suitability_and_configuration_only",
            "forbidden_uses": [
                "celltypist_suitability",
                "celltypist_model_shortlisting",
                "celltypist_model_selection",
                "gptcelltype_suitability",
            ],
        },
        "method_inputs": {
            "harmony": ["context", "reference", "method_cards.harmony"],
            "celltypist": [
                "context",
                "query.matrix",
                "celltypist",
                "method_cards.celltypist",
            ],
            "gptcelltype": [
                "context",
                "query.gptcelltype_readiness",
                "worker_llm",
                "method_cards.gptcelltype",
            ],
        },
    }


def _purge_expired(now: float) -> None:
    for registry in (_CONTRACTS, _EXECUTION_TOKENS):
        expired = [
            key
            for key, record in registry.items()
            if now - float(record["created_at"]) > _CONTRACT_TTL_SECONDS
        ]
        for key in expired:
            registry.pop(key, None)
        if len(registry) > _MAX_LIVE_RECORDS:
            oldest = sorted(
                registry,
                key=lambda key: float(registry[key]["created_at"]),
            )
            for key in oldest[: len(registry) - _MAX_LIVE_RECORDS]:
                registry.pop(key, None)


def _top_celltypist_model(celltypist: Mapping[str, Any]) -> str | None:
    models = celltypist.get("models")
    if not isinstance(models, list) or not models:
        return None
    top = models[0]
    model = top.get("model") if isinstance(top, Mapping) else None
    return model if isinstance(model, str) and model else None


def _celltypist_candidate_models(celltypist: Mapping[str, Any]) -> list[str]:
    """Return technically inspected built-in candidates in agent shortlist order."""
    preflights = celltypist.get("candidate_model_preflights")
    models = celltypist.get("models")
    if isinstance(preflights, Mapping) and isinstance(models, list):
        assessments = celltypist.get("candidate_model_assessments")
        candidates = []
        for record in models:
            model = record.get("model") if isinstance(record, Mapping) else None
            preflight = preflights.get(model) if isinstance(model, str) else None
            assessment = assessments.get(model) if isinstance(assessments, Mapping) else None
            if (
                isinstance(preflight, Mapping)
                and preflight.get("status") == "success"
                and (
                    not isinstance(assessment, Mapping)
                    or assessment.get("prerequisites") != "not_met"
                )
            ):
                candidates.append(model)
        return candidates
    top = _top_celltypist_model(celltypist)
    return [top] if top is not None else []


def _canonical_json_value(value: Any, *, field: str) -> Any:
    """Return a deterministic JSON-compatible representation."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{field} must not contain non-finite numbers.")
        return value
    if isinstance(value, Mapping):
        canonical: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str) or not key:
                raise ValueError(f"{field} keys must be non-empty strings.")
            canonical[key] = _canonical_json_value(
                item,
                field=f"{field}.{key}",
            )
        return {key: canonical[key] for key in sorted(canonical)}
    if isinstance(value, (list, tuple)):
        return [
            _canonical_json_value(item, field=f"{field}[{index}]")
            for index, item in enumerate(value)
        ]
    scalar_item = getattr(value, "item", None)
    if callable(scalar_item):
        converted = scalar_item()
        if converted is not value:
            return _canonical_json_value(converted, field=field)
    raise ValueError(
        f"{field} must contain only JSON-compatible scalar, list, tuple, or mapping values."
    )


def _canonical_mapping(value: Mapping[str, Any], *, field: str) -> dict[str, Any]:
    """Canonicalize a configuration mapping without accepting implicit stringification."""
    canonical = _canonical_json_value(value, field=field)
    if not isinstance(canonical, dict):
        raise ValueError(f"{field} must be a mapping.")
    return canonical


def _canonical_sha256(value: Any) -> str:
    """Hash a canonical JSON value."""
    payload = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _file_identity(path: Path) -> dict[str, int | str]:
    """Return a cheap stat plus bounded-content identity without hashing a full H5AD."""
    stat = path.stat()
    with path.open("rb") as handle:
        first = handle.read(_INPUT_IDENTITY_SAMPLE_BYTES)
        if stat.st_size > _INPUT_IDENTITY_SAMPLE_BYTES:
            handle.seek(max(0, stat.st_size - _INPUT_IDENTITY_SAMPLE_BYTES))
            last = handle.read(_INPUT_IDENTITY_SAMPLE_BYTES)
        else:
            last = b""
    sampled_content_sha256 = hashlib.sha256(first + b"\x00" + last).hexdigest()
    return {
        "version": INPUT_IDENTITY_VERSION,
        "size_bytes": int(stat.st_size),
        "mtime_ns": int(stat.st_mtime_ns),
        "sample_bytes_per_edge": _INPUT_IDENTITY_SAMPLE_BYTES,
        "sampled_content_sha256": sampled_content_sha256,
    }


def _registered_input_identities(
    query_path: Path,
    reference_path: Path | None,
) -> dict[str, dict[str, int | str] | None]:
    """Capture cheap query and reference identities at inspection time."""
    return {
        "query": _file_identity(query_path),
        "reference": (_file_identity(reference_path) if reference_path is not None else None),
    }


def _input_identity_violations(
    record: Mapping[str, Any],
    *,
    selected_method: str,
) -> list[str]:
    """Report mutations of inputs authorized for the selected method."""
    violations: list[str] = []
    input_identities = record["input_identities"]
    roles = [("query", "query_path")]
    if selected_method == "harmony":
        roles.append(("reference", "reference_path"))
    for role, path_key in roles:
        expected = input_identities[role]
        path = record[path_key]
        if expected is None or path is None:
            continue
        try:
            observed = _file_identity(path)
        except OSError as exc:
            violations.append(f"inspected {role} identity could not be verified: {exc}")
            continue
        if observed != expected:
            violations.append(f"inspected {role} input identity changed since method inspection")
    return violations


def _clean_parameter_policy_version(value: str | None) -> str:
    """Validate a stable scientific-parameter policy or profile version."""
    cleaned = value.strip() if isinstance(value, str) else ""
    if not cleaned:
        raise ValueError("parameter_policy_version is required with scientific_configuration.")
    if len(cleaned) > _MAX_PARAMETER_POLICY_VERSION_CHARACTERS:
        raise ValueError(
            "parameter_policy_version must contain at most "
            f"{_MAX_PARAMETER_POLICY_VERSION_CHARACTERS} characters."
        )
    if any(character in cleaned for character in "\r\n"):
        raise ValueError("parameter_policy_version must be a single-line value.")
    return cleaned


def _require_exact_configuration_fields(
    value: Mapping[str, Any],
    *,
    field: str,
    expected: set[str],
) -> None:
    """Reject partial or expanded configurations before a token is minted."""
    observed = set(value)
    missing = sorted(expected - observed)
    unexpected = sorted(observed - expected)
    problems = []
    if missing:
        problems.append("missing " + ", ".join(missing))
    if unexpected:
        problems.append("unexpected " + ", ".join(unexpected))
    if problems:
        raise ValueError(f"{field} fields are invalid: {'; '.join(problems)}.")


def _positive_integer(value: Any, *, field: str, minimum: int = 1) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{field} must be an integer greater than or equal to {minimum}.")
    return value


def _finite_number(value: Any, *, field: str, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a finite number.")
    normalized = float(value)
    if not math.isfinite(normalized) or (positive and normalized <= 0):
        qualifier = "positive " if positive else ""
        raise ValueError(f"{field} must be a finite {qualifier}number.")
    return normalized


def _nonempty_string(value: Any, *, field: str) -> str:
    normalized = value.strip() if isinstance(value, str) else ""
    if not normalized:
        raise ValueError(f"{field} must be a non-empty string.")
    return normalized


def _normalize_harmony_configuration(
    scientific: dict[str, Any],
    operational: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    skip_preprocessing = scientific["skip_preprocessing"]
    if skip_preprocessing is not None and not isinstance(skip_preprocessing, bool):
        raise ValueError("scientific_configuration.skip_preprocessing must be null or a boolean.")
    preprocess_spatial = scientific["preprocess_spatial"]
    preprocess_reference = scientific["preprocess_reference"]
    if not isinstance(preprocess_spatial, bool):
        raise ValueError("scientific_configuration.preprocess_spatial must be a boolean.")
    if not isinstance(preprocess_reference, bool):
        raise ValueError("scientific_configuration.preprocess_reference must be a boolean.")
    if skip_preprocessing is not None and (
        preprocess_spatial is skip_preprocessing
        or preprocess_reference is skip_preprocessing
    ):
        raise ValueError(
            "scientific_configuration.skip_preprocessing conflicts with the per-input decisions."
        )
    preserve_all = scientific["preserve_all_spatial_obs"]
    if preserve_all is not True:
        raise ValueError(
            "scientific_configuration.preserve_all_spatial_obs must be true for the "
            "cross-backend output contract."
        )
    reference_min_genes = scientific["reference_min_genes"]
    if preprocess_reference:
        reference_min_genes = _positive_integer(
            reference_min_genes,
            field="scientific_configuration.reference_min_genes",
        )
    elif reference_min_genes is not None:
        raise ValueError(
            "scientific_configuration.reference_min_genes must be null when "
            "preprocess_reference is false."
        )

    hidden_layers = scientific["mlp_hidden_layers"]
    if not isinstance(hidden_layers, (list, tuple)) or not hidden_layers:
        raise ValueError(
            "scientific_configuration.mlp_hidden_layers must be a non-empty list of "
            "positive integers."
        )
    normalized_hidden_layers = [
        _positive_integer(
            width,
            field=f"scientific_configuration.mlp_hidden_layers[{index}]",
        )
        for index, width in enumerate(hidden_layers)
    ]
    classifier = scientific["classifier"]
    if classifier not in {"mlp", "knn"}:
        raise ValueError("scientific_configuration.classifier must be 'mlp' or 'knn'.")
    gene_mapping_target = scientific["gene_mapping_target"]
    if gene_mapping_target not in {"symbol", "ensembl"}:
        raise ValueError(
            "scientific_configuration.gene_mapping_target must be 'symbol' or 'ensembl'."
        )
    if not isinstance(scientific["map_spatial_gene_names"], bool):
        raise ValueError("scientific_configuration.map_spatial_gene_names must be a boolean.")
    mlp_random_state = scientific["mlp_random_state"]
    if isinstance(mlp_random_state, bool) or not isinstance(mlp_random_state, int):
        raise ValueError("scientific_configuration.mlp_random_state must be an integer.")

    normalized_scientific = {
        **scientific,
        "reference_min_genes": reference_min_genes,
        "min_cells": _positive_integer(
            scientific["min_cells"], field="scientific_configuration.min_cells"
        ),
        "target_sum": _finite_number(
            scientific["target_sum"],
            field="scientific_configuration.target_sum",
            positive=True,
        ),
        "n_top_genes": _positive_integer(
            scientific["n_top_genes"], field="scientific_configuration.n_top_genes"
        ),
        "n_pcs": _positive_integer(scientific["n_pcs"], field="scientific_configuration.n_pcs"),
        "min_shared_genes": _positive_integer(
            scientific["min_shared_genes"],
            field="scientific_configuration.min_shared_genes",
            minimum=2,
        ),
        "harmony_key": _nonempty_string(
            scientific["harmony_key"], field="scientific_configuration.harmony_key"
        ),
        "harmony_max_iter": _positive_integer(
            scientific["harmony_max_iter"],
            field="scientific_configuration.harmony_max_iter",
        ),
        "mlp_hidden_layers": normalized_hidden_layers,
        "mlp_max_iter": _positive_integer(
            scientific["mlp_max_iter"], field="scientific_configuration.mlp_max_iter"
        ),
        "mlp_random_state": mlp_random_state,
        "knn_neighbors": _positive_integer(
            scientific["knn_neighbors"], field="scientific_configuration.knn_neighbors"
        ),
        "gene_mapping_species": _nonempty_string(
            scientific["gene_mapping_species"],
            field="scientific_configuration.gene_mapping_species",
        ),
        "pca_feature_selection_policy": "union_of_reference_and_spatial_hvgs",
    }
    normalized_operational = {
        "output_dir": _nonempty_string(
            operational["output_dir"], field="operational_configuration.output_dir"
        ),
        "output_filename": operational["output_filename"],
    }
    if normalized_operational["output_filename"] is not None:
        normalized_operational["output_filename"] = _nonempty_string(
            normalized_operational["output_filename"],
            field="operational_configuration.output_filename",
        )
    return normalized_scientific, normalized_operational


def _normalize_celltypist_configuration(
    scientific: dict[str, Any],
    operational: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(scientific["majority_voting"], bool):
        raise ValueError("scientific_configuration.majority_voting must be a boolean.")
    mode = scientific["mode"]
    if mode not in {"best match", "prob match"}:
        raise ValueError("scientific_configuration.mode must be 'best match' or 'prob match'.")
    p_thres = _finite_number(scientific["p_thres"], field="scientific_configuration.p_thres")
    if not 0 <= p_thres <= 1:
        raise ValueError("scientific_configuration.p_thres must be between 0 and 1.")
    return (
        {
            **scientific,
            "p_thres": p_thres,
            "min_feature_overlap": _positive_integer(
                scientific["min_feature_overlap"],
                field="scientific_configuration.min_feature_overlap",
            ),
        },
        {
            "n_jobs": _positive_integer(
                operational["n_jobs"], field="operational_configuration.n_jobs"
            )
        },
    )


def _normalize_gptcelltype_configuration(
    scientific: dict[str, Any],
    operational: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    from agents.agent_registry.cell_annotater_agent.tools_impl.gptcelltype_readiness import (
        gptcelltype_readiness_execution_binding,
    )
    from models import get_model_id, get_model_spec

    cluster_column = scientific["cluster_column"]
    if cluster_column is not None:
        cluster_column = _nonempty_string(
            cluster_column,
            field="scientific_configuration.cluster_column",
        )
    resolution = _finite_number(
        scientific["resolution"],
        field="scientific_configuration.resolution",
        positive=True,
    )
    top_marker_genes = _positive_integer(
        scientific["top_marker_genes"],
        field="scientific_configuration.top_marker_genes",
    )
    binding = gptcelltype_readiness_execution_binding(
        cluster_column=cluster_column,
        resolution=resolution,
        top_marker_genes=top_marker_genes,
    )
    if binding["status"] != "matched":
        raise ValueError(
            "GPTCellType execution is outside the inspected readiness profile: "
            + ", ".join(binding["mismatch_codes"])
            + ". Rerun method inspection with a separately implemented readiness profile."
        )
    worker_model_id = get_model_id("worker")
    worker_model = get_model_spec(worker_model_id)
    normalized_scientific = {
        "cluster_column": cluster_column,
        "resolution": resolution,
        "top_marker_genes": top_marker_genes,
        "readiness_execution_binding": {
            "version": binding["version"],
            "status": binding["status"],
            "readiness_profile_id": binding["readiness_profile_id"],
            "execution_clustering_profile_id": binding["execution_clustering_profile_id"],
        },
        "worker_model": {
            "model_id": worker_model.id,
            "provider": worker_model.provider,
            "api_model": worker_model.api_model,
            "reasoning_effort": worker_model.reasoning_effort,
            "temperature": "provider_default",
            "seed": get_model_seed(),
            "model_client_max_retries": 0,
        },
    }
    normalized_operational = {
        "api_batch_size": _positive_integer(
            operational["api_batch_size"],
            field="operational_configuration.api_batch_size",
        ),
        "max_api_attempts_per_batch": _positive_integer(
            operational["max_api_attempts_per_batch"],
            field="operational_configuration.max_api_attempts_per_batch",
        ),
        "api_timeout_seconds": _positive_integer(
            operational["api_timeout_seconds"],
            field="operational_configuration.api_timeout_seconds",
        ),
    }
    if normalized_operational["api_batch_size"] > 25:
        raise ValueError("operational_configuration.api_batch_size must be at most 25.")
    if normalized_operational["max_api_attempts_per_batch"] > 10:
        raise ValueError("operational_configuration.max_api_attempts_per_batch must be at most 10.")
    if normalized_operational["api_timeout_seconds"] > 600:
        raise ValueError("operational_configuration.api_timeout_seconds must be at most 600.")
    return normalized_scientific, normalized_operational


def _normalize_method_configuration(
    *,
    selected_method: str,
    parameter_policy_version: str | None,
    scientific_configuration: Mapping[str, Any],
    operational_configuration: Mapping[str, Any],
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    policy_version = _clean_parameter_policy_version(parameter_policy_version)
    expected_policy_version = _PARAMETER_POLICY_VERSION_BY_METHOD[selected_method]
    if policy_version != expected_policy_version:
        raise ValueError(
            f"parameter_policy_version must be {expected_policy_version!r} for {selected_method}."
        )
    scientific = _canonical_mapping(
        scientific_configuration,
        field="scientific_configuration",
    )
    operational = _canonical_mapping(
        operational_configuration,
        field="operational_configuration",
    )
    _require_exact_configuration_fields(
        scientific,
        field="scientific_configuration",
        expected=_SCIENTIFIC_CONFIGURATION_FIELDS[selected_method],
    )
    _require_exact_configuration_fields(
        operational,
        field="operational_configuration",
        expected=_OPERATIONAL_CONFIGURATION_FIELDS[selected_method],
    )
    if selected_method == "harmony":
        scientific, operational = _normalize_harmony_configuration(
            scientific,
            operational,
        )
    elif selected_method == "celltypist":
        scientific, operational = _normalize_celltypist_configuration(
            scientific,
            operational,
        )
    else:
        scientific, operational = _normalize_gptcelltype_configuration(
            scientific,
            operational,
        )
    return policy_version, scientific, operational


def _configuration_contract(
    *,
    selected_method: str,
    parameter_policy_version: str | None,
    scientific_configuration: Mapping[str, Any],
    operational_configuration: Mapping[str, Any] | None,
    selection_evidence_sha256: str,
) -> dict[str, Any]:
    """Build a canonical method-specific configuration envelope and hashes."""
    policy_version, scientific, operational = _normalize_method_configuration(
        selected_method=selected_method,
        parameter_policy_version=parameter_policy_version,
        scientific_configuration=scientific_configuration,
        operational_configuration=operational_configuration or {},
    )
    envelope = {
        "version": CONFIGURATION_CONTRACT_VERSION,
        "selected_method": selected_method,
        "parameter_policy_version": policy_version,
        "scientific_configuration": scientific,
        "operational_configuration": operational,
        "selection_evidence_sha256": selection_evidence_sha256,
    }
    return {
        **envelope,
        "scientific_configuration_sha256": _canonical_sha256(scientific),
        "operational_configuration_sha256": _canonical_sha256(operational),
        "configuration_sha256": _canonical_sha256(envelope),
    }


def _required_adverse_codes(
    selected_method: str,
    method_assessments: Mapping[str, Any],
) -> list[str]:
    return sorted(
        {
            str(code)
            for method, assessment in method_assessments.items()
            if method == selected_method
            or (isinstance(assessment, Mapping) and assessment.get("risk_tier") == "high")
            for code in (
                assessment.get("adverse_codes", []) if isinstance(assessment, Mapping) else []
            )
        }
    )


def _normalize_method_suitability_confidences(
    value: Mapping[str, Any],
) -> dict[str, str]:
    """Validate the agent's qualitative comparison across all methods."""
    if not isinstance(value, Mapping):
        raise ValueError("method_suitability_confidences must be a complete mapping")
    keys = set(value)
    expected = set(_METHODS)
    if keys != expected:
        missing = sorted(expected.difference(keys))
        extra = sorted(keys.difference(expected))
        details = []
        if missing:
            details.append("missing " + ", ".join(missing))
        if extra:
            details.append("unexpected " + ", ".join(extra))
        raise ValueError(
            "method_suitability_confidences must contain exactly harmony, celltypist, and "
            "gptcelltype (" + "; ".join(details) + ")"
        )
    normalized: dict[str, str] = {}
    for method in _METHODS:
        level = value[method]
        cleaned = level.strip().casefold() if isinstance(level, str) else ""
        if cleaned not in _SUITABILITY_LEVELS:
            raise ValueError(
                f"method_suitability_confidences.{method} must be high, moderate, or low"
            )
        normalized[method] = cleaned
    return normalized


def _normalize_method_suitability_rationales(
    value: Mapping[str, Any],
) -> dict[str, str]:
    """Validate complete method-scoped rationales."""
    if not isinstance(value, Mapping) or set(value) != set(_METHODS):
        raise ValueError(
            "method_suitability_rationales must contain exactly harmony, celltypist, and "
            "gptcelltype"
        )
    normalized: dict[str, str] = {}
    for method in _METHODS:
        rationale = value[method].strip() if isinstance(value[method], str) else ""
        if not rationale:
            raise ValueError(f"method_suitability_rationales.{method} must be non-empty")
        if len(rationale) > _MAX_AGENT_RATIONALE_CHARACTERS:
            raise ValueError(
                f"method_suitability_rationales.{method} must contain at most "
                f"{_MAX_AGENT_RATIONALE_CHARACTERS} characters"
            )
        normalized[method] = rationale
    return normalized


def _normalize_method_evidence_sources(
    value: Mapping[str, Any],
    expected_scopes: Mapping[str, Any],
) -> dict[str, list[str]]:
    """Require an exact, structured declaration of evidence used by each method."""
    if not isinstance(value, Mapping) or set(value) != set(_METHODS):
        raise ValueError(
            "method_evidence_sources must contain exactly harmony, celltypist, and gptcelltype"
        )
    normalized: dict[str, list[str]] = {}
    for method in _METHODS:
        sources = value[method]
        if not isinstance(sources, (list, tuple)) or not all(
            isinstance(source, str) for source in sources
        ):
            raise ValueError(f"method_evidence_sources.{method} must be a list of strings")
        expected = list(expected_scopes[method])
        if list(sources) != expected:
            raise ValueError(
                f"method_evidence_sources.{method} must exactly match "
                f"method_evidence_scopes.method_inputs.{method}: {expected}"
            )
        normalized[method] = expected
    return normalized


def _normalize_celltypist_model_suitability_confidences(
    value: Mapping[str, Any],
    candidate_models: list[str],
) -> dict[str, str]:
    """Validate the agent's qualitative comparison across shortlisted models."""
    if not isinstance(value, Mapping):
        raise ValueError(
            "celltypist_model_suitability_confidences must be a complete mapping"
        )
    expected = set(candidate_models)
    if set(value) != expected:
        missing = sorted(expected.difference(value))
        extra = sorted(set(value).difference(expected))
        details = []
        if missing:
            details.append("missing " + ", ".join(missing))
        if extra:
            details.append("unexpected " + ", ".join(extra))
        raise ValueError(
            "celltypist_model_suitability_confidences must contain exactly the inspected "
            "candidate models (" + "; ".join(details) + ")"
        )
    normalized = {}
    for model in candidate_models:
        level = value[model]
        cleaned = level.strip().casefold() if isinstance(level, str) else ""
        if cleaned not in _SUITABILITY_LEVELS:
            raise ValueError(
                f"celltypist_model_suitability_confidences.{model} must be high, moderate, or low"
            )
        normalized[model] = cleaned
    return normalized


def _normalize_celltypist_model_scope_assessments(
    value: Mapping[str, Any],
    candidate_models: list[str],
) -> dict[str, dict[str, Any]]:
    """Validate an evidence-backed biological coverage comparison."""
    if not isinstance(value, Mapping):
        raise ValueError("celltypist_model_scope_assessments must be a complete mapping")
    expected_models = set(candidate_models)
    if set(value) != expected_models:
        missing = sorted(expected_models.difference(value))
        extra = sorted(set(value).difference(expected_models))
        details = []
        if missing:
            details.append("missing " + ", ".join(missing))
        if extra:
            details.append("unexpected " + ", ".join(extra))
        raise ValueError(
            "celltypist_model_scope_assessments must contain exactly the inspected "
            "candidate models (" + "; ".join(details) + ")"
        )
    normalized: dict[str, dict[str, Any]] = {}
    for model in candidate_models:
        assessment = value[model]
        if not isinstance(assessment, Mapping):
            raise ValueError(
                f"celltypist_model_scope_assessments.{model} must be a mapping"
            )
        if set(assessment) != _CELLTYPIST_MODEL_SCOPE_FIELDS:
            missing = sorted(_CELLTYPIST_MODEL_SCOPE_FIELDS.difference(assessment))
            extra = sorted(set(assessment).difference(_CELLTYPIST_MODEL_SCOPE_FIELDS))
            details = []
            if missing:
                details.append("missing " + ", ".join(missing))
            if extra:
                details.append("unexpected " + ", ".join(extra))
            raise ValueError(
                f"celltypist_model_scope_assessments.{model} fields are invalid: "
                + "; ".join(details)
            )
        normalized_assessment: dict[str, Any] = {}
        for field in (
            "primary_scope_coverage",
            "secondary_scope_coverage",
            "requested_output_coverage",
            "technical_compatibility",
        ):
            level = assessment[field]
            cleaned = level.strip().casefold() if isinstance(level, str) else ""
            if cleaned not in _SCOPE_COVERAGE_LEVELS:
                raise ValueError(
                    f"celltypist_model_scope_assessments.{model}.{field} must be "
                    "adequate, partial, inadequate, or unknown"
                )
            normalized_assessment[field] = cleaned
        for field, minimum_items in (("evidence", 1), ("unsupported_populations", 0)):
            items = assessment[field]
            if isinstance(items, str):
                items = [items] if items.strip() else []
            if (
                not isinstance(items, (list, tuple))
                or len(items) < minimum_items
                or len(items) > 50
                or any(
                    not isinstance(item, str)
                    or not item.strip()
                    or len(item.strip()) > 1_000
                    for item in items
                )
            ):
                qualifier = "one or more" if minimum_items else "zero or more"
                raise ValueError(
                    f"celltypist_model_scope_assessments.{model}.{field} must contain "
                    f"{qualifier} non-empty strings"
                )
            normalized_assessment[field] = [item.strip() for item in items]
        normalized[model] = normalized_assessment
    return normalized


def _celltypist_scope_priority(assessment: Mapping[str, Any]) -> tuple[int, int, int]:
    """Prioritize primary objective, then requested output, then technical support."""
    return (
        _SCOPE_COVERAGE_LEVELS[str(assessment["primary_scope_coverage"])],
        _SCOPE_COVERAGE_LEVELS[str(assessment["requested_output_coverage"])],
        _SCOPE_COVERAGE_LEVELS[str(assessment["technical_compatibility"])],
    )


def _backend_configuration_requirements() -> dict[str, Any]:
    """Describe the complete parameter envelope the validator requires per method."""
    from agents.agent_registry.cell_annotater_agent.tools_impl.gptcelltype_readiness import (
        gptcelltype_readiness_profile,
    )

    readiness_profile = gptcelltype_readiness_profile()
    return {
        method: {
            "parameter_policy_version": _PARAMETER_POLICY_VERSION_BY_METHOD[method],
            "scientific_configuration_fields": sorted(_SCIENTIFIC_CONFIGURATION_FIELDS[method]),
            "operational_configuration_fields": sorted(_OPERATIONAL_CONFIGURATION_FIELDS[method]),
        }
        for method in _METHODS
    } | {
        "gptcelltype": {
            "parameter_policy_version": GPTCELLTYPE_PARAMETER_POLICY_VERSION,
            "scientific_configuration_fields": sorted(
                _SCIENTIFIC_CONFIGURATION_FIELDS["gptcelltype"]
            ),
            "operational_configuration_fields": sorted(
                _OPERATIONAL_CONFIGURATION_FIELDS["gptcelltype"]
            ),
            "readiness_profile_id": readiness_profile["profile_id"],
            "required_readiness_profiled_values": readiness_profile[
                "supported_execution_arguments"
            ],
        }
    }


def register_selection_contract(
    *,
    query_path: Path,
    reference_path: Path | None,
    reference_cell_type_column: str,
    context: Mapping[str, Any],
    method_assessments: Mapping[str, Any],
    selection_policy: Mapping[str, Any],
    celltypist: Mapping[str, Any],
) -> dict[str, Any]:
    """Register one inspector result for validation before backend execution."""
    default_candidates = selection_policy.get("default_candidates")
    fallback_candidates = selection_policy.get("fallback_candidates")
    unknown_candidates = selection_policy.get("unknown_candidates")
    if not all(
        isinstance(candidates, list) and all(candidate in _METHODS for candidate in candidates)
        for candidates in (default_candidates, fallback_candidates, unknown_candidates)
    ):
        raise ValueError("Selection policy contains invalid candidate lists.")
    allowed_candidates = (
        list(default_candidates)
        if default_candidates
        else [*fallback_candidates, *unknown_candidates]
    )
    rationale_guard = selection_policy.get("rationale_guard")
    if not isinstance(rationale_guard, Mapping):
        raise ValueError("Selection policy lacks a structured rationale guard.")
    recommendation = celltypist.get("majority_voting_recommendation")
    majority_voting = (
        recommendation.get("recommended") if isinstance(recommendation, Mapping) else None
    )
    if not isinstance(majority_voting, bool):
        raise ValueError("CellTypist majority-voting recommendation is missing.")

    resolved_query_path = query_path.resolve()
    resolved_reference_path = reference_path.resolve() if reference_path is not None else None
    input_identities = _registered_input_identities(
        resolved_query_path,
        resolved_reference_path,
    )
    celltypist_candidate_models = _celltypist_candidate_models(celltypist)
    configuration_requirements = _backend_configuration_requirements()
    evidence_scopes = method_evidence_scopes(
        reference_provided=resolved_reference_path is not None
    )
    selection_evidence = _canonical_mapping(
        {
            "query_path": str(resolved_query_path),
            "reference_path": (
                str(resolved_reference_path) if resolved_reference_path is not None else None
            ),
            "reference_cell_type_column": reference_cell_type_column,
            "context": context,
            "method_assessments": method_assessments,
            "selection_policy": selection_policy,
            "method_evidence_scopes": evidence_scopes,
            "celltypist_candidate_models": celltypist_candidate_models,
            "celltypist_majority_voting": majority_voting,
            "input_identities": input_identities,
            "backend_configuration_requirements": configuration_requirements,
        },
        field="selection_evidence",
    )
    selection_evidence_sha256 = _canonical_sha256(selection_evidence)
    annotation_context_sha256 = _canonical_sha256(context)
    now = time.monotonic()
    contract_id = secrets.token_hex(16)
    record = {
        "created_at": now,
        "query_path": resolved_query_path,
        "reference_path": resolved_reference_path,
        "reference_cell_type_column": reference_cell_type_column,
        "context": dict(context),
        "annotation_context_sha256": annotation_context_sha256,
        "method_assessments": dict(method_assessments),
        "selection_policy": dict(selection_policy),
        "method_evidence_scopes": evidence_scopes,
        "annotation_context_identity": {
            "version": ANNOTATION_CONTEXT_CONTRACT_VERSION,
            "sha256": annotation_context_sha256,
        },
        "allowed_candidates": allowed_candidates,
        "celltypist_majority_voting": majority_voting,
        "celltypist_candidate_models": celltypist_candidate_models,
        "celltypist_agent_model_selection_required": (
            celltypist.get("selection_mode") == "agent_shortlist"
        ),
        "input_identities": input_identities,
        "selection_evidence_sha256": selection_evidence_sha256,
        "backend_configuration_requirements": configuration_requirements,
        "authorized": False,
    }
    with _LOCK:
        _purge_expired(now)
        _CONTRACTS[contract_id] = record

    return {
        "version": SELECTION_CONTRACT_VERSION,
        "supported_configuration_contract_version": CONFIGURATION_CONTRACT_VERSION,
        "contract_id": contract_id,
        "allowed_candidates": allowed_candidates,
        "validator_tool": "validate_cell_annotation_selection_tool",
        "backend_requires_execution_token": True,
        "expires_in_seconds": _CONTRACT_TTL_SECONDS,
        "celltypist_backend_requirements": {
            "candidate_model_names": record["celltypist_candidate_models"],
            "model_selection_required": record["celltypist_agent_model_selection_required"],
            "model_name": (
                record["celltypist_candidate_models"][0]
                if len(record["celltypist_candidate_models"]) == 1
                else None
            ),
            "inspected_reference_allowed": False,
            "reference_cell_type_column": None,
            "majority_voting": majority_voting,
        },
        "method_evidence_scopes": evidence_scopes,
        "annotation_context_identity": record["annotation_context_identity"],
        "backend_configuration_requirements": configuration_requirements,
        "selection_evidence_identity": {
            "sha256": selection_evidence_sha256,
            "input_identity_version": INPUT_IDENTITY_VERSION,
            "inputs": input_identities,
        },
        "rule": (
            "Validate the selected method and comparative rationale before any annotation "
            "backend. Bind the complete versioned scientific and operational configuration, "
            "then pass the returned one-time execution token to the selected backend."
        ),
    }


def _validation_error(violations: list[str]) -> dict[str, Any]:
    return {
        "status": "error",
        "operation": "validate_cell_annotation_selection",
        "stage": "validate_selection",
        "error_type": "SelectionContractViolation",
        "violations": violations,
        "message": "Selection validation failed: " + "; ".join(violations),
    }


def _validated_backend_rationale(
    rationale: str,
    audit_fragments: list[str],
    required_terms: list[str],
) -> tuple[str, bool]:
    suffix = " ".join(audit_fragments)
    combined = " ".join(fragment for fragment in (rationale, suffix) if fragment)
    if len(combined) <= _MAX_BACKEND_RATIONALE_CHARACTERS:
        return combined, False

    required_terms = list(dict.fromkeys(term for term in required_terms if term))
    policy_suffix = (
        "Required policy audit terms: " + ", ".join(required_terms) + "." if required_terms else ""
    )
    compacted_suffix = " ".join(
        fragment for fragment in (*audit_fragments, policy_suffix) if fragment
    )
    note = (
        " [Full agent rationale retained in the selection-validator trace; "
        "backend metadata is deterministically compacted.] "
    )
    fixed_length = len(note) + len(compacted_suffix) + (1 if compacted_suffix else 0)
    available = _MAX_BACKEND_RATIONALE_CHARACTERS - fixed_length
    if available < 200:
        raise ValueError(
            "Required policy audit terms leave insufficient backend rationale capacity."
        )
    head_length = int(available * 0.65)
    tail_length = available - head_length
    head = rationale[:head_length].rsplit(maxsplit=1)[0]
    tail = rationale[-tail_length:].split(maxsplit=1)[-1]
    compacted = head + note + tail
    if compacted_suffix:
        compacted += " " + compacted_suffix
    return compacted, True


def validate_cell_annotation_selection_tool(
    selection_contract_id: str,
    selected_method: str,
    selection_rationale: str,
    method_suitability_confidences: Mapping[str, str],
    method_suitability_rationales: Mapping[str, str],
    method_evidence_sources: Mapping[str, list[str]],
    output_path: str,
    scientific_configuration: Mapping[str, Any],
    operational_configuration: Mapping[str, Any],
    parameter_policy_version: str,
    celltypist_model_name: str | None = None,
    celltypist_model_selection_rationale: str | None = None,
    celltypist_model_suitability_confidences: Mapping[str, str] | None = None,
    celltypist_model_scope_assessments: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Validate a choice and complete configuration, then mint an execution token."""
    now = time.monotonic()
    with _LOCK:
        _purge_expired(now)
        contract = _CONTRACTS.get(selection_contract_id)
    if contract is None:
        return _validation_error(
            ["selection_contract_id is unknown or expired; rerun method inspection"]
        )

    method = selected_method.strip().casefold() if isinstance(selected_method, str) else ""
    rationale = selection_rationale.strip() if isinstance(selection_rationale, str) else ""
    violations: list[str] = []
    if contract["authorized"]:
        violations.append("selection contract has already been authorized; rerun method inspection")
    if method not in _METHODS:
        violations.append("selected_method must be harmony, celltypist, or gptcelltype")
    elif method not in contract["allowed_candidates"]:
        violations.append(
            f"selected_method {method!r} is outside policy candidates "
            f"{contract['allowed_candidates']}"
        )
    if not rationale:
        violations.append("selection_rationale must be non-empty")
    elif len(rationale) > _MAX_AGENT_RATIONALE_CHARACTERS:
        violations.append(
            f"selection_rationale must contain at most {_MAX_AGENT_RATIONALE_CHARACTERS} characters"
        )
    normalized_rationale = "".join(
        character for character in rationale.casefold() if character.isalnum()
    )
    missing_methods = [name for name in _METHODS if name not in normalized_rationale]
    if missing_methods:
        violations.append(
            "selection_rationale must compare all methods; missing " + ", ".join(missing_methods)
        )
    if (
        contract["reference_path"] is not None
        and REFERENCE_EVIDENCE_SCOPE_PHRASE not in rationale
    ):
        violations.append(
            "selection_rationale must include the exact candidate-reference scope statement: "
            + REFERENCE_EVIDENCE_SCOPE_PHRASE
        )
    suitability_confidences = None
    try:
        suitability_confidences = _normalize_method_suitability_confidences(
            method_suitability_confidences
        )
    except ValueError as exc:
        violations.append(str(exc))
    suitability_rationales = None
    try:
        suitability_rationales = _normalize_method_suitability_rationales(
            method_suitability_rationales
        )
    except ValueError as exc:
        violations.append(str(exc))
    evidence_sources = None
    try:
        evidence_sources = _normalize_method_evidence_sources(
            method_evidence_sources,
            contract["method_evidence_scopes"]["method_inputs"],
        )
    except ValueError as exc:
        violations.append(str(exc))
    if method in _METHODS and suitability_confidences is not None:
        eligible_methods = [
            candidate
            for candidate in _METHODS
            if contract["method_assessments"].get(candidate, {}).get("prerequisites")
            != "not_met"
        ]
        selected_level = _SUITABILITY_LEVELS[suitability_confidences[method]]
        higher_methods = [
            candidate
            for candidate in eligible_methods
            if _SUITABILITY_LEVELS[suitability_confidences[candidate]] > selected_level
        ]
        if higher_methods:
            violations.append(
                f"selected_method {method!r} has lower qualitative suitability than runnable "
                "method(s): " + ", ".join(higher_methods)
            )
    selected_celltypist_model = None
    celltypist_model_confidences = None
    celltypist_scope_assessments = None
    model_rationale = (
        celltypist_model_selection_rationale.strip()
        if isinstance(celltypist_model_selection_rationale, str)
        else ""
    )
    if method == "celltypist":
        candidate_models = list(contract["celltypist_candidate_models"])
        selected_celltypist_model = (
            celltypist_model_name.strip()
            if isinstance(celltypist_model_name, str) and celltypist_model_name.strip()
            else (candidate_models[0] if len(candidate_models) == 1 else None)
        )
        if selected_celltypist_model not in candidate_models:
            violations.append(
                "celltypist_model_name must be one of the technically inspected candidate models"
            )
        try:
            celltypist_scope_assessments = _normalize_celltypist_model_scope_assessments(
                celltypist_model_scope_assessments,
                candidate_models,
            )
        except ValueError as exc:
            violations.append(str(exc))
        if contract["celltypist_agent_model_selection_required"]:
            if not model_rationale:
                violations.append("celltypist_model_selection_rationale must be non-empty")
            else:
                missing_candidate_names = [
                    candidate for candidate in candidate_models if candidate not in model_rationale
                ]
                if missing_candidate_names:
                    violations.append(
                        "celltypist_model_selection_rationale must compare every shortlisted "
                        "model; missing " + ", ".join(missing_candidate_names)
                    )
            try:
                celltypist_model_confidences = (
                    _normalize_celltypist_model_suitability_confidences(
                        celltypist_model_suitability_confidences,
                        candidate_models,
                    )
                )
            except ValueError as exc:
                violations.append(str(exc))
            if (
                selected_celltypist_model in candidate_models
                and celltypist_model_confidences is not None
            ):
                selected_level = _SUITABILITY_LEVELS[
                    celltypist_model_confidences[selected_celltypist_model]
                ]
                higher_models = [
                    candidate
                    for candidate in candidate_models
                    if _SUITABILITY_LEVELS[celltypist_model_confidences[candidate]]
                    > selected_level
                ]
                if higher_models:
                    violations.append(
                        f"celltypist_model_name {selected_celltypist_model!r} has lower "
                        "qualitative suitability than inspected model(s): "
                        + ", ".join(higher_models)
                    )
        else:
            celltypist_model_confidences = {
                candidate: "high" if candidate == selected_celltypist_model else "moderate"
                for candidate in candidate_models
            }
        if (
            selected_celltypist_model in candidate_models
            and celltypist_scope_assessments is not None
        ):
            selected_priority = _celltypist_scope_priority(
                celltypist_scope_assessments[selected_celltypist_model]
            )
            better_scope_models = [
                candidate
                for candidate in candidate_models
                if _celltypist_scope_priority(celltypist_scope_assessments[candidate])
                > selected_priority
            ]
            if better_scope_models:
                violations.append(
                    f"celltypist_model_name {selected_celltypist_model!r} is lower priority for "
                    "the immutable annotation scope than inspected model(s): "
                    + ", ".join(better_scope_models)
                )
    try:
        authorized_output_path = resolve_project_output(
            output_path,
            suffix=".h5ad",
        ).resolve()
    except Exception as exc:
        violations.append(f"output_path is invalid: {exc}")
    configuration_contract = None
    if not isinstance(scientific_configuration, Mapping):
        violations.append("scientific_configuration must be a complete mapping")
    if not isinstance(operational_configuration, Mapping):
        violations.append("operational_configuration must be a complete mapping")
    if not violations:
        violations.extend(
            _input_identity_violations(contract, selected_method=method)
        )
    if not violations:
        try:
            configuration_contract = _configuration_contract(
                selected_method=method,
                parameter_policy_version=parameter_policy_version,
                scientific_configuration=scientific_configuration,
                operational_configuration=operational_configuration,
                selection_evidence_sha256=contract["selection_evidence_sha256"],
            )
            if method == "gptcelltype":
                expected_readiness_profile_id = contract["backend_configuration_requirements"][
                    "gptcelltype"
                ]["readiness_profile_id"]
                actual_readiness_profile_id = configuration_contract["scientific_configuration"][
                    "readiness_execution_binding"
                ]["readiness_profile_id"]
                if actual_readiness_profile_id != expected_readiness_profile_id:
                    violations.append(
                        "GPTCellType readiness profile changed since method inspection; "
                        "rerun method inspection"
                    )
        except ValueError as exc:
            violations.append(str(exc))
    if violations:
        return _validation_error(violations)

    selection_policy = contract["selection_policy"]
    rationale_guard = selection_policy["rationale_guard"]
    claim_status = rationale_guard["claim_status_by_method"][method]
    required_phrase = rationale_guard["required_exact_phrase_by_claim_status"].get(claim_status)
    disclosure_codes = list(rationale_guard["required_disclosure_codes"])
    adverse_codes = _required_adverse_codes(
        method,
        contract["method_assessments"],
    )
    audit_fragments = [
        "Method suitability confidences: "
        + ", ".join(
            f"{candidate}={suitability_confidences[candidate]}" for candidate in _METHODS
        )
        + "."
    ]
    backend_rationale = rationale + " Method-scoped evidence: " + " ".join(
        f"{candidate}: {suitability_rationales[candidate]}" for candidate in _METHODS
    )
    if method == "celltypist" and selected_celltypist_model is not None:
        backend_rationale += (
            " CellTypist model selection: "
            + (model_rationale or f"{selected_celltypist_model} was the sole inspected model.")
        )
        audit_fragments.append(
            f"Selected CellTypist model: {selected_celltypist_model}. Model suitability "
            "confidences: "
            + ", ".join(
                f"{candidate}={celltypist_model_confidences[candidate]}"
                for candidate in contract["celltypist_candidate_models"]
            )
            + "."
        )
        audit_fragments.append(
            "CellTypist scope coverage: "
            + ", ".join(
                f"{candidate}(primary="
                f"{celltypist_scope_assessments[candidate]['primary_scope_coverage']},"
                f"requested_output="
                f"{celltypist_scope_assessments[candidate]['requested_output_coverage']},"
                f"secondary="
                f"{celltypist_scope_assessments[candidate]['secondary_scope_coverage']},"
                f"technical="
                f"{celltypist_scope_assessments[candidate]['technical_compatibility']})"
                for candidate in contract["celltypist_candidate_models"]
            )
            + "."
        )
    if required_phrase and required_phrase not in rationale:
        audit_fragments.append(f"Selection status: {required_phrase}.")
    missing_disclosures = [code for code in disclosure_codes if code not in rationale]
    if missing_disclosures:
        audit_fragments.append("Reference disclosures: " + ", ".join(missing_disclosures) + ".")
    missing_adverse = [code for code in adverse_codes if code not in rationale]
    if missing_adverse:
        audit_fragments.append("Adverse policy evidence: " + ", ".join(missing_adverse) + ".")
    try:
        validated_rationale, rationale_compacted = _validated_backend_rationale(
            backend_rationale,
            audit_fragments,
            [
                *_METHODS,
                *([required_phrase] if required_phrase else []),
                *disclosure_codes,
                *adverse_codes,
            ],
        )
    except ValueError as exc:
        return _validation_error([str(exc)])

    execution_token = secrets.token_hex(16)
    execution_record = {
        "created_at": now,
        "contract_id": selection_contract_id,
        "selected_method": method,
        "validated_selection_rationale": validated_rationale,
        "method_suitability_confidences": suitability_confidences,
        "method_suitability_rationales": suitability_rationales,
        "method_evidence_sources": evidence_sources,
        "query_path": contract["query_path"],
        "reference_path": contract["reference_path"],
        "reference_cell_type_column": contract["reference_cell_type_column"],
        "output_path": authorized_output_path,
        "context": contract["context"],
        "method_evidence_scopes": contract["method_evidence_scopes"],
        "celltypist_majority_voting": contract["celltypist_majority_voting"],
        "celltypist_model_name": selected_celltypist_model,
        "celltypist_model_suitability_confidences": celltypist_model_confidences,
        "celltypist_model_scope_assessments": celltypist_scope_assessments,
        "input_identities": contract["input_identities"],
        "selection_evidence_sha256": contract["selection_evidence_sha256"],
        "configuration_contract": configuration_contract,
        "consumed": False,
    }
    with _LOCK:
        _purge_expired(now)
        current = _CONTRACTS.get(selection_contract_id)
        if current is None or current["authorized"]:
            return _validation_error(
                [
                    "selection contract expired or was concurrently authorized; "
                    "rerun method inspection"
                ]
            )
        current["authorized"] = True
        _EXECUTION_TOKENS[execution_token] = execution_record
    return {
        "status": "success",
        "operation": "validate_cell_annotation_selection",
        "version": SELECTION_CONTRACT_VERSION,
        "execution_token_version": CONFIGURATION_EXECUTION_TOKEN_VERSION,
        "selection_contract_id": selection_contract_id,
        "selected_method": method,
        "authorized_output_path": str(authorized_output_path),
        "agent_selection_rationale": rationale,
        "agent_selection_rationale_sha256": hashlib.sha256(rationale.encode("utf-8")).hexdigest(),
        "validated_selection_rationale": validated_rationale,
        "method_suitability_confidences": suitability_confidences,
        "method_suitability_rationales": suitability_rationales,
        "method_evidence_sources": evidence_sources,
        "celltypist_model_name": selected_celltypist_model,
        "celltypist_model_selection_rationale": model_rationale or None,
        "celltypist_model_suitability_confidences": celltypist_model_confidences,
        "celltypist_model_scope_assessments": celltypist_scope_assessments,
        "validated_rationale_compacted_for_backend": rationale_compacted,
        "required_exact_phrase": required_phrase,
        "required_disclosure_codes": disclosure_codes,
        "required_adverse_reason_codes": adverse_codes,
        "method_evidence_scopes": contract["method_evidence_scopes"],
        "configuration_contract": configuration_contract,
        "backend_requirements": {
            "selection_execution_token": execution_token,
            "configuration_contract_version": (
                configuration_contract["version"] if configuration_contract is not None else None
            ),
            "configuration_sha256": (
                configuration_contract["configuration_sha256"]
                if configuration_contract is not None
                else None
            ),
            "celltypist_model_name": selected_celltypist_model,
            "celltypist_reference_allowed": False,
            "celltypist_reference_cell_type_column": None,
            "celltypist_majority_voting": contract["celltypist_majority_voting"],
            "gptcelltype_species": (
                contract["context"].get("species") if method == "gptcelltype" else None
            ),
            "gptcelltype_tissue": (
                contract["context"].get("tissue") if method == "gptcelltype" else None
            ),
        },
    }


def authorize_backend_execution(
    *,
    selection_execution_token: str,
    selected_method: str,
    spatial_anndata_path: str,
    output_path: str,
    reference_anndata_path: str | None = None,
    reference_cell_type_column: str | None = None,
    celltypist_model_name: str | None = None,
    celltypist_majority_voting: bool | None = None,
    species: str | None = None,
    tissue: str | None = None,
    scientific_configuration: Mapping[str, Any] | None = None,
    operational_configuration: Mapping[str, Any] | None = None,
    parameter_policy_version: str | None = None,
    configuration_sha256: str | None = None,
) -> dict[str, Any]:
    """Consume a validated token after checking the exact backend invocation."""
    now = time.monotonic()
    with _LOCK:
        _purge_expired(now)
        record = _EXECUTION_TOKENS.get(selection_execution_token)
        if record is None:
            return _validation_error(["selection_execution_token is unknown or expired"])
        violations: list[str] = []
        if record["consumed"]:
            violations.append("selection_execution_token has already been consumed")
        if selected_method != record["selected_method"]:
            violations.append("backend does not match the validated selected method")
        try:
            query_path = resolve_workspace_input(spatial_anndata_path).resolve()
        except Exception as exc:
            violations.append(f"could not resolve spatial_anndata_path: {exc}")
        else:
            if query_path != record["query_path"]:
                violations.append("backend query path does not match the inspected query")
        try:
            backend_output_path = resolve_project_output(
                output_path,
                suffix=".h5ad",
            ).resolve()
        except Exception as exc:
            violations.append(f"could not resolve output_path: {exc}")
        else:
            if backend_output_path != record["output_path"]:
                violations.append("backend output path does not match the authorized output")
        if selected_method == "harmony":
            try:
                reference_path = (
                    resolve_workspace_input(reference_anndata_path).resolve()
                    if reference_anndata_path is not None
                    else None
                )
            except Exception as exc:
                violations.append(f"could not resolve reference_anndata_path: {exc}")
            else:
                if reference_path != record["reference_path"]:
                    violations.append(
                        "Harmony reference path does not match the inspected reference"
                    )
            if reference_cell_type_column != record["reference_cell_type_column"]:
                violations.append(
                    "Harmony label column does not match the inspected reference label column"
                )
        if selected_method == "celltypist":
            built_in_matches = bool(
                celltypist_model_name == record["celltypist_model_name"]
                and reference_anndata_path is None
            )
            if not built_in_matches:
                violations.append(
                    "CellTypist must use the exact selected built-in model; the candidate "
                    "reference is authorized only for Harmony"
                )
            if celltypist_majority_voting is not record["celltypist_majority_voting"]:
                violations.append(
                    "CellTypist majority_voting does not match the inspector recommendation"
                )
        if selected_method == "gptcelltype":
            for field, provided in (("species", species), ("tissue", tissue)):
                expected = record["context"].get(field)
                if (
                    isinstance(expected, str)
                    and expected.strip()
                    and (
                        not isinstance(provided, str)
                        or provided.strip().casefold() != expected.strip().casefold()
                    )
                ):
                    violations.append(f"GPTCellType {field} does not match the inspected context")
        expected_configuration = record["configuration_contract"]
        if expected_configuration is None:
            violations.append("execution token is missing its required configuration contract")
        else:
            violations.extend(
                _input_identity_violations(record, selected_method=selected_method)
            )
            if not isinstance(scientific_configuration, Mapping):
                violations.append(
                    "backend scientific_configuration is required for a v2 execution token"
                )
            if not isinstance(operational_configuration, Mapping):
                violations.append(
                    "backend operational_configuration is required for a v2 execution token"
                )
            actual_configuration = None
            if isinstance(scientific_configuration, Mapping) and isinstance(
                operational_configuration, Mapping
            ):
                try:
                    actual_configuration = _configuration_contract(
                        selected_method=selected_method,
                        parameter_policy_version=parameter_policy_version,
                        scientific_configuration=scientific_configuration,
                        operational_configuration=operational_configuration,
                        selection_evidence_sha256=record["selection_evidence_sha256"],
                    )
                except ValueError as exc:
                    violations.append(str(exc))
            if actual_configuration is not None:
                if (
                    actual_configuration["parameter_policy_version"]
                    != expected_configuration["parameter_policy_version"]
                ):
                    violations.append(
                        "backend parameter_policy_version does not match the authorized version"
                    )
                if (
                    actual_configuration["scientific_configuration"]
                    != expected_configuration["scientific_configuration"]
                ):
                    violations.append(
                        "backend scientific_configuration does not match the "
                        "authorized configuration"
                    )
                if (
                    actual_configuration["operational_configuration"]
                    != expected_configuration["operational_configuration"]
                ):
                    violations.append(
                        "backend operational_configuration does not match the "
                        "authorized configuration"
                    )
                if (
                    actual_configuration["configuration_sha256"]
                    != expected_configuration["configuration_sha256"]
                ):
                    violations.append(
                        "backend canonical configuration hash does not match the authorized hash"
                    )
            if not isinstance(configuration_sha256, str) or (
                configuration_sha256 != expected_configuration["configuration_sha256"]
            ):
                violations.append("backend configuration_sha256 does not match the authorized hash")
        if violations:
            return _validation_error(violations)
        record["consumed"] = True
        result = {
            "status": "success",
            "validated_selection_rationale": record["validated_selection_rationale"],
            "selection_contract_id": record["contract_id"],
        }
        result["configuration_contract"] = expected_configuration
        return result
