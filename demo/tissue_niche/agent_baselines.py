"""Native agent runners for the named tissue-niche benchmark."""

from __future__ import annotations

import json
import hashlib
import os
import errno
import re
import shutil
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path

import anndata as ad
import pandas as pd

from .agent_inputs import ROOT
from .agent_collection import validate_annotation
from .protocol import (
    DEFAULT_MODEL,
    METHODS,
    PROMPT_VERSION,
    PROTOCOL,
    normalize_predictions,
    scientific_prompt,
    sha256,
    validate_query,
    write_json,
)


def safe_id(value: str) -> str:
    """Validate identifiers before using them as output directory components."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", value):
        raise ValueError(f"Invalid run identifier: {value!r}.")
    return value


def _link_artifact(source, destination):
    try:
        os.link(source, destination)
    except OSError as error:
        if error.errno != errno.EXDEV:
            raise
        shutil.copy2(source, destination)
    return str(destination)


def allocated_bytes(root: Path) -> int:
    """Count allocated file bytes once per inode, including hard-linked archives."""
    seen, total = set(), 0
    for directory, _, files in os.walk(root):
        for name in files:
            try:
                stat = (Path(directory) / name).stat()
            except FileNotFoundError:
                continue
            identity = (stat.st_dev, stat.st_ino)
            if identity not in seen:
                total += stat.st_blocks * 512
                seen.add(identity)
    return total


def _revision(path: Path) -> str:
    return subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()


def preflight(method: str, config: dict) -> dict:
    """Resolve runtime dependencies without launching agents or model requests."""
    if method not in METHODS:
        raise ValueError(f"Unknown method {method!r}.")
    settings = config.get(method, {})
    interpreter = settings.get("python_executable") or os.environ.get(f"{method.upper()}_PYTHON")
    if method == "tissueagent":
        interpreter = interpreter or sys.executable
    if not interpreter or not Path(interpreter).is_file():
        raise FileNotFoundError(f"Set {method.upper()}_PYTHON to the native Python executable.")
    result = {"python_executable": str(Path(interpreter).absolute())}
    if method == "spatialagent":
        source = settings.get("source_path") or os.environ.get("SPATIALAGENT_REPO")
        if not source or not (Path(source) / "spatialagent/agent/spatialagent.py").is_file():
            raise FileNotFoundError("Set SPATIALAGENT_REPO to the pinned upstream checkout.")
        result["source_path"] = str(Path(source).resolve())
        result["source_revision"] = _revision(Path(source))
        if result["source_revision"] != settings["source_revision"]:
            raise ValueError("SpatialAgent checkout differs from the configured pinned revision.")
        changed = subprocess.check_output(
            ["git", "-C", source, "status", "--porcelain", "--", "spatialagent"], text=True
        ).strip()
        if changed:
            raise ValueError("SpatialAgent package has uncommitted changes; use the pinned source.")
    package = "biomni" if method == "biomni" else "langgraph"
    version = subprocess.check_output(
        [interpreter, "-c", f"import importlib.metadata as m; print(m.version('{package}'))"],
        text=True,
    ).strip()
    if method == "biomni" and version != settings["expected_version"]:
        raise ValueError(f"Expected Biomni {settings['expected_version']}; found {version}.")
    result["package_version"] = version
    return result


def _stage_tissueagent(runtime: Path) -> Path:
    destination = runtime / "tissueagent"
    ignore = shutil.ignore_patterns("frontend", "__pycache__", "*.pyc", ".git", "node_modules")
    for name in ("src", "knowledge"):
        shutil.copytree(ROOT / name, destination / name, ignore=ignore)
    return destination


def _source_snapshot_hash(source: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(source.rglob("*")):
        if path.is_file() and path.suffix in {".py", ".md", ".json", ".yaml", ".yml", ".txt"}:
            digest.update(str(path.relative_to(source)).encode())
            digest.update(bytes.fromhex(sha256(path)))
    return digest.hexdigest()


def _execute_worker(request: dict, runtime: Path, executable: str, timeout: int) -> dict:
    worker = runtime / "agent_baseline_worker.py"
    shutil.copy2(Path(__file__).with_name(worker.name), worker)
    request_path, result_path = runtime / "worker_request.json", runtime / "worker_result.json"
    write_json(request_path, request)
    environment = os.environ.copy()
    environment["PATH"] = str(Path(executable).parent) + os.pathsep + environment.get("PATH", "")
    environment["PYTHONHASHSEED"] = str(request["seed"])
    environment["TMPDIR"] = str(runtime / "tmp")
    environment["MPLCONFIGDIR"] = str(runtime / "cache/matplotlib")
    environment["NUMBA_CACHE_DIR"] = str(runtime / "cache/numba")
    environment["XDG_CACHE_HOME"] = str(runtime / "cache")
    environment["JUPYTER_RUNTIME_DIR"] = str(runtime / "cache/jupyter/runtime")
    environment["JUPYTER_CONFIG_DIR"] = str(runtime / "cache/jupyter/config")
    environment["IPYTHONDIR"] = str(runtime / "cache/ipython")
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment.pop("PYTHONPATH", None)
    if pythonpath := os.environ.get(f"{request['method'].upper()}_PYTHONPATH"):
        environment["PYTHONPATH"] = pythonpath
    command = [
        executable,
        str(worker),
        "--request",
        str(request_path),
        "--result",
        str(result_path),
    ]
    with (runtime / "stdout.log").open("w") as stdout, (runtime / "stderr.log").open("w") as stderr:
        process = subprocess.Popen(
            command,
            cwd=runtime,
            env=environment,
            stdout=stdout,
            stderr=stderr,
            start_new_session=True,
        )
        try:
            deadline = time.monotonic() + timeout
            while process.poll() is None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(f"{request['method']} exceeded {timeout} seconds.")
                if budget := request.get("storage_budget"):
                    usage = allocated_bytes(Path(budget["root"]))
                    if usage >= budget["max_bytes"] or shutil.disk_usage(runtime).free < 4 * 10**9:
                        raise RuntimeError(f"Storage budget reached; allocated {usage} bytes.")
                try:
                    process.wait(timeout=min(10, remaining))
                except subprocess.TimeoutExpired:
                    pass
        except (TimeoutError, RuntimeError):
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            raise
    if not result_path.exists():
        raise RuntimeError(f"Worker exited {process.returncode} without a result; see stderr.log.")
    result = json.loads(result_path.read_text())
    if process.returncode or result["status"] != "success":
        raise RuntimeError(result.get("error", f"Worker exited {process.returncode}."))
    return result


def _collect_predictions(section: dict, runtime: Path, output: Path) -> dict:
    validate_annotation(section, runtime / "outputs/niche_annotated.h5ad")
    query = ad.read_h5ad(section["query_h5ad"], backed="r")
    try:
        ids = query.obs_names.copy()
    finally:
        query.file.close()
    raw = pd.read_csv(
        runtime / "outputs/raw_predictions.tsv", sep="\t", dtype="string", keep_default_na=False
    ).set_index("cell_id")
    if not raw.index.is_unique or not set(raw.index).issubset(ids):
        raise ValueError("Predictions contain duplicate or foreign cell IDs.")
    predictions = raw.reindex(ids)
    predictions["tissue_niche"] = normalize_predictions(
        predictions["raw_label"], section["contract"]["labels"]
    )
    predictions.index.name = "cell_id"
    predictions.to_csv(output / "predictions.tsv", sep="\t")
    missing = len(ids.difference(raw.index))
    abstentions = int((predictions["tissue_niche"] == "Unmatched").sum())
    return {
        "n_cells": len(ids),
        "n_missing_predictions": missing,
        "n_unmatched": abstentions,
        "annotation_outcome": "unassigned" if abstentions == len(ids) else "assigned",
        "predictions_sha256": sha256(output / "predictions.tsv"),
        "status": "partial" if missing else "success",
    }


def run_method(
    section: dict,
    *,
    method: str,
    output_dir: Path,
    config: dict,
    model: str = DEFAULT_MODEL,
    seed: int = 42,
) -> dict:
    """Run one method on one public section, preserving successful and failed attempts."""
    if output_dir.exists():
        raise FileExistsError(f"Run already exists: {output_dir}")
    runtime_config = preflight(method, config)
    validation = validate_query(Path(section["query_h5ad"]))
    if validation["query_sha256"] != section["query_sha256"]:
        raise ValueError("Prepared query was modified.")
    runtime = Path(config["runtime_root"]).expanduser().resolve() / uuid.uuid4().hex
    for name in ("input", "outputs", "data", "tmp", "cache"):
        (runtime / name).mkdir(parents=True, exist_ok=False)
    output_dir.mkdir(parents=True)
    query = runtime / "input/query.h5ad"
    shutil.copy2(section["query_h5ad"], query)
    annotated = runtime / "outputs/niche_annotated.h5ad"
    template = scientific_prompt(section["contract"], "<QUERY_H5AD>", "<ANNOTATED_H5AD>")
    task = scientific_prompt(section["contract"], str(query), str(annotated))
    request = {
        "prompt_version": PROMPT_VERSION,
        "method": method,
        "model": model,
        "seed": seed,
        "reasoning_effort": config.get("reasoning_effort"),
        "contract": section["contract"],
        "query_h5ad": str(query),
        "annotated_h5ad": str(annotated),
        "output_dir": str(runtime / "outputs"),
        "data_path": str(runtime / "data"),
        "task_prompt_template": template,
        "task_prompt": task,
        "execution_prompt": "",
        "prompt": task,
        "execution_timeout_seconds": config["execution_timeout_seconds"],
        "recursion_limit": config["recursion_limit"],
        "method_config": config.get(method, {}),
        "storage_budget": config.get("storage_budget"),
        **runtime_config,
    }
    if method == "tissueagent":
        request["source_path"] = str(_stage_tissueagent(runtime))
        request["source_revision"] = _revision(ROOT)
        runtime_config["source_revision"] = request["source_revision"]
        runtime_config["source_snapshot_sha256"] = _source_snapshot_hash(
            Path(request["source_path"])
        )
    record = {
        "protocol": PROTOCOL,
        "prompt_version": PROMPT_VERSION,
        "method": method,
        "model": model,
        "seed": seed,
        "reasoning_effort": config.get("reasoning_effort"),
        "section_id": section["section_id"],
        "query_sha256": section["query_sha256"],
        "contract": section["contract"],
        "runtime_dir": str(runtime),
        "task_prompt_template": template,
        "status": "running",
        "runtime": runtime_config,
        "adapter_sha256": sha256(Path(__file__)),
        "worker_sha256": sha256(Path(__file__).with_name("agent_baseline_worker.py")),
        "filesystem_isolation": "staged input and independent process; not an OS sandbox",
    }
    write_json(output_dir / "run_record.json", record)
    started = time.monotonic()
    try:
        result = _execute_worker(
            request, runtime, runtime_config["python_executable"], config["process_timeout_seconds"]
        )
        record["worker_result"] = result
        record["staged_query_sha256_after"] = sha256(query)
        record["staged_input_modified"] = (
            record["staged_query_sha256_after"] != section["query_sha256"]
        )
        record.update(_collect_predictions(section, runtime, output_dir))
        if result.get("workflow_error"):
            record.update(status="partial", workflow_error=result["workflow_error"])
        record["annotated_h5ad_sha256"] = sha256(annotated)
    except Exception as error:
        record.update(status="failed", error_type=type(error).__name__, error=str(error))
    finally:
        record["elapsed_seconds"] = time.monotonic() - started
        for name in ("worker_request.json", "worker_result.json", "stdout.log", "stderr.log"):
            if (runtime / name).exists():
                shutil.copy2(runtime / name, output_dir / name)
        shutil.copytree(runtime / "outputs", output_dir / "artifacts", copy_function=_link_artifact)
        write_json(output_dir / "run_record.json", record)
    return record


def run_biomni(
    section: dict, *, output_dir: Path, config: dict, model: str = DEFAULT_MODEL, seed: int = 42
) -> dict:
    """Run native Biomni tissue-niche annotation on a prepared section."""
    return run_method(
        section, method="biomni", output_dir=output_dir, config=config, model=model, seed=seed
    )


def run_spatialagent(
    section: dict, *, output_dir: Path, config: dict, model: str = DEFAULT_MODEL, seed: int = 42
) -> dict:
    """Run native SpatialAgent tissue-niche annotation on a prepared section."""
    return run_method(
        section, method="spatialagent", output_dir=output_dir, config=config, model=model, seed=seed
    )
