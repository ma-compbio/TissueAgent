"""Run TissueAgent repeatability studies on fixed benchmark datasets."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import shutil
import subprocess
import time
import traceback
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from models import (
    build_chat_model,
    get_model_spec,
    get_selection,
    model_seed_context,
    set_selection,
)

from .benchmarks import REPO_ROOT, _label_contract_sha256, _sha256, prepare_benchmark
from .evaluation import evaluate_predictions, materialize_prediction_mapping
from .tissueagent_runner import run_tissueagent


DEFAULT_STUDY_ID = "tissueagent-end-to-end-repeatability-heart-bcl-han-20260806-v1"
STUDY_OUTPUT_ROOT = REPO_ROOT / "demo/outputs/cell_annotation"
FROZEN_HAN_MAPPING = (
    REPO_ROOT
    / "demo/cell_annotation/mappings/han_mouse_brain_stereoseq_frozen.json"
)


@dataclass(frozen=True)
class DatasetSpec:
    """Frozen per-dataset execution and evaluation settings."""

    dataset_id: str
    display_name: str
    label_space: str
    exclusions: tuple[str, ...]
    expected_n_obs: int
    expected_n_truth_cells: int
    expected_n_excluded_truth_cells: int
    expected_prepared_query_sha256: str
    expected_label_contract_sha256: str
    expected_evaluation_mapping_sha256: str


DATASETS = (
    DatasetSpec(
        dataset_id="developing_human_heart",
        display_name="Developing human heart",
        label_space="primary",
        exclusions=(),
        expected_n_obs=228_635,
        expected_n_truth_cells=228_635,
        expected_n_excluded_truth_cells=0,
        expected_prepared_query_sha256=(
            "6c45b5c82fe20f88537d9d77d45667b2b7a110aa056cd2bfb21a35acf66d5dd1"
        ),
        expected_label_contract_sha256=(
            "680980cc253dd8ae28c24c35f52878c3d6397bb4e77dd82327d3e42eec16c61f"
        ),
        expected_evaluation_mapping_sha256=(
            "4f7d33d2cd8ad30f132695ba6c65e2eee2b4f21ccee79245aca42a4c7cfd8ac4"
        ),
    ),
    DatasetSpec(
        dataset_id="bcl",
        display_name="BCL",
        label_space="primary",
        exclusions=("B14",),
        expected_n_obs=49_910,
        expected_n_truth_cells=49_566,
        expected_n_excluded_truth_cells=344,
        expected_prepared_query_sha256=(
            "30e89b96220b7c481fa619d65aa0f3f7a508a2438a0cb8a6a341621c2b86ddc8"
        ),
        expected_label_contract_sha256=(
            "6153f62a39bdb7858e28187b10fb5b820eddc8a383bf83c12fc90211ec306025"
        ),
        expected_evaluation_mapping_sha256=(
            "4616feed9c36242bd8a87766eaa25349b8a659952f09bcd423941c16152adf74"
        ),
    ),
    DatasetSpec(
        dataset_id="han_mouse_brain_stereoseq",
        display_name="Mouse brain Stereo-seq",
        label_space="cell_ontology_shared",
        exclusions=(),
        expected_n_obs=478_740,
        expected_n_truth_cells=478_740,
        expected_n_excluded_truth_cells=0,
        expected_prepared_query_sha256=(
            "7247b476b7137397401de0c843b265bfbe3478319dfef346005291a6e40cf320"
        ),
        expected_label_contract_sha256=(
            "3569ec3fdb88169b1c484089fe7756ab9c16d849abfb41e2f28b3f1ef1c61f21"
        ),
        expected_evaluation_mapping_sha256=(
            "1a250a515fbf614333c4900422478899f34d371e5d359f4cfb9d807f951218a7"
        ),
    ),
)
DATASET_BY_ID = {spec.dataset_id: spec for spec in DATASETS}

# A balanced order limits dataset-specific confounding with remote-model time drift.
EXECUTION_SCHEDULE = (
    ("developing_human_heart", 1),
    ("bcl", 1),
    ("han_mouse_brain_stereoseq", 1),
    ("bcl", 2),
    ("han_mouse_brain_stereoseq", 2),
    ("developing_human_heart", 2),
    ("han_mouse_brain_stereoseq", 3),
    ("developing_human_heart", 3),
    ("bcl", 3),
)
MODEL_SEED_BY_REPLICATE = {1: 42, 2: 43, 3: 44}
PREDICTION_MAPPING_MODEL_SEED = 42

EXPECTED_SOURCE_HASHES = {
    "demo/data/cell_annotation/inputs/developing_human_heart/full.h5ad": (
        "3af2b996834d23f73e77ac197e8c4a9d604dbb67ffe024af9f5d2e6bd41ddecf"
    ),
    "demo/data/cell_annotation/inputs/bcl/full.h5ad": (
        "790106bd504a5de030e005cb4a12e20cc978ead100bcc3af7a85a90230e829be"
    ),
    "demo/data/cell_annotation/inputs/bcl/full.ground_truth.tsv": (
        "e9e19b7475c43a50ce3d9744f42fd0d5cce1ed721394ab83281e43397ed623dc"
    ),
    "demo/data/cell_annotation/inputs/han_mouse_brain_stereoseq/full.h5ad": (
        "7247b476b7137397401de0c843b265bfbe3478319dfef346005291a6e40cf320"
    ),
    (
        "demo/data/cell_annotation/inputs/"
        "han_mouse_brain_stereoseq/full.ground_truth.tsv"
    ): "0106199d103f383651990c506784f1b2df8fdbbaa61b154ffdbacd2cd136a9ac",
    "demo/cell_annotation/mappings/developing_human_heart.json": (
        "4f7d33d2cd8ad30f132695ba6c65e2eee2b4f21ccee79245aca42a4c7cfd8ac4"
    ),
    "demo/cell_annotation/mappings/bcl.json": (
        "4616feed9c36242bd8a87766eaa25349b8a659952f09bcd423941c16152adf74"
    ),
    "demo/cell_annotation/mappings/han_mouse_brain_stereoseq.json": (
        "97b6c8054bd2174a420d1d11b2f49842cf2252c362d20c89ac719997caa7bc28"
    ),
    (
        "demo/cell_annotation/mappings/han_mouse_brain_stereoseq_frozen.json"
    ): "1a250a515fbf614333c4900422478899f34d371e5d359f4cfb9d807f951218a7",
}

SNAPSHOT_FILES = (
    "pyproject.toml",
    "uv.lock",
    "src/models.py",
    "src/config.py",
    "src/graph/graph.py",
    "src/agents/agent_defns.py",
    "src/agents/planner_agent/prompt.txt",
    "src/agents/planner_agent/replan_prompt.txt",
    "src/agents/recruiter_agent/prompt.txt",
    "src/agents/cell_annotation_context.py",
    "src/agents/manager_agent/prompt.txt",
    "src/agents/manager_agent/tools.py",
    "knowledge/plans/cell_annotation.md",
    "knowledge/skills/cell_type_annotation.md",
    "demo/cell_annotation/benchmarks.py",
    "demo/cell_annotation/evaluation.py",
    "demo/cell_annotation/plot_tissueagent_repeatability.py",
    "demo/cell_annotation/tissueagent_runner.py",
    "demo/cell_annotation/run_tissueagent_repeatability.py",
    "demo/cell_annotation/manifests/developing_human_heart.yaml",
    "demo/cell_annotation/manifests/bcl.yaml",
    "demo/cell_annotation/manifests/han_mouse_brain_stereoseq.yaml",
    "src/agents/agent_registry/cell_annotater_agent/prompt.py",
    "src/agents/agent_registry/cell_annotater_agent/tools.py",
    "src/agents/agent_registry/cell_annotater_agent/tools_impl/harmony_transfer.py",
    "src/agents/agent_registry/cell_annotater_agent/tools_impl/celltypist_annotation.py",
    "src/agents/agent_registry/cell_annotater_agent/tools_impl/gptcelltype_annotation.py",
    "src/agents/agent_registry/cell_annotater_agent/tools_impl/gptcelltype_readiness.py",
    "src/agents/agent_registry/cell_annotater_agent/tools_impl/method_selection.py",
    "src/agents/agent_registry/cell_annotater_agent/tools_impl/selection_contract.py",
    "src/agents/agent_registry/cell_annotater_agent/tools_impl/selection_preflight.py",
    "src/agents/agent_registry/single_cell_agent/prompt.py",
    "src/agents/agent_registry/single_cell_agent/tools.py",
    ("src/agents/agent_registry/single_cell_agent/tools_impl/query_cellxgene_single_cell_tool.py"),
    (
        "src/agents/agent_registry/single_cell_agent/tools_impl/"
        "retrieve_cellxgene_single_cell_tool.py"
    ),
)


def _timestamp() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _run_git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def _text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _study_relative(path: Path, study_root: Path) -> str:
    return os.path.relpath(path, start=study_root)


def _write_manifest(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.partial")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(path)


def _verify_expected_sources() -> dict[str, dict[str, Any]]:
    observed: dict[str, dict[str, Any]] = {}
    for relative, expected_sha256 in EXPECTED_SOURCE_HASHES.items():
        path = REPO_ROOT / relative
        if not path.is_file():
            raise FileNotFoundError(f"Required study source is absent: {path}")
        observed_sha256 = _sha256(path)
        if observed_sha256 != expected_sha256:
            raise ValueError(
                f"Study source SHA-256 changed for {relative}: "
                f"expected {expected_sha256}, observed {observed_sha256}."
            )
        observed[relative] = {
            "sha256": observed_sha256,
            "size_bytes": path.stat().st_size,
        }
    return observed


def _package_versions() -> dict[str, str]:
    packages = (
        "anndata",
        "celltypist",
        "harmonypy",
        "langchain-openai",
        "matplotlib",
        "numpy",
        "openai",
        "pandas",
        "scanpy",
        "scikit-learn",
    )
    return {name: importlib.metadata.version(name) for name in packages}


def _source_snapshot() -> dict[str, Any]:
    status = _run_git("status", "--porcelain=v1")
    diff = _run_git("diff", "--binary")
    cached_diff = _run_git("diff", "--cached", "--binary")
    files: dict[str, dict[str, Any]] = {}
    for relative in SNAPSHOT_FILES:
        path = REPO_ROOT / relative
        if not path.is_file():
            raise FileNotFoundError(f"Snapshot file is absent: {path}")
        files[relative] = {"sha256": _sha256(path), "size_bytes": path.stat().st_size}
    return {
        "captured_utc": _timestamp(),
        "git_head": _run_git("rev-parse", "HEAD").strip(),
        "git_status_porcelain": status.splitlines(),
        "git_status_sha256": _text_sha256(status),
        "git_diff_sha256": _text_sha256(diff),
        "git_cached_diff_sha256": _text_sha256(cached_diff),
        "model_selection": get_selection(),
        "package_versions": _package_versions(),
        "source_files": _verify_expected_sources(),
        "implementation_files": files,
    }


def _new_manifest(
    study_id: str,
    study_root: Path,
    dataset_ids: tuple[str, ...],
) -> dict[str, Any]:
    selected_specs = tuple(DATASET_BY_ID[dataset_id] for dataset_id in dataset_ids)
    execution_schedule = tuple(entry for entry in EXECUTION_SCHEDULE if entry[0] in dataset_ids)
    runs = []
    for execution_order, (dataset_id, replicate) in enumerate(execution_schedule, start=1):
        spec = DATASET_BY_ID[dataset_id]
        run_id = f"{study_id}-r{replicate}"
        run_dir = REPO_ROOT / "demo/outputs/cell_annotation" / dataset_id / run_id
        runs.append(
            {
                "execution_order": execution_order,
                "dataset_id": dataset_id,
                "display_name": spec.display_name,
                "replicate": replicate,
                "model_seed": MODEL_SEED_BY_REPLICATE[replicate],
                "run_id": run_id,
                "status": "planned",
                "label_space": spec.label_space,
                "exclude_ground_truth_raw_labels": list(spec.exclusions),
                "prepared_run_json": _study_relative(run_dir / "prepared_run.json", study_root),
                "tissueagent_run_json": _study_relative(
                    run_dir / "tissueagent_run.json", study_root
                ),
                "metrics_tsv": _study_relative(run_dir / "metrics_repeatability.tsv", study_root),
                "metrics_json": _study_relative(run_dir / "metrics_repeatability.json", study_root),
            }
        )
    dataset_records = []
    for spec in selected_specs:
        dataset_runs = [
            {
                "replicate": run["replicate"],
                "model_seed": run["model_seed"],
                "run_id": run["run_id"],
                "prepared_run_json": run["prepared_run_json"],
                "tissueagent_run_json": run["tissueagent_run_json"],
                "metrics_tsv": run["metrics_tsv"],
                "metrics_json": run["metrics_json"],
            }
            for run in runs
            if run["dataset_id"] == spec.dataset_id
        ]
        dataset_records.append(
            {
                "dataset_id": spec.dataset_id,
                "display_name": spec.display_name,
                "expected_label_space": spec.label_space,
                "expected_exclusions": list(spec.exclusions),
                "expected_n_obs": spec.expected_n_obs,
                "expected_n_truth_cells": spec.expected_n_truth_cells,
                "expected_n_excluded_truth_cells": spec.expected_n_excluded_truth_cells,
                "expected_prepared_query_sha256": spec.expected_prepared_query_sha256,
                "expected_label_contract_sha256": spec.expected_label_contract_sha256,
                "expected_evaluation_mapping_sha256": (spec.expected_evaluation_mapping_sha256),
                "runs": dataset_runs,
            }
        )
    return {
        "schema_version": "1.0",
        "study_id": study_id,
        "status": "initialized",
        "created_utc": _timestamp(),
        "updated_utc": _timestamp(),
        "design": {
            "description": (
                "Three independent end-to-end TissueAgent executions per selected fixed blinded "
                "query. "
                "Each run starts in a clean project, exposes the full domain-agent registry, "
                "and leaves reference acquisition, method selection, and complete backend "
                "configuration to TissueAgent."
            ),
            "run_mode": "full",
            "preparation_random_seed": 42,
            "tissueagent_model_seeds_by_replicate": MODEL_SEED_BY_REPLICATE,
            "tissueagent_model_seed_scope": (
                "all orchestration and worker ChatOpenAI requests within a replicate"
            ),
            "n_replicates_per_dataset": 3,
            "dataset_ids": list(dataset_ids),
            "execution_order": "balanced three-period Latin order",
            "error_bars": "plus or minus one sample standard deviation across n=3 runs",
            "agent_input": (
                "selection-blind query plus immutable biological and annotation-scope context"
            ),
            "reference_policy": "acquired independently by TissueAgent within each run",
            "backend_parameter_policy": "selected and contract-bound inside Cell Annotator",
            "domain_agent_registry": "full production registry",
            "recovery_runs_allowed": False,
        },
        "datasets": dataset_records,
        "source_snapshot": _source_snapshot(),
        "runs": runs,
    }


def initialize_study(
    study_id: str,
    dataset_ids: tuple[str, ...] | None = None,
) -> tuple[Path, Path, dict[str, Any]]:
    """Create the immutable design record and planned run ledger."""
    selected_dataset_ids = dataset_ids or tuple(spec.dataset_id for spec in DATASETS)
    study_root = STUDY_OUTPUT_ROOT / study_id
    manifest_path = study_root / "study_manifest.json"
    study_root.mkdir(parents=True, exist_ok=False)
    manifest = _new_manifest(study_id, study_root, selected_dataset_ids)
    _write_manifest(manifest_path, manifest)
    return study_root, manifest_path, manifest


def load_study(study_id: str) -> tuple[Path, Path, dict[str, Any]]:
    """Load an existing study without mutating completed attempts."""
    study_root = STUDY_OUTPUT_ROOT / study_id
    manifest_path = study_root / "study_manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Study manifest is absent: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("study_id") != study_id:
        raise ValueError("Study manifest identifier does not match its requested directory.")
    return study_root, manifest_path, manifest


def _save_study(manifest_path: Path, manifest: dict[str, Any]) -> None:
    manifest["updated_utc"] = _timestamp()
    analysis_runs = [run for run in manifest["runs"] if run.get("analysis_included", True)]
    statuses = [run["status"] for run in analysis_runs]
    has_failed_attempts = any(run["status"] == "failed" for run in manifest["runs"])
    if statuses and all(status == "evaluated" for status in statuses):
        manifest["status"] = "complete_with_failed_attempts" if has_failed_attempts else "complete"
    elif any(status == "failed" for status in statuses):
        manifest["status"] = "has_failed_attempt"
    elif any(status in {"running", "inference_complete"} for status in statuses):
        manifest["status"] = "running"
    elif all(status == "prepared" for status in statuses):
        manifest["status"] = "prepared"
    else:
        manifest["status"] = "preparing"
    _write_manifest(manifest_path, manifest)


def replace_failed_run(
    study_root: Path,
    manifest_path: Path,
    manifest: dict[str, Any],
) -> None:
    """Preserve one failed analysis attempt and prepare a fresh replacement."""
    failed = [
        run
        for run in manifest["runs"]
        if run.get("analysis_included", True) and run["status"] == "failed"
    ]
    if len(failed) != 1:
        raise RuntimeError(
            "Replacement requires exactly one analysis-included failed run; "
            f"observed {len(failed)}."
        )
    failed_run = failed[0]
    attempt = int(failed_run.get("attempt", 1)) + 1
    replacement_run_id = (
        f"{manifest['study_id']}-r{failed_run['replicate']}-replacement{attempt - 1}"
    )
    run_dir = (
        REPO_ROOT / "demo/outputs/cell_annotation" / failed_run["dataset_id"] / replacement_run_id
    )
    if run_dir.exists():
        raise FileExistsError(f"Replacement run directory already exists: {run_dir}")

    replacement_order = int(failed_run["execution_order"]) + 1
    for run in manifest["runs"]:
        if int(run["execution_order"]) >= replacement_order:
            run["execution_order"] = int(run["execution_order"]) + 1

    replacement = {
        "execution_order": replacement_order,
        "dataset_id": failed_run["dataset_id"],
        "display_name": failed_run["display_name"],
        "replicate": failed_run["replicate"],
        "model_seed": failed_run["model_seed"],
        "attempt": attempt,
        "run_id": replacement_run_id,
        "status": "planned",
        "analysis_included": True,
        "replaces_run_id": failed_run["run_id"],
        "label_space": failed_run["label_space"],
        "exclude_ground_truth_raw_labels": list(failed_run["exclude_ground_truth_raw_labels"]),
        "prepared_run_json": _study_relative(run_dir / "prepared_run.json", study_root),
        "tissueagent_run_json": _study_relative(run_dir / "tissueagent_run.json", study_root),
        "metrics_tsv": _study_relative(run_dir / "metrics_repeatability.tsv", study_root),
        "metrics_json": _study_relative(run_dir / "metrics_repeatability.json", study_root),
    }
    failed_run["analysis_included"] = False
    failed_run["replacement_run_id"] = replacement_run_id
    failed_run["failure_preserved"] = True
    failed_index = manifest["runs"].index(failed_run)
    manifest["runs"].insert(failed_index + 1, replacement)

    dataset = next(
        record
        for record in manifest["datasets"]
        if record["dataset_id"] == failed_run["dataset_id"]
    )
    nested_index = next(
        index
        for index, record in enumerate(dataset["runs"])
        if int(record["replicate"]) == int(failed_run["replicate"])
    )
    dataset["runs"][nested_index] = {
        "replicate": replacement["replicate"],
        "model_seed": replacement["model_seed"],
        "run_id": replacement["run_id"],
        "prepared_run_json": replacement["prepared_run_json"],
        "tissueagent_run_json": replacement["tissueagent_run_json"],
        "metrics_tsv": replacement["metrics_tsv"],
        "metrics_json": replacement["metrics_json"],
    }

    design = manifest["design"]
    design["recovery_runs_allowed"] = False
    design["fresh_replacement_runs_allowed"] = True
    design["failed_attempts_excluded_from_summary"] = True
    design["n_failed_attempts"] = sum(run["status"] == "failed" for run in manifest["runs"])
    manifest.setdefault("source_snapshot_amendments", []).append(
        {
            "captured_utc": _timestamp(),
            "reason": (
                "Prepared a new independent replacement after an exactly-once routing "
                "audit failure; the failed attempt remains in the ledger and is excluded."
            ),
            "replaced_run_id": failed_run["run_id"],
            "replacement_run_id": replacement_run_id,
            "snapshot": _source_snapshot(),
        }
    )
    _save_study(manifest_path, manifest)
    prepare_study(study_root, manifest_path, manifest)


def prepare_study(
    study_root: Path,
    manifest_path: Path,
    manifest: dict[str, Any],
) -> None:
    """Prepare all planned blinded inputs before any fresh graph execution."""
    analysis_runs = [run for run in manifest["runs"] if run.get("analysis_included", True)]
    total_runs = len(analysis_runs)
    for run in manifest["runs"]:
        if run["status"] != "planned":
            continue
        spec = DATASET_BY_ID[run["dataset_id"]]
        _verify_expected_sources()
        print(
            f"[prepare {run['execution_order']}/{total_runs}] {run['dataset_id']} "
            f"replicate {run['replicate']}",
            flush=True,
        )
        prepared = prepare_benchmark(
            run["dataset_id"],
            run_mode="full",
            run_id=run["run_id"],
            random_seed=42,
        )
        query_path = REPO_ROOT / prepared["query_h5ad"]
        ground_truth_path = REPO_ROOT / prepared["ground_truth_tsv"]
        mapping_path = REPO_ROOT / prepared["label_mapping_json"]
        query_sha256 = _sha256(query_path)
        if query_sha256 != spec.expected_prepared_query_sha256:
            raise ValueError(
                f"Prepared query SHA-256 changed for {spec.dataset_id}: {query_sha256}."
            )
        if prepared["label_contract_sha256"] != spec.expected_label_contract_sha256:
            raise ValueError(f"Label contract changed for {spec.dataset_id}.")
        run.update(
            {
                "status": "prepared",
                "prepared_utc": _timestamp(),
                "selection_blind_id": prepared["selection_blind_id"],
                "query_h5ad": _study_relative(query_path, study_root),
                "query_sha256": query_sha256,
                "ground_truth_tsv": _study_relative(ground_truth_path, study_root),
                "ground_truth_sha256": _sha256(ground_truth_path),
                "label_mapping_json": _study_relative(mapping_path, study_root),
                "prepared_mapping_sha256": _sha256(mapping_path),
                "label_contract_sha256": prepared["label_contract_sha256"],
                "n_obs": prepared["n_obs"],
                "n_vars": prepared["n_vars"],
            }
        )
        _save_study(manifest_path, manifest)


def _install_frozen_han_mapping(prepared: dict[str, Any], spec: DatasetSpec) -> None:
    mapping_path = REPO_ROOT / prepared["label_mapping_json"]
    pending = json.loads(mapping_path.read_text(encoding="utf-8"))
    frozen = json.loads(FROZEN_HAN_MAPPING.read_text(encoding="utf-8"))
    if pending.get("prediction_mapping_status") != "pending":
        raise ValueError("Fresh Han run-local mapping was not pending before evaluation.")
    if frozen.get("prediction_mapping_status") != "complete":
        raise ValueError("Frozen Han evaluation mapping is not complete.")
    if _label_contract_sha256(pending) != spec.expected_label_contract_sha256:
        raise ValueError("Pending Han biological label contract changed.")
    if _label_contract_sha256(frozen) != spec.expected_label_contract_sha256:
        raise ValueError("Frozen Han biological label contract changed.")
    if _sha256(FROZEN_HAN_MAPPING) != spec.expected_evaluation_mapping_sha256:
        raise ValueError("Frozen Han evaluation mapping SHA-256 changed.")
    shutil.copy2(FROZEN_HAN_MAPPING, mapping_path)


def _validate_fresh_result(result: dict[str, Any]) -> None:
    from agents.agent_defns import AgentDefns

    if result.get("status") != "success":
        raise RuntimeError(f"TissueAgent result did not succeed: {result.get('status')!r}")
    if result.get("outer_graph_status") != "completed":
        raise RuntimeError(
            f"Fresh TissueAgent outer graph did not complete: {result.get('outer_graph_status')!r}"
        )
    routing = result.get("routing_audit")
    if not isinstance(routing, dict) or routing.get("status") != "passed":
        raise RuntimeError("Fresh TissueAgent routing audit did not pass.")
    reference = result.get("reference_audit")
    if (
        not isinstance(reference, dict)
        or reference.get("status") != "passed"
        or reference.get("agent_generated_under_project_outputs") is not True
    ):
        raise RuntimeError("TissueAgent did not acquire an auditable per-run reference.")
    available_ids = {
        agent.get("id")
        for agent in result.get("available_domain_agents", [])
        if isinstance(agent, dict)
    }
    expected_ids = {agent.id for agent in AgentDefns}
    registry_audit = result.get("domain_agent_registry_audit")
    if (
        available_ids != expected_ids
        or not isinstance(registry_audit, dict)
        or registry_audit.get("status") != "passed"
        or registry_audit.get("graph_domain_agents_override") is not False
    ):
        raise RuntimeError("Fresh TissueAgent run did not expose the full domain-agent registry.")
    invoked_names = {
        invocation.get("agent_name")
        for invocation in result.get("agent_invocations", [])
        if isinstance(invocation, dict)
    }
    if not {"Single Cell Agent", "Cell Annotator Agent"}.issubset(invoked_names):
        raise RuntimeError(
            "Fresh TissueAgent run did not autonomously recruit reference and annotation agents."
        )
    project = result.get("evaluation_project")
    if (
        not isinstance(project, dict)
        or project.get("status") != "parked"
        or project.get("isolated_from_other_replicates") is not True
    ):
        raise RuntimeError("Fresh TissueAgent run did not finish in an isolated parked project.")


def _evaluate_run(
    prepared: dict[str, Any],
    result: dict[str, Any],
    spec: DatasetSpec,
) -> tuple[dict[str, Any], str, Path, dict[str, Any]]:
    mapping_path = REPO_ROOT / prepared["label_mapping_json"]
    if spec.dataset_id == "han_mouse_brain_stereoseq":
        _install_frozen_han_mapping(prepared, spec)
    if _sha256(mapping_path) != spec.expected_evaluation_mapping_sha256:
        raise ValueError(f"Evaluation mapping SHA-256 changed for {spec.dataset_id}.")
    prediction_path = Path(result["predictions_path"])
    if not prediction_path.is_absolute():
        prediction_path = REPO_ROOT / prediction_path
    prediction_mapping_path = prediction_path.with_name("prediction_mapping.json")
    model_id = get_selection()["worker"]
    model_spec = get_model_spec(model_id)
    with model_seed_context(PREDICTION_MAPPING_MODEL_SEED):
        prediction_mapping = materialize_prediction_mapping(
            mapping_path,
            prediction_path,
            prediction_mapping_path,
            prediction_method="tissueagent",
            model=build_chat_model(model_id),
            model_metadata={
                "model_id": model_spec.id,
                "provider": model_spec.provider,
                "api_model": model_spec.api_model,
                "reasoning_effort": model_spec.reasoning_effort,
                "request_seed": PREDICTION_MAPPING_MODEL_SEED,
            },
        )
    metrics = evaluate_predictions(
        prepared,
        prediction_paths={"tissueagent": prediction_path},
        label_space=spec.label_space,
        exclude_ground_truth_raw_labels=list(spec.exclusions),
        prediction_mapping_path=prediction_mapping_path,
        output_stem="metrics_repeatability",
    )
    row = json.loads(metrics.reset_index().to_json(orient="records"))[0]
    if row["method"] != "tissueagent":
        raise ValueError("Repeatability evaluation produced an unexpected method row.")
    expected = {
        "n_truth_cells": spec.expected_n_truth_cells,
        "n_excluded_truth_cells": spec.expected_n_excluded_truth_cells,
        "n_prediction_rows": spec.expected_n_obs,
    }
    for field, value in expected.items():
        if int(row[field]) != value:
            raise ValueError(
                f"Unexpected {field} for {spec.dataset_id}: {row[field]} instead of {value}."
            )
    if float(row["backend_prediction_row_coverage"]) != 1.0:
        raise ValueError(f"Prediction row coverage was incomplete for {spec.dataset_id}.")
    return row, _sha256(mapping_path), prediction_mapping_path, prediction_mapping


def run_study(
    study_root: Path,
    manifest_path: Path,
    manifest: dict[str, Any],
) -> None:
    """Execute and score every prepared run serially."""
    analysis_runs = [run for run in manifest["runs"] if run.get("analysis_included", True)]
    total_runs = len(analysis_runs)
    if any(run["status"] == "planned" for run in analysis_runs):
        raise RuntimeError("All study inputs must be prepared before execution.")
    set_selection("gpt-5.1", "gpt-5.1")
    if get_selection() != {"orchestration": "gpt-5.1", "worker": "gpt-5.1"}:
        raise RuntimeError("TissueAgent model selection did not remain pinned to gpt-5.1.")
    for run in manifest["runs"]:
        if not run.get("analysis_included", True):
            continue
        if run["status"] == "evaluated":
            continue
        if run["status"] != "prepared":
            raise RuntimeError(f"Run {run['run_id']} cannot execute from status {run['status']!r}.")
        _verify_expected_sources()
        spec = DATASET_BY_ID[run["dataset_id"]]
        prepared_path = (study_root / run["prepared_run_json"]).resolve()
        prepared = json.loads(prepared_path.read_text(encoding="utf-8"))
        run["status"] = "running"
        run["started_utc"] = _timestamp()
        _save_study(manifest_path, manifest)
        started = time.monotonic()
        print(
            f"[run {run['execution_order']}/{total_runs}] {run['dataset_id']} "
            f"replicate {run['replicate']} seed {run['model_seed']}",
            flush=True,
        )
        try:
            with model_seed_context(run["model_seed"]):
                result = run_tissueagent(prepared, resume_existing=False)
            _validate_fresh_result(result)
            if result.get("model_configuration", {}).get("request_seed") != run["model_seed"]:
                raise RuntimeError("TissueAgent run did not preserve its assigned model seed.")
            run.update(
                {
                    "status": "inference_complete",
                    "annotation_method": result["annotation_method"],
                    "mapping_method": result["mapping_method"],
                    "outer_graph_status": result["outer_graph_status"],
                    "routing_audit_status": result["routing_audit"]["status"],
                    "reference_sha256": result["reference_audit"]["sha256"],
                    "reference_dataset_ids": result["reference_audit"]["observed_dataset_ids"],
                    "reference_path": _study_relative(
                        REPO_ROOT / result["reference_audit"]["archived_path"], study_root
                    ),
                    "evaluation_project": result["evaluation_project"],
                    "agent_invocations": result["agent_invocations"],
                    "predictions_path": _study_relative(
                        REPO_ROOT / result["predictions_path"], study_root
                    ),
                    "predictions_sha256": _sha256(REPO_ROOT / result["predictions_path"]),
                    "annotated_h5ad": _study_relative(
                        REPO_ROOT / result["annotated_h5ad"], study_root
                    ),
                }
            )
            _save_study(manifest_path, manifest)
            (
                metrics,
                mapping_sha256,
                prediction_mapping_path,
                prediction_mapping,
            ) = _evaluate_run(prepared, result, spec)
            run.update(
                {
                    "status": "evaluated",
                    "completed_utc": _timestamp(),
                    "duration_seconds": round(time.monotonic() - started, 3),
                    "evaluation_mapping_sha256": mapping_sha256,
                    "prediction_mapping_path": _study_relative(
                        prediction_mapping_path,
                        study_root,
                    ),
                    "prediction_mapping_sha256": _sha256(prediction_mapping_path),
                    "prediction_mapping_status": prediction_mapping["status"],
                    "n_run_local_prediction_mappings": len(prediction_mapping["mapping"]),
                    "metrics": metrics,
                    "metrics_tsv_sha256": _sha256((study_root / run["metrics_tsv"]).resolve()),
                    "metrics_json_sha256": _sha256((study_root / run["metrics_json"]).resolve()),
                }
            )
            _save_study(manifest_path, manifest)
            print(
                f"[done {run['execution_order']}/{total_runs}] "
                f"backend={run['annotation_method']} "
                f"accuracy={metrics['accuracy']:.6f} "
                f"macro_precision={metrics['macro_precision']:.6f}",
                flush=True,
            )
        except Exception as error:
            run.update(
                {
                    "status": "failed",
                    "failed_utc": _timestamp(),
                    "duration_seconds": round(time.monotonic() - started, 3),
                    "error_type": type(error).__name__,
                    "error": str(error),
                    "traceback": traceback.format_exc(),
                }
            )
            _save_study(manifest_path, manifest)
            raise


def main() -> None:
    """Prepare, execute, or continue the fixed repeatability study."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "replace-failed", "run", "all"))
    parser.add_argument("--study-id", default=DEFAULT_STUDY_ID)
    parser.add_argument(
        "--dataset",
        action="append",
        choices=tuple(DATASET_BY_ID),
        dest="datasets",
        help="Limit a newly prepared study to one or more datasets.",
    )
    args = parser.parse_args()

    if args.command in {"prepare", "all"}:
        selected_dataset_ids = tuple(args.datasets or DATASET_BY_ID)
        study_root, manifest_path, manifest = initialize_study(
            args.study_id,
            selected_dataset_ids,
        )
        prepare_study(study_root, manifest_path, manifest)
    else:
        if args.datasets:
            parser.error("--dataset is only valid with prepare or all")
        study_root, manifest_path, manifest = load_study(args.study_id)
    if args.command == "replace-failed":
        replace_failed_run(study_root, manifest_path, manifest)
    if args.command in {"run", "all"}:
        run_study(study_root, manifest_path, manifest)


if __name__ == "__main__":
    main()
