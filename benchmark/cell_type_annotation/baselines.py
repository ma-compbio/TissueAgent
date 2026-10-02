"""Direct cell-annotation benchmark runners."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import anndata as ad
import numpy as np
import pandas as pd
import scanpy as sc
from scipy import sparse

from .benchmarks import DATA_DIR, REPO_ROOT, load_manifest


EXPECTED_VERSIONS = {"celltypist": "1.7.1", "omicverse": "2.2.3"}
GPTCELLTYPE_NATIVE_MAX_MARKER_GENES = 10


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024**2), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_revision(path: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode:
        raise RuntimeError(f"Cannot determine git revision for {path}.")
    return completed.stdout.strip()


def _load_prepared(prepared: dict[str, Any] | str | Path) -> dict[str, Any]:
    if isinstance(prepared, dict):
        return prepared
    path = Path(prepared)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return json.loads(path.read_text(encoding="utf-8"))


def _require_version(distribution: str) -> str:
    try:
        installed = importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError as exc:
        raise RuntimeError(
            f"{distribution} is not installed. Run the locked benchmark environment setup; "
            "the notebook will not install packages automatically."
        ) from exc
    expected = EXPECTED_VERSIONS[distribution]
    if installed != expected:
        raise RuntimeError(f"{distribution}=={expected} is required; found {installed}.")
    return installed


def _prepare_log1p(dataset: ad.AnnData) -> tuple[ad.AnnData, dict[str, Any]]:
    """Create canonical log1p-per-10K expression without double-transforming input."""
    working = dataset.copy()
    matrix = working.X
    values = matrix.data if sparse.issparse(matrix) else np.asarray(matrix).ravel()
    if not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("Baseline input contains negative or non-finite expression values.")
    indices = np.linspace(0, max(0, len(values) - 1), min(len(values), 1_000_000), dtype=int)
    sampled = np.asarray(values[indices], dtype=np.float64) if len(values) else values
    integer_like_fraction = (
        float(np.mean(np.isclose(sampled, np.rint(sampled), atol=1e-6, rtol=0)))
        if len(sampled)
        else 0.0
    )
    explicit_log1p = "log1p" in working.uns

    if integer_like_fraction >= 0.99 and not explicit_log1p:
        source_state = "raw_count_like"
        inferred_target_sum = None
    else:
        linear = working.X.copy()
        if sparse.issparse(linear):
            linear.data = np.expm1(linear.data)
        else:
            linear = np.expm1(np.asarray(linear))
        totals = np.asarray(linear.sum(axis=1)).ravel()
        positive_totals = totals[totals > 0]
        if not len(positive_totals):
            raise ValueError("Baseline input contains no positive-expression observations.")
        quantiles = np.quantile(positive_totals, [0.05, 0.5, 0.95])
        relative_spread = float((quantiles[2] - quantiles[0]) / quantiles[1])
        if not explicit_log1p and relative_spread > 0.01:
            raise ValueError(
                "Continuous nonnegative expression lacks explicit log1p metadata and does not "
                "have a stable inferred normalization total."
            )
        working.X = linear
        source_state = "explicit_log1p" if explicit_log1p else "inferred_log1p_normalized"
        inferred_target_sum = float(quantiles[1])

    sc.pp.normalize_total(working, target_sum=10_000)
    sc.pp.log1p(working)
    audit = {
        "source_state": source_state,
        "sampled_integer_like_fraction": integer_like_fraction,
        "explicit_log1p_metadata": explicit_log1p,
        "inferred_input_target_sum": inferred_target_sum,
        "output_transform": "normalize_total_10000_log1p",
    }
    return working, audit


def _normalize_log1p(dataset: ad.AnnData) -> ad.AnnData:
    """Backward-compatible wrapper for callers that only need the prepared object."""
    return _prepare_log1p(dataset)[0]


def _prediction_output(prepared: dict[str, Any], method: str) -> Path:
    run_dir = REPO_ROOT / prepared["run_dir"]
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir / f"{method}_predictions.tsv"


def _agent_task_prompt(
    query_path: Path,
    annotated_path: Path,
    manifest: dict[str, Any],
    task_prompt_template: str | None = None,
) -> str:
    if task_prompt_template is not None:
        return task_prompt_template.replace("<QUERY_H5AD>", str(query_path)).replace(
            "<ANNOTATED_H5AD>", str(annotated_path)
        )
    assay = "spatial AnnData" if manifest["query"].get("require_spatial", True) else "AnnData"
    context = (
        f"species='{manifest['species']}', tissue='{manifest['tissue']}', "
        f"disease='{manifest['disease']}'"
    )
    if manifest.get("developmental_stage"):
        context += f", developmental_stage='{manifest['developmental_stage']}'"
    if manifest.get("study_context"):
        context += f". Study context: {manifest['study_context'].rstrip('.')}"
    if manifest.get("annotation_scope"):
        context += ". Annotation scope contract: " + json.dumps(
            manifest["annotation_scope"], ensure_ascii=False, separators=(",", ":"), sort_keys=True
        )
    return (
        f"Annotate cell types in {assay} '{query_path}'. Biological context: {context}. "
        f"Save the annotated H5AD to '{annotated_path}'."
    )


def _agent_execution_contract(manifest: dict[str, Any], model: str) -> str:
    excluded_dois = manifest.get("reference_audit", {}).get("forbidden_collection_dois", [])
    return f"""\
Execution requirements: The input is the original selection-blind query, not an adapter-preprocessed
object. Inspect its state and perform any preprocessing required by your workflow yourself. Do not
modify the input file. Keep intermediate and final outputs in the specified output directory.
Do not inspect other benchmark files, ground truth, existing predictions, or label mappings.
Public reference and marker resources are allowed. Do not use reference datasets from these excluded
source-study DOIs: {excluded_dois}.
Use exactly {model!r} for the main agent, retrieval, subagents, and annotation/model subcalls.
Preserve original observation identifiers and save predicted labels in .obs['cell_type'].
Complete cell-type annotation rather than returning instructions; do not run tissue-niche analysis.
"""


def _biomni_prompt(
    query_path: Path,
    annotated_path: Path,
    manifest: dict[str, Any],
    model: str,
    task_prompt_template: str | None = None,
) -> str:
    return f"""\
{_agent_task_prompt(query_path, annotated_path, manifest, task_prompt_template)}

{_agent_execution_contract(manifest, model)}

Choose and execute the analysis using Biomni's tools and coding capabilities. Preprocessing,
clustering, annotation strategy and their parameters are your decisions based on this input.

Execute one step per execution block and wait for the actual tool result before reporting success.
Biomni's solution block terminates the run. Do not use it for an intermediate plan or progress
checklist: continue using execution blocks until the final H5AD has been saved and verified.
Execute scientific Python directly inside the existing execution block. Do not invoke a shell,
subprocess, second interpreter, or nested Python REPL for the analysis:
the required model-compatibility bindings live in the existing Python process.
Never mention XML control tags inside code, strings, or
comments, because Biomni's router parses those as control flow even inside an execution block.

Verify that the final file exists at {str(annotated_path)!r} and contains one predicted label per
retained query observation. Use compressed H5AD output and avoid unnecessary large file copies.
"""


def _spatialagent_prompt(
    query_path: Path,
    annotated_path: Path,
    manifest: dict[str, Any],
    model: str,
    task_prompt_template: str | None = None,
) -> str:
    return f"""\
{_agent_task_prompt(query_path, annotated_path, manifest, task_prompt_template)}

{_agent_execution_contract(manifest, model)}

Follow SpatialAgent's Spatial Annotation workflow through cell-type annotation. Its configured
celltype_annotated.h5ad output is the requested final file.

SpatialAgent injects selected tool functions directly into its stateful Python REPL. In <act>
blocks, invoke those functions directly with their argument dictionaries.
Run one workflow step at a time. Do not import tool names as Python modules, and do not call an
execute_python wrapper.
The download_czi_reference tool returns a human-readable status message rather than a bare path.
After it runs, locate the generated H5AD under save_path/czi_reference and pass that filesystem path
to harmony_transfer_labels, including when the reference was already cached.
The harmony_transfer_labels tool writes celltype_transferred.csv under save_path (without an
index suffix). Verify that file exists before passing it to annotate_cell_types. The annotation
tool saves a separate celltype_annotated.h5ad; reload that output to verify labels, not the
unannotated preprocessed.h5ad, and do not overwrite it from the unannotated object.

The saved object must contain predicted labels in .obs['cell_type'].
"""


def _execute_agent_worker(
    method: str,
    request: dict[str, Any],
    *,
    python_executable: str,
    workspace: Path,
    working_directory: Path,
    timeout_seconds: int,
) -> dict[str, Any]:
    workspace.mkdir(parents=True, exist_ok=False)
    if request.get("resume_from"):
        request["resumed_artifacts"] = _stage_spatialagent_resume(request, workspace)
    request_path = workspace / "worker_request.json"
    result_path = workspace / "worker_result.json"
    stdout_path = workspace / "worker_stdout.log"
    stderr_path = workspace / "worker_stderr.log"
    request_path.write_text(json.dumps(request, indent=2), encoding="utf-8")
    worker_path = Path(__file__).with_name("agent_baseline_worker.py")
    command = [
        python_executable,
        str(worker_path),
        "--method",
        method,
        "--request",
        str(request_path),
        "--result",
        str(result_path),
    ]
    environment = os.environ.copy()
    environment["PATH"] = (
        str(Path(python_executable).resolve().parent) + os.pathsep + environment["PATH"]
    )
    with (
        stdout_path.open("w", encoding="utf-8") as stdout,
        stderr_path.open("w", encoding="utf-8") as stderr,
    ):
        completed = subprocess.run(
            command,
            cwd=working_directory,
            stdout=stdout,
            stderr=stderr,
            timeout=timeout_seconds,
            check=False,
            env=environment,
        )
    if not result_path.exists():
        raise RuntimeError(
            f"{method} worker exited with code {completed.returncode} without a result; "
            f"see {stdout_path} and {stderr_path}."
        )
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if completed.returncode or result.get("status") != "success":
        message = result.get("message", f"worker exit code {completed.returncode}")
        raise RuntimeError(
            f"{method} worker failed: {message}; see {stdout_path} and {stderr_path}."
        )
    return result


def _stage_spatialagent_resume(request: dict[str, Any], workspace: Path) -> list[dict[str, str]]:
    source = Path(request["resume_from"])
    previous = json.loads((source / "worker_request.json").read_text())
    if _sha256(Path(previous["query_h5ad"])) != _sha256(Path(request["query_h5ad"])):
        raise ValueError("SpatialAgent resume requires the identical query input.")
    for key in ("model", "source_revision", "task_prompt_template"):
        if previous[key] != request[key]:
            raise ValueError(f"SpatialAgent resume changed {key}.")
    files = [source / "preprocessed.h5ad", source / "celltype_transferred.csv"]
    files.extend(sorted((source / "czi_reference").glob("*")))
    files.extend(sorted(source.glob("celltype-transferred_*.h5ad")))
    records = []
    for path in files:
        destination = workspace / path.relative_to(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        digest = _sha256(path)
        if _sha256(destination) != digest:
            raise ValueError(f"SpatialAgent resume copy differs: {path}")
        records.append({"source": str(path), "destination": str(destination), "sha256": digest})
    return records


def _write_agent_predictions(
    *,
    query_path: Path,
    annotated_path: Path,
    output_path: Path,
    method: str,
    prediction_column: str,
    confidence_column: str | None,
) -> dict[str, Any]:
    query = ad.read_h5ad(query_path, backed="r")
    try:
        query_index = pd.Index(query.obs_names.astype(str))
    finally:
        query.file.close()
    annotated = ad.read_h5ad(annotated_path, backed="r")
    try:
        if prediction_column not in annotated.obs:
            raise KeyError(
                f"{method} output lacks the required .obs['{prediction_column}'] column."
            )
        annotated_index = pd.Index(annotated.obs_names.astype(str))
        if not annotated_index.is_unique:
            raise ValueError(f"{method} output contains duplicate observation identifiers.")
        extra = annotated_index.difference(query_index)
        if len(extra):
            raise ValueError(
                f"{method} output contains {len(extra)} observations absent from the query."
            )
        ordered_index = query_index[query_index.isin(annotated_index)]
        output_order_preserved = annotated_index.equals(ordered_index)
        labels = annotated.obs[prediction_column].astype("string").copy()
        labels.index = annotated_index
        labels = labels.reindex(ordered_index)
        if confidence_column is None:
            confidence = pd.Series(np.nan, index=ordered_index, dtype=float)
        else:
            if confidence_column not in annotated.obs:
                raise KeyError(
                    f"{method} output lacks configured confidence column "
                    f".obs['{confidence_column}']."
                )
            confidence = pd.to_numeric(annotated.obs[confidence_column], errors="raise")
            confidence.index = annotated_index
            confidence = confidence.reindex(ordered_index)
    finally:
        annotated.file.close()

    frame = pd.DataFrame(
        {
            "raw_prediction": labels,
            "confidence": confidence,
            "method": method,
            "mapping_method": "gptcelltype",
        },
        index=ordered_index,
    )
    frame.index.name = "cell_id"
    frame.to_csv(output_path, sep="\t")
    return {
        "n_input_cells": len(query_index),
        "n_predictions": len(frame),
        "n_nonmissing_predictions": int(frame["raw_prediction"].notna().sum()),
        "prediction_row_coverage": float(len(frame) / len(query_index)),
        "upstream_observation_order_preserved": output_order_preserved,
        "prediction_column": prediction_column,
        "confidence_column": confidence_column,
    }


def _run_agent_baseline(
    prepared: dict[str, Any],
    *,
    method: str,
    model: str,
    request: dict[str, Any],
    python_executable: str,
    working_directory: Path,
    process_timeout_seconds: int,
    prediction_column: str,
    confidence_column: str | None,
) -> dict[str, Any]:
    output = _prediction_output(prepared, method)
    workspace = output.parent / method
    query_path = Path(request["query_h5ad"])
    query_sha256 = _sha256(query_path)
    annotated_path = Path(request["annotated_h5ad"])
    run_path = output.with_suffix(".run.json")
    try:
        worker_result = _execute_agent_worker(
            method,
            request,
            python_executable=python_executable,
            workspace=workspace,
            working_directory=working_directory,
            timeout_seconds=process_timeout_seconds,
        )
        if _sha256(query_path) != query_sha256:
            raise RuntimeError(f"{method} mutated the selection-blind query input.")
        if not annotated_path.exists():
            raise FileNotFoundError(
                f"{method} completed without producing the required output: {annotated_path}"
            )
        prediction_audit = _write_agent_predictions(
            query_path=query_path,
            annotated_path=annotated_path,
            output_path=output,
            method=method,
            prediction_column=prediction_column,
            confidence_column=confidence_column,
        )
    except Exception as error:
        failure = {
            "status": "error",
            "method": method,
            "model": model,
            "error_type": type(error).__name__,
            "message": str(error),
            "workspace": str(workspace.relative_to(REPO_ROOT)),
            "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        run_path.write_text(json.dumps(failure, indent=2), encoding="utf-8")
        raise

    metadata = {
        "status": "success",
        "method": method,
        "version": worker_result.get("version"),
        "model": model,
        "worker_python": python_executable,
        "process_timeout_seconds": process_timeout_seconds,
        "query_sha256": query_sha256,
        **prediction_audit,
        "prompt_sha256": hashlib.sha256(request["prompt"].encode("utf-8")).hexdigest(),
        "output_path": str(output.relative_to(REPO_ROOT)),
        "annotated_h5ad": str(annotated_path.relative_to(REPO_ROOT)),
        "annotated_h5ad_sha256": _sha256(annotated_path),
        "worker_request_path": str((workspace / "worker_request.json").relative_to(REPO_ROOT)),
        "worker_request_sha256": _sha256(workspace / "worker_request.json"),
        "worker_result_path": str((workspace / "worker_result.json").relative_to(REPO_ROOT)),
        "worker_result_sha256": _sha256(workspace / "worker_result.json"),
        "worker_stdout_path": str((workspace / "worker_stdout.log").relative_to(REPO_ROOT)),
        "worker_stderr_path": str((workspace / "worker_stderr.log").relative_to(REPO_ROOT)),
        "data_sent_to_provider": "agent-selected context derived from the selection-blind query",
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    for key in (
        "source",
        "source_revision",
        "use_azure",
        "use_local_embeddings",
        "embedding_cache_path",
        "resume_from",
        "resumed_artifacts",
        "task_prompt_template",
        "task_prompt",
    ):
        if key in request:
            metadata[key] = request[key]
    if "query_preprocessing" in worker_result:
        metadata["query_preprocessing"] = worker_result["query_preprocessing"]
    if "harmony_compatibility" in worker_result:
        metadata["harmony_compatibility"] = worker_result["harmony_compatibility"]
    if "h5ad_compatibility" in worker_result:
        metadata["h5ad_compatibility"] = worker_result["h5ad_compatibility"]
    if "llm_output_normalization" in worker_result:
        metadata["llm_output_normalization"] = worker_result["llm_output_normalization"]
    if "runtime_dependencies" in worker_result:
        metadata["runtime_dependencies"] = worker_result["runtime_dependencies"]
        metadata["pythonpath"] = worker_result["pythonpath"]
    run_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def run_biomni(
    prepared: dict[str, Any] | str | Path,
    *,
    model: str | None = None,
    source: str | None = None,
    python_executable: str | Path | None = None,
    process_timeout_seconds: int = 21_600,
    task_prompt_template: str | None = None,
    execution_timeout_seconds: int | None = None,
) -> dict[str, Any]:
    """Execute the upstream Biomni agent and adapt its output for benchmark scoring."""
    prepared = _load_prepared(prepared)
    manifest = load_manifest(prepared["dataset_id"])
    config = manifest["baselines"]["biomni"]
    selected_model = model or config["model"]
    selected_source = source or config.get("source")
    selected_python = str(python_executable or os.environ.get("BIOMNI_PYTHON") or sys.executable)
    output = _prediction_output(prepared, "biomni")
    annotated_path = output.parent / "biomni" / "annotated.h5ad"
    query_path = (REPO_ROOT / prepared["query_h5ad"]).resolve()
    prompt = _biomni_prompt(
        query_path, annotated_path.resolve(), manifest, selected_model, task_prompt_template
    )
    data_lake_path = DATA_DIR / "cache" / "biomni" / "biomni_data" / "data_lake"
    request = {
        "query_h5ad": str(query_path),
        "annotated_h5ad": str(annotated_path.resolve()),
        "prompt": prompt,
        "task_prompt": _agent_task_prompt(
            query_path, annotated_path.resolve(), manifest, task_prompt_template
        ),
        "task_prompt_template": task_prompt_template,
        "model": selected_model,
        "source": selected_source,
        "data_path": str((DATA_DIR / "cache" / "biomni").resolve()),
        "data_lake_path": str(data_lake_path.resolve()),
        "agent_timeout_seconds": execution_timeout_seconds
        or int(config.get("agent_timeout_seconds", 1_800)),
        "use_tool_retriever": bool(config.get("use_tool_retriever", True)),
        "commercial_mode": bool(config.get("commercial_mode", False)),
        "expected_version": config.get("expected_version"),
        "expected_data_lake_files": config.get(
            "expected_data_lake_files", ["czi_census_datasets_v4.parquet"]
        ),
    }
    return _run_agent_baseline(
        prepared,
        method="biomni",
        model=selected_model,
        request=request,
        python_executable=selected_python,
        working_directory=annotated_path.parent,
        process_timeout_seconds=process_timeout_seconds,
        prediction_column=config.get("prediction_column", "cell_type"),
        confidence_column=config.get("confidence_column"),
    )


def run_spatialagent(
    prepared: dict[str, Any] | str | Path,
    *,
    model: str | None = None,
    source_path: str | Path | None = None,
    python_executable: str | Path | None = None,
    process_timeout_seconds: int = 21_600,
    resume_from: str | Path | None = None,
    task_prompt_template: str | None = None,
    execution_timeout_seconds: int | None = None,
) -> dict[str, Any]:
    """Execute the upstream SpatialAgent and adapt its output for benchmark scoring."""
    prepared = _load_prepared(prepared)
    manifest = load_manifest(prepared["dataset_id"])
    config = manifest["baselines"]["spatialagent"]
    selected_model = model or config["model"]
    selected_python = str(
        python_executable or os.environ.get("SPATIALAGENT_PYTHON") or sys.executable
    )
    configured_source = source_path or os.environ.get("SPATIALAGENT_REPO")
    if configured_source is None:
        raise RuntimeError(
            "SpatialAgent source is required; pass source_path or set SPATIALAGENT_REPO."
        )
    resolved_source = Path(configured_source).expanduser().resolve()
    if not (resolved_source / "spatialagent" / "agent" / "spatialagent.py").is_file():
        raise FileNotFoundError(f"Invalid SpatialAgent repository: {resolved_source}")
    source_revision = _git_revision(resolved_source)
    expected_revision = config.get("source_revision")
    if expected_revision is not None and source_revision != expected_revision:
        raise RuntimeError(
            f"SpatialAgent revision {expected_revision} is required; found {source_revision}."
        )
    output = _prediction_output(prepared, "spatialagent")
    annotated_path = output.parent / "spatialagent" / "celltype_annotated.h5ad"
    query_path = (REPO_ROOT / prepared["query_h5ad"]).resolve()
    prompt = _spatialagent_prompt(
        query_path, annotated_path.resolve(), manifest, selected_model, task_prompt_template
    )
    request = {
        "query_h5ad": str(query_path),
        "annotated_h5ad": str(annotated_path.resolve()),
        "prompt": prompt,
        "task_prompt": _agent_task_prompt(
            query_path, annotated_path.resolve(), manifest, task_prompt_template
        ),
        "task_prompt_template": task_prompt_template,
        "model": selected_model,
        "source_path": str(resolved_source),
        "source_revision": source_revision,
        "use_azure": bool(config.get("use_azure", False)),
        "use_local_embeddings": bool(config.get("use_local_embeddings", True)),
        "embedding_cache_path": str(
            (DATA_DIR / "cache" / "spatialagent" / "embedding_cache").resolve()
        ),
        "data_path": str((resolved_source / "data").resolve()),
        "save_path": str(annotated_path.parent.resolve()),
        "tool_retrieval": bool(config.get("tool_retrieval", True)),
        "tool_retrieval_method": config.get("tool_retrieval_method", "llm"),
        "skill_retrieval": bool(config.get("skill_retrieval", True)),
        "act_timeout_seconds": execution_timeout_seconds
        or int(config.get("act_timeout_seconds", 1_800)),
        "recursion_limit": int(config.get("recursion_limit", 50)),
    }
    if resume_from is not None:
        request["resume_from"] = str(Path(resume_from).resolve())
        request["prompt"] += (
            "\nResume the previous native workflow: preprocessing, reference acquisition and "
            "Harmony label transfer have already completed on this identical query. Their "
            "verified artifacts are copied into save_path. Reuse preprocessed.h5ad and "
            "celltype_transferred.csv there and execute annotate_cell_types with resolution=0, "
            "then verify the saved celltype_annotated.h5ad. The previous execution stopped before "
            "annotation finished; this run gives annotation a fresh full execution budget. "
            "Do not redo the completed preprocessing, "
            "reference search, download or label-transfer steps."
        )
    return _run_agent_baseline(
        prepared,
        method="spatialagent",
        model=selected_model,
        request=request,
        python_executable=selected_python,
        working_directory=resolved_source,
        process_timeout_seconds=process_timeout_seconds,
        prediction_column=config.get("prediction_column", "cell_type"),
        confidence_column=config.get("confidence_column"),
    )


def run_celltypist(
    prepared: dict[str, Any] | str | Path,
    majority_voting: bool = True,
    n_jobs: int = 1,
) -> dict[str, Any]:
    """Execute CellTypist directly using the dataset's declared model strategy."""
    version = _require_version("celltypist")
    import celltypist
    from celltypist import models

    prepared = _load_prepared(prepared)
    manifest = load_manifest(prepared["dataset_id"])
    config = manifest["baselines"]["celltypist"]
    query = ad.read_h5ad(REPO_ROOT / prepared["query_h5ad"])
    normalized_query, query_preprocessing = _prepare_log1p(query)

    if config["mode"] == "builtin":
        model_name = config["model"]
        celltypist_cache = DATA_DIR / "cache" / "celltypist"
        model_dir = celltypist_cache / "data" / "models"
        model_dir.mkdir(parents=True, exist_ok=True)
        models.celltypist_path = str(celltypist_cache)
        models.data_path = str(celltypist_cache / "data")
        models.models_path = str(model_dir)
        model_path = model_dir / model_name
        if not model_path.exists():
            models.download_models(force_update=False, model=model_name)
        if not model_path.exists():
            raise FileNotFoundError(f"CellTypist did not produce requested model: {model_path}")
        model_sha256 = _sha256(model_path)
        expected_model_sha256 = config.get("model_sha256")
        if expected_model_sha256 and model_sha256 != expected_model_sha256:
            raise ValueError(f"CellTypist model SHA-256 changed: {model_path}")
        model = models.Model.load(str(model_path))
        model_description = model_name
    elif config["mode"] == "train_reference":
        reference = ad.read_h5ad(REPO_ROOT / prepared["reference_h5ad"])
        label_column = config["label_column"]
        if label_column not in reference.obs:
            raise KeyError(f"CellTypist training reference lacks .obs['{label_column}'].")
        if reference.obs[label_column].isna().any():
            raise ValueError(f"CellTypist training labels contain missing values: {label_column}")
        normalized_reference, reference_preprocessing = _prepare_log1p(reference)
        model = celltypist.train(
            normalized_reference,
            labels=label_column,
            n_jobs=n_jobs,
            use_SGD=normalized_reference.n_obs > 100_000,
            feature_selection=True,
        )
        model_description = f"trained_from:{prepared['reference_h5ad']}:{label_column}"
        model_sha256 = None
    else:
        raise ValueError(f"Unsupported CellTypist mode '{config['mode']}'.")

    model_features = pd.Index(np.asarray(model.features).astype(str))
    canonical_by_casefold = {feature.casefold(): feature for feature in model_features}
    original_query_names = pd.Index(normalized_query.var_names.astype(str))
    aligned_query_names = pd.Index(
        [canonical_by_casefold.get(name.casefold(), name) for name in original_query_names]
    )
    normalized_query.var["celltypist_original_gene_name"] = original_query_names
    normalized_query.var_names = aligned_query_names
    if not normalized_query.var_names.is_unique:
        raise ValueError(
            "CellTypist model-derived gene case alignment created duplicate query genes."
        )
    matched_features = normalized_query.var_names.intersection(model_features)
    if len(matched_features) < 10:
        raise ValueError(
            f"Only {len(matched_features)} query genes match the CellTypist model; "
            "at least 10 are required for a valid baseline run."
        )

    removed_input_graph = {
        "obsm": sorted(str(key) for key in normalized_query.obsm),
        "obsp": sorted(str(key) for key in normalized_query.obsp),
        "neighbors_uns": "neighbors" in normalized_query.uns,
    }
    if majority_voting:
        normalized_query.obsm.clear()
        normalized_query.obsp.clear()
        normalized_query.uns.pop("neighbors", None)
    predictions = celltypist.annotate(
        normalized_query,
        model=model,
        majority_voting=majority_voting,
    )
    label_frame = predictions.predicted_labels
    preferred_column = (
        "majority_voting"
        if majority_voting and "majority_voting" in label_frame
        else "predicted_labels"
    )
    raw_labels = label_frame[preferred_column].astype(str).reindex(query.obs_names)
    probability = predictions.probability_matrix.reindex(query.obs_names)
    confidence = probability.max(axis=1)
    if raw_labels.isna().any():
        missing_count = int(raw_labels.isna().sum())
        raise RuntimeError(f"CellTypist returned {missing_count} missing predictions.")

    output = _prediction_output(prepared, "celltypist")
    frame = pd.DataFrame(
        {
            "cell_id": query.obs_names,
            "raw_prediction": raw_labels.to_numpy(),
            "confidence": confidence.to_numpy(dtype=float),
            "method": "celltypist",
        }
    ).set_index("cell_id")
    frame.to_csv(output, sep="\t")
    metadata = {
        "status": "success",
        "method": "celltypist",
        "version": version,
        "model": model_description,
        "model_sha256": model_sha256,
        "n_model_features_matched": len(matched_features),
        "n_query_gene_names_case_aligned": int((original_query_names != aligned_query_names).sum()),
        "majority_voting": majority_voting,
        "majority_voting_graph": (
            "celltypist_transcriptomic_over_clustering" if majority_voting else None
        ),
        "removed_input_graph": removed_input_graph,
        "query_preprocessing": query_preprocessing,
        "reference_preprocessing": (
            reference_preprocessing if config["mode"] == "train_reference" else None
        ),
        "n_predictions": len(frame),
        "output_path": str(output.relative_to(REPO_ROOT)),
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    output.with_suffix(".run.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def _marker_dictionary(
    dataset: ad.AnnData,
    group_key: str,
    top_n: int = 20,
) -> dict[str, list[str]]:
    result = dataset.uns["rank_genes_groups"]
    names = result["names"]
    groups = list(names.dtype.names or [])
    if not groups:
        raise ValueError("rank_genes_groups did not return named cluster fields.")
    return {
        str(group): [str(gene) for gene in names[group][:top_n] if str(gene) not in {"", "nan"}]
        for group in groups
    }


def _rank_gptcelltype_markers(
    working: ad.AnnData,
    group_key: str,
    *,
    top_marker_genes: int,
    max_cells_per_cluster: int | None,
    max_cells_total: int | None,
    random_seed: int,
) -> tuple[dict[str, list[str]], dict[str, Any]]:
    assignments = working.obs[group_key].astype(str)
    cluster_counts = assignments.value_counts().sort_index()
    selected_positions = np.arange(working.n_obs, dtype=np.int64)
    effective_cluster_cap: int | None = None
    strategy = "all_cells_full_gene_wilcoxon"
    if max_cells_total is not None and max_cells_per_cluster is None:
        raise ValueError("max_cells_total requires max_cells_per_cluster.")
    if max_cells_per_cluster is not None:
        if max_cells_per_cluster < 1:
            raise ValueError("max_cells_per_cluster must be positive when configured.")
        if max_cells_total is not None and max_cells_total < len(cluster_counts):
            raise ValueError("max_cells_total must allow at least one cell per cluster.")
        effective_cluster_cap = max_cells_per_cluster
        if max_cells_total is not None:
            effective_cluster_cap = min(
                effective_cluster_cap,
                max_cells_total // len(cluster_counts),
            )
        rng = np.random.default_rng(random_seed)
        cluster_values = assignments.to_numpy()
        selected = []
        for cluster in cluster_counts.index:
            positions = np.flatnonzero(cluster_values == cluster)
            if len(positions) > effective_cluster_cap:
                positions = rng.choice(
                    positions,
                    size=effective_cluster_cap,
                    replace=False,
                )
            selected.append(positions)
        selected_positions = np.sort(np.concatenate(selected).astype(np.int64, copy=False))
        strategy = "cluster_balanced_sample_full_gene_wilcoxon"

    marker_view = (
        working if len(selected_positions) == working.n_obs else working[selected_positions].copy()
    )
    sc.tl.rank_genes_groups(
        marker_view,
        group_key,
        method="wilcoxon",
        n_genes=top_marker_genes,
        use_raw=False,
    )
    markers = _marker_dictionary(marker_view, group_key, top_n=top_marker_genes)
    selected_assignments = marker_view.obs[group_key].astype(str)
    selected_counts = selected_assignments.value_counts().sort_index()
    digest = hashlib.sha256()
    for cell_id in marker_view.obs_names.astype(str):
        digest.update(cell_id.encode("utf-8"))
        digest.update(b"\0")
    audit = {
        "marker_ranking_strategy": strategy,
        "marker_ranking_method": "wilcoxon",
        "marker_ranking_gene_scope": "all_query_genes",
        "marker_ranking_source_cells": working.n_obs,
        "marker_ranking_cells": marker_view.n_obs,
        "marker_ranking_source_cluster_counts": {
            str(cluster): int(count) for cluster, count in cluster_counts.items()
        },
        "marker_ranking_selected_cluster_counts": {
            str(cluster): int(count) for cluster, count in selected_counts.items()
        },
        "marker_ranking_requested_max_cells_per_cluster": max_cells_per_cluster,
        "marker_ranking_effective_max_cells_per_cluster": effective_cluster_cap,
        "marker_ranking_max_cells_total": max_cells_total,
        "marker_ranking_random_seed": random_seed,
        "marker_ranking_selected_cell_ids_sha256": digest.hexdigest(),
        "all_cells_used_for_clustering_and_final_predictions": True,
        "marker_sampling_uses_query_annotations_or_spatial_metadata": False,
    }
    return markers, audit


def _gptcelltype_marker_audit(
    markers: dict[str, list[str]],
    cluster_assignments: pd.Series,
    *,
    requested_top_marker_genes: int,
) -> dict[str, Any]:
    if requested_top_marker_genes < 1:
        raise ValueError("top_marker_genes must be positive.")
    assignments = cluster_assignments.astype(str)
    cluster_counts = assignments.value_counts(sort=False)
    assignment_clusters = set(cluster_counts.index.astype(str))
    marker_clusters = set(markers)
    if assignment_clusters != marker_clusters:
        raise RuntimeError(
            "GPTCellType marker and cluster assignments disagree: "
            f"markers_only={sorted(marker_clusters - assignment_clusters)}, "
            f"assignments_only={sorted(assignment_clusters - marker_clusters)}."
        )
    effective_top_marker_genes = min(
        requested_top_marker_genes,
        GPTCELLTYPE_NATIVE_MAX_MARKER_GENES,
    )
    return {
        "requested_top_marker_genes": requested_top_marker_genes,
        "native_provider_max_marker_genes": GPTCELLTYPE_NATIVE_MAX_MARKER_GENES,
        "effective_provider_top_marker_genes": effective_top_marker_genes,
        "effective_provider_marker_genes_by_cluster": {
            cluster: min(len(genes), effective_top_marker_genes)
            for cluster, genes in markers.items()
        },
        "cluster_sizes": {cluster: int(cluster_counts.loc[cluster]) for cluster in markers},
    }


def prepare_gptcelltype_markers(
    prepared: dict[str, Any] | str | Path,
    resolution: float = 1.0,
    top_marker_genes: int = 20,
    max_marker_cells_per_cluster: int | None = None,
    max_marker_cells_total: int | None = None,
    marker_sampling_random_seed: int | None = None,
) -> dict[str, Any]:
    """Prepare the exact transcriptomic clusters and marker lists without calling an LLM."""
    version = _require_version("omicverse")
    prepared = _load_prepared(prepared)
    manifest = load_manifest(prepared["dataset_id"])
    config = manifest["baselines"]["gptcelltype"]
    query = ad.read_h5ad(REPO_ROOT / prepared["query_h5ad"])
    working, query_preprocessing = _prepare_log1p(query)
    if working.n_obs < 3 or working.n_vars < 3:
        raise ValueError("GPTCellType requires at least three cells and three genes.")

    n_top_genes = min(2_000, working.n_vars)
    clustering = working
    if n_top_genes < working.n_vars:
        sc.pp.highly_variable_genes(working, n_top_genes=n_top_genes, flavor="seurat")
        clustering = working[:, working.var["highly_variable"]].copy()
    n_pcs = min(50, clustering.n_obs - 1, clustering.n_vars - 1)
    sc.pp.pca(clustering, n_comps=n_pcs)
    sc.pp.neighbors(
        clustering,
        n_neighbors=min(15, clustering.n_obs - 1),
        n_pcs=n_pcs,
    )
    sc.tl.leiden(
        clustering,
        key_added="gptcelltype_cluster",
        resolution=resolution,
        random_state=42,
    )
    working.obs["gptcelltype_cluster"] = clustering.obs["gptcelltype_cluster"].copy()
    max_marker_cells_per_cluster = (
        max_marker_cells_per_cluster
        if max_marker_cells_per_cluster is not None
        else config.get("max_marker_cells_per_cluster")
    )
    max_marker_cells_total = (
        max_marker_cells_total
        if max_marker_cells_total is not None
        else config.get("max_marker_cells_total")
    )
    marker_sampling_random_seed = (
        marker_sampling_random_seed
        if marker_sampling_random_seed is not None
        else int(config.get("marker_sampling_random_seed", 42))
    )
    markers, marker_ranking_audit = _rank_gptcelltype_markers(
        working,
        "gptcelltype_cluster",
        top_marker_genes=top_marker_genes,
        max_cells_per_cluster=max_marker_cells_per_cluster,
        max_cells_total=max_marker_cells_total,
        random_seed=marker_sampling_random_seed,
    )
    cluster_assignments = working.obs["gptcelltype_cluster"].astype(str)
    marker_audit = _gptcelltype_marker_audit(
        markers,
        cluster_assignments,
        requested_top_marker_genes=top_marker_genes,
    )

    output = _prediction_output(prepared, "gptcelltype")
    markers_path = output.with_suffix(".markers.json")
    clusters_path = output.with_suffix(".cluster_assignments.tsv")
    if output.exists() or markers_path.exists() or clusters_path.exists():
        raise FileExistsError("GPTCellType marker or prediction artifacts already exist.")
    markers_path.write_text(
        json.dumps(
            {
                "markers": markers,
                "labels": {},
                "species": config["species_name"],
                "tissue": config["tissue_name"],
                **marker_ranking_audit,
                **marker_audit,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    pd.DataFrame(
        {"cluster": cluster_assignments},
        index=working.obs_names,
    ).to_csv(clusters_path, sep="\t")
    metadata = {
        "status": "markers_ready",
        "method": "gptcelltype",
        "version": version,
        "configured_model": config["model"],
        "n_clusters": len(markers),
        "resolution": resolution,
        **marker_ranking_audit,
        **marker_audit,
        "query_preprocessing": query_preprocessing,
        "markers_path": str(markers_path.relative_to(REPO_ROOT)),
        "cluster_assignments_path": str(clusters_path.relative_to(REPO_ROOT)),
        "data_sent_to_provider": "none",
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    output.with_suffix(".run.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def complete_gptcelltype_from_cluster_labels(
    prepared: dict[str, Any] | str | Path,
    cluster_labels: dict[str, str],
    *,
    label_provider: str,
) -> dict[str, Any]:
    """Map independently generated marker-only labels back to every query observation."""
    prepared = _load_prepared(prepared)
    manifest = load_manifest(prepared["dataset_id"])
    config = manifest["baselines"]["gptcelltype"]
    output = _prediction_output(prepared, "gptcelltype")
    markers_path = output.with_suffix(".markers.json")
    assignments_path = output.with_suffix(".cluster_assignments.tsv")
    payload = json.loads(markers_path.read_text(encoding="utf-8"))
    markers = payload["markers"]
    missing = sorted(set(markers).difference(cluster_labels))
    extra = sorted(set(cluster_labels).difference(markers))
    if missing or extra:
        raise ValueError(f"Cluster labels mismatch: missing={missing}, extra={extra}.")
    cleaned = {str(key): str(value).strip() for key, value in cluster_labels.items()}
    if any(not value for value in cleaned.values()):
        raise ValueError("GPTCellType cluster labels must be non-empty.")
    assignments = pd.read_csv(assignments_path, sep="\t", index_col=0)
    assignments.index = assignments.index.astype(str)
    cluster_assignments = assignments["cluster"].astype(str)
    requested_top_marker_genes = int(
        payload.get(
            "requested_top_marker_genes",
            max((len(genes) for genes in markers.values()), default=1),
        )
    )
    marker_audit = _gptcelltype_marker_audit(
        markers,
        cluster_assignments,
        requested_top_marker_genes=requested_top_marker_genes,
    )
    raw_predictions = cluster_assignments.map(cleaned)
    if raw_predictions.isna().any():
        raise RuntimeError("One or more GPTCellType clusters lack a label.")

    pd.DataFrame(
        {
            "raw_prediction": raw_predictions,
            "confidence": np.nan,
            "method": "gptcelltype",
        },
        index=assignments.index,
    ).to_csv(output, sep="\t")
    clusters_path = output.with_suffix(".clusters.json")
    clusters_path.write_text(
        json.dumps(
            {
                "markers": markers,
                "labels": cleaned,
                **marker_audit,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    version = _require_version("omicverse")
    metadata = {
        "status": "success",
        "method": "gptcelltype",
        "version": version,
        "configured_model": config["model"],
        "label_provider": label_provider,
        "remote_configured_model_executed": False,
        "n_clusters": len(markers),
        "n_predictions": len(assignments),
        **marker_audit,
        "output_path": str(output.relative_to(REPO_ROOT)),
        "clusters_path": str(clusters_path.relative_to(REPO_ROOT)),
        "cluster_assignments_path": str(assignments_path.relative_to(REPO_ROOT)),
        "data_sent_to_provider": "cluster marker gene names only",
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    output.with_suffix(".run.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def _run_gptcelltype_batch(
    ov: Any,
    markers: dict[str, list[str]],
    config: dict[str, Any],
    *,
    max_api_attempts: int,
    timeout_seconds: int,
    provider_top_marker_genes: int = GPTCELLTYPE_NATIVE_MAX_MARKER_GENES,
    prompt_records: list[dict[str, Any]] | None = None,
    api_batch_index: int | None = None,
) -> tuple[dict[str, str], int]:
    """Call OmicVerse GPTCellType with bounded retries and formatting normalization."""
    import openai

    if not 1 <= provider_top_marker_genes <= GPTCELLTYPE_NATIVE_MAX_MARKER_GENES:
        raise ValueError(
            "provider_top_marker_genes must be between 1 and "
            f"{GPTCELLTYPE_NATIVE_MAX_MARKER_GENES}."
        )
    real_openai = openai.OpenAI
    api_calls = 0

    class BoundedCompletions:
        def __init__(self, completions: Any) -> None:
            self._completions = completions

        def create(self, *args: Any, **kwargs: Any) -> Any:
            nonlocal api_calls
            if api_calls >= max_api_attempts:
                raise RuntimeError(
                    "GPTCellType did not return exactly one label per cluster after "
                    f"{max_api_attempts} API attempts."
                )
            api_calls += 1
            kwargs.setdefault("timeout", timeout_seconds)
            prompt = kwargs.get("messages", [{}])[-1].get("content", "")
            if prompt_records is not None:
                prompt_records.append(
                    {
                        "api_call_index": api_calls,
                        "api_batch_index": api_batch_index,
                        "model": kwargs.get("model"),
                        "cluster_ids": list(markers),
                        "effective_marker_genes_by_cluster": {
                            cluster: min(len(genes), provider_top_marker_genes)
                            for cluster, genes in markers.items()
                        },
                        "exact_user_prompt": prompt,
                        "exact_user_prompt_sha256": hashlib.sha256(
                            prompt.encode("utf-8")
                        ).hexdigest(),
                    }
                )
            response = self._completions.create(*args, **kwargs)
            content = response.choices[0].message.content or ""
            expected_lines = max(0, len(prompt.splitlines()) - 1)
            nonempty_lines = [line.strip() for line in content.splitlines() if line.strip()]
            if len(nonempty_lines) == expected_lines:
                cleaned = [
                    re.sub(r"^(?:[-*\u2022]|\d+[.)-])\s*", "", line).strip()
                    for line in nonempty_lines
                ]
                response.choices[0].message.content = "\n".join(cleaned)
            return response

    class BoundedOpenAI:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            if not kwargs.get("api_key"):
                kwargs["api_key"] = os.environ["OPENAI_API_KEY"]
            client = real_openai(*args, **kwargs)
            self.chat = type("BoundedChat", (), {})()
            self.chat.completions = BoundedCompletions(client.chat.completions)

    openai.OpenAI = BoundedOpenAI
    try:
        labels = ov.single.gptcelltype(
            markers,
            tissuename=config["tissue_name"],
            speciename=config["species_name"],
            model=config["model"],
            provider="openai",
            topgenenumber=provider_top_marker_genes,
        )
    finally:
        openai.OpenAI = real_openai
    if not isinstance(labels, dict):
        raise RuntimeError("GPTCellType returned a prompt instead of a cluster-label dictionary.")
    return {str(key): str(value) for key, value in labels.items()}, api_calls


def run_gptcelltype(
    prepared: dict[str, Any] | str | Path,
    resolution: float = 1.0,
    top_marker_genes: int = 20,
    api_batch_size: int = 25,
    max_api_attempts_per_batch: int = 3,
    api_timeout_seconds: int = 120,
    max_marker_cells_per_cluster: int | None = None,
    max_marker_cells_total: int | None = None,
    marker_sampling_random_seed: int | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """Execute GPTCellType directly; only cluster marker names are sent to OpenAI."""
    version = _require_version("omicverse")
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not visible to this process.")
    import omicverse as ov

    prepared = _load_prepared(prepared)
    manifest = load_manifest(prepared["dataset_id"])
    config = dict(manifest["baselines"]["gptcelltype"])
    if model is not None:
        config["model"] = model
    query = ad.read_h5ad(REPO_ROOT / prepared["query_h5ad"])
    working, query_preprocessing = _prepare_log1p(query)
    if working.n_obs < 3 or working.n_vars < 3:
        raise ValueError("GPTCellType requires at least three cells and three genes.")

    n_top_genes = min(2_000, working.n_vars)
    clustering = working
    if n_top_genes < working.n_vars:
        sc.pp.highly_variable_genes(working, n_top_genes=n_top_genes, flavor="seurat")
        clustering = working[:, working.var["highly_variable"]].copy()
    n_pcs = min(50, clustering.n_obs - 1, clustering.n_vars - 1)
    sc.pp.pca(clustering, n_comps=n_pcs)
    sc.pp.neighbors(
        clustering,
        n_neighbors=min(15, clustering.n_obs - 1),
        n_pcs=n_pcs,
    )
    sc.tl.leiden(
        clustering,
        key_added="gptcelltype_cluster",
        resolution=resolution,
        random_state=42,
    )
    working.obs["gptcelltype_cluster"] = clustering.obs["gptcelltype_cluster"].copy()
    max_marker_cells_per_cluster = (
        max_marker_cells_per_cluster
        if max_marker_cells_per_cluster is not None
        else config.get("max_marker_cells_per_cluster")
    )
    max_marker_cells_total = (
        max_marker_cells_total
        if max_marker_cells_total is not None
        else config.get("max_marker_cells_total")
    )
    marker_sampling_random_seed = (
        marker_sampling_random_seed
        if marker_sampling_random_seed is not None
        else int(config.get("marker_sampling_random_seed", 42))
    )
    markers, marker_ranking_audit = _rank_gptcelltype_markers(
        working,
        "gptcelltype_cluster",
        top_marker_genes=top_marker_genes,
        max_cells_per_cluster=max_marker_cells_per_cluster,
        max_cells_total=max_marker_cells_total,
        random_seed=marker_sampling_random_seed,
    )
    cluster_assignments = working.obs["gptcelltype_cluster"].astype(str)
    marker_audit = _gptcelltype_marker_audit(
        markers,
        cluster_assignments,
        requested_top_marker_genes=top_marker_genes,
    )
    effective_provider_top_marker_genes = marker_audit["effective_provider_top_marker_genes"]
    if api_batch_size < 1 or api_batch_size > 29:
        raise ValueError("api_batch_size must be between 1 and 29.")
    if max_api_attempts_per_batch < 1:
        raise ValueError("max_api_attempts_per_batch must be positive.")

    output = _prediction_output(prepared, "gptcelltype")
    markers_path = output.with_suffix(".markers.json")
    assignments_path = output.with_suffix(".cluster_assignments.tsv")
    prompts_path = output.with_suffix(".prompts.json")
    markers_path.write_text(
        json.dumps(
            {
                "markers": markers,
                "labels": {},
                **marker_ranking_audit,
                **marker_audit,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    pd.DataFrame(
        {"cluster": cluster_assignments},
        index=working.obs_names,
    ).to_csv(assignments_path, sep="\t")
    marker_items = list(markers.items())
    cluster_labels: dict[str, str] = {}
    prompt_records: list[dict[str, Any]] = []
    api_calls = 0
    api_batches = 0
    try:
        for start in range(0, len(marker_items), api_batch_size):
            batch = dict(marker_items[start : start + api_batch_size])
            batch_labels, batch_calls = _run_gptcelltype_batch(
                ov,
                batch,
                config,
                max_api_attempts=max_api_attempts_per_batch,
                timeout_seconds=api_timeout_seconds,
                provider_top_marker_genes=effective_provider_top_marker_genes,
                prompt_records=prompt_records,
                api_batch_index=api_batches + 1,
            )
            cluster_labels.update(batch_labels)
            api_calls += batch_calls
            api_batches += 1
    except Exception as error:
        prompts_path.write_text(
            json.dumps(
                {
                    "status": "error",
                    "prompt_hash_algorithm": "sha256_utf8",
                    "records": prompt_records,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        failure = {
            "status": "error",
            "method": "gptcelltype",
            "version": version,
            "model": config["model"],
            "stage": "remote_cluster_annotation",
            "error_type": type(error).__name__,
            "message": str(error),
            "n_clusters": len(markers),
            "api_batch_size": api_batch_size,
            "api_batches_completed": api_batches,
            "api_calls_completed": api_calls,
            **marker_ranking_audit,
            **marker_audit,
            "markers_path": str(markers_path.relative_to(REPO_ROOT)),
            "cluster_assignments_path": str(assignments_path.relative_to(REPO_ROOT)),
            "prompts_path": str(prompts_path.relative_to(REPO_ROOT)),
            "data_sent_to_provider": "cluster marker gene names only",
            "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        output.with_suffix(".run.json").write_text(
            json.dumps(failure, indent=2),
            encoding="utf-8",
        )
        raise
    prompts_path.write_text(
        json.dumps(
            {
                "status": "success",
                "prompt_hash_algorithm": "sha256_utf8",
                "records": prompt_records,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    missing_clusters = sorted(set(markers).difference(cluster_labels))
    if missing_clusters:
        raise RuntimeError("GPTCellType omitted clusters: " + ", ".join(missing_clusters))
    raw_predictions = cluster_assignments.map(cluster_labels)
    if raw_predictions.isna().any():
        missing_count = int(raw_predictions.isna().sum())
        raise RuntimeError(f"GPTCellType returned {missing_count} missing predictions.")

    frame = pd.DataFrame(
        {
            "cell_id": working.obs_names,
            "raw_prediction": raw_predictions.to_numpy(),
            "confidence": np.nan,
            "method": "gptcelltype",
        }
    ).set_index("cell_id")
    frame.to_csv(output, sep="\t")
    clusters_path = output.with_suffix(".clusters.json")
    clusters_path.write_text(
        json.dumps(
            {
                "markers": markers,
                "labels": cluster_labels,
                **marker_ranking_audit,
                **marker_audit,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    metadata = {
        "status": "success",
        "method": "gptcelltype",
        "version": version,
        "model": config["model"],
        "n_clusters": len(markers),
        "resolution": resolution,
        **marker_ranking_audit,
        **marker_audit,
        "api_batch_size": api_batch_size,
        "api_batches": api_batches,
        "api_calls": api_calls,
        "max_api_attempts_per_batch": max_api_attempts_per_batch,
        "api_timeout_seconds": api_timeout_seconds,
        "n_predictions": len(frame),
        "query_preprocessing": query_preprocessing,
        "output_path": str(output.relative_to(REPO_ROOT)),
        "clusters_path": str(clusters_path.relative_to(REPO_ROOT)),
        "cluster_assignments_path": str(assignments_path.relative_to(REPO_ROOT)),
        "prompts_path": str(prompts_path.relative_to(REPO_ROOT)),
        "data_sent_to_provider": "cluster marker gene names only",
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    output.with_suffix(".run.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata
