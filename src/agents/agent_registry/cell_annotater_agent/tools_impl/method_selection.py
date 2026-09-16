"""Leakage-safe evidence gathering for cell-annotation method selection."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Annotated, Any

import anndata as ad
import numpy as np
import requests
from pydantic import Field

from agents.cell_annotation_context import get_bound_cell_annotation_context
from agents.agent_registry.cell_annotater_agent.tools_impl.harmony_transfer import (
    ENSEMBL_GENE_RE,
    GENE_ID_COLUMNS,
    GENE_SYMBOL_COLUMNS,
    _evenly_spaced_indices,
    _inspect_expression_matrix,
)
from agents.agent_registry.cell_annotater_agent.tools_impl.gptcelltype_readiness import (
    inspect_gptcelltype_readiness,
)
from agents.agent_registry.cell_annotater_agent.tools_impl.selection_preflight import (
    assess_celltypist_selection_evidence,
    assess_gptcelltype_selection_evidence,
    assess_harmony_selection_evidence,
    build_method_selection_policy,
    preflight_reference_query_panel,
    preflight_celltypist_model,
)
from agents.agent_registry.cell_annotater_agent.tools_impl.selection_contract import (
    method_evidence_scopes,
    register_selection_contract,
)
from agents.workspace_paths import (
    resolve_project_output,
    resolve_workspace_input,
    workspace_relative,
)


_HEALTHY_DISEASE_VALUES = {
    "control",
    "healthy",
    "normal",
    "unaffected",
}
_DISEASE_FAMILY_TERMS = {
    "carcinoma": {"adenocarcinoma", "carcinoma"},
    "glioma": {"glioblastoma", "glioma"},
    "leukemia": {"leukaemia", "leukemia"},
    "lymphoma": {"lymphoma"},
    "melanoma": {"melanoma"},
    "myeloma": {"myeloma"},
    "sarcoma": {"sarcoma"},
}
_REFERENCE_METADATA_COLUMNS = {
    "tissues": ("tissue", "tissue_general"),
    "diseases": ("disease",),
    "assays": ("assay",),
    "developmental_stages": ("development_stage", "developmental_stage"),
}
_CELLXGENE_PROVENANCE_KEYS = (
    "dataset_ids",
    "census_version",
    "label_column",
    "max_cells_per_label",
    "random_state",
    "include_labels",
    "organism",
    "tissues",
    "diseases",
)
_MAX_REFERENCE_METADATA_VALUES = 50
_CELLTYPIST_CACHE_PATH = "cell_annotation/celltypist_cache"
_CELLTYPIST_MODEL_STRING_FIELDS = ("source", "url", "version", "date")
_CELLTYPIST_MODEL_CATALOG_VERSION = "celltypist_model_catalog_v1"
_MAX_CELLTYPIST_MODEL_SHORTLIST = 3
_CELLTYPIST_MAJORITY_VOTING_POLICY_VERSION = (
    "celltypist_majority_voting_policy_v1"
)
_CELLTYPIST_MAJORITY_VOTING_MIN_NONZERO_CELLS = 51
_REFERENCE_CONTEXT_DISCLOSURE_CODES = {
    "tissues": "reference_tissue_context_heterogeneity",
    "diseases": "reference_disease_context_heterogeneity",
    "assays": "reference_assay_context_heterogeneity",
    "developmental_stages": "reference_developmental_stage_context_heterogeneity",
}
_ANNOTATION_SCOPE_FIELDS = (
    "primary_scope",
    "secondary_scope",
    "sampling_context",
    "requested_output",
)
_ANNOTATION_CONTEXT_IDENTITY_VERSION = "cell_annotation_context_contract_v1"


def _json_safe(value: Any) -> Any:
    """Convert common AnnData metadata values into JSON-compatible values."""
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return [_json_safe(item) for item in value.tolist()]
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _clean_context_value(value: str | None) -> str | None:
    """Normalize an optional user-supplied biological context string."""
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _normalize_annotation_scope(
    value: Mapping[str, Any] | None,
) -> dict[str, str] | None:
    """Validate the caller's immutable annotation objective."""
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise ValueError("annotation_scope must be a mapping.")
    expected = set(_ANNOTATION_SCOPE_FIELDS)
    observed = set(value)
    if observed != expected:
        missing = sorted(expected.difference(observed))
        unexpected = sorted(observed.difference(expected))
        details = []
        if missing:
            details.append("missing " + ", ".join(missing))
        if unexpected:
            details.append("unexpected " + ", ".join(unexpected))
        raise ValueError("annotation_scope fields are invalid: " + "; ".join(details) + ".")
    normalized: dict[str, str] = {}
    for field in _ANNOTATION_SCOPE_FIELDS:
        item = _clean_context_value(value[field])
        if item is None:
            raise ValueError(f"annotation_scope.{field} must be a non-empty string.")
        normalized[field] = item
    return normalized


def _annotation_context_sha256(context: Mapping[str, Any]) -> str:
    payload = json.dumps(
        context,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _catalog_model_card(record: Mapping[str, Any]) -> dict[str, Any] | None:
    """Return one verified, compact model card from the official catalog."""
    model = str(record.get("model") or record.get("filename") or "").strip()
    description = str(record.get("description") or record.get("details") or "").strip()
    if not model:
        return None
    card: dict[str, Any] = {"model": model, "description": description}
    for field in _CELLTYPIST_MODEL_STRING_FIELDS:
        value = record.get(field)
        if value is not None and str(value).strip():
            card[field] = str(value).strip()
    n_cell_types = record.get("n_cell_types", record.get("No_celltypes"))
    if n_cell_types is not None and not isinstance(n_cell_types, (bool, np.bool_)):
        try:
            parsed_n_cell_types = int(n_cell_types)
        except (TypeError, ValueError):
            parsed_n_cell_types = None
        if parsed_n_cell_types is not None and parsed_n_cell_types >= 0:
            card["n_cell_types"] = parsed_n_cell_types
    if isinstance(record.get("default"), (bool, np.bool_)):
        card["default"] = bool(record["default"])
    return card


def _load_celltypist_catalog() -> dict[str, Any]:
    """Load the official catalog without ranking models or interpreting context."""
    cache_root = resolve_project_output(_CELLTYPIST_CACHE_PATH)
    model_dir = cache_root / "data" / "models"
    cache_display = workspace_relative(cache_root)
    version = importlib.metadata.version("celltypist")
    index_path = model_dir / "models.json"
    if index_path.exists():
        catalog = json.loads(index_path.read_text(encoding="utf-8"))
        catalog_source = "cached"
    else:
        response = requests.get(
            "https://celltypist.cog.sanger.ac.uk/models/models.json",
            timeout=30,
        )
        response.raise_for_status()
        catalog = response.json()
        catalog_source = "live"
    cards = [
        card
        for record in catalog.get("models", [])
        if (card := _catalog_model_card(record)) is not None
    ]
    canonical_catalog = json.dumps(cards, ensure_ascii=False, separators=(",", ":"))
    return {
        "status": "success",
        "catalog_version": _CELLTYPIST_MODEL_CATALOG_VERSION,
        "celltypist_version": version,
        "cache_dir": cache_display,
        "catalog_source": catalog_source,
        "catalog_last_update": catalog.get("last_update"),
        "catalog_sha256": hashlib.sha256(canonical_catalog.encode("utf-8")).hexdigest(),
        "models": cards,
        "n_models": len(cards),
    }


def list_celltypist_model_catalog_tool() -> dict[str, Any]:
    """List verified CellTypist model cards without choosing or scoring a model."""
    try:
        return _load_celltypist_catalog()
    except Exception as exc:
        return {
            "status": "error",
            "operation": "list_celltypist_model_catalog",
            "error_type": type(exc).__name__,
            "message": str(exc),
            "models": [],
        }


def _agent_shortlisted_celltypist_catalog(
    model_names: list[str],
    expected_catalog_sha256: str,
) -> dict[str, Any]:
    """Resolve an LLM shortlist against the verified catalog without re-ranking it."""
    if not 1 <= len(model_names) <= _MAX_CELLTYPIST_MODEL_SHORTLIST:
        raise ValueError(
            "celltypist_model_names must contain between 1 and "
            f"{_MAX_CELLTYPIST_MODEL_SHORTLIST} exact catalog filenames"
        )
    if any(not isinstance(name, str) or not name.strip() for name in model_names):
        raise ValueError("celltypist_model_names must contain non-empty strings")
    cleaned_names = [name.strip() for name in model_names]
    if len(set(cleaned_names)) != len(cleaned_names):
        raise ValueError("celltypist_model_names must not contain duplicates")
    catalog = _load_celltypist_catalog()
    if catalog["catalog_sha256"] != expected_catalog_sha256:
        raise ValueError("CellTypist catalog changed since the agent reviewed it")
    by_name = {record["model"]: record for record in catalog["models"]}
    unknown = [name for name in cleaned_names if name not in by_name]
    if unknown:
        raise ValueError("Unknown CellTypist model filename(s): " + ", ".join(unknown))
    return {
        **{key: value for key, value in catalog.items() if key != "models"},
        "selection_mode": "agent_shortlist",
        "models": [by_name[name] for name in cleaned_names],
        "shortlist_size": len(cleaned_names),
    }


def _metadata_coverage(dataset: ad.AnnData, candidates: tuple[str, ...]) -> dict[str, Any]:
    """Summarize allowed reference metadata without inspecting query annotations."""
    column = next((candidate for candidate in candidates if candidate in dataset.obs), None)
    if column is None:
        return {"column_present": False, "column": None, "n_unique": 0, "values": []}
    values = dataset.obs[column].dropna().astype(str).map(str.strip)
    values = values[values != ""]
    unique_values = sorted(set(values), key=str.casefold)
    return {
        "column_present": True,
        "column": column,
        "n_unique": int(len(unique_values)),
        "values": unique_values[:_MAX_REFERENCE_METADATA_VALUES],
        "values_truncated": len(unique_values) > _MAX_REFERENCE_METADATA_VALUES,
    }


def _cellxgene_provenance(dataset: ad.AnnData) -> dict[str, Any]:
    """Return a safe whitelist from a CELLxGENE subset provenance record."""
    provenance = dataset.uns.get("tissueagent_cellxgene_subset")
    if not isinstance(provenance, Mapping):
        return {"available": False}
    safe = {
        key: _json_safe(provenance[key]) for key in _CELLXGENE_PROVENANCE_KEYS if key in provenance
    }
    return {"available": True, **safe}


def _reference_source_breakdown(
    dataset: ad.AnnData,
    source_column: str | None,
    label_column: str,
) -> tuple[list[dict[str, Any]], bool]:
    """Summarize independent-reference coverage within each source dataset."""
    if source_column is None:
        return [], False

    source_values = dataset.obs[source_column].astype("string").fillna("").str.strip()
    source_ids = sorted(
        {value for value in source_values if value},
        key=lambda value: (value.casefold(), value),
    )
    breakdown: list[dict[str, Any]] = []
    for source_id in source_ids[:_MAX_REFERENCE_METADATA_VALUES]:
        source_mask = source_values == source_id
        if label_column in dataset.obs:
            labels = (
                dataset.obs.loc[source_mask, label_column].dropna().astype(str).map(str.strip)
            )
            labels = labels[labels != ""]
            label_counts = labels.value_counts()
            label_inventory = [
                {"label": str(label), "count": int(count)}
                for label, count in sorted(
                    label_counts.items(),
                    key=lambda item: (str(item[0]).casefold(), str(item[0])),
                )[:_MAX_REFERENCE_METADATA_VALUES]
            ]
            label_inventory_truncated = len(label_counts) > _MAX_REFERENCE_METADATA_VALUES
        else:
            label_inventory = []
            label_inventory_truncated = False

        metadata_values: dict[str, list[str]] = {}
        metadata_values_truncated: dict[str, bool] = {}
        for name, candidates in _REFERENCE_METADATA_COLUMNS.items():
            column = next((candidate for candidate in candidates if candidate in dataset.obs), None)
            if column is None:
                unique_values: list[str] = []
            else:
                values = dataset.obs.loc[source_mask, column].dropna().astype(str).map(str.strip)
                values = values[values != ""]
                unique_values = sorted(
                    set(values),
                    key=lambda value: (value.casefold(), value),
                )
            metadata_values[name] = unique_values[:_MAX_REFERENCE_METADATA_VALUES]
            metadata_values_truncated[name] = (
                len(unique_values) > _MAX_REFERENCE_METADATA_VALUES
            )
        breakdown.append(
            {
                "source_id": source_id,
                "n_cells": int(source_mask.sum()),
                "label_inventory": label_inventory,
                "label_inventory_truncated": label_inventory_truncated,
                "metadata_values": metadata_values,
                "metadata_values_truncated": metadata_values_truncated,
            }
        )
    return breakdown, len(source_ids) > _MAX_REFERENCE_METADATA_VALUES


def _reference_coverage(
    spatial_path: Path,
    reference_path: Path,
    reference_cell_type_column: str,
) -> dict[str, Any]:
    """Summarize independent-reference suitability without inspecting query labels."""
    spatial = ad.read_h5ad(spatial_path, backed="r")
    reference = ad.read_h5ad(reference_path, backed="r")
    try:

        def identifier_sets(dataset: ad.AnnData) -> dict[str, set[str]]:
            representations = {
                "var_names": {
                    str(value).strip() for value in dataset.var_names if str(value).strip()
                }
            }
            for column in (*GENE_SYMBOL_COLUMNS, *GENE_ID_COLUMNS):
                if column not in dataset.var:
                    continue
                values = dataset.var[column].astype("string").fillna("").astype(str).str.strip()
                identifiers = {
                    value
                    for value in values
                    if value and value.casefold() not in {"nan", "none", "na"}
                }
                if identifiers:
                    representations[f"var['{column}']"] = identifiers
            return representations

        spatial_identifiers = identifier_sets(spatial)
        reference_identifiers = identifier_sets(reference)
        overlaps: list[dict[str, Any]] = []
        for query_source, query_values in spatial_identifiers.items():
            query_casefold = {value.casefold() for value in query_values}
            for reference_source, reference_values in reference_identifiers.items():
                reference_casefold = {value.casefold() for value in reference_values}
                overlaps.append(
                    {
                        "query_source": query_source,
                        "reference_source": reference_source,
                        "exact_count": int(len(query_values.intersection(reference_values))),
                        "case_insensitive_count": int(
                            len(query_casefold.intersection(reference_casefold))
                        ),
                        "query_fraction_case_insensitive": float(
                            len(query_casefold.intersection(reference_casefold))
                            / max(1, len(query_casefold))
                        ),
                        "reference_fraction_case_insensitive": float(
                            len(query_casefold.intersection(reference_casefold))
                            / max(1, len(reference_casefold))
                        ),
                    }
                )
        best_overlap = max(
            overlaps,
            key=lambda item: (
                item["case_insensitive_count"],
                item["exact_count"],
                item["query_source"] == "var_names",
                item["reference_source"] == "var_names",
            ),
        )

        spatial_obs_names = {str(value) for value in spatial.obs_names}
        reference_obs_names = {str(value) for value in reference.obs_names}
        observation_name_overlap_count = len(
            spatial_obs_names.intersection(reference_obs_names)
        )
        observation_name_overlap = {
            "status": (
                "overlap_detected"
                if observation_name_overlap_count
                else "no_overlap_detected"
            ),
            "exact_count": int(observation_name_overlap_count),
            "query_fraction": float(
                observation_name_overlap_count / max(1, spatial.n_obs)
            ),
            "reference_fraction": float(
                observation_name_overlap_count / max(1, reference.n_obs)
            ),
            "warning": (
                "Exact query/reference observation-name overlap may indicate data leakage or "
                "an identifier collision; review dataset provenance before using the reference."
                if observation_name_overlap_count
                else None
            ),
        }

        if reference_cell_type_column in reference.obs:
            labels = reference.obs[reference_cell_type_column]
            non_missing = labels.notna()
            nonempty = labels[non_missing].astype(str).map(str.strip) != ""
            n_labeled = int(nonempty.sum())
            n_unique_labels = int(labels[non_missing][nonempty].astype(str).nunique())
            label_counts = (
                labels[non_missing][nonempty]
                .astype(str)
                .value_counts()
                .sort_index(key=lambda index: index.str.casefold())
            )
            label_coverage = {
                "column": reference_cell_type_column,
                "column_present": True,
                "n_labeled": n_labeled,
                "n_missing_or_empty": int(reference.n_obs - n_labeled),
                "completeness_fraction": float(n_labeled / reference.n_obs),
                "n_unique_labels": n_unique_labels,
                "inventory": [
                    {"label": str(label), "count": int(count)}
                    for label, count in label_counts.iloc[:_MAX_REFERENCE_METADATA_VALUES].items()
                ],
                "inventory_truncated": len(label_counts) > _MAX_REFERENCE_METADATA_VALUES,
            }
        else:
            label_coverage = {
                "column": reference_cell_type_column,
                "column_present": False,
                "n_labeled": 0,
                "n_missing_or_empty": int(reference.n_obs),
                "completeness_fraction": 0.0,
                "n_unique_labels": 0,
                "inventory": [],
                "inventory_truncated": False,
            }

        source_column = next(
            (
                candidate
                for candidate in ("dataset_id", "source_dataset_id")
                if candidate in reference.obs
            ),
            None,
        )
        if source_column:
            source_values = (
                reference.obs[source_column].astype("string").fillna("").str.strip()
            )
            source_count = len({value for value in source_values if value})
        else:
            source_count = None
        source_breakdown, source_breakdown_truncated = _reference_source_breakdown(
            reference,
            source_column,
            reference_cell_type_column,
        )
        provenance = _cellxgene_provenance(reference)
        if source_count is None and provenance.get("available"):
            dataset_ids = provenance.get("dataset_ids")
            if isinstance(dataset_ids, list):
                source_count = len(set(str(value) for value in dataset_ids))

        return {
            "shape": [int(reference.n_obs), int(reference.n_vars)],
            "label_coverage": label_coverage,
            "metadata_coverage": {
                name: _metadata_coverage(reference, candidates)
                for name, candidates in _REFERENCE_METADATA_COLUMNS.items()
            },
            "source_count": source_count,
            "source_column": source_column,
            "source_breakdown": source_breakdown,
            "source_breakdown_truncated": source_breakdown_truncated,
            "cellxgene_provenance": provenance,
            "observation_name_overlap": observation_name_overlap,
            "shared_genes": {
                "exact_var_name_count": next(
                    item["exact_count"]
                    for item in overlaps
                    if item["query_source"] == item["reference_source"] == "var_names"
                ),
                "case_insensitive_var_name_count": next(
                    item["case_insensitive_count"]
                    for item in overlaps
                    if item["query_source"] == item["reference_source"] == "var_names"
                ),
                "best_available_representation": best_overlap,
                "representations_checked": {
                    "query": sorted(spatial_identifiers),
                    "reference": sorted(reference_identifiers),
                },
            },
        }
    finally:
        spatial.file.close()
        reference.file.close()


def _gene_identifier_summary(path: Path) -> dict[str, Any]:
    """Summarize feature identifiers without returning any gene names."""
    dataset = ad.read_h5ad(path, backed="r")
    try:
        indices = _evenly_spaced_indices(dataset.n_vars, 2048)
        names = [str(dataset.var_names[index]).strip() for index in indices]
        ensembl_fraction = float(np.mean([bool(ENSEMBL_GENE_RE.match(name)) for name in names]))
        numeric_fraction = float(np.mean([name.isdigit() for name in names]))
        symbol_fraction = float(
            np.mean(
                [
                    bool(re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]*", name))
                    and not ENSEMBL_GENE_RE.match(name)
                    for name in names
                ]
            )
        )
        if ensembl_fraction >= 0.8:
            namespace = "ensembl_like"
        elif symbol_fraction >= 0.8:
            namespace = "gene_symbol_like"
        elif numeric_fraction >= 0.8:
            namespace = "numeric_like"
        else:
            namespace = "mixed_or_unknown"
        return {
            "sampled_features": len(names),
            "var_names_unique": bool(dataset.var_names.is_unique),
            "namespace": namespace,
            "ensembl_like_fraction": ensembl_fraction,
            "gene_symbol_like_fraction": symbol_fraction,
            "numeric_like_fraction": numeric_fraction,
            "symbol_columns_present": [
                column for column in GENE_SYMBOL_COLUMNS if column in dataset.var
            ],
            "identifier_columns_present": [
                column for column in GENE_ID_COLUMNS if column in dataset.var
            ],
        }
    finally:
        dataset.file.close()


def _private_feature_representations(path: Path) -> dict[str, list[str]]:
    """Read full feature identifiers privately for supervised method preflights."""
    dataset = ad.read_h5ad(path, backed="r")
    try:
        representations = {
            "var_names": [str(value).strip() for value in dataset.var_names]
        }
        for column in (*GENE_SYMBOL_COLUMNS, *GENE_ID_COLUMNS):
            if column in dataset.var:
                representations[f"var['{column}']"] = [
                    str(value).strip() for value in dataset.var[column]
                ]
        return representations
    finally:
        dataset.file.close()


def _reference_preflight_expression_state(matrix: Mapping[str, Any]) -> str:
    """Map inspected reference state to the two safely supported preflight states."""
    if matrix.get("expression_state") == "raw_count_like":
        return "raw_count_like"
    if (
        matrix.get("expression_state") == "processed_continuous"
        and matrix.get("processed_expression_state") == "log1p_normalized"
    ):
        return "log1p_normalized"
    return "not_safely_assessable"


def _reference_training_provenance(
    observation_overlap: Mapping[str, Any],
) -> dict[str, Any]:
    """Interpret exact identifier overlap without claiming study independence."""
    exact_count = int(observation_overlap.get("exact_count") or 0)
    if exact_count:
        status = "possible_overlap"
        interpretation = (
            "Exact query/reference observation identifiers overlap. This may be leakage or an "
            "identifier collision and requires provenance review."
        )
    else:
        status = "no_exact_observation_id_overlap_study_independence_unverified"
        interpretation = (
            "No exact observation-ID overlap was detected, but study, donor, sample, and "
            "publication independence remain unverified."
        )
    return {
        "status": status,
        "exact_observation_id_overlap_count": exact_count,
        "query_fraction": observation_overlap.get("query_fraction"),
        "reference_fraction": observation_overlap.get("reference_fraction"),
        "interpretation": interpretation,
    }


def _worker_llm_availability() -> dict[str, Any]:
    """Report worker-model credential status without exposing credential values."""
    try:
        from models import get_key_status, get_model_id, get_model_spec

        model_id = get_model_id("worker")
        model = get_model_spec(model_id)
        key_status = get_key_status()
        provider_status = key_status[model.provider]
        return {
            "status": "success",
            "model_id": model.id,
            "provider": model.provider,
            "credential_available": bool(provider_status["effective"]),
            "credential_source": {
                "environment": bool(provider_status["env_set"]),
                "runtime_ui": bool(provider_status["ui_set"]),
            },
            "provider_credentials": {
                provider: bool(status["effective"])
                for provider, status in sorted(key_status.items())
            },
        }
    except Exception as exc:
        return {
            "status": "unavailable",
            "credential_available": False,
            "error_type": type(exc).__name__,
            "message": f"Worker LLM availability could not be inspected: {exc}",
        }


def _method_cards() -> dict[str, Any]:
    """Return concise, method-neutral strengths and limitations."""
    return {
        "harmony": {
            "documentation": "https://portals.broadinstitute.org/harmony/",
            "unit_of_prediction": "observation",
            "requires": [
                "a biologically matched labeled reference",
                "compatible expression states and sufficient shared genes",
                "a coherent reference label space supported by the query gene panel",
            ],
            "strengths": [
                "uses labels and biological states represented in the selected reference",
                "can adapt to developmental or disease contexts when the reference covers them",
                (
                    "a source-audited composite can cover complementary tissue-resident and "
                    "disease-associated lineages when no single atlas contains both"
                ),
            ],
            "limitations": [
                "reference mismatch or missing populations directly limits predictions",
                (
                    "aggregate composite-reference matches require per-source review because "
                    "separate tissue and disease sources are not a jointly matched cohort and "
                    "can introduce source-confounded transfer"
                ),
                (
                    "closed-set transfer can force unsupported labels, and integration can "
                    "overcorrect when assay/source and biology are confounded"
                ),
                "integration and classifier fitting are more computationally expensive",
            ],
            "preflight_evidence": "reference.query_panel_preflight",
        },
        "celltypist": {
            "documentation": "https://celltypist.readthedocs.io/en/stable/",
            "model_catalog": "https://www.celltypist.org/models",
            "unit_of_prediction": "observation",
            "requires": [
                "a biologically suitable pretrained model",
                "sufficient overlap with model features",
                "raw counts or complete gene-symbol log1p expression normalized per 10000",
            ],
            "strengths": [
                "fast linear classification with per-observation decision scores",
                "curated pretrained models can avoid reference integration",
            ],
            "limitations": [
                "performance depends on species, tissue, state, and feature match to training data",
                "a convenient pretrained model may not cover developmental or disease populations",
                "targeted panels and forced best-match labels can hide out-of-distribution cells",
            ],
            "preflight_evidence": "celltypist.candidate_model_preflights",
        },
        "gptcelltype": {
            "documentation": "https://github.com/Winnie09/GPTCelltype",
            "paper": "https://doi.org/10.1038/s41592-024-02235-4",
            "unit_of_prediction": "expression cluster",
            "requires": [
                "informative cluster marker genes and accurate species/tissue context",
                "an available worker LLM credential",
            ],
            "strengths": [
                "does not require a labeled reference or pretrained classifier",
                (
                    "can interpret informative full-transcriptome cluster markers in rare "
                    "biological contexts"
                ),
            ],
            "limitations": [
                "cluster-level labels depend on clustering and marker quality",
                "LLM labels may vary, hallucinate, or lack calibrated confidence",
                (
                    "low-plex panels, tiny clusters, fine states, and malignancy without specific "
                    "marker support are weak cases"
                ),
            ],
            "query_readiness_interpretation": {
                "strong": (
                    "Disjoint gene views support reproducible clusters and redundant "
                    "held-out positive markers."
                ),
                "moderate": (
                    "Some independent cluster and marker evidence is present, but uncertainty "
                    "must be weighed against reference and pretrained-model evidence."
                ),
                "weak": (
                    "The bounded query-only diagnostic provides adverse evidence for marker-based "
                    "cluster annotation."
                ),
                "not_assessable_or_error": (
                    "Readiness is unknown and must not be treated as evidence against GPTCellType."
                ),
            },
            "preflight_evidence": "query.gptcelltype_readiness",
        },
    }


def _decision_rules() -> list[str]:
    """Return general rules for the agent's subsequent method decision."""
    return [
        (
            "Do not use query annotation columns, benchmark truth, or historical benchmark "
            "performance."
        ),
        (
            "Assess each method only from method_evidence_scopes: candidate-reference evidence "
            "is exclusive to Harmony, CellTypist uses query context and inspected model evidence, "
            "and GPTCellType uses query-only readiness."
        ),
        (
            "Consider Harmony when a matched reference has coherent labels, adequate shared "
            "genes, query-panel discriminability, and acceptable source-confounding risk."
        ),
        (
            "Assign high, moderate, or low suitability to each method before selection. For "
            "Harmony, rate the selected reference against the supplied species, tissue or "
            "compartment, disease, developmental stage, and needed label inventory as well as "
            "technical compatibility. Reference-only separability and shared genes establish "
            "runnability but cannot upgrade a biologically weak reference match."
        ),
        (
            "Consider CellTypist when a pretrained model closely matches the biological context "
            "and its model preflight shows feature and retained-coefficient support."
        ),
        (
            "Choose and rate CellTypist models only from the caller's query context, requested "
            "populations, official model cards, label inventories, training provenance, and "
            "query-model technical preflights. Never use candidate-reference identity, anatomy, "
            "disease, labels, or feature overlap in that reasoning."
        ),
        (
            "Strong GPTCellType readiness is affirmative independent evidence and is not merely a "
            "fallback after rejecting supervised methods. Moderate readiness requires caution, "
            "weak readiness is adverse evidence, and not-assessable or errored readiness is "
            "unknown."
        ),
        (
            "Choose exactly one method only after naming the strongest alternative and recording "
            "supporting, adverse, and unresolved evidence for all three methods. Do not use "
            "benchmark identities, outcomes, or calibrated performance thresholds."
        ),
        (
            "Pass all three qualitative suitability levels to selection validation. Do not "
            "select a method when another runnable method has higher assessed suitability."
        ),
        (
            "When a candidate reference was inspected, state exactly: Candidate reference "
            "evidence was used only to assess Harmony."
        ),
        (
            "Follow selection_policy.default_candidates. A high-risk method is a fallback only "
            "when no non-high-risk affirmative candidate exists or the user explicitly requested "
            "that otherwise runnable method."
        ),
        (
            "When default candidates tie, prefer evidence specific to the supplied disease or "
            "developmental context over a generic tissue-only match. A catalog default is only "
            "a final tie-break between otherwise equivalent official models."
        ),
        (
            "If the selected method has claim status best_supported_unresolved, describe it with "
            "the exact phrase 'best-supported unresolved option'. Include every rationale-guard "
            "reference disclosure code verbatim."
        ),
        (
            "For CellTypist, pass celltypist.majority_voting_recommendation.recommended exactly. "
            "It is true only when CellTypist prerequisites are met and the successful query-only "
            "readiness diagnostic has strong disjoint-view coherence with at least 51 sampled "
            "nonzero cells."
        ),
    ]


def _reference_rationale_disclosures(
    reference: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Build reference caveats only from the inspector's leakage-safe evidence."""
    if reference.get("provided") is not True:
        return []

    disclosures: list[dict[str, Any]] = []
    preflight = reference.get("query_panel_preflight")
    label_coherence = (
        preflight.get("label_coherence")
        if isinstance(preflight, Mapping)
        else None
    )
    if isinstance(label_coherence, Mapping):
        n_placeholder = label_coherence.get("n_placeholder_labeled_observations")
        placeholder_fraction = label_coherence.get(
            "placeholder_labeled_observation_fraction"
        )
        if (
            isinstance(n_placeholder, int)
            and not isinstance(n_placeholder, bool)
            and n_placeholder > 0
        ):
            disclosures.append(
                {
                    "code": "reference_placeholder_label_prevalence",
                    "category": "placeholder_label_prevalence",
                    "evidence_path": (
                        "reference.query_panel_preflight.label_coherence"
                    ),
                    "n_placeholder_labeled_observations": n_placeholder,
                    "placeholder_labeled_observation_fraction": placeholder_fraction,
                }
            )

    coverage = reference.get("coverage")
    metadata_coverage = (
        coverage.get("metadata_coverage")
        if isinstance(coverage, Mapping)
        else None
    )
    if isinstance(metadata_coverage, Mapping):
        for category, code in _REFERENCE_CONTEXT_DISCLOSURE_CODES.items():
            summary = metadata_coverage.get(category)
            n_unique = summary.get("n_unique") if isinstance(summary, Mapping) else None
            if (
                isinstance(n_unique, int)
                and not isinstance(n_unique, bool)
                and n_unique > 1
            ):
                disclosures.append(
                    {
                        "code": code,
                        "category": category,
                        "evidence_path": (
                            f"reference.coverage.metadata_coverage.{category}"
                        ),
                        "n_unique": n_unique,
                    }
                )
    return disclosures


def _celltypist_majority_voting_recommendation(
    celltypist_assessment: Mapping[str, Any],
    query: Mapping[str, Any],
) -> dict[str, Any]:
    """Recommend transcriptomic majority voting from query-only readiness evidence."""
    readiness = query.get("gptcelltype_readiness")
    readiness = readiness if isinstance(readiness, Mapping) else {}
    component_grades = readiness.get("component_grades")
    component_grades = (
        component_grades if isinstance(component_grades, Mapping) else {}
    )
    sampling = readiness.get("sampling")
    sampling = sampling if isinstance(sampling, Mapping) else {}
    n_nonzero = sampling.get("n_sampled_nonzero_cells")
    valid_n_nonzero = (
        isinstance(n_nonzero, int)
        and not isinstance(n_nonzero, bool)
        and n_nonzero >= 0
    )

    prerequisites = celltypist_assessment.get("prerequisites")
    prerequisites_met = prerequisites == "met"
    readiness_success = readiness.get("status") == "success"
    coherence_strong = component_grades.get("coherence") == "strong"
    sufficient_nonzero_cells = bool(
        valid_n_nonzero
        and n_nonzero >= _CELLTYPIST_MAJORITY_VOTING_MIN_NONZERO_CELLS
    )
    recommended = bool(
        prerequisites_met
        and readiness_success
        and coherence_strong
        and sufficient_nonzero_cells
    )

    reason_codes = [
        (
            "celltypist_majority_voting_prerequisites_met"
            if prerequisites_met
            else "celltypist_majority_voting_prerequisites_not_confirmed"
        ),
        (
            "celltypist_majority_voting_readiness_success"
            if readiness_success
            else "celltypist_majority_voting_readiness_not_successful"
        ),
        (
            "celltypist_majority_voting_strong_disjoint_view_coherence"
            if coherence_strong
            else "celltypist_majority_voting_coherence_not_strong"
        ),
        (
            "celltypist_majority_voting_sufficient_nonzero_cells"
            if sufficient_nonzero_cells
            else "celltypist_majority_voting_insufficient_nonzero_cells"
        ),
    ]
    return {
        "version": _CELLTYPIST_MAJORITY_VOTING_POLICY_VERSION,
        "recommended": recommended,
        "reason_codes": reason_codes,
        "criteria": {
            "celltypist_prerequisites_met": prerequisites_met,
            "gptcelltype_readiness_success": readiness_success,
            "disjoint_view_coherence_strong": coherence_strong,
            "sampled_nonzero_cells_at_least_51": sufficient_nonzero_cells,
        },
        "evidence": {
            "celltypist_prerequisites": prerequisites,
            "gptcelltype_readiness_status": readiness.get("status"),
            "coherence_grade": component_grades.get("coherence"),
            "n_sampled_nonzero_cells": n_nonzero if valid_n_nonzero else None,
            "minimum_sampled_nonzero_cells": (
                _CELLTYPIST_MAJORITY_VOTING_MIN_NONZERO_CELLS
            ),
            "source": "query.gptcelltype_readiness",
        },
        "rule": (
            "Enable CellTypist majority voting only when CellTypist is runnable and a successful "
            "query-only diagnostic shows strong disjoint-gene-view coherence with enough nonzero "
            "cells for transcriptomic overclustering. The recommendation never uses query "
            "annotations, spatial neighborhoods, predictions, confidence, or evaluation metrics."
        ),
    }


def _method_selection_policy(
    reference: Mapping[str, Any],
    celltypist: Mapping[str, Any],
    query: Mapping[str, Any],
    worker_llm: Mapping[str, Any],
    context: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build method assessments and categorical dominance policy from preflight evidence."""
    reference_preflight = (
        reference.get("query_panel_preflight")
        if reference.get("provided") is True
        else None
    )
    candidate_assessments = celltypist.get("candidate_model_assessments")
    if isinstance(candidate_assessments, Mapping) and candidate_assessments:
        viable = [
            assessment
            for assessment in candidate_assessments.values()
            if isinstance(assessment, Mapping)
            and assessment.get("prerequisites") == "met"
            and assessment.get("risk_tier") != "high"
        ]
        if viable:
            celltypist_assessment = {
                "version": "cell_annotation_method_assessment_v1",
                "prerequisites": "met",
                "evidence_tier": "conditional",
                "risk_tier": "moderate",
                "reason_codes": sorted(
                    {
                        code
                        for assessment in viable
                        for code in assessment.get("supporting_codes", [])
                    }
                ),
                "supporting_codes": sorted(
                    {
                        code
                        for assessment in viable
                        for code in assessment.get("supporting_codes", [])
                    }
                ),
                "adverse_codes": [],
                "unresolved_codes": sorted(
                    {
                        "celltypist_agent_model_selection_required",
                        *(
                            code
                            for assessment in viable
                            for code in assessment.get("unresolved_codes", [])
                        ),
                    }
                ),
                "evidence_annotations": {
                    "candidate_model_assessments": dict(candidate_assessments),
                    "selection_rule": (
                        "The Cell Annotator must compare the shortlisted model cards, label "
                        "inventories, provenance, and technical preflights; no deterministic "
                        "catalog rank selects the model."
                    ),
                },
            }
        else:
            celltypist_assessment = next(
                (
                    dict(assessment)
                    for assessment in candidate_assessments.values()
                    if isinstance(assessment, Mapping)
                ),
                assess_celltypist_selection_evidence(None, query),
            )
    else:
        celltypist_assessment = assess_celltypist_selection_evidence(None, query)
    method_assessments = {
        "harmony": assess_harmony_selection_evidence(reference_preflight),
        "celltypist": celltypist_assessment,
        "gptcelltype": assess_gptcelltype_selection_evidence(
            query.get("gptcelltype_readiness"),
            worker_llm,
        ),
    }

    def disease_families(value: str) -> set[str]:
        tokens = set(re.findall(r"[a-z0-9]+", value.casefold()))
        return {
            family
            for family, terms in _DISEASE_FAMILY_TERMS.items()
            if tokens.intersection(terms)
        }

    supplied_disease = str((context or {}).get("disease") or "").strip()
    normalized_disease = " ".join(re.findall(r"[a-z0-9]+", supplied_disease.casefold()))
    reference_disease = (
        reference.get("coverage", {}).get("metadata_coverage", {}).get("diseases", {})
    )
    reference_disease_values = [
        str(value).strip()
        for value in reference_disease.get("values", [])
        if str(value).strip()
    ]
    disease_specific_query = bool(
        normalized_disease and normalized_disease not in _HEALTHY_DISEASE_VALUES
    )
    normal_only_reference = bool(
        reference_disease_values
        and all(
            " ".join(re.findall(r"[a-z0-9]+", value.casefold()))
            in _HEALTHY_DISEASE_VALUES
            for value in reference_disease_values
        )
    )
    query_disease_families = disease_families(supplied_disease)
    reference_disease_families = set().union(
        *(disease_families(value) for value in reference_disease_values)
    )
    disease_family_mismatch = bool(
        query_disease_families
        and reference_disease_values
        and not normal_only_reference
        and not query_disease_families.intersection(reference_disease_families)
    )
    harmony_assessment = method_assessments["harmony"]
    harmony_annotations = dict(harmony_assessment.get("evidence_annotations", {}))
    harmony_annotations["biological_context_match"] = {
        "query_disease": supplied_disease or None,
        "reference_disease_values": reference_disease_values,
        "query_disease_families": sorted(query_disease_families),
        "reference_disease_families": sorted(reference_disease_families),
        "status": (
            "disease_specific_query_with_normal_only_reference"
            if disease_specific_query and normal_only_reference
            else (
                "disease_family_mismatch"
                if disease_family_mismatch
                else "requires_agent_reasoning"
            )
        ),
    }
    harmony_assessment["evidence_annotations"] = harmony_annotations
    if disease_specific_query and normal_only_reference:
        harmony_assessment["evidence_tier"] = "adverse"
        harmony_assessment["risk_tier"] = "high"
        adverse_codes = list(harmony_assessment.get("adverse_codes", []))
        if "reference_disease_context_mismatch" not in adverse_codes:
            adverse_codes.append("reference_disease_context_mismatch")
        harmony_assessment["adverse_codes"] = adverse_codes
        harmony_assessment["reason_codes"] = list(
            dict.fromkeys(
                [
                    *harmony_assessment.get("supporting_codes", []),
                    *adverse_codes,
                ]
            )
        )
    elif disease_family_mismatch:
        harmony_assessment["evidence_tier"] = "adverse"
        harmony_assessment["risk_tier"] = "high"
        adverse_codes = list(harmony_assessment.get("adverse_codes", []))
        if "reference_disease_family_mismatch" not in adverse_codes:
            adverse_codes.append("reference_disease_family_mismatch")
        harmony_assessment["adverse_codes"] = adverse_codes
        harmony_assessment["reason_codes"] = list(
            dict.fromkeys(
                [
                    *harmony_assessment.get("supporting_codes", []),
                    *adverse_codes,
                ]
            )
        )
    selection_policy = build_method_selection_policy(method_assessments)
    disclosures = _reference_rationale_disclosures(reference)
    rationale_guard = selection_policy["rationale_guard"]
    rationale_guard["reference_disclosures"] = disclosures
    rationale_guard["required_disclosure_codes"] = [
        disclosure["code"] for disclosure in disclosures
    ]
    return method_assessments, selection_policy


def _error_result(operation: str, stage: str, exc: Exception) -> dict[str, Any]:
    """Build a structured top-level inspection error."""
    return {
        "status": "error",
        "operation": operation,
        "stage": stage,
        "error_type": type(exc).__name__,
        "message": f"Cell-annotation method inspection failed during {stage}: {exc}",
    }


def inspect_cell_annotation_methods_tool(
    spatial_anndata_path: str,
    reference_anndata_path: str | None = None,
    reference_cell_type_column: str = "cell_type",
    species: str | None = None,
    tissue: str | None = None,
    disease: str | None = None,
    developmental_stage: str | None = None,
    *,
    annotation_scope: Mapping[str, str] | None = None,
    annotation_context_sha256: str | None = None,
    celltypist_model_names: Annotated[
        list[str],
        Field(min_length=1, max_length=_MAX_CELLTYPIST_MODEL_SHORTLIST),
    ],
    celltypist_catalog_sha256: str,
) -> dict[str, Any]:
    """Gather leakage-safe evidence for an agent to select one annotation method."""
    operation = "inspect_cell_annotation_methods"
    if not reference_cell_type_column or not reference_cell_type_column.strip():
        return _error_result(
            operation,
            "validate_parameters",
            ValueError("reference_cell_type_column must be a non-empty string."),
        )
    if not isinstance(celltypist_catalog_sha256, str) or not celltypist_catalog_sha256.strip():
        return _error_result(
            operation,
            "validate_parameters",
            ValueError("celltypist_catalog_sha256 must be a non-empty string"),
        )

    try:
        agent_supplied_context = {
            "species": _clean_context_value(species),
            "tissue": _clean_context_value(tissue),
            "disease": _clean_context_value(disease),
            "developmental_stage": _clean_context_value(developmental_stage),
        }
        agent_supplied_context = {
            field: value
            for field, value in agent_supplied_context.items()
            if value is not None
        }
        try:
            agent_scope = _normalize_annotation_scope(annotation_scope)
        except ValueError:
            agent_scope = None
        if agent_scope is not None:
            agent_supplied_context["annotation_scope"] = agent_scope
        bound_context = get_bound_cell_annotation_context()
        if bound_context is not None:
            context = {
                field: _clean_context_value(bound_context.get(field))
                for field in ("species", "tissue", "disease", "developmental_stage")
            }
            context = {field: value for field, value in context.items() if value is not None}
            bound_scope = _normalize_annotation_scope(bound_context.get("annotation_scope"))
            if bound_scope is not None:
                context["annotation_scope"] = bound_scope
            context_source = "orchestrator_bound"
        else:
            context = agent_supplied_context
            if annotation_scope is not None and agent_scope is None:
                _normalize_annotation_scope(annotation_scope)
            context_source = "explicit_tool_arguments"
        observed_context_sha256 = _annotation_context_sha256(context)
        supplied_context_sha256 = (
            annotation_context_sha256.strip()
            if isinstance(annotation_context_sha256, str)
            else None
        )
        if (
            context_source == "explicit_tool_arguments"
            and annotation_scope is not None
            and supplied_context_sha256 is None
        ):
            raise ValueError(
                "annotation_context_sha256 is required when annotation_scope is provided."
            )
        if (
            context_source == "explicit_tool_arguments"
            and supplied_context_sha256 is not None
            and supplied_context_sha256 != observed_context_sha256
        ):
            raise ValueError(
                "annotation_context_sha256 does not match the exact supplied biological context."
            )
    except Exception as exc:
        return _error_result(operation, "validate_annotation_context", exc)
    annotation_context_identity = {
        "version": _ANNOTATION_CONTEXT_IDENTITY_VERSION,
        "source": context_source,
        "sha256": observed_context_sha256,
        "caller_sha256": observed_context_sha256,
        "caller_binding_verified": True,
        "agent_supplied_sha256": supplied_context_sha256,
        "agent_supplied_context_matches": (
            agent_supplied_context == context
            and supplied_context_sha256 == observed_context_sha256
        ),
    }
    try:
        spatial_path = resolve_workspace_input(spatial_anndata_path)
    except Exception as exc:
        return _error_result(operation, "resolve_spatial_input", exc)
    try:
        query = _inspect_expression_matrix(spatial_path, role="query")
        query["gene_identifiers"] = _gene_identifier_summary(spatial_path)
        query_feature_representations = _private_feature_representations(spatial_path)
        query["gptcelltype_readiness"] = inspect_gptcelltype_readiness(
            spatial_path,
            query,
        )
    except Exception as exc:
        return _error_result(operation, "inspect_query", exc)

    reference: dict[str, Any] = {"provided": False}
    if reference_anndata_path is not None:
        try:
            reference_path = resolve_workspace_input(reference_anndata_path)
        except Exception as exc:
            return _error_result(operation, "resolve_reference_input", exc)
        try:
            reference_matrix = _inspect_expression_matrix(reference_path, role="reference")
            reference_matrix["gene_identifiers"] = _gene_identifier_summary(reference_path)
            coverage = _reference_coverage(
                spatial_path,
                reference_path,
                reference_cell_type_column.strip(),
            )
            training_provenance = _reference_training_provenance(
                coverage["observation_name_overlap"]
            )
            query_panel_preflight = preflight_reference_query_panel(
                query_feature_representations,
                reference_path,
                reference_cell_type_column.strip(),
                _reference_preflight_expression_state(reference_matrix),
            )
            query_panel_preflight["provenance"] = {
                **query_panel_preflight.get("provenance", {}),
                **training_provenance,
            }
            reference = {
                "provided": True,
                "path": workspace_relative(reference_path),
                "matrix": reference_matrix,
                "coverage": coverage,
                "training_evidence_provenance": training_provenance,
                "query_panel_preflight": query_panel_preflight,
            }
        except Exception as exc:
            return _error_result(operation, "inspect_reference", exc)

    try:
        celltypist = _agent_shortlisted_celltypist_catalog(
            celltypist_model_names,
            celltypist_catalog_sha256,
        )
    except Exception as exc:
        return _error_result(operation, "resolve_celltypist_shortlist", exc)
    try:
        celltypist_cache_root = resolve_project_output(_CELLTYPIST_CACHE_PATH)
        candidate_preflights = {
            record["model"]: preflight_celltypist_model(
                query_feature_representations,
                [record],
                celltypist_cache_root,
            )
            for record in celltypist.get("models", [])
        }
        celltypist["candidate_model_preflights"] = candidate_preflights
        celltypist["candidate_model_assessments"] = {
            model_name: assess_celltypist_selection_evidence(preflight, query)
            for model_name, preflight in candidate_preflights.items()
        }
        celltypist["model_feature_overlap"] = {
            "status": "agent_shortlist_preflight",
            "reason": (
                "Exact feature, label-inventory, and retained-coefficient evidence is "
                "reported for every agent-shortlisted model without query inference."
            ),
        }
    except Exception as exc:
        error = {
            "status": "error",
            "assessment": "unknown",
            "stage": "prepare_celltypist_candidate_preflight",
            "error_type": type(exc).__name__,
            "message": str(exc),
        }
        celltypist["candidate_model_preflights"] = {
            record["model"]: dict(error) for record in celltypist.get("models", [])
        }
        celltypist["candidate_model_assessments"] = {
            model_name: assess_celltypist_selection_evidence(preflight, query)
            for model_name, preflight in celltypist["candidate_model_preflights"].items()
        }
    worker_llm = _worker_llm_availability()
    reference_training_evidence = (
        reference["training_evidence_provenance"]
        if reference.get("provided")
        else {
            "status": "not_applicable",
            "interpretation": "No candidate reference was provided.",
        }
    )
    method_assessments, selection_policy = _method_selection_policy(
        reference,
        celltypist,
        query,
        worker_llm,
        context,
    )
    celltypist["majority_voting_recommendation"] = (
        _celltypist_majority_voting_recommendation(
            method_assessments["celltypist"],
            query,
        )
    )
    result = {
        "status": "success",
        "operation": operation,
        "selection_status": selection_policy["status"],
        "context": context,
        "annotation_context_identity": annotation_context_identity,
        "query": query,
        "reference": reference,
        "celltypist": celltypist,
        "worker_llm": worker_llm,
        "method_assessments": method_assessments,
        "selection_policy": selection_policy,
        "method_evidence_scopes": method_evidence_scopes(
            reference_provided=reference_anndata_path is not None
        ),
        "method_cards": _method_cards(),
        "decision_rules": _decision_rules(),
        "leakage_safety": {
            "query_obs_columns_or_values_inspected": False,
            "query_obs_names_compared_for_reference_overlap": bool(
                reference_anndata_path is not None
            ),
            "query_obs_names_returned": False,
            "query_annotations_returned": False,
            "query_expression_used_for_gptcelltype_readiness": True,
            "gptcelltype_readiness_query_obs_accessed": False,
            "gptcelltype_readiness_gene_names_returned": False,
            "gptcelltype_readiness_cluster_assignments_returned": False,
            "supervised_preflights_query_expression_accessed": False,
            "supervised_preflights_query_obs_accessed": False,
            "supervised_preflights_query_feature_names_returned": False,
            "reference_label_values_returned": True,
            "reference_training_evidence": reference_training_evidence,
        },
    }
    result["selection_contract"] = register_selection_contract(
        query_path=spatial_path,
        reference_path=reference_path if reference_anndata_path is not None else None,
        reference_cell_type_column=reference_cell_type_column.strip(),
        context=context,
        method_assessments=method_assessments,
        selection_policy=selection_policy,
        celltypist=celltypist,
    )
    return result
