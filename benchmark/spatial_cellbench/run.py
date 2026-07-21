#!/usr/bin/env python3
"""Run and resume the three-arm spatial paper benchmark."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from benchmark.spatial_cellbench.evaluation import JUDGE_PROTOCOL, evaluate_proposals
from benchmark.spatial_cellbench.methods import (
    LangChainModelCall,
    register_benchmark_models,
    run_direct,
)
from benchmark.spatial_cellbench.prompts import (
    DIRECT_SYSTEM,
    direct_prompt,
)
from benchmark.spatial_cellbench.schemas import (
    GroundTruthPaper,
    PublicContext,
    validate_proposal_count,
)
from benchmark.spatial_cellbench.statistics import paired_summary, paper_arm_means
from benchmark.spatial_cellbench.ta import (
    TA_ARM,
    TA_CV_ARM,
    recover_ta_partial_trace,
    run_tissueagent,
)
from benchmark.spatial_cellbench.validate_data import _read_jsonl, validate_data

ROOT = Path(__file__).resolve().parents[2]

BENCHMARK_DIR = Path(__file__).resolve().parent
DATA_DIR = BENCHMARK_DIR / "data"
MANIFEST_PATH = DATA_DIR / "corpus_manifest.json"
CONTEXTS_PATH = DATA_DIR / "public_contexts.json"
TRUTH_PATH = DATA_DIR / "ground_truth.json"
OVERVIEW_PATH = BENCHMARK_DIR / "prompts" / "spatial_analysis_overview.md"
PROTOCOL = "spatial_cellbench_dynamic_n_v2"
ARMS = ("direct", TA_ARM, TA_CV_ARM)
GENERATION_MODEL = "o3-mini"
ORCHESTRATION_MODEL = "gpt-5.1"
JUDGE_MODEL = "gpt-4o"


class GenerationMethodError(RuntimeError):
    """Carry a failed standalone method's observable trace."""

    def __init__(self, cause: Exception, trace: dict) -> None:
        """Preserve the underlying provider error and partial trace."""
        super().__init__(str(cause))
        self.error_type = type(cause).__name__
        self.trace = trace


def _load_local_env() -> None:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env", override=False)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _sha256_json(value: object) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return _sha256_text(canonical)


def _atomic_write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _seal_checkpoint(payload: dict) -> dict:
    sealed = dict(payload)
    sealed["checkpoint_sha256"] = _sha256_json(sealed)
    return sealed


def _validate_checkpoint_hash(payload: dict, label: str) -> None:
    expected = payload.get("checkpoint_sha256")
    content = {key: value for key, value in payload.items() if key != "checkpoint_sha256"}
    if expected != _sha256_json(content):
        raise ValueError(f"{label} checkpoint hash mismatch")


def _source_fingerprint() -> dict:
    paths = []
    for pattern in ("*.py", "*.md", "prompts/*.md"):
        paths.extend(BENCHMARK_DIR.glob(pattern))
    paths.extend(
        ROOT / relative
        for relative in (
            "pyproject.toml",
            "uv.lock",
            "src/config.py",
            "src/models.py",
            "src/server/plan_store.py",
            "src/server/rate_limit.py",
            "src/server/usage_tracker.py",
            "knowledge/__init__.py",
        )
    )
    for directory in (ROOT / "src" / "graph", ROOT / "src" / "agents"):
        paths.extend(
            path for path in directory.rglob("*") if path.suffix in {".py", ".txt", ".md"}
        )
    paths.extend((ROOT / "knowledge" / "plans").glob("*.md"))
    digest = hashlib.sha256()
    files = sorted({path.resolve() for path in paths if path.is_file()})
    for path in files:
        digest.update(path.relative_to(ROOT).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return {"sha256": digest.hexdigest(), "file_count": len(files)}


def _model_metadata(model_id: str) -> dict:
    if model_id == GENERATION_MODEL:
        return {
            "id": GENERATION_MODEL,
            "provider": "openai",
            "api_model": GENERATION_MODEL,
            "reasoning_effort": "medium",
        }
    if model_id == JUDGE_MODEL:
        return {
            "id": JUDGE_MODEL,
            "provider": "openai",
            "api_model": JUDGE_MODEL,
            "reasoning_effort": None,
        }
    register_benchmark_models()
    from models import get_model_spec

    spec = get_model_spec(model_id)
    return {
        "id": spec.id,
        "provider": spec.provider,
        "api_model": spec.api_model,
        "reasoning_effort": spec.reasoning_effort,
    }


def _load_corpus() -> tuple[list[PublicContext], dict[str, GroundTruthPaper], dict, str]:
    validate_data(MANIFEST_PATH, CONTEXTS_PATH, TRUTH_PATH)
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    overview = OVERVIEW_PATH.read_text(encoding="utf-8")
    if _sha256_text(overview) != manifest["frozen_artifacts"]["spatial_overview_sha256"]:
        raise ValueError("Frozen spatial overview hash mismatch")
    contexts = {
        record.eval_id: record for record in _read_jsonl(CONTEXTS_PATH, PublicContext)
    }
    truths = {
        record.eval_id: record for record in _read_jsonl(TRUTH_PATH, GroundTruthPaper)
    }
    included = [
        paper["opaque_id"]
        for paper in manifest["papers"]
        if paper["eligibility"] == "include"
    ]
    return [contexts[eval_id] for eval_id in included], truths, manifest, overview


def _run_identity(
    contexts: list[PublicContext],
    truths: dict[str, GroundTruthPaper],
    manifest: dict,
    overview: str,
    arms: list[str],
    replicates: int,
) -> dict:
    counts = {public.eval_id: len(truths[public.eval_id].analyses) for public in contexts}
    return {
        "protocol": PROTOCOL,
        "paper_ids": [public.eval_id for public in contexts],
        "oracle_analysis_counts": counts,
        "arms": arms,
        "replicates": replicates,
        "generation_units": len(contexts) * len(arms) * replicates,
        "judge_units": len(contexts) * len(arms) * replicates,
        "generation_model": _model_metadata(GENERATION_MODEL),
        "orchestration_model": _model_metadata(ORCHESTRATION_MODEL),
        "judge_model": _model_metadata(JUDGE_MODEL),
        "source_fingerprint": _source_fingerprint(),
        "overview_sha256": _sha256_text(overview),
        "public_contexts_sha256": manifest["frozen_artifacts"]["public_contexts_sha256"],
        "ground_truth_sha256": manifest["frozen_artifacts"]["ground_truth_sha256"],
        "scope_adjudication_sha256": manifest["frozen_artifacts"][
            "scope_adjudication_sha256"
        ],
    }


def _select_contexts(
    contexts: list[PublicContext],
    paper_ids: list[str] | None,
    paper_count: int | None,
) -> list[PublicContext]:
    if paper_ids:
        indexed = {public.eval_id: public for public in contexts}
        unknown = sorted(set(paper_ids) - set(indexed))
        if unknown:
            raise ValueError(f"Unknown or ineligible paper IDs: {unknown}")
        if len(paper_ids) != len(set(paper_ids)):
            raise ValueError("Duplicate --paper-id values are not allowed")
        return [indexed[eval_id] for eval_id in paper_ids]
    if paper_count is not None:
        if not 1 <= paper_count <= len(contexts):
            raise ValueError(f"--paper-count must be between 1 and {len(contexts)}")
        return contexts[:paper_count]
    return contexts


def _generation_fingerprint(
    public: PublicContext,
    proposal_count: int,
    arm: str,
    replicate: int,
    model_id: str,
    orchestration_model_id: str,
    overview: str,
    source_sha256: str,
) -> str:
    return _sha256_json(
        {
            "protocol": PROTOCOL,
            "source_sha256": source_sha256,
            "eval_id": public.eval_id,
            "context_sha256": public.context_sha256,
            "proposal_count": proposal_count,
            "arm": arm,
            "replicate": replicate,
            "model_id": model_id,
            "orchestration_model_id": orchestration_model_id,
            "overview_sha256": _sha256_text(overview),
        }
    )


def _generation_payload(
    public: PublicContext,
    proposal_count: int,
    arm: str,
    replicate: int,
    model_id: str,
    orchestration_model_id: str,
    overview: str,
    source_sha256: str,
) -> dict:
    if arm not in ARMS:
        raise ValueError(f"Unknown arm: {arm}")
    return {
        "protocol": PROTOCOL,
        "source_sha256": source_sha256,
        "unit_fingerprint": _generation_fingerprint(
            public,
            proposal_count,
            arm,
            replicate,
            model_id,
            orchestration_model_id,
            overview,
            source_sha256,
        ),
        "arm": arm,
        "replicate": replicate,
        "model_id": model_id,
        "orchestration_model_id": orchestration_model_id,
        "proposal_count": proposal_count,
        "public": public.model_dump(),
        "overview": overview,
    }


def _caller_trace(
    caller: LangChainModelCall,
    public: PublicContext,
    arm: str,
    model_id: str,
    prompt_hash: str,
    overview: str,
    started: float,
) -> dict:
    return {
        "arm": arm,
        "context_sha256": public.context_sha256,
        "model": _model_metadata(model_id),
        "logical_model_calls": caller.call_count,
        "observable_model_attempts": caller.observable_attempt_count,
        "semantic_retries": 0,
        "fallback_model": None,
        "calls": caller.traces,
        "failed_attempts": caller.failed_attempts,
        "prompt_bundle_sha256": prompt_hash,
        "overview_sha256": None,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }


def run_generation_worker(payload: dict, workspace_root: Path) -> dict:
    """Execute one public-only generation unit."""
    expected = {
        "protocol",
        "source_sha256",
        "unit_fingerprint",
        "arm",
        "replicate",
        "model_id",
        "orchestration_model_id",
        "proposal_count",
        "public",
        "overview",
    }
    if set(payload) != expected:
        raise ValueError(f"Invalid generation payload fields: {sorted(payload)}")
    if payload["protocol"] != PROTOCOL:
        raise ValueError("Generation protocol mismatch")
    public = PublicContext.model_validate(payload["public"])
    proposal_count = int(payload["proposal_count"])
    arm = payload["arm"]
    replicate = int(payload["replicate"])
    model_id = payload["model_id"]
    orchestration_model_id = payload["orchestration_model_id"]
    overview = payload["overview"]
    source_sha256 = _source_fingerprint()["sha256"]
    if payload["source_sha256"] != source_sha256:
        raise ValueError("Generation source fingerprint mismatch")
    expected_fingerprint = _generation_fingerprint(
        public,
        proposal_count,
        arm,
        replicate,
        model_id,
        orchestration_model_id,
        overview,
        source_sha256,
    )
    if payload["unit_fingerprint"] != expected_fingerprint:
        raise ValueError("Generation unit fingerprint mismatch")
    if arm in {TA_ARM, TA_CV_ARM}:
        result = run_tissueagent(
            public,
            overview,
            model_id,
            orchestration_model_id,
            proposal_count,
            workspace_root,
            include_spatial_cv=arm == TA_CV_ARM,
        )
        proposals = validate_proposal_count(result["proposals"], proposal_count)
        trace = result["trace"]
    else:
        caller = LangChainModelCall(model_id)
        started = time.perf_counter()
        prompt_hash = _sha256_text(
            DIRECT_SYSTEM + "\n" + direct_prompt(public.context, proposal_count)
        )
        try:
            proposals = run_direct(public, proposal_count, caller)
        except Exception as exc:
            trace = _caller_trace(
                caller,
                public,
                arm,
                model_id,
                prompt_hash,
                overview,
                started,
            )
            raise GenerationMethodError(exc, trace) from exc
        trace = _caller_trace(
            caller,
            public,
            arm,
            model_id,
            prompt_hash,
            overview,
            started,
        )
        if caller.call_count != 1:
            raise RuntimeError(
                f"{arm} made {caller.call_count} successful calls; expected 1"
            )
    return {
        "protocol": PROTOCOL,
        "unit_fingerprint": expected_fingerprint,
        "eval_id": public.eval_id,
        "replicate": replicate,
        "proposal_count": proposal_count,
        "proposal_sha256": _sha256_json(proposals.model_dump()),
        "proposals": proposals.model_dump(),
        "trace": trace,
        "trace_sha256": _sha256_json(trace),
    }


def _worker_main(args: argparse.Namespace) -> int:
    payload = json.loads(args.payload.read_text(encoding="utf-8"))
    try:
        result = run_generation_worker(payload, args.workspace_root)
        output = {"status": "success", **result}
    except Exception as exc:
        output = {
            "status": "failed",
            "protocol": payload.get("protocol"),
            "unit_fingerprint": payload.get("unit_fingerprint"),
            "eval_id": payload.get("public", {}).get("eval_id"),
            "replicate": payload.get("replicate"),
            "proposal_count": payload.get("proposal_count"),
            "error_type": getattr(exc, "error_type", type(exc).__name__),
            "error": str(exc)[:1000],
        }
        trace = getattr(exc, "trace", None)
        if payload.get("arm") in {TA_ARM, TA_CV_ARM}:
            try:
                trace = recover_ta_partial_trace(
                    PublicContext.model_validate(payload["public"]),
                    payload["overview"],
                    payload["model_id"],
                    payload["orchestration_model_id"],
                    payload["proposal_count"],
                    args.workspace_root,
                    include_spatial_cv=payload["arm"] == TA_CV_ARM,
                )
            except Exception as recovery_exc:
                output["partial_trace_error"] = (
                    f"{type(recovery_exc).__name__}: {str(recovery_exc)[:300]}"
                )
        if isinstance(trace, dict):
            output["trace"] = trace
            output["trace_sha256"] = _sha256_json(trace)
    _atomic_write_json(args.output, _seal_checkpoint(output))
    return 0


def _validate_generation_checkpoint(result: dict, payload: dict) -> None:
    for field in ("protocol", "unit_fingerprint", "replicate", "proposal_count"):
        if result.get(field) != payload[field]:
            raise ValueError(f"Generation checkpoint {field} mismatch")
    if result.get("eval_id") != payload["public"]["eval_id"]:
        raise ValueError("Generation checkpoint eval_id mismatch")
    if result.get("status") not in {"success", "failed"}:
        raise ValueError("Generation checkpoint has invalid status")
    if result["status"] == "success":
        proposals = validate_proposal_count(
            result.get("proposals"),
            payload["proposal_count"],
        )
        if result.get("proposal_sha256") != _sha256_json(proposals.model_dump()):
            raise ValueError("Generation checkpoint proposal hash mismatch")
    trace = result.get("trace")
    if trace is not None and result.get("trace_sha256") != _sha256_json(trace):
        raise ValueError("Generation checkpoint trace hash mismatch")
    _validate_checkpoint_hash(result, "Generation")


def _run_generation_subprocess(
    run_dir: Path,
    public: PublicContext,
    proposal_count: int,
    arm: str,
    replicate: int,
    model_id: str,
    orchestration_model_id: str,
    overview: str,
    source_sha256: str,
    timeout: int,
    retry_failed: bool,
) -> dict:
    result_path = (
        run_dir
        / "generation"
        / public.eval_id
        / f"replicate_{replicate:02d}"
        / f"{arm}.json"
    )
    payload = _generation_payload(
        public,
        proposal_count,
        arm,
        replicate,
        model_id,
        orchestration_model_id,
        overview,
        source_sha256,
    )
    unit_dir = run_dir / "work" / public.eval_id / f"replicate_{replicate:02d}" / arm
    attempts = sorted(unit_dir.glob("attempt_*")) if unit_dir.exists() else []
    if result_path.is_file():
        existing = json.loads(result_path.read_text(encoding="utf-8"))
        _validate_generation_checkpoint(existing, payload)
        if existing["status"] == "success" or not retry_failed:
            return existing
        archive = unit_dir / f"failed_checkpoint_{len(attempts):02d}.json"
        archive.parent.mkdir(parents=True, exist_ok=True)
        result_path.replace(archive)
    attempt_dir = unit_dir / f"attempt_{len(attempts) + 1:02d}"
    runtime = attempt_dir / "runtime"
    runtime.mkdir(parents=True)
    payload_path = attempt_dir / "payload.json"
    _atomic_write_json(payload_path, payload)
    command = [
        sys.executable,
        "-m",
        "benchmark.spatial_cellbench.run",
        "_worker",
        "--payload",
        str(payload_path),
        "--output",
        str(result_path),
        "--workspace-root",
        str(runtime),
    ]
    env = {
        **os.environ,
        "PYTHONPATH": f"{ROOT / 'src'}:{ROOT}",
        "NUMBA_CACHE_DIR": str(run_dir / "cache" / "numba"),
        "MPLCONFIGDIR": str(run_dir / "cache" / "matplotlib"),
    }
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if completed.returncode != 0 or not result_path.is_file():
            detail = (completed.stderr or completed.stdout)[-4000:]
            failure = _seal_checkpoint(
                {
                    "status": "failed",
                    "protocol": PROTOCOL,
                    "unit_fingerprint": payload["unit_fingerprint"],
                    "eval_id": public.eval_id,
                    "replicate": replicate,
                    "proposal_count": proposal_count,
                    "error_type": "WorkerProcessError",
                    "error": detail,
                }
            )
            _atomic_write_json(result_path, failure)
    except subprocess.TimeoutExpired:
        failure = _seal_checkpoint(
            {
                "status": "failed",
                "protocol": PROTOCOL,
                "unit_fingerprint": payload["unit_fingerprint"],
                "eval_id": public.eval_id,
                "replicate": replicate,
                "proposal_count": proposal_count,
                "error_type": "TimeoutExpired",
                "error": f"Generation exceeded {timeout} seconds",
            }
        )
        _atomic_write_json(result_path, failure)
    result = json.loads(result_path.read_text(encoding="utf-8"))
    _validate_generation_checkpoint(result, payload)
    return result


def _judge_checkpoint(
    run_dir: Path,
    public: PublicContext,
    truth: GroundTruthPaper,
    arm: str,
    replicate: int,
    generation: dict,
    judge_model: str,
    truth_artifact_sha256: str,
    retry_failed: bool,
) -> dict:
    path = run_dir / "judging" / public.eval_id / f"replicate_{replicate:02d}" / f"{arm}.json"
    truth_sha256 = _sha256_json(truth.model_dump())
    fingerprint = _sha256_json(
        {
            "judge_protocol": JUDGE_PROTOCOL,
            "eval_id": public.eval_id,
            "replicate": replicate,
            "arm": arm,
            "judge_model": judge_model,
            "generation_proposal_sha256": generation.get("proposal_sha256"),
            "truth_sha256": truth_sha256,
            "truth_artifact_sha256": truth_artifact_sha256,
        }
    )
    if path.is_file():
        existing = json.loads(path.read_text(encoding="utf-8"))
        _validate_checkpoint_hash(existing, "Judge")
        retry_after_generation_failure = (
            retry_failed
            and existing.get("status") == "skipped"
            and existing.get("reason") == "generation_failed"
        )
        if (
            existing.get("unit_fingerprint") != fingerprint
            and not retry_after_generation_failure
        ):
            raise ValueError("Judge checkpoint fingerprint mismatch")
        if existing.get("status") == "success" or not retry_failed:
            return existing
        archive_dir = path.parent / "failed"
        archive_dir.mkdir(parents=True, exist_ok=True)
        path.replace(archive_dir / f"{arm}_{len(list(archive_dir.glob('*.json'))) + 1:02d}.json")
    if generation.get("status") != "success":
        result = _seal_checkpoint(
            {
                "status": "skipped",
                "reason": "generation_failed",
                "unit_fingerprint": fingerprint,
                "generation_proposal_sha256": None,
                "truth_sha256": truth_sha256,
            }
        )
        _atomic_write_json(path, result)
        return result
    caller = LangChainModelCall(judge_model)
    started = time.perf_counter()
    try:
        proposals = validate_proposal_count(
            generation["proposals"],
            generation["proposal_count"],
        )
        evaluated = evaluate_proposals(public, truth, proposals, caller, replicate)
        trace = {
            "model": _model_metadata(judge_model),
            "logical_model_calls": caller.call_count,
            "observable_model_attempts": caller.observable_attempt_count,
            "semantic_retries": 0,
            "fallback_model": None,
            "calls": caller.traces,
            "failed_attempts": caller.failed_attempts,
            "elapsed_seconds": round(time.perf_counter() - started, 3),
        }
        result = {
            "status": "success",
            "unit_fingerprint": fingerprint,
            "generation_proposal_sha256": generation["proposal_sha256"],
            "truth_sha256": truth_sha256,
            "truth_artifact_sha256": truth_artifact_sha256,
            **evaluated,
            "trace": trace,
            "trace_sha256": _sha256_json(trace),
        }
    except Exception as exc:
        result = {
            "status": "failed",
            "unit_fingerprint": fingerprint,
            "generation_proposal_sha256": generation["proposal_sha256"],
            "truth_sha256": truth_sha256,
            "truth_artifact_sha256": truth_artifact_sha256,
            "error_type": type(exc).__name__,
            "error": str(exc)[:1000],
            "trace": {
                "logical_model_calls": caller.call_count,
                "observable_model_attempts": caller.observable_attempt_count,
                "calls": caller.traces,
                "failed_attempts": caller.failed_attempts,
            },
        }
        result["trace_sha256"] = _sha256_json(result["trace"])
    result = _seal_checkpoint(result)
    _atomic_write_json(path, result)
    return result


def _aggregate(
    run_dir: Path,
    rows: list[dict],
    units: list[dict],
    expected_paper_ids: list[str],
    arms: list[str],
    replicates: int,
) -> dict:
    aggregate = {
        "scheduled_units": len(units),
        "scored_unit_count": len(rows),
        "scored_rows": rows,
        "completion": {},
        "arm_summaries": {},
        "contrasts": {},
        "unit_ledger": units,
    }
    for arm in arms:
        arm_units = [unit for unit in units if unit["arm"] == arm]
        arm_rows = [row for row in rows if row["arm"] == arm]
        aggregate["completion"][arm] = {
            "scheduled": len(arm_units),
            "generation_success": sum(
                unit["generation_status"] == "success" for unit in arm_units
            ),
            "judge_success": sum(unit["judge_status"] == "success" for unit in arm_units),
        }
        matched = sum(row["metrics"]["matched_candidates"] for row in arm_rows)
        candidates = sum(row["metrics"]["candidate_count"] for row in arm_rows)
        summary = {
            "scored_units": len(arm_rows),
            "pooled_candidate_hit": matched / candidates if candidates else None,
            "mean_scored_unit_hit": (
                sum(row["metrics"]["candidate_hit_fraction"] for row in arm_rows)
                / len(arm_rows)
                if arm_rows
                else None
            ),
            "mean_paper_hit": None,
            "complete_paper_count": 0,
        }
        if replicates == 3:
            means = paper_arm_means(rows, "candidate_hit_fraction")
            paper_values = [
                by_arm[arm] for by_arm in means.values() if arm in by_arm
            ]
            summary["mean_paper_hit"] = (
                sum(paper_values) / len(paper_values) if paper_values else None
            )
            summary["complete_paper_count"] = len(paper_values)
        aggregate["arm_summaries"][arm] = summary
    if replicates == 3:
        for name, treatment, baseline in (
            ("tissueagent_minus_direct", TA_ARM, "direct"),
            ("tissueagent_spatial_cv_minus_tissueagent", TA_CV_ARM, TA_ARM),
        ):
            if treatment not in arms or baseline not in arms:
                continue
            try:
                aggregate["contrasts"][name] = paired_summary(
                    rows,
                    "candidate_hit_fraction",
                    treatment,
                    baseline,
                )
            except ValueError as exc:
                aggregate["contrasts"][name] = {
                    "status": "unavailable",
                    "reason": str(exc),
                    "expected_papers": expected_paper_ids,
                }
    integration_units = [unit for unit in units if unit["arm"] == TA_CV_ARM]
    if integration_units:
        fields = (
            "spatial_cv_available",
            "spatial_cv_invoked",
            "spatial_cv_artifact_valid",
            "spatial_cv_exposed_to_hypothesis",
        )
        integration = {}
        for field in fields:
            values = [
                unit["generation_trace"].get(field)
                for unit in integration_units
                if isinstance(unit.get("generation_trace"), dict)
                and unit["generation_trace"].get(field) is not None
            ]
            integration[field + "_rate"] = (
                sum(bool(value) for value in values) / len(values) if values else None
            )
            integration[field + "_observed"] = len(values)
        recruited = [
            bool(unit["generation_trace"].get("spatial_cv_recruited_steps"))
            for unit in integration_units
            if isinstance(unit.get("generation_trace"), dict)
            and unit["generation_trace"].get("spatial_cv_recruited_steps") is not None
        ]
        integration["spatial_cv_recruitment_rate"] = (
            sum(recruited) / len(recruited) if recruited else None
        )
        integration["spatial_cv_recruitment_observed"] = len(recruited)
        aggregate["ta_plus_cv_integration"] = integration
    sealed = _seal_checkpoint(aggregate)
    _atomic_write_json(run_dir / "aggregate.json", sealed)
    return sealed


def _completion_exit_code(units: list[dict], skip_judge: bool) -> int:
    if any(unit["generation_status"] != "success" for unit in units):
        return 1
    if not skip_judge and any(unit["judge_status"] != "success" for unit in units):
        return 1
    return 0


def _git_metadata() -> dict:
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
        status = subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=ROOT, text=True
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {"commit": None, "dirty": None}
    return {"commit": commit, "dirty": bool(status), "status_sha256": _sha256_text(status)}


def run_controller(args: argparse.Namespace) -> int:
    """Validate, run missing checkpoints, and aggregate one selected corpus slice."""
    if (
        args.model != GENERATION_MODEL
        or args.orchestration_model != ORCHESTRATION_MODEL
        or args.judge_model != JUDGE_MODEL
    ):
        raise ValueError(
            f"Frozen protocol requires --model {GENERATION_MODEL}, "
            f"--orchestration-model {ORCHESTRATION_MODEL}, and --judge-model {JUDGE_MODEL}"
        )
    contexts, truths, manifest, overview = _load_corpus()
    contexts = _select_contexts(contexts, args.paper_id, args.paper_count)
    arms = args.arms.split(",")
    if not arms or len(arms) != len(set(arms)) or any(arm not in ARMS for arm in arms):
        raise ValueError(f"--arms must be unique values from {ARMS}")
    if args.replicates not in (1, 2, 3):
        raise ValueError("--replicates must be 1, 2, or 3")
    identity = _run_identity(contexts, truths, manifest, overview, arms, args.replicates)
    source = identity["source_fingerprint"]
    if args.validate_only:
        print(json.dumps(identity, indent=2))
        return 0
    args.run_dir.mkdir(parents=True, exist_ok=True)
    meta_path = args.run_dir / "run_meta.json"
    invocation = {
        "at": datetime.now(timezone.utc).isoformat(),
        "skip_judge": args.skip_judge,
        "retry_failed": args.retry_failed,
    }
    if meta_path.is_file():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("identity") != identity:
            raise ValueError("Existing run_meta.json does not match the requested protocol")
        meta["invocations"].append(invocation)
    else:
        meta = {
            "identity": identity,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "git": _git_metadata(),
            "invocations": [invocation],
        }
    _atomic_write_json(meta_path, meta)

    rows = []
    units = []
    for public in contexts:
        truth = truths[public.eval_id]
        proposal_count = len(truth.analyses)
        for replicate in range(1, args.replicates + 1):
            for arm in arms:
                generation = _run_generation_subprocess(
                    args.run_dir,
                    public,
                    proposal_count,
                    arm,
                    replicate,
                    args.model,
                    args.orchestration_model,
                    overview,
                    source["sha256"],
                    args.timeout,
                    args.retry_failed,
                )
                judged = None
                judge_status = "not_run"
                if not args.skip_judge:
                    judged = _judge_checkpoint(
                        args.run_dir,
                        public,
                        truth,
                        arm,
                        replicate,
                        generation,
                        args.judge_model,
                        manifest["frozen_artifacts"]["ground_truth_sha256"],
                        args.retry_failed,
                    )
                    judge_status = judged["status"]
                unit = {
                    "eval_id": public.eval_id,
                    "replicate": replicate,
                    "arm": arm,
                    "proposal_count": proposal_count,
                    "generation_status": generation["status"],
                    "judge_status": judge_status,
                    "error_type": generation.get("error_type")
                    or (judged or {}).get("error_type"),
                    "reason": generation.get("error")
                    or (judged or {}).get("error")
                    or (judged or {}).get("reason"),
                    "generation_trace": generation.get("trace"),
                }
                units.append(unit)
                if judged and judged.get("status") == "success":
                    rows.append(
                        {
                            "eval_id": public.eval_id,
                            "replicate": replicate,
                            "arm": arm,
                            "metrics": judged["metrics"],
                        }
                    )
    _aggregate(
        args.run_dir,
        rows,
        units,
        [public.eval_id for public in contexts],
        arms,
        args.replicates,
    )
    return _completion_exit_code(units, args.skip_judge)


def merge_paper_runs(args: argparse.Namespace) -> int:
    """Merge per-paper Slurm outputs into one formal aggregate."""
    contexts, truths, manifest, overview = _load_corpus()
    contexts = _select_contexts(contexts, args.paper_id, None)
    rows = []
    units = []
    for public in contexts:
        paper_root = args.run_root / "papers" / public.eval_id
        meta_path = paper_root / "run_meta.json"
        path = paper_root / "aggregate.json"
        if not meta_path.is_file():
            raise FileNotFoundError(f"Missing paper run metadata: {meta_path}")
        if not path.is_file():
            raise FileNotFoundError(f"Missing paper aggregate: {path}")
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        expected_identity = _run_identity(
            [public], truths, manifest, overview, list(ARMS), 3
        )
        if meta.get("identity") != expected_identity:
            raise ValueError(f"Paper run identity mismatch: {public.eval_id}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        _validate_checkpoint_hash(payload, f"Paper aggregate {public.eval_id}")
        expected_keys = {
            (public.eval_id, replicate, arm)
            for replicate in (1, 2, 3)
            for arm in ARMS
        }
        unit_keys = {
            (unit["eval_id"], int(unit["replicate"]), unit["arm"])
            for unit in payload.get("unit_ledger", [])
        }
        row_keys = {
            (row["eval_id"], int(row["replicate"]), row["arm"])
            for row in payload.get("scored_rows", [])
        }
        if (
            len(payload.get("unit_ledger", [])) != len(expected_keys)
            or len(payload.get("scored_rows", [])) != len(expected_keys)
            or unit_keys != expected_keys
            or row_keys != expected_keys
        ):
            raise ValueError(f"Paper aggregate is incomplete: {public.eval_id}")
        if any(
            unit.get("generation_status") != "success"
            or unit.get("judge_status") != "success"
            for unit in payload["unit_ledger"]
        ):
            raise ValueError(f"Paper aggregate contains failed units: {public.eval_id}")
        rows.extend(payload["scored_rows"])
        units.extend(payload["unit_ledger"])
    _aggregate(
        args.run_root,
        rows,
        units,
        [public.eval_id for public in contexts],
        list(ARMS),
        3,
    )
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run", help="Run or resume benchmark units")
    run_parser.add_argument("--run-dir", type=Path, required=True)
    run_parser.add_argument("--model", default=GENERATION_MODEL)
    run_parser.add_argument("--orchestration-model", default=ORCHESTRATION_MODEL)
    run_parser.add_argument("--judge-model", default=JUDGE_MODEL)
    run_parser.add_argument("--arms", default=",".join(ARMS))
    run_parser.add_argument("--replicates", type=int, default=3)
    selection = run_parser.add_mutually_exclusive_group()
    selection.add_argument("--paper-id", action="append")
    selection.add_argument("--paper-count", type=int)
    run_parser.add_argument("--timeout", type=int, default=7200)
    run_parser.add_argument("--skip-judge", action="store_true")
    run_parser.add_argument("--retry-failed", action="store_true")
    run_parser.add_argument("--validate-only", action="store_true")

    merge_parser = subparsers.add_parser("merge", help="Merge per-paper runs")
    merge_parser.add_argument("--run-root", type=Path, required=True)
    merge_parser.add_argument("--paper-id", action="append")

    worker = subparsers.add_parser("_worker")
    worker.add_argument("--payload", type=Path, required=True)
    worker.add_argument("--output", type=Path, required=True)
    worker.add_argument("--workspace-root", type=Path, required=True)
    return parser


def main() -> int:
    """Run the requested controller, merge, or isolated worker command."""
    _load_local_env()
    args = _parser().parse_args()
    if args.command == "_worker":
        return _worker_main(args)
    if args.command == "merge":
        return merge_paper_runs(args)
    return run_controller(args)


if __name__ == "__main__":
    raise SystemExit(main())
