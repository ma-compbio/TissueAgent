"""Run TissueAgent itself for a prepared benchmark."""

from __future__ import annotations

import ast
import fcntl
import hashlib
import json
import os
import re
import shutil
import time
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from queue import Empty, Queue
from typing import Any

import anndata as ad
import pandas as pd
from models import get_model_seed, get_selection

from agents.cell_annotation_context import bind_cell_annotation_context
from config import (
    ACTIVE_PROJECT_DIR,
    DATA_DIR,
    PROJECTS_DIR,
    RECURSION_LIMIT,
    active_project_outputs,
)

from .benchmarks import (
    REPO_ROOT,
    _provenance_value,
    _sha256,
    load_manifest,
    validate_selection_blind_input_pair,
    validate_selection_blind_query,
)


_ANNOTATION_MAPPING_METHODS = {
    ("harmony", "reference"): "tissueagent",
    ("celltypist", "reference"): "tissueagent",
    ("celltypist", "celltypist_builtin"): "celltypist",
    ("gptcelltype", "gptcelltype_free_text"): "gptcelltype",
}
_METHOD_INSPECTION_TOOL = "inspect_cell_annotation_methods_tool"
_CELLTYPIST_CATALOG_TOOL = "list_celltypist_model_catalog_tool"
_SELECTION_VALIDATION_TOOL = "validate_cell_annotation_selection_tool"
_PREPROCESSING_INSPECTION_TOOL = "inspect_anndata_preprocessing_tool"
_SELECTION_POLICY_VERSION = "cell_annotation_selection_policy_v6"
_RATIONALE_GUARD_VERSION = "cell_annotation_rationale_guard_v1"
_CELLTYPIST_MAJORITY_VOTING_POLICY_VERSION = (
    "celltypist_majority_voting_policy_v1"
)
_UNKNOWN_CANDIDATE_CLAIM_STATUS = "best_supported_unresolved"
_UNKNOWN_CANDIDATE_REQUIRED_PHRASE = "best-supported unresolved option"
_BACKEND_TOOL_BY_METHOD = {
    "harmony": "harmony_transfer_tool",
    "celltypist": "celltypist_annotation_tool",
    "gptcelltype": "gptcelltype_annotation_tool",
}
_ROUTING_TOOLS = (
    _CELLTYPIST_CATALOG_TOOL,
    _METHOD_INSPECTION_TOOL,
    _SELECTION_VALIDATION_TOOL,
    _PREPROCESSING_INSPECTION_TOOL,
    *_BACKEND_TOOL_BY_METHOD.values(),
)
_FRESH_GRAPH_LOCK_ROOT = Path("/tmp")


@dataclass(frozen=True)
class _EvaluationProject:
    project_id: str
    original_project_id: str | None
    query_path: Path


def _anonymous_project_is_empty() -> bool:
    if not ACTIVE_PROJECT_DIR.exists():
        return True
    for child in ACTIVE_PROJECT_DIR.iterdir():
        if child.name in {"uploads", "outputs"} and child.is_dir():
            if any(child.iterdir()):
                return False
            continue
        return False
    return True


@contextmanager
def _isolated_evaluation_project(prepared: Mapping[str, Any]) -> Iterator[_EvaluationProject]:
    """Run one benchmark in a clean project and restore the user's active project."""
    from server.utils import (
        clear_active_project_dir,
        read_active_project_id,
        switch_active_project,
        write_active_project_id,
    )

    blind_id = prepared.get("selection_blind_id")
    if not isinstance(blind_id, str) or not re.fullmatch(r"[0-9a-f]{16,64}", blind_id):
        raise ValueError("Fresh evaluation requires an opaque selection_blind_id.")
    project_id = f"tissueagent-eval-{blind_id}"
    if (PROJECTS_DIR / project_id).exists():
        raise FileExistsError(f"Evaluation project already exists: {PROJECTS_DIR / project_id}")

    source_query = (REPO_ROOT / str(prepared["query_h5ad"])).resolve()
    if not source_query.is_file():
        raise FileNotFoundError(f"Prepared blinded query is absent: {source_query}")
    original_project_id = read_active_project_id()
    source_relative_to_active: Path | None = None
    try:
        source_relative_to_active = source_query.relative_to(ACTIVE_PROJECT_DIR.resolve())
    except ValueError:
        pass
    if original_project_id is None and not _anonymous_project_is_empty():
        raise RuntimeError(
            "A non-empty anonymous active project cannot be safely parked for evaluation. "
            "Save or activate it as a named project first."
        )

    activated = False
    try:
        if original_project_id is None:
            clear_active_project_dir()
        else:
            switch_active_project(None)
            if source_relative_to_active is not None:
                source_query = PROJECTS_DIR / original_project_id / source_relative_to_active
        write_active_project_id(project_id)
        activated = True
        staged_query = (
            ACTIVE_PROJECT_DIR
            / "uploads"
            / "benchmark_inputs"
            / "blind"
            / blind_id
            / "query.h5ad"
        )
        staged_query.parent.mkdir(parents=True, exist_ok=False)
        try:
            staged_query.hardlink_to(source_query)
        except OSError:
            shutil.copy2(source_query, staged_query)
        if _sha256(staged_query) != _sha256(source_query):
            raise RuntimeError("Staged query hash differs from the prepared blinded query.")
        yield _EvaluationProject(
            project_id=project_id,
            original_project_id=original_project_id,
            query_path=staged_query,
        )
    finally:
        if activated and read_active_project_id() == project_id:
            switch_active_project(None)
        if original_project_id is not None and read_active_project_id() != original_project_id:
            switch_active_project(original_project_id)


def _fresh_full_graph_lock_path(repo_root: Path = REPO_ROOT) -> Path:
    """Return the repository-specific advisory lock path for fresh graph runs."""
    repo_key = hashlib.sha256(os.fsencode(repo_root.resolve())).hexdigest()[:24]
    return _FRESH_GRAPH_LOCK_ROOT / f"tissueagent-fresh-full-graph-{repo_key}.lock"


@contextmanager
def _fresh_full_graph_lock(repo_root: Path = REPO_ROOT) -> Iterator[Path]:
    """Serialize fresh full-graph runs that share process-global planner state."""
    resolved_repo = repo_root.resolve()
    lock_path = _fresh_full_graph_lock_path(resolved_repo)
    handle = lock_path.open("a+b")
    acquired = False
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError(
                "Another fresh TissueAgent benchmark graph is already running for "
                f"repository '{resolved_repo}'. Fresh full-graph run_tissueagent calls share "
                "process-global planner state and must be serialized; wait for the active run "
                f"to finish before retrying. Lock: {lock_path}"
            ) from exc
        acquired = True
        yield lock_path
    finally:
        if acquired:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            finally:
                handle.close()
        else:
            handle.close()


def _load_prepared(prepared: dict[str, Any] | str | Path) -> dict[str, Any]:
    if isinstance(prepared, dict):
        return prepared
    path = Path(prepared)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return json.loads(path.read_text(encoding="utf-8"))


def _annotation_output_path(prepared: dict[str, Any]) -> Path:
    selection_blind_id = prepared.get("selection_blind_id")
    if selection_blind_id is None:
        return (
            active_project_outputs()
            / "cell_annotation_runs"
            / prepared["dataset_id"]
            / prepared["run_id"]
            / "tissueagent_annotated.h5ad"
        )
    if not isinstance(selection_blind_id, str) or not re.fullmatch(
        r"[0-9a-f]{16,64}",
        selection_blind_id,
    ):
        raise ValueError("selection_blind_id must contain 16-64 lowercase hexadecimal characters.")
    return (
        active_project_outputs()
        / "cell_annotation_runs"
        / "blind"
        / selection_blind_id
        / "tissueagent_annotated.h5ad"
    )


def _evaluation_prompt(
    manifest: Mapping[str, Any],
    query_relative: Path,
    output_relative: Path,
) -> str:
    assay_description = (
        "spatial AnnData" if manifest["query"].get("require_spatial", True) else "AnnData"
    )
    context = (
        f"species='{manifest['species']}', tissue='{manifest['tissue']}', "
        f"disease='{manifest['disease']}'"
    )
    developmental_stage = manifest.get("developmental_stage")
    if developmental_stage:
        context += f", developmental_stage='{developmental_stage}'"
    study_context = manifest.get("study_context")
    if study_context:
        context += f". Study context: {study_context.rstrip('.')}"
    annotation_scope = manifest.get("annotation_scope")
    if annotation_scope:
        context += ". Annotation scope contract: " + json.dumps(
            annotation_scope,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    return (
        f"Annotate cell types in {assay_description} '{query_relative}'. "
        f"Biological context: {context}. "
        f"Save the annotated H5AD to '{output_relative}'."
    )


def _harmony_convergence_audit(
    transcript: Path,
    tool_metadata: Path | None = None,
) -> dict[str, Any]:
    if tool_metadata is not None and tool_metadata.exists():
        metadata = json.loads(tool_metadata.read_text(encoding="utf-8"))
        status = metadata.get("summary", {}).get("harmony_convergence_status")
        if status == "converged":
            return {"status": "converged", "warnings": []}
        if status == "iteration_limit_reached":
            return {
                "status": "iteration_limit_reached",
                "warnings": [
                    "Harmony reached its configured iteration limit before declaring convergence."
                ],
            }
        if status not in {None, "not_reported"}:
            raise ValueError(
                f"Unsupported Harmony convergence status in {tool_metadata}: {status!r}."
            )

    text = transcript.read_text(encoding="utf-8", errors="replace")
    if "Stopped before convergence" in text:
        return {
            "status": "iteration_limit_reached",
            "warnings": [
                "Harmony reached its configured iteration limit before declaring convergence."
            ],
        }
    if "Converged after" in text:
        return {"status": "converged", "warnings": []}
    return {
        "status": "not_reported",
        "warnings": ["Harmony did not report a convergence status in the captured transcript."],
    }


def _annotation_provenance(
    annotation_context: dict[str, Any],
) -> tuple[str, str, str]:
    missing = [
        field
        for field in ("annotation_method", "label_source")
        if not isinstance(annotation_context.get(field), str)
        or not annotation_context[field].strip()
    ]
    if missing:
        raise ValueError(
            "TissueAgent annotation provenance must explicitly declare: " + ", ".join(missing)
        )

    annotation_method = annotation_context["annotation_method"].strip()
    label_source = annotation_context["label_source"].strip()
    combination = (annotation_method, label_source)
    if combination not in _ANNOTATION_MAPPING_METHODS:
        valid = ", ".join(
            f"{method}/{source}" for method, source in sorted(_ANNOTATION_MAPPING_METHODS)
        )
        raise ValueError(
            "Unsupported TissueAgent annotation_method/label_source combination "
            f"{annotation_method!r}/{label_source!r}; expected one of: {valid}."
        )
    return annotation_method, label_source, _ANNOTATION_MAPPING_METHODS[combination]


def _fresh_graph_routing_audit(
    transcript: Path,
    annotation_method: str,
    *,
    messages: Sequence[Any] | None = None,
    query_path: Path | None = None,
    reference_path: Path | None = None,
    output_path: Path | None = None,
    label_source: str | None = None,
    subagent_invocation_count: int | None = None,
    expected_backend_args: Mapping[str, Any] | None = None,
    expected_inspection_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if annotation_method not in _BACKEND_TOOL_BY_METHOD:
        raise ValueError(f"Unsupported annotation method for routing audit: {annotation_method!r}.")
    if not transcript.exists():
        raise FileNotFoundError(f"Fresh TissueAgent run lacks its transcript: {transcript}")

    if messages is not None:
        return _structured_graph_routing_audit(
            messages,
            annotation_method,
            query_path=query_path,
            reference_path=reference_path,
            output_path=output_path,
            label_source=label_source,
            subagent_invocation_count=subagent_invocation_count,
            expected_backend_args=expected_backend_args,
            expected_inspection_context=expected_inspection_context,
        )

    transcript_lines = transcript.read_text(encoding="utf-8", errors="replace").splitlines()
    counts = {
        tool: sum(line == f"Name: {tool}" for line in transcript_lines)
        for tool in _ROUTING_TOOLS
    }
    selected_backend = _BACKEND_TOOL_BY_METHOD[annotation_method]
    backend_counts = {tool: counts[tool] for tool in _BACKEND_TOOL_BY_METHOD.values()}
    violations = []
    if counts[_CELLTYPIST_CATALOG_TOOL] != 1:
        violations.append(
            f"expected exactly one {_CELLTYPIST_CATALOG_TOOL} call, "
            f"observed {counts[_CELLTYPIST_CATALOG_TOOL]}"
        )
    if counts[_METHOD_INSPECTION_TOOL] != 1:
        violations.append(
            f"expected exactly one {_METHOD_INSPECTION_TOOL} call, "
            f"observed {counts[_METHOD_INSPECTION_TOOL]}"
        )
    if counts[_SELECTION_VALIDATION_TOOL] != 1:
        violations.append(
            f"expected exactly one {_SELECTION_VALIDATION_TOOL} call, "
            f"observed {counts[_SELECTION_VALIDATION_TOOL]}"
        )
    if sum(backend_counts.values()) != 1:
        violations.append(
            "expected exactly one annotation backend call, observed "
            f"{sum(backend_counts.values())}"
        )
    elif backend_counts[selected_backend] != 1:
        violations.append(
            f"output declares {annotation_method!r}, but the transcript did not call "
            f"{selected_backend} exactly once"
        )
    preprocessing_count = counts[_PREPROCESSING_INSPECTION_TOOL]
    if annotation_method == "harmony" and preprocessing_count != 1:
        violations.append(
            f"Harmony requires exactly one {_PREPROCESSING_INSPECTION_TOOL} call, "
            f"observed {preprocessing_count}"
        )
    elif annotation_method != "harmony" and preprocessing_count != 0:
        violations.append(
            f"{_PREPROCESSING_INSPECTION_TOOL} is only valid for Harmony, "
            f"observed {preprocessing_count} for {annotation_method}"
        )

    audit = {
        "status": "passed" if not violations else "failed",
        "enforced": True,
        "source": "fresh_graph_transcript_legacy",
        "line_contract": "Name: <tool>",
        "annotation_method": annotation_method,
        "selected_backend_tool": selected_backend,
        "tool_call_counts": counts,
        "violations": violations,
    }
    if violations:
        raise RuntimeError(
            "TissueAgent fresh-run routing contract failed: "
            + "; ".join(violations)
            + f". Tool counts: {counts}"
        )
    return audit


def _tool_result_payload(content: Any) -> dict[str, Any] | None:
    parsed = _parsed_tool_content(content)
    return dict(parsed) if isinstance(parsed, Mapping) else None


def _parsed_tool_content(content: Any) -> Any:
    if isinstance(content, Mapping):
        return dict(content)
    if isinstance(content, list) and len(content) == 1:
        block = content[0]
        if isinstance(block, Mapping) and block.get("type") == "text":
            content = block.get("text")
    if not isinstance(content, str):
        return None
    stripped = content.strip()
    if not stripped:
        return None
    for parser in (json.loads, ast.literal_eval):
        try:
            parsed = parser(stripped)
        except (ValueError, SyntaxError, TypeError, json.JSONDecodeError):
            continue
        if isinstance(parsed, Mapping):
            return dict(parsed)
        if isinstance(parsed, list):
            return parsed
    return None


def _structured_routing_events(messages: Sequence[Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for message_index, message in enumerate(messages):
        if isinstance(message, Mapping):
            message_type = message.get("type")
            tool_calls = message.get("tool_calls") or []
            name = message.get("name")
            tool_call_id = message.get("tool_call_id")
            content = message.get("content")
            message_status = message.get("status")
        else:
            message_type = getattr(message, "type", None)
            tool_calls = getattr(message, "tool_calls", None) or []
            name = getattr(message, "name", None)
            tool_call_id = getattr(message, "tool_call_id", None)
            content = getattr(message, "content", None)
            message_status = getattr(message, "status", None)

        for call_index, tool_call in enumerate(tool_calls):
            if not isinstance(tool_call, Mapping):
                continue
            tool_name = tool_call.get("name")
            if tool_name not in _ROUTING_TOOLS:
                continue
            args = tool_call.get("args")
            events.append(
                {
                    "event": "call",
                    "tool": tool_name,
                    "tool_call_id": tool_call.get("id"),
                    "args": dict(args) if isinstance(args, Mapping) else {},
                    "message_index": message_index,
                    "call_index": call_index,
                }
            )

        if message_type != "tool" or name not in _ROUTING_TOOLS:
            continue
        events.append(
            {
                "event": "result",
                "tool": name,
                "tool_call_id": tool_call_id,
                "payload": _tool_result_payload(content),
                "message_status": message_status,
                "message_index": message_index,
            }
        )
    return events


def _method_selection_evidence(messages: Sequence[Any]) -> dict[str, Any]:
    """Return the single successful structured method-inspection result."""
    matches = [
        event
        for event in _structured_routing_events(messages)
        if event["event"] == "result" and event["tool"] == _METHOD_INSPECTION_TOOL
    ]
    if len(matches) != 1:
        raise RuntimeError(
            "Expected exactly one structured method-selection result, "
            f"observed {len(matches)}."
        )
    payload = matches[0]["payload"]
    if not isinstance(payload, Mapping) or payload.get("status") != "success":
        raise RuntimeError("Method-selection evidence is absent or did not succeed.")
    return dict(payload)


def _resolved_tool_path(value: Any) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    path = Path(value)
    if not path.is_absolute():
        path = DATA_DIR / path
    return path.resolve(strict=False)


def _path_matches(value: Any, expected: Path) -> bool:
    observed = _resolved_tool_path(value)
    return observed is not None and observed == expected.resolve(strict=False)


def _is_readable_h5ad(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        dataset = ad.read_h5ad(path, backed="r")
    except (OSError, ValueError, TypeError, KeyError):
        return False
    dataset.file.close()
    return True


def _resolve_fresh_annotation_output(
    requested_output: Path,
    messages: Sequence[Any],
) -> Path:
    backend_paths: list[Path] = []
    output_root = active_project_outputs().resolve(strict=False)
    for event in _structured_routing_events(messages):
        if event["event"] != "result" or event["tool"] not in _BACKEND_TOOL_BY_METHOD.values():
            continue
        payload = event["payload"]
        if not isinstance(payload, Mapping) or payload.get("status") != "success":
            continue
        candidate = _resolved_tool_path(payload.get("annotated_object_h5ad"))
        if candidate is None:
            continue
        try:
            candidate.relative_to(output_root)
        except ValueError:
            continue
        if candidate not in backend_paths and _is_readable_h5ad(candidate):
            backend_paths.append(candidate)
    if len(backend_paths) > 1:
        raise RuntimeError(
            "TissueAgent reported multiple distinct readable annotation backend outputs: "
            + ", ".join(str(path) for path in backend_paths)
        )
    if backend_paths:
        return backend_paths[0]
    return requested_output


def _provenance_dataset_ids(value: Any) -> set[str]:
    dataset_ids: set[str] = set()
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if key == "dataset_id" and nested is not None:
                dataset_ids.add(str(nested))
            elif key == "dataset_ids" and not isinstance(nested, (str, bytes, Mapping)):
                try:
                    dataset_ids.update(str(item) for item in nested)
                except TypeError:
                    pass
            if isinstance(nested, (Mapping, list, tuple)):
                dataset_ids.update(_provenance_dataset_ids(nested))
    elif isinstance(value, (list, tuple)):
        for nested in value:
            dataset_ids.update(_provenance_dataset_ids(nested))
    return dataset_ids


def _selected_reference_audit(
    messages: Sequence[Any],
    query_path: Path,
    policy: Mapping[str, Any] | None,
    reference_discovery_messages: Sequence[Any] = (),
) -> tuple[Path | None, dict[str, Any]]:
    calls = [
        event
        for event in _structured_routing_events(messages)
        if event["event"] == "call" and event["tool"] == _METHOD_INSPECTION_TOOL
    ]
    if len(calls) != 1:
        raise RuntimeError(
            "Reference provenance requires exactly one structured method-inspection call."
        )
    call = calls[0]
    reference_path = _resolved_tool_path(call["args"].get("reference_anndata_path"))
    require_agent_generated = bool((policy or {}).get("require_agent_generated", False))
    if reference_path is None:
        if require_agent_generated:
            raise RuntimeError(
                "The end-to-end evaluation requires TissueAgent to acquire and inspect its own "
                "candidate reference, but Cell Annotator received none."
            )
        return None, {"status": "not_used", "agent_generated_required": False}
    if not reference_path.is_file() or reference_path.suffix.casefold() != ".h5ad":
        raise FileNotFoundError(
            f"Agent-selected reference is not a readable H5AD: {reference_path}"
        )

    generated_under_project_outputs = False
    project_relative: Path | None = None
    try:
        project_relative = reference_path.relative_to(ACTIVE_PROJECT_DIR.resolve())
        reference_path.relative_to(active_project_outputs().resolve())
        generated_under_project_outputs = True
    except ValueError:
        pass
    if require_agent_generated and not generated_under_project_outputs:
        raise RuntimeError(
            "Agent-selected reference was not created beneath the isolated project's outputs: "
            f"{reference_path}"
        )

    label_column = call["args"].get("reference_cell_type_column", "cell_type")
    reference = ad.read_h5ad(reference_path, backed="r")
    try:
        if label_column not in reference.obs:
            raise KeyError(f"Agent-selected reference lacks .obs[{label_column!r}].")
        if reference.obs[label_column].isna().any():
            raise ValueError(f"Agent-selected reference has missing {label_column!r} labels.")
        subset_provenance = reference.uns.get("tissueagent_cellxgene_subset")
        dimensions = {"n_obs": int(reference.n_obs), "n_vars": int(reference.n_vars)}
        n_labels = int(reference.obs[label_column].astype(str).nunique())
    finally:
        reference.file.close()

    provenance_path = reference_path.with_suffix(".provenance.json")
    sidecar_provenance = None
    if provenance_path.is_file():
        sidecar_provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    has_retrieval_provenance = isinstance(subset_provenance, Mapping) or isinstance(
        sidecar_provenance, Mapping
    )
    if require_agent_generated and not has_retrieval_provenance:
        raise RuntimeError(
            "Agent-selected reference lacks CELLxGENE retrieval provenance in the H5AD or its "
            "adjacent provenance JSON."
        )

    require_zero_overlap = bool(
        (policy or {}).get("require_zero_observation_id_overlap", False)
    )
    independence = validate_selection_blind_input_pair(query_path, reference_path)
    if (
        require_zero_overlap
        and independence["reference_independence_audit"]["exact_count"] != 0
    ):
        raise RuntimeError("Agent-selected reference overlaps the blinded query observations.")
    configured_forbidden_ids = {
        str(value) for value in (policy or {}).get("forbidden_dataset_ids", [])
    }
    observed_dataset_ids: set[str] = set()
    for provenance in (subset_provenance, sidecar_provenance):
        if not isinstance(provenance, Mapping):
            continue
        observed_dataset_ids.update(_provenance_dataset_ids(provenance))
    forbidden_overlap = sorted(configured_forbidden_ids.intersection(observed_dataset_ids))
    if forbidden_overlap:
        raise RuntimeError(
            "Agent-selected reference uses forbidden benchmark source dataset IDs: "
            + ", ".join(forbidden_overlap)
        )

    discovery_records: dict[str, dict[str, Any]] = {}
    for message in reference_discovery_messages:
        if isinstance(message, Mapping):
            message_type = message.get("type")
            name = message.get("name")
            content = message.get("content")
        else:
            message_type = getattr(message, "type", None)
            name = getattr(message, "name", None)
            content = getattr(message, "content", None)
        if message_type != "tool" or name != "query_cellxgene_census_live_tool":
            continue
        payload = _parsed_tool_content(content)
        if not isinstance(payload, list):
            continue
        for record in payload:
            if not isinstance(record, Mapping) or record.get("dataset_id") is None:
                continue
            discovery_records[str(record["dataset_id"])] = _provenance_value(dict(record))

    require_live_discovery = bool((policy or {}).get("require_live_discovery", False))
    missing_discovery_ids = sorted(observed_dataset_ids.difference(discovery_records))
    if require_live_discovery and (not observed_dataset_ids or missing_discovery_ids):
        raise RuntimeError(
            "Agent-selected reference dataset IDs are not fully bound to the Single Cell "
            "Agent's live discovery results: "
            + ", ".join(missing_discovery_ids or ["no retrieved dataset IDs"])
        )
    selected_discovery_records = [
        discovery_records[dataset_id]
        for dataset_id in sorted(observed_dataset_ids)
        if dataset_id in discovery_records
    ]

    def normalize_doi(value: Any) -> str:
        normalized = str(value or "").strip().casefold()
        for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix) :]
        return normalized.rstrip("/")

    forbidden_dois = {
        normalize_doi(value)
        for value in (policy or {}).get("forbidden_collection_dois", [])
        if normalize_doi(value)
    }
    selected_dois = {
        normalize_doi(record.get("collection_doi"))
        for record in selected_discovery_records
        if normalize_doi(record.get("collection_doi"))
    }
    missing_collection_dois = sorted(
        str(record.get("dataset_id"))
        for record in selected_discovery_records
        if not normalize_doi(record.get("collection_doi"))
    )
    if forbidden_dois and missing_collection_dois:
        raise RuntimeError(
            "Reference discovery metadata lacks collection DOI for selected dataset IDs: "
            + ", ".join(missing_collection_dois)
        )
    forbidden_doi_overlap = sorted(forbidden_dois.intersection(selected_dois))
    if forbidden_doi_overlap:
        raise RuntimeError(
            "Agent-selected reference comes from a forbidden benchmark publication DOI: "
            + ", ".join(forbidden_doi_overlap)
        )

    audit = {
        "status": "passed",
        "agent_generated_required": require_agent_generated,
        "agent_generated_under_project_outputs": generated_under_project_outputs,
        "zero_observation_id_overlap_required": require_zero_overlap,
        "agent_visible_path": reference_path.relative_to(DATA_DIR).as_posix(),
        "sha256": _sha256(reference_path),
        **dimensions,
        "cell_type_column": str(label_column),
        "n_cell_types": n_labels,
        "observed_dataset_ids": sorted(observed_dataset_ids),
        "forbidden_dataset_id_overlap": forbidden_overlap,
        "live_discovery_required": require_live_discovery,
        "selected_dataset_ids_missing_from_live_discovery": missing_discovery_ids,
        "selected_discovery_records": selected_discovery_records,
        "selected_collection_dois": sorted(selected_dois),
        "forbidden_collection_doi_overlap": forbidden_doi_overlap,
        "source_independence_scope": (
            "CELLxGENE dataset and collection provenance plus exact observation-ID overlap; "
            "donor, sample, and unpublished-source independence are not established."
        ),
        "retrieval_provenance": _provenance_value(
            dict(subset_provenance)
            if isinstance(subset_provenance, Mapping)
            else sidecar_provenance
        ),
        "query_reference_independence": independence["reference_independence_audit"],
    }
    if project_relative is not None:
        audit["_project_relative"] = project_relative.as_posix()
    if provenance_path.is_file():
        try:
            audit["_provenance_project_relative"] = provenance_path.relative_to(
                ACTIVE_PROJECT_DIR.resolve()
            ).as_posix()
        except ValueError:
            audit["provenance_path"] = str(provenance_path)
    return reference_path, audit


def _inspection_context_matches(field: str, expected: Any, observed: Any) -> bool:
    del field
    return expected == observed


def _annotation_context_sha256(context: Mapping[str, Any]) -> str:
    payload = json.dumps(
        context,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _structured_graph_routing_audit(
    messages: Sequence[Any],
    annotation_method: str,
    *,
    query_path: Path | None,
    reference_path: Path | None,
    output_path: Path | None,
    label_source: str | None,
    subagent_invocation_count: int | None,
    expected_backend_args: Mapping[str, Any] | None,
    expected_inspection_context: Mapping[str, Any] | None,
) -> dict[str, Any]:
    events = _structured_routing_events(messages)
    calls = [event for event in events if event["event"] == "call"]
    results = [event for event in events if event["event"] == "result"]
    selected_backend = _BACKEND_TOOL_BY_METHOD[annotation_method]
    counts = {
        tool: sum(event["tool"] == tool for event in calls)
        for tool in _ROUTING_TOOLS
    }
    violations: list[str] = []

    if subagent_invocation_count is not None and subagent_invocation_count != 1:
        violations.append(
            "expected exactly one Cell Annotator sub-agent invocation, observed "
            f"{subagent_invocation_count}"
        )
    if counts[_CELLTYPIST_CATALOG_TOOL] != 1:
        violations.append(
            f"expected exactly one {_CELLTYPIST_CATALOG_TOOL} call, "
            f"observed {counts[_CELLTYPIST_CATALOG_TOOL]}"
        )
    if counts[_METHOD_INSPECTION_TOOL] != 1:
        violations.append(
            f"expected exactly one {_METHOD_INSPECTION_TOOL} call, "
            f"observed {counts[_METHOD_INSPECTION_TOOL]}"
        )
    if counts[_SELECTION_VALIDATION_TOOL] != 1:
        violations.append(
            f"expected exactly one {_SELECTION_VALIDATION_TOOL} call, "
            f"observed {counts[_SELECTION_VALIDATION_TOOL]}"
        )
    backend_count = sum(counts[tool] for tool in _BACKEND_TOOL_BY_METHOD.values())
    if backend_count != 1:
        violations.append(f"expected exactly one annotation backend call, observed {backend_count}")
    elif counts[selected_backend] != 1:
        violations.append(
            f"output declares {annotation_method!r}, but the structured graph route did not call "
            f"{selected_backend} exactly once"
        )
    preprocessing_count = counts[_PREPROCESSING_INSPECTION_TOOL]
    if annotation_method == "harmony" and preprocessing_count != 1:
        violations.append(
            f"Harmony requires exactly one {_PREPROCESSING_INSPECTION_TOOL} call, "
            f"observed {preprocessing_count}"
        )
    elif annotation_method != "harmony" and preprocessing_count != 0:
        violations.append(
            f"{_PREPROCESSING_INSPECTION_TOOL} is only valid for Harmony, "
            f"observed {preprocessing_count} for {annotation_method}"
        )

    calls_by_id: dict[str, dict[str, Any]] = {}
    paired_results: dict[str, dict[str, Any]] = {}
    for call in calls:
        tool_call_id = call["tool_call_id"]
        if not isinstance(tool_call_id, str) or not tool_call_id:
            violations.append(f"{call['tool']} call lacks a non-empty tool_call_id")
            continue
        if tool_call_id in calls_by_id:
            violations.append(f"duplicate routing tool_call_id {tool_call_id!r}")
            continue
        calls_by_id[tool_call_id] = call
        matches = [result for result in results if result["tool_call_id"] == tool_call_id]
        if len(matches) != 1:
            violations.append(
                f"{call['tool']} call {tool_call_id!r} has "
                f"{len(matches)} paired ToolMessage results"
            )
            continue
        result = matches[0]
        paired_results[tool_call_id] = result
        if result["tool"] != call["tool"]:
            violations.append(
                f"tool result name {result['tool']!r} does not match call {call['tool']!r}"
            )
        payload = result["payload"]
        if payload is None:
            violations.append(f"{call['tool']} returned a non-structured tool result")
        elif payload.get("status") != "success":
            violations.append(
                f"{call['tool']} did not succeed; status={payload.get('status')!r}"
            )
        if result["message_status"] == "error":
            violations.append(f"{call['tool']} ToolMessage has error status")

    for result in results:
        if result["tool_call_id"] not in calls_by_id:
            violations.append(
                f"orphan {result['tool']} ToolMessage for call "
                f"{result['tool_call_id']!r}"
            )

    def one_call(tool: str) -> dict[str, Any] | None:
        matches = [event for event in calls if event["tool"] == tool]
        return matches[0] if len(matches) == 1 else None

    def paired(call: dict[str, Any] | None) -> dict[str, Any] | None:
        if call is None:
            return None
        return paired_results.get(call["tool_call_id"])

    catalog_call = one_call(_CELLTYPIST_CATALOG_TOOL)
    method_call = one_call(_METHOD_INSPECTION_TOOL)
    selection_validation_call = one_call(_SELECTION_VALIDATION_TOOL)
    preprocessing_call = one_call(_PREPROCESSING_INSPECTION_TOOL)
    backend_call = one_call(selected_backend)
    catalog_result = paired(catalog_call)
    method_result = paired(method_call)
    selection_validation_result = paired(selection_validation_call)
    preprocessing_result = paired(preprocessing_call)
    backend_result = paired(backend_call)

    def require_completed_before(
        first_call: dict[str, Any] | None,
        first_result: dict[str, Any] | None,
        later_call: dict[str, Any] | None,
        description: str,
    ) -> None:
        if first_call is None or first_result is None or later_call is None:
            return
        if not (
            first_call["message_index"]
            < first_result["message_index"]
            < later_call["message_index"]
        ):
            violations.append(description)

    require_completed_before(
        catalog_call,
        catalog_result,
        method_call,
        "CellTypist catalog review must complete before method inspection",
    )
    require_completed_before(
        method_call,
        method_result,
        selection_validation_call,
        "method inspection must complete successfully before selection validation",
    )
    if annotation_method == "harmony":
        require_completed_before(
            method_call,
            method_result,
            preprocessing_call,
            "method inspection must complete successfully before preprocessing inspection",
        )
        require_completed_before(
            preprocessing_call,
            preprocessing_result,
            selection_validation_call,
            "preprocessing inspection must complete successfully before selection validation",
        )
        require_completed_before(
            selection_validation_call,
            selection_validation_result,
            backend_call,
            "selection validation must complete successfully before the Harmony backend",
        )
    else:
        require_completed_before(
            selection_validation_call,
            selection_validation_result,
            backend_call,
            "selection validation must complete successfully before the selected backend",
        )

    path_checks: list[dict[str, Any]] = []

    def require_path(
        call: dict[str, Any] | None,
        field: str,
        expected: Path | None,
        *,
        required: bool = True,
    ) -> None:
        if call is None or expected is None:
            return
        observed = call["args"].get(field)
        matches = _path_matches(observed, expected)
        path_checks.append(
            {
                "tool": call["tool"],
                "field": field,
                "status": "passed" if matches else "failed",
            }
        )
        if required and not matches:
            violations.append(
                f"{call['tool']} {field} does not match the prepared input/output path"
            )

    require_path(method_call, "spatial_anndata_path", query_path)
    require_path(method_call, "reference_anndata_path", reference_path)
    require_path(selection_validation_call, "output_path", output_path)
    require_path(preprocessing_call, "spatial_anndata_path", query_path)
    require_path(preprocessing_call, "reference_anndata_path", reference_path)
    require_path(backend_call, "spatial_anndata_path", query_path)
    if annotation_method == "harmony" or (
        annotation_method == "celltypist" and label_source == "reference"
    ):
        require_path(backend_call, "reference_anndata_path", reference_path)
    require_path(backend_call, "output_path", output_path)
    backend_parameter_checks: list[dict[str, Any]] = []
    if backend_call is not None and expected_backend_args is not None:
        for field, expected in expected_backend_args.items():
            provided = backend_call["args"].get(field)
            matches = provided == expected
            backend_parameter_checks.append(
                {
                    "field": field,
                    "expected": expected,
                    "provided": provided,
                    "status": "passed" if matches else "failed",
                }
            )
            if not matches:
                violations.append(
                    f"{backend_call['tool']} {field}={provided!r} does not match "
                    f"the benchmark configuration {expected!r}"
                )

    method_payload = method_result["payload"] if method_result is not None else None
    catalog_payload = catalog_result["payload"] if catalog_result is not None else None
    celltypist_catalog_audit: dict[str, Any] | None = None
    if isinstance(catalog_payload, Mapping) and method_call is not None:
        catalog_sha256 = catalog_payload.get("catalog_sha256")
        provided_catalog_sha256 = method_call["args"].get(
            "celltypist_catalog_sha256"
        )
        shortlisted_models = method_call["args"].get("celltypist_model_names")
        catalog_models = catalog_payload.get("models")
        catalog_model_names = {
            record.get("model")
            for record in catalog_models
            if isinstance(record, Mapping)
        } if isinstance(catalog_models, list) else set()
        returned_celltypist = (
            method_payload.get("celltypist")
            if isinstance(method_payload, Mapping)
            else None
        )
        returned_models = (
            returned_celltypist.get("models")
            if isinstance(returned_celltypist, Mapping)
            else None
        )
        returned_model_names = [
            record.get("model") for record in returned_models
        ] if isinstance(returned_models, list) and all(
            isinstance(record, Mapping) for record in returned_models
        ) else None
        hash_matches = bool(
            isinstance(catalog_sha256, str)
            and catalog_sha256
            and provided_catalog_sha256 == catalog_sha256
        )
        shortlist_valid = bool(
            isinstance(shortlisted_models, list)
            and 1 <= len(shortlisted_models) <= 3
            and len(set(shortlisted_models)) == len(shortlisted_models)
            and all(model in catalog_model_names for model in shortlisted_models)
        )
        inspection_matches = bool(
            shortlist_valid
            and returned_model_names == shortlisted_models
            and returned_celltypist.get("selection_mode") == "agent_shortlist"
        )
        celltypist_catalog_audit = {
            "catalog_sha256": catalog_sha256,
            "provided_catalog_sha256_matches": hash_matches,
            "shortlisted_model_names": shortlisted_models,
            "shortlist_is_verified_and_bounded": shortlist_valid,
            "inspection_preserves_agent_shortlist": inspection_matches,
            "status": (
                "passed" if hash_matches and shortlist_valid and inspection_matches else "failed"
            ),
        }
        if not hash_matches:
            violations.append(
                "method inspection does not use the reviewed CellTypist catalog identity"
            )
        if not shortlist_valid:
            violations.append(
                "method inspection CellTypist shortlist is not a verified one-to-three model list"
            )
        if not inspection_matches:
            violations.append(
                "method inspection does not preserve the exact agent CellTypist shortlist"
            )
    inspection_context_audit: dict[str, Any] | None = None
    if expected_inspection_context is not None:
        context_fields = tuple(expected_inspection_context)
        result_context = (
            method_payload.get("context")
            if isinstance(method_payload, Mapping)
            else None
        )
        returned_context_identity = (
            method_payload.get("annotation_context_identity")
            if isinstance(method_payload, Mapping)
            else None
        )
        orchestrator_bound = bool(
            isinstance(returned_context_identity, Mapping)
            and returned_context_identity.get("source") == "orchestrator_bound"
            and returned_context_identity.get("caller_binding_verified") is True
        )
        field_checks: list[dict[str, Any]] = []
        for field in context_fields:
            expected = expected_inspection_context.get(field)
            provided = (
                method_call["args"].get(field)
                if method_call is not None
                else None
            )
            returned = (
                result_context.get(field)
                if isinstance(result_context, Mapping)
                else None
            )
            provided_matches = _inspection_context_matches(field, expected, provided)
            returned_matches = _inspection_context_matches(field, expected, returned)
            field_checks.append(
                {
                    "field": field,
                    "expected": expected,
                    "provided": provided,
                    "returned": returned,
                    "matching": "exact_context_equality_v2",
                    "call_status": (
                        "passed"
                        if provided_matches
                        else "overridden_by_orchestrator"
                        if orchestrator_bound
                        else "failed"
                    ),
                    "result_status": "passed" if returned_matches else "failed",
                }
            )
            if not provided_matches and not orchestrator_bound:
                violations.append(
                    f"{_METHOD_INSPECTION_TOOL} {field} does not match the "
                    "benchmark manifest context"
                )
            if not returned_matches:
                violations.append(
                    f"{_METHOD_INSPECTION_TOOL} result context.{field} does not match "
                    "the benchmark manifest context"
                )
        expected_context_sha256 = _annotation_context_sha256(expected_inspection_context)
        provided_context_sha256 = (
            method_call["args"].get("annotation_context_sha256")
            if method_call is not None
            else None
        )
        context_hash_matches = bool(
            isinstance(returned_context_identity, Mapping)
            and returned_context_identity.get("sha256") == expected_context_sha256
            and returned_context_identity.get("caller_sha256") == expected_context_sha256
            and returned_context_identity.get("caller_binding_verified") is True
            and (
                orchestrator_bound
                or provided_context_sha256 == expected_context_sha256
            )
        )
        if not context_hash_matches:
            violations.append(
                f"{_METHOD_INSPECTION_TOOL} does not preserve the exact annotation-context hash"
            )
        inspection_context_audit = {
            "expected": {
                field: expected_inspection_context.get(field)
                for field in context_fields
            },
            "expected_sha256": expected_context_sha256,
            "provided_sha256": provided_context_sha256,
            "returned_identity": returned_context_identity,
            "context_hash_status": "passed" if context_hash_matches else "failed",
            "field_checks": field_checks,
            "status": (
                "passed"
                if all(
                    check["call_status"] in {"passed", "overridden_by_orchestrator"}
                    and check["result_status"] == "passed"
                    for check in field_checks
                )
                and context_hash_matches
                else "failed"
            ),
        }
    selection_validation_payload = (
        selection_validation_result["payload"]
        if selection_validation_result is not None
        else None
    )
    selection_validation_audit: dict[str, Any] | None = None
    if isinstance(method_payload, Mapping):
        selection_contract = method_payload.get("selection_contract")
        expected_contract_id = (
            selection_contract.get("contract_id")
            if isinstance(selection_contract, Mapping)
            else None
        )
        provided_contract_id = (
            selection_validation_call["args"].get("selection_contract_id")
            if selection_validation_call is not None
            else None
        )
        validated_contract_id = (
            selection_validation_payload.get("selection_contract_id")
            if isinstance(selection_validation_payload, Mapping)
            else None
        )
        validated_method = (
            selection_validation_payload.get("selected_method")
            if isinstance(selection_validation_payload, Mapping)
            else None
        )
        provided_method = (
            selection_validation_call["args"].get("selected_method")
            if selection_validation_call is not None
            else None
        )
        backend_requirements = (
            selection_validation_payload.get("backend_requirements")
            if isinstance(selection_validation_payload, Mapping)
            else None
        )
        execution_token = (
            backend_requirements.get("selection_execution_token")
            if isinstance(backend_requirements, Mapping)
            else None
        )
        provided_execution_token = (
            backend_call["args"].get("selection_execution_token")
            if backend_call is not None
            else None
        )
        configuration_sha256 = (
            backend_requirements.get("configuration_sha256")
            if isinstance(backend_requirements, Mapping)
            else None
        )
        provided_configuration_sha256 = (
            backend_call["args"].get("configuration_sha256")
            if backend_call is not None
            else None
        )
        contract_matches = bool(
            isinstance(expected_contract_id, str)
            and expected_contract_id
            and provided_contract_id == expected_contract_id
            and validated_contract_id == expected_contract_id
        )
        method_matches = bool(
            provided_method == annotation_method
            and validated_method == annotation_method
        )
        token_matches = bool(
            isinstance(execution_token, str)
            and execution_token
            and provided_execution_token == execution_token
        )
        configuration_matches = bool(
            isinstance(configuration_sha256, str)
            and configuration_sha256
            and provided_configuration_sha256 == configuration_sha256
        )
        provided_suitability_confidences = selection_validation_call["args"].get(
            "method_suitability_confidences"
        )
        validated_suitability_confidences = (
            selection_validation_payload.get("method_suitability_confidences")
            if isinstance(selection_validation_payload, Mapping)
            else None
        )
        suitability_confidences_match = bool(
            isinstance(provided_suitability_confidences, Mapping)
            and dict(provided_suitability_confidences)
            == validated_suitability_confidences
        )
        configuration_contract = (
            selection_validation_payload.get("configuration_contract")
            if isinstance(selection_validation_payload, Mapping)
            else None
        )
        backend_payload = backend_result["payload"] if backend_result is not None else None
        backend_execution_contract = (
            backend_payload.get("execution_contract")
            if isinstance(backend_payload, Mapping)
            else None
        )
        backend_contract_matches = bool(
            isinstance(configuration_contract, Mapping)
            and isinstance(backend_execution_contract, Mapping)
            and all(
                backend_execution_contract.get(field) == value
                for field, value in configuration_contract.items()
            )
            and backend_execution_contract.get("selection_contract_id")
            == expected_contract_id
        )
        authorized_output_matches = bool(
            output_path is not None
            and isinstance(selection_validation_payload, Mapping)
            and _path_matches(
                selection_validation_payload.get("authorized_output_path"),
                output_path,
            )
        )
        selection_validation_audit = {
            "contract_version": (
                selection_contract.get("version")
                if isinstance(selection_contract, Mapping)
                else None
            ),
            "expected_contract_id": expected_contract_id,
            "provided_contract_id_matches": contract_matches,
            "selected_method_matches": method_matches,
            "authorized_output_matches": authorized_output_matches,
            "backend_execution_token_matches": token_matches,
            "backend_configuration_sha256_matches": configuration_matches,
            "method_suitability_confidences_match": suitability_confidences_match,
            "method_suitability_confidences": validated_suitability_confidences,
            "backend_complete_configuration_matches": backend_contract_matches,
            "configuration_contract": configuration_contract,
            "status": (
                "passed"
                if contract_matches
                and method_matches
                and authorized_output_matches
                and token_matches
                and configuration_matches
                and suitability_confidences_match
                and backend_contract_matches
                else "failed"
            ),
        }
        if not contract_matches:
            violations.append(
                "selection validation does not use the method inspector's exact contract"
            )
        if not method_matches:
            violations.append(
                "selection validation method does not match output provenance"
            )
        if not authorized_output_matches:
            violations.append(
                "selection validation output path does not match the prepared output"
            )
        if not token_matches:
            violations.append(
                "selected backend does not use the validator's exact execution token"
            )
        if not configuration_matches:
            violations.append(
                "selected backend does not use the validator's exact configuration hash"
            )
        if not suitability_confidences_match:
            violations.append(
                "selection validation does not preserve all method suitability confidences"
            )
        if not backend_contract_matches:
            violations.append(
                "selected backend result does not retain the validator's complete "
                "configuration contract"
            )

    selection_policy_audit: dict[str, Any] | None = None
    if isinstance(method_payload, Mapping):
        if query_path is not None and not _path_matches(
            method_payload.get("query", {}).get("path"),
            query_path,
        ):
            violations.append("method-inspection result query path does not match prepared input")
        if reference_path is not None and not _path_matches(
            method_payload.get("reference", {}).get("path"),
            reference_path,
        ):
            violations.append(
                "method-inspection result reference path does not match prepared input"
            )
        selection_policy = method_payload.get("selection_policy")
        method_assessments = method_payload.get("method_assessments")
        if not isinstance(selection_policy, Mapping) or not isinstance(
            method_assessments,
            Mapping,
        ):
            violations.append(
                "method-inspection result lacks structured method_assessments/selection_policy"
            )
        else:
            policy_version_valid = (
                selection_policy.get("version") == _SELECTION_POLICY_VERSION
            )
            if not policy_version_valid:
                violations.append(
                    "method-selection policy version is missing or unsupported"
                )
            default_candidates = selection_policy.get("default_candidates")
            fallback_candidates = selection_policy.get("fallback_candidates")
            unknown_candidates = selection_policy.get("unknown_candidates")
            if not all(
                isinstance(candidates, list)
                and all(candidate in _BACKEND_TOOL_BY_METHOD for candidate in candidates)
                for candidates in (
                    default_candidates,
                    fallback_candidates,
                    unknown_candidates,
                )
            ):
                violations.append("method-selection policy contains invalid candidate lists")
            else:
                allowed_candidates = (
                    default_candidates
                    if default_candidates
                    else [*fallback_candidates, *unknown_candidates]
                )
                selected_from_policy = annotation_method in allowed_candidates
                if not selected_from_policy:
                    violations.append(
                        f"selected method {annotation_method!r} is outside the method-inspection "
                        f"policy candidates {allowed_candidates}"
                    )

                agent_rationale = (
                    selection_validation_call["args"].get("selection_rationale")
                    if selection_validation_call is not None
                    else None
                )
                rationale = (
                    selection_validation_payload.get(
                        "validated_selection_rationale"
                    )
                    if isinstance(selection_validation_payload, Mapping)
                    else None
                )
                rationale_guard = selection_policy.get("rationale_guard")
                rationale_guard_valid = True
                selected_claim_status: str | None = None
                required_exact_phrase: str | None = None
                required_disclosure_codes: list[str] = []
                if (
                    not isinstance(rationale_guard, Mapping)
                    or rationale_guard.get("version") != _RATIONALE_GUARD_VERSION
                ):
                    rationale_guard_valid = False
                    violations.append(
                        "method-selection policy lacks a supported structured rationale_guard"
                    )
                else:
                    claim_status_by_method = rationale_guard.get(
                        "claim_status_by_method"
                    )
                    phrase_by_status = rationale_guard.get(
                        "required_exact_phrase_by_claim_status"
                    )
                    disclosure_codes = rationale_guard.get(
                        "required_disclosure_codes"
                    )
                    reference_disclosures = rationale_guard.get(
                        "reference_disclosures"
                    )
                    if not isinstance(claim_status_by_method, Mapping):
                        rationale_guard_valid = False
                        violations.append(
                            "rationale_guard claim_status_by_method is invalid"
                        )
                    else:
                        selected_claim_status_value = claim_status_by_method.get(
                            annotation_method
                        )
                        if isinstance(selected_claim_status_value, str):
                            selected_claim_status = selected_claim_status_value
                        else:
                            rationale_guard_valid = False
                            violations.append(
                                "rationale_guard lacks a claim status for the selected method"
                            )
                        if any(
                            claim_status_by_method.get(method)
                            != _UNKNOWN_CANDIDATE_CLAIM_STATUS
                            for method in unknown_candidates
                        ):
                            rationale_guard_valid = False
                            violations.append(
                                "rationale_guard does not mark every unknown candidate as "
                                "best_supported_unresolved"
                            )
                    if (
                        not isinstance(phrase_by_status, Mapping)
                        or phrase_by_status.get(_UNKNOWN_CANDIDATE_CLAIM_STATUS)
                        != _UNKNOWN_CANDIDATE_REQUIRED_PHRASE
                    ):
                        rationale_guard_valid = False
                        violations.append(
                            "rationale_guard lacks the required exact unknown-candidate phrase"
                        )
                    if not (
                        isinstance(disclosure_codes, list)
                        and all(
                            isinstance(code, str) and code
                            for code in disclosure_codes
                        )
                    ):
                        rationale_guard_valid = False
                        violations.append(
                            "rationale_guard required_disclosure_codes is invalid"
                        )
                    else:
                        required_disclosure_codes = disclosure_codes
                    if not (
                        isinstance(reference_disclosures, list)
                        and all(
                            isinstance(disclosure, Mapping)
                            and isinstance(disclosure.get("code"), str)
                            for disclosure in reference_disclosures
                        )
                    ):
                        rationale_guard_valid = False
                        violations.append(
                            "rationale_guard reference_disclosures is invalid"
                        )
                    elif [
                        disclosure["code"] for disclosure in reference_disclosures
                    ] != required_disclosure_codes:
                        rationale_guard_valid = False
                        violations.append(
                            "rationale_guard disclosure records do not match required codes"
                        )

                if selected_claim_status == _UNKNOWN_CANDIDATE_CLAIM_STATUS:
                    required_exact_phrase = _UNKNOWN_CANDIDATE_REQUIRED_PHRASE
                missing_exact_phrase = bool(
                    required_exact_phrase
                    and (
                        not isinstance(rationale, str)
                        or required_exact_phrase not in rationale
                    )
                )
                if missing_exact_phrase:
                    violations.append(
                        "selection_rationale omits required exact phrase: "
                        + _UNKNOWN_CANDIDATE_REQUIRED_PHRASE
                    )
                missing_disclosure_codes = [
                    code
                    for code in required_disclosure_codes
                    if not isinstance(rationale, str) or code not in rationale
                ]
                if missing_disclosure_codes:
                    violations.append(
                        "selection_rationale omits required disclosure codes: "
                        + ", ".join(missing_disclosure_codes)
                    )

                required_adverse_codes = sorted(
                    {
                        str(code)
                        for method, assessment in method_assessments.items()
                        if method == annotation_method
                        or (
                            isinstance(assessment, Mapping)
                            and assessment.get("risk_tier") == "high"
                        )
                        for code in (
                            assessment.get("adverse_codes", [])
                            if isinstance(assessment, Mapping)
                            else []
                        )
                    }
                )
                missing_reason_codes = [
                    code
                    for code in required_adverse_codes
                    if not isinstance(rationale, str) or code not in rationale
                ]
                if missing_reason_codes:
                    violations.append(
                        "selection_rationale omits adverse policy reason codes: "
                        + ", ".join(missing_reason_codes)
                    )
                selection_policy_audit = {
                    "version": selection_policy.get("version"),
                    "default_candidates": default_candidates,
                    "fallback_candidates": fallback_candidates,
                    "unknown_candidates": unknown_candidates,
                    "selected_method": annotation_method,
                    "selected_from_policy": selected_from_policy,
                    "agent_selection_rationale": agent_rationale,
                    "validated_selection_rationale": rationale,
                    "rationale_guard_version": (
                        rationale_guard.get("version")
                        if isinstance(rationale_guard, Mapping)
                        else None
                    ),
                    "rationale_guard_valid": rationale_guard_valid,
                    "selected_claim_status": selected_claim_status,
                    "required_exact_phrase": required_exact_phrase,
                    "missing_exact_phrase": missing_exact_phrase,
                    "required_disclosure_codes": required_disclosure_codes,
                    "missing_disclosure_codes": missing_disclosure_codes,
                    "required_adverse_reason_codes": required_adverse_codes,
                    "missing_adverse_reason_codes": missing_reason_codes,
                    "status": (
                        "passed"
                        if policy_version_valid
                        and selected_from_policy
                        and rationale_guard_valid
                        and not missing_exact_phrase
                        and not missing_disclosure_codes
                        and not missing_reason_codes
                        else "failed"
                    ),
                }

    celltypist_model_selection_audit: dict[str, Any] | None = None
    majority_voting_audit: dict[str, Any] | None = None
    if annotation_method == "celltypist":
        celltypist_evidence = (
            method_payload.get("celltypist")
            if isinstance(method_payload, Mapping)
            else None
        )
        recommendation = (
            celltypist_evidence.get("majority_voting_recommendation")
            if isinstance(celltypist_evidence, Mapping)
            else None
        )
        candidate_models = (
            method_payload.get("selection_contract", {})
            .get("celltypist_backend_requirements", {})
            .get("candidate_model_names")
            if isinstance(method_payload, Mapping)
            else None
        )
        provided_model = (
            selection_validation_call["args"].get("celltypist_model_name")
            if selection_validation_call is not None
            else None
        )
        validated_model = (
            selection_validation_payload.get("celltypist_model_name")
            if isinstance(selection_validation_payload, Mapping)
            else None
        )
        required_model = (
            selection_validation_payload.get("backend_requirements", {}).get(
                "celltypist_model_name"
            )
            if isinstance(selection_validation_payload, Mapping)
            else None
        )
        executed_model = (
            backend_call["args"].get("model_name")
            if backend_call is not None
            else None
        )
        provided_model_confidences = (
            selection_validation_call["args"].get(
                "celltypist_model_suitability_confidences"
            )
            if selection_validation_call is not None
            else None
        )
        validated_model_confidences = (
            selection_validation_payload.get(
                "celltypist_model_suitability_confidences"
            )
            if isinstance(selection_validation_payload, Mapping)
            else None
        )
        provided_scope_assessments = (
            selection_validation_call["args"].get(
                "celltypist_model_scope_assessments"
            )
            if selection_validation_call is not None
            else None
        )
        validated_scope_assessments = (
            selection_validation_payload.get("celltypist_model_scope_assessments")
            if isinstance(selection_validation_payload, Mapping)
            else None
        )
        model_matches = bool(
            isinstance(candidate_models, list)
            and provided_model in candidate_models
            and provided_model == validated_model == required_model == executed_model
        )
        model_confidences_match = bool(
            isinstance(provided_model_confidences, Mapping)
            and dict(provided_model_confidences) == validated_model_confidences
            and set(provided_model_confidences) == set(candidate_models or [])
        )
        scope_assessments_match = bool(
            isinstance(provided_scope_assessments, Mapping)
            and dict(provided_scope_assessments) == validated_scope_assessments
            and set(provided_scope_assessments) == set(candidate_models or [])
        )
        celltypist_model_selection_audit = {
            "candidate_model_names": candidate_models,
            "selected_model_name": validated_model,
            "validated_model_matches_backend": model_matches,
            "model_suitability_confidences": validated_model_confidences,
            "model_suitability_confidences_match": model_confidences_match,
            "model_scope_assessments": validated_scope_assessments,
            "model_scope_assessments_match": scope_assessments_match,
            "status": (
                "passed"
                if model_matches and model_confidences_match and scope_assessments_match
                else "failed"
            ),
        }
        if not model_matches:
            violations.append(
                "CellTypist backend model does not match the agent-selected inspected model"
            )
        if not model_confidences_match:
            violations.append(
                "CellTypist model selection does not preserve all candidate suitability ratings"
            )
        if not scope_assessments_match:
            violations.append(
                "CellTypist model selection does not preserve all structured scope assessments"
            )
        recommended = (
            recommendation.get("recommended")
            if isinstance(recommendation, Mapping)
            else None
        )
        provided = (
            backend_call["args"].get("majority_voting")
            if backend_call is not None
            else None
        )
        version_valid = bool(
            isinstance(recommendation, Mapping)
            and recommendation.get("version")
            == _CELLTYPIST_MAJORITY_VOTING_POLICY_VERSION
        )
        matches = bool(
            version_valid
            and isinstance(recommended, bool)
            and isinstance(provided, bool)
            and provided is recommended
        )
        majority_voting_audit = {
            "version": (
                recommendation.get("version")
                if isinstance(recommendation, Mapping)
                else None
            ),
            "recommended_majority_voting": recommended,
            "provided_majority_voting": provided,
            "status": "passed" if matches else "failed",
        }
        if not matches:
            violations.append(
                "CellTypist majority_voting does not exactly match the supported "
                "method-inspection recommendation"
            )

    preprocessing_payload = (
        preprocessing_result["payload"] if preprocessing_result is not None else None
    )
    if isinstance(preprocessing_payload, Mapping):
        if query_path is not None and not _path_matches(
            preprocessing_payload.get("spatial", {}).get("path"),
            query_path,
        ):
            violations.append(
                "preprocessing-inspection result query path does not match prepared input"
            )
        if reference_path is not None and not _path_matches(
            preprocessing_payload.get("reference", {}).get("path"),
            reference_path,
        ):
            violations.append(
                "preprocessing-inspection result reference path does not match prepared input"
            )

    skip_preprocessing_audit: dict[str, Any] | None = None
    if annotation_method == "harmony" and backend_call is not None:
        recommended_skip = (
            preprocessing_payload.get("recommended_skip_preprocessing")
            if isinstance(preprocessing_payload, Mapping)
            else None
        )
        recommended_spatial = (
            preprocessing_payload.get("recommended_preprocess_spatial")
            if isinstance(preprocessing_payload, Mapping)
            else None
        )
        recommended_reference = (
            preprocessing_payload.get("recommended_preprocess_reference")
            if isinstance(preprocessing_payload, Mapping)
            else None
        )
        provided_skip = backend_call["args"].get("skip_preprocessing")
        provided_spatial = backend_call["args"].get("preprocess_spatial")
        provided_reference = backend_call["args"].get("preprocess_reference")
        matches = (
            isinstance(recommended_spatial, bool)
            and isinstance(recommended_reference, bool)
            and provided_spatial is recommended_spatial
            and provided_reference is recommended_reference
            and provided_skip is recommended_skip
        )
        skip_preprocessing_audit = {
            "recommended_skip_preprocessing": recommended_skip,
            "provided_skip_preprocessing": provided_skip,
            "recommended_preprocess_spatial": recommended_spatial,
            "provided_preprocess_spatial": provided_spatial,
            "recommended_preprocess_reference": recommended_reference,
            "provided_preprocess_reference": provided_reference,
            "status": "passed" if matches else "failed",
        }
        if not matches:
            violations.append(
                "Harmony per-input preprocessing decisions do not exactly match the "
                "successful preprocessing-inspection recommendation"
            )

    backend_payload = backend_result["payload"] if backend_result is not None else None
    if isinstance(backend_payload, Mapping):
        if backend_payload.get("annotation_method") != annotation_method:
            violations.append(
                "selected backend tool result does not match annotated output provenance"
            )
        if label_source is not None and backend_payload.get("label_source") != label_source:
            violations.append(
                "selected backend label source does not match annotated output provenance"
            )
        if output_path is not None and not _path_matches(
            backend_payload.get("annotated_object_h5ad"),
            output_path,
        ):
            violations.append("selected backend result path does not match requested output")

    audit = {
        "status": "passed" if not violations else "failed",
        "enforced": True,
        "source": "fresh_graph_structured_messages",
        "annotation_method": annotation_method,
        "label_source": label_source,
        "selected_backend_tool": selected_backend,
        "subagent_invocation_count": subagent_invocation_count,
        "tool_call_counts": counts,
        "event_sequence": [
            {
                "event": event["event"],
                "tool": event["tool"],
                "tool_call_id": event["tool_call_id"],
                "message_index": event["message_index"],
                **(
                    {"status": event["payload"].get("status")}
                    if event["event"] == "result"
                    and isinstance(event["payload"], Mapping)
                    else {}
                ),
            }
            for event in events
        ],
        "path_checks": path_checks,
        "inspection_context_audit": inspection_context_audit,
        "backend_parameter_checks": backend_parameter_checks,
        "celltypist_catalog_audit": celltypist_catalog_audit,
        "selection_validation_audit": selection_validation_audit,
        "selection_policy_audit": selection_policy_audit,
        "celltypist_model_selection_audit": celltypist_model_selection_audit,
        "majority_voting_audit": majority_voting_audit,
        "skip_preprocessing_audit": skip_preprocessing_audit,
        "violations": violations,
    }
    if violations:
        raise RuntimeError(
            "TissueAgent fresh-run structured routing contract failed: "
            + "; ".join(violations)
            + f". Tool counts: {counts}"
        )
    return audit


def _drain_subagent_messages(
    state_queue: Queue,
) -> tuple[list[Any], int, list[dict[str, Any]], dict[str, list[Any]]]:
    messages: list[Any] = []
    invocation_count = 0
    invocations: list[dict[str, Any]] = []
    agent_messages: dict[str, list[Any]] = {}
    while True:
        try:
            agent_name, state, invocation_id = state_queue.get_nowait()
        except Empty:
            break
        state_messages = state.get("messages") if isinstance(state, Mapping) else None
        invocations.append(
            {
                "agent_name": str(agent_name),
                "invocation_id": str(invocation_id),
                "message_count": len(state_messages) if isinstance(state_messages, Sequence) else 0,
            }
        )
        if agent_name == "Cell Annotator Agent":
            invocation_count += 1
        if isinstance(state, Mapping):
            if isinstance(state_messages, Sequence):
                agent_messages.setdefault(str(agent_name), []).extend(state_messages)
                if agent_name == "Cell Annotator Agent":
                    messages.extend(state_messages)
    return messages, invocation_count, invocations, agent_messages


def run_tissueagent(
    prepared: dict[str, Any] | str | Path,
    *,
    resume_existing: bool = False,
) -> dict[str, Any]:
    """Invoke the full TissueAgent graph and verify its annotation artifact."""
    if not resume_existing and not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not visible to this process.")
    if resume_existing:
        return _run_tissueagent(prepared, resume_existing=True)
    with _fresh_full_graph_lock():
        return _run_tissueagent(prepared, resume_existing=False)


def _finalize_evaluation_project_metadata(
    metadata: dict[str, Any],
    project: _EvaluationProject,
) -> dict[str, Any]:
    project_root = PROJECTS_DIR / project.project_id
    annotated_relative = Path(metadata.pop("_annotated_project_relative"))
    metadata["annotated_h5ad"] = str(
        (project_root / annotated_relative).relative_to(REPO_ROOT)
    )
    backend_metadata_relative = metadata.pop("_backend_metadata_project_relative", None)
    if backend_metadata_relative is not None:
        metadata["backend_run_metadata"] = str(
            (project_root / backend_metadata_relative).relative_to(REPO_ROOT)
        )
    reference_audit = metadata.get("reference_audit")
    if isinstance(reference_audit, dict):
        project_relative = reference_audit.pop("_project_relative", None)
        if project_relative is not None:
            reference_audit["archived_path"] = str(
                (project_root / project_relative).relative_to(REPO_ROOT)
            )
        provenance_relative = reference_audit.pop("_provenance_project_relative", None)
        if provenance_relative is not None:
            reference_audit["archived_provenance_path"] = str(
                (project_root / provenance_relative).relative_to(REPO_ROOT)
            )
    metadata["evaluation_project"] = {
        "project_id": project.project_id,
        "status": "parked",
        "path": str(project_root.relative_to(REPO_ROOT)),
        "isolated_from_other_replicates": True,
    }
    metadata_path = REPO_ROOT / metadata["run_metadata"]
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def _run_tissueagent(
    prepared: dict[str, Any] | str | Path,
    *,
    resume_existing: bool,
    _evaluation_project: _EvaluationProject | None = None,
) -> dict[str, Any]:
    """Execute TissueAgent after fresh-run exclusivity has been established."""
    prepared = _load_prepared(prepared)
    if not resume_existing and _evaluation_project is None:
        with _isolated_evaluation_project(prepared) as project:
            metadata = _run_tissueagent(
                prepared,
                resume_existing=False,
                _evaluation_project=project,
            )
        return _finalize_evaluation_project_metadata(metadata, project)
    manifest = load_manifest(prepared["dataset_id"])
    query_path = (
        _evaluation_project.query_path
        if _evaluation_project is not None
        else REPO_ROOT / prepared["query_h5ad"]
    )
    reference_path = (
        REPO_ROOT / prepared["reference_h5ad"]
        if resume_existing and prepared.get("reference_h5ad")
        else None
    )
    run_dir = REPO_ROOT / prepared["run_dir"]
    output_path = _annotation_output_path(prepared)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists() and not resume_existing:
        raise FileExistsError(f"TissueAgent output already exists: {output_path}")

    query_relative = query_path.relative_to(DATA_DIR)
    output_relative = output_path.relative_to(DATA_DIR)
    developmental_stage = manifest.get("developmental_stage")
    expected_inspection_context = {
        "species": manifest["species"],
        "tissue": manifest["tissue"],
        "disease": manifest["disease"],
        "developmental_stage": developmental_stage,
        **(
            {"annotation_scope": manifest["annotation_scope"]}
            if manifest.get("annotation_scope") is not None
            else {}
        ),
    }
    prompt = _evaluation_prompt(manifest, query_relative, output_relative)

    transcript = run_dir / "tissueagent_transcript.log"
    outer_graph_status = "completed"
    outer_graph_warning: str | None = None
    result: dict[str, Any] = {}
    fresh_routing_messages: list[Any] | None = None
    fresh_subagent_invocation_count: int | None = None
    agent_invocations: list[dict[str, Any]] = []
    fresh_agent_messages: dict[str, list[Any]] = {}
    available_domain_agents: list[dict[str, str]] = []
    domain_agent_registry_audit: dict[str, Any] = {
        "status": "not_enforced",
        "source": "resume_or_recovery",
    }
    query_blinding_audit: dict[str, Any] = {
        "status": "not_enforced",
        "scope": "selection_blind_query",
        "reason": "Fresh query blinding is not inferred during resume or recovery.",
    }
    if resume_existing:
        tool_metadata = output_path.with_suffix(".run_meta.json")
        recovery_path = run_dir / "direct_tool_recovery.json"
        recovery = (
            json.loads(recovery_path.read_text(encoding="utf-8"))
            if recovery_path.exists()
            else None
        )
        outer_graph_attempted = (
            bool(recovery.get("outer_graph_attempted", True))
            if recovery is not None
            else True
        )
        if (
            not output_path.exists()
            or not tool_metadata.exists()
            or (not transcript.exists() and outer_graph_attempted)
        ):
            raise FileNotFoundError(
                "Resuming requires the annotated H5AD and its run metadata; a transcript is "
                "also required when the outer graph was attempted."
            )
        if recovery is not None:
            if outer_graph_attempted:
                outer_graph_status = "direct_tool_recovery_after_outer_graph_failure"
                outer_graph_warning = (
                    "The configured outer TissueAgent graph failed before annotation; the exact "
                    "production Cell Annotater inspection and selected backend tools were then "
                    "run directly with provenance in direct_tool_recovery.json."
                )
            else:
                outer_graph_status = "direct_tools_after_prior_quota_blocker"
                outer_graph_warning = (
                    "This clean rerun invoked the exact production Cell Annotater inspection "
                    "and backend tools directly after an earlier benchmark run established the "
                    "same configured-LLM quota blocker; no new outer-graph transcript was "
                    "created."
                )
        else:
            outer_graph_status = "resumed_after_annotation"
            outer_graph_warning = (
                "The annotation tool completed, but the outer TissueAgent graph did not finish "
                "its reporting phase; benchmark postprocessing resumed from verified artifacts."
            )
    else:
        from agents.agent_defns import AgentDefns
        from agents.agent_registry.coding_agent.sandbox import KernelClient
        from demo.notebook_utils import tee_output
        from graph.graph import create_tissueagent_graph
        from server.plan_store import plan_store

        plan_store.reset()
        state_queue = Queue()
        tee = partial(tee_output, path=transcript, mode="w")
        available_domain_agents = [
            {"id": agent.id, "name": agent.name} for agent in AgentDefns
        ]
        domain_agent_registry_audit = {
            "status": "passed",
            "source": "agents.agent_defns.AgentDefns",
            "graph_domain_agents_override": False,
            "available_agent_ids": [agent["id"] for agent in available_domain_agents],
        }
        kernel_client = KernelClient()
        kernel_client.set_workspace(DATA_DIR)
        graph_error: Exception | None = None
        try:
            with tee():
                graph = create_tissueagent_graph(
                    state_queue,
                    lambda model: model,
                    kernel_client=kernel_client,
                )
                tissueagent = graph.compile()
                if prepared.get("selection_blind_id") is not None:
                    query_blinding_audit = validate_selection_blind_query(
                        query_path, manifest["query"]
                    )
                with bind_cell_annotation_context(expected_inspection_context):
                    result = tissueagent.invoke(
                        {"messages": [("user", prompt)]},
                        config={"recursion_limit": RECURSION_LIMIT},
                    )
        except Exception as error:
            graph_error = error
        finally:
            (
                fresh_routing_messages,
                fresh_subagent_invocation_count,
                agent_invocations,
                fresh_agent_messages,
            ) = _drain_subagent_messages(state_queue)
            kernel_client.shutdown_kernels()
        output_path = _resolve_fresh_annotation_output(
            output_path,
            fresh_routing_messages or [],
        )
        if graph_error is not None:
            if (
                not _is_readable_h5ad(output_path)
                or not output_path.with_suffix(".run_meta.json").is_file()
            ):
                raise graph_error
            outer_graph_status = "reporting_failed_after_annotation"
            outer_graph_warning = (
                "The annotation tool completed, but the outer TissueAgent graph failed during "
                f"post-annotation reporting: {type(graph_error).__name__}: {graph_error}"
            )

    if not _is_readable_h5ad(output_path):
        final_message = result["messages"][-1].content if result.get("messages") else ""
        raise RuntimeError(
            "TissueAgent completed without a readable annotation output artifact. "
            f"Final message: {final_message}"
        )
    query = ad.read_h5ad(query_path, backed="r")
    output = ad.read_h5ad(output_path, backed="r")
    try:
        if not output.obs_names.equals(query.obs_names):
            missing = query.obs_names.difference(output.obs_names)
            extra = output.obs_names.difference(query.obs_names)
            raise RuntimeError(
                "TissueAgent changed the query cell set/order: "
                f"missing={len(missing)}, extra={len(extra)}."
            )
        prediction_column = "cell_annotation_predicted_cell_type"
        confidence_column = "cell_annotation_prediction_confidence"
        if prediction_column not in output.obs and "harmony_predicted_cell_type" in output.obs:
            prediction_column = "harmony_predicted_cell_type"
            confidence_column = "harmony_prediction_confidence"
        if prediction_column not in output.obs:
            raise KeyError(f"TissueAgent output lacks .obs['{prediction_column}'].")
        annotation_context = dict(output.uns.get("tissueagent_cell_annotation", {}))
        annotation_method, label_source, mapping_method = _annotation_provenance(
            annotation_context
        )
        selection_rationale_value = annotation_context.get("selection_rationale")
        selection_rationale = (
            selection_rationale_value.strip()
            if isinstance(selection_rationale_value, str)
            and selection_rationale_value.strip()
            else None
        )
        if not resume_existing and selection_rationale is None:
            raise ValueError(
                "Fresh TissueAgent output must record a non-empty selection_rationale in "
                ".uns['tissueagent_cell_annotation']."
            )
        raw_prediction = output.obs[prediction_column].astype("string").fillna("Unassigned")
        confidence = (
            output.obs[confidence_column]
            if confidence_column in output.obs
            else pd.Series(float("nan"), index=output.obs_names)
        )
        predictions = pd.DataFrame(
            {
                "cell_id": output.obs_names,
                "raw_prediction": raw_prediction.to_numpy(),
                "confidence": confidence.to_numpy(dtype=float),
                "method": "tissueagent",
                "mapping_method": mapping_method,
            }
        ).set_index("cell_id")
    finally:
        query.file.close()
        output.file.close()

    if not resume_existing:
        reference_path, reference_audit = _selected_reference_audit(
            fresh_routing_messages or [],
            query_path,
            manifest.get("reference_audit"),
            fresh_agent_messages.get("Single Cell Agent", []),
        )
    else:
        reference_audit = {
            "status": "legacy_supplied" if reference_path is not None else "not_available",
            "agent_generated_required": False,
        }

    routing_audit = (
        _fresh_graph_routing_audit(
            transcript,
            annotation_method,
            messages=fresh_routing_messages,
            query_path=query_path,
            reference_path=reference_path,
            output_path=output_path,
            label_source=label_source,
            subagent_invocation_count=fresh_subagent_invocation_count,
            expected_backend_args=None,
            expected_inspection_context=expected_inspection_context,
        )
        if not resume_existing
        else {
            "status": "not_enforced",
            "enforced": False,
            "source": "resume_or_recovery_artifacts",
            "reason": "Fresh-graph transcript routing is not inferred during resume or recovery.",
            "annotation_method": annotation_method,
            "selected_backend_tool": _BACKEND_TOOL_BY_METHOD[annotation_method],
            "tool_call_counts": None,
            "violations": [],
        }
    )
    if not resume_existing:
        policy_audit = routing_audit.get("selection_policy_audit")
        audited_rationale = (
            policy_audit.get("validated_selection_rationale")
            if isinstance(policy_audit, Mapping)
            else None
        )
        if selection_rationale != audited_rationale:
            raise RuntimeError(
                "Annotated output selection rationale does not match the exact "
                "selection-validator rationale."
            )
    selection_evidence: dict[str, Any] | None = None
    if not resume_existing:
        evidence_path = run_dir / "tissueagent_selection_evidence.json"
        evidence_path.write_text(
            json.dumps(_method_selection_evidence(fresh_routing_messages or []), indent=2),
            encoding="utf-8",
        )
        selection_evidence = {
            "path": str(evidence_path.relative_to(REPO_ROOT)),
            "sha256": _sha256(evidence_path),
        }
    predictions_path = run_dir / "tissueagent_predictions.tsv"
    predictions.to_csv(predictions_path, sep="\t")
    convergence = (
        _harmony_convergence_audit(
            transcript,
            output_path.with_suffix(".run_meta.json"),
        )
        if annotation_method == "harmony"
        else {"status": "not_applicable", "warnings": []}
    )
    warnings = list(convergence["warnings"])
    if outer_graph_warning:
        warnings.append(outer_graph_warning)
    metadata = {
        "status": "success",
        "method": "tissueagent",
        "model_configuration": {
            "selection": get_selection(),
            "request_seed": get_model_seed(),
            "seed_scope": "all orchestration and worker ChatOpenAI requests in this run",
            "langgraph_config": {"recursion_limit": RECURSION_LIMIT},
        },
        "annotation_method": annotation_method,
        "label_source": label_source,
        "mapping_method": mapping_method,
        "selection_rationale": selection_rationale,
        "method_selection": {
            "annotation_method": annotation_method,
            "label_source": label_source,
            "mapping_method": mapping_method,
            "rationale": selection_rationale,
            "rationale_source": (
                "annotated_h5ad.uns.tissueagent_cell_annotation.selection_rationale"
            ),
        },
        "routing_audit": routing_audit,
        "selection_evidence": selection_evidence,
        "selection_blind_query_audit": query_blinding_audit,
        "reference_audit": reference_audit,
        "available_domain_agents": available_domain_agents,
        "domain_agent_registry_audit": domain_agent_registry_audit,
        "agent_invocations": agent_invocations,
        "outer_graph_status": outer_graph_status,
        "n_predictions": len(predictions),
        "annotated_h5ad": str(output_path.relative_to(REPO_ROOT)),
        "predictions_path": str(predictions_path.relative_to(REPO_ROOT)),
        "transcript_path": (
            str(transcript.relative_to(REPO_ROOT)) if transcript.exists() else None
        ),
        "harmony_convergence_status": convergence["status"],
        "warnings": warnings,
        "prompt": prompt,
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    if _evaluation_project is not None:
        metadata["_annotated_project_relative"] = output_path.relative_to(
            ACTIVE_PROJECT_DIR
        ).as_posix()
        backend_metadata_path = output_path.with_suffix(".run_meta.json")
        if backend_metadata_path.is_file():
            metadata["_backend_metadata_project_relative"] = backend_metadata_path.relative_to(
                ACTIVE_PROJECT_DIR
            ).as_posix()
    metadata_path = run_dir / "tissueagent_run.json"
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    metadata["run_metadata"] = str(metadata_path.relative_to(REPO_ROOT))
    return metadata
