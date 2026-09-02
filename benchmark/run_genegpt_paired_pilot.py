#!/usr/bin/env python3
"""Compare direct GeneGPT with TissueAgent-recruited GeneGPT on 10 questions."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent
_SRC = _REPO / "src"
_UPSTREAM = _SRC / "agents/agent_registry/genegpt_agent/upstream"

if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

_FEWSHOT_MARKERS = (
    "LMP10",
    "rs1217074595",
    "Meesmann corneal dystrophy",
    "ATTCTGCCTTTAGTAATTTGATGACAGAGACTTCTTGGGAACCACAGCCAGGGAGCCACCC",
)
_TASK_ORDER = [
    "Gene name conversion",
    "Gene SNP association",
    "SNP location",
    "Protein-coding genes",
    "Gene alias",
    "Gene location",
    "Gene disease association",
    "Multi-species DNA aligment",
    "Human genome DNA aligment",
]


def _is_fewshot(question: str) -> bool:
    return any(marker in question for marker in _FEWSHOT_MARKERS)


def _select_subset() -> list[tuple[str, str, str]]:
    data = json.loads((_UPSTREAM / "data/geneturing.json").read_text())
    by_task: dict[str, list[tuple[str, str, str]]] = {}
    for task in _TASK_ORDER:
        rows = [
            (task, question, gold)
            for question, gold in data[task].items()
            if not _is_fewshot(question)
        ]
        by_task[task] = rows[:2]

    picked: list[tuple[str, str, str]] = []
    offset = 0
    while len(picked) < 10:
        for task in _TASK_ORDER:
            if offset < len(by_task[task]) and len(picked) < 10:
                picked.append(by_task[task][offset])
        offset += 1
    return picked


def _tissueagent_prompt(question: str) -> str:
    return (
        "This is a paired GeneGPT integration benchmark. You must choose ROUTE: PLAN so the "
        "recruiter runs, then recruit the `genegpt_agent` external agent for the single execution "
        "step. Use GeneGPT and its live NCBI APIs to answer the benchmark question below. Do "
        "not answer from internal knowledge and do not assign another domain agent. Treat "
        "GeneGPT's generated result.json as the required artifact, and preserve GeneGPT's "
        "factual answer in the final response.\n\n"
        f"Benchmark question: {question}"
    )


def _parse_json_stdout(stdout: str) -> dict[str, Any]:
    lines = stdout.splitlines()
    for i in range(len(lines) - 1, -1, -1):
        if not lines[i].lstrip().startswith("{"):
            continue
        try:
            value = json.loads("\n".join(lines[i:]))
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return {}


def _score(raw: str, gold: Any, task: str) -> tuple[Any, float]:
    sys.path.insert(0, str(_UPSTREAM))
    try:
        from evaluate import get_answer  # type: ignore[import-not-found]
    finally:
        sys.path.remove(str(_UPSTREAM))

    pred = get_answer(raw or "", task)
    if task in ("Gene disease association", "Disease gene location"):
        golds = gold.split(", ") if isinstance(gold, str) else list(gold)
        score = sum(item in pred for item in golds) / len(golds)
    elif task == "Human genome DNA aligment":
        pred_text = str(pred)
        score = 1.0 if pred_text == gold else (
            0.5 if pred_text.split(":")[0] == str(gold).split(":")[0] else 0.0
        )
    else:
        score = 1.0 if pred == gold else 0.0
    return pred, score


def _plan_evidence(metrics: dict[str, Any]) -> tuple[list[str], bool]:
    steps = (metrics.get("plan") or {}).get("steps") or []
    assigned = [str(step.get("assigned_agent") or "") for step in steps]
    recruited = any(agent.lower() == "genegpt_agent" for agent in assigned)
    return assigned, recruited


def _tool_result_snapshot(project_dir: Path) -> dict[Path, tuple[int, int]]:
    snapshot = {}
    for path in (project_dir / "outputs" / "genegpt").glob("*/result.json"):
        stat = path.stat()
        snapshot[path] = (stat.st_mtime_ns, stat.st_size)
    return snapshot


def _find_tool_result(
    project_dir: Path,
    question: str,
    prior: dict[Path, tuple[int, int]],
) -> tuple[Path | None, dict[str, Any]]:
    candidates: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted((project_dir / "outputs" / "genegpt").glob("*/result.json")):
        stat = path.stat()
        if prior.get(path) == (stat.st_mtime_ns, stat.st_size):
            continue
        try:
            result = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        candidates.append((path, result))
    for path, result in candidates:
        if question in str(result.get("question") or ""):
            return path, result
    return candidates[-1] if candidates else (None, {})


def _run_direct(index: int, question: str, out_dir: Path) -> dict[str, Any]:
    from agents.agent_registry.genegpt_agent.runner import run_genegpt_question

    started = time.perf_counter()
    try:
        result = run_genegpt_question(
            question,
            mask="111111",
            request_id=f"paired_direct_{index:02d}",
        )
    except Exception as exc:
        result = {
            "status": "exception",
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
    elapsed = time.perf_counter() - started
    raw_path = out_dir / "raw" / f"{index:02d}_direct.json"
    raw_path.write_text(json.dumps(result, indent=2))
    return {
        "status": result.get("status"),
        "answer": result.get("answer"),
        "raw_completion": result.get("raw_completion") or "",
        "num_calls": result.get("num_calls", 0),
        "model_used": result.get("model_used"),
        "elapsed_s": round(elapsed, 2),
        "error": result.get("error"),
        "error_type": result.get("error_type"),
        "raw_artifact": str(raw_path),
    }


def _run_tissueagent(
    index: int,
    question: str,
    out_dir: Path,
    timeout: int,
) -> dict[str, Any]:
    prompt = _tissueagent_prompt(question)
    active_project = _REPO / "workspace" / "project"
    prior_tool_results = _tool_result_snapshot(active_project)
    started = time.perf_counter()
    child_env = {**os.environ, "PYTHONPATH": str(_SRC)}
    child_env.setdefault("TISSUEAGENT_CODING_AGENT", "cache")
    try:
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "cli",
                prompt,
                "--json",
                "--no-docker",
                "--task-id",
                f"genegpt_paired_{index:02d}",
                "--seed",
                "0",
            ],
            cwd=_SRC,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=child_env,
        )
    except subprocess.TimeoutExpired as exc:
        elapsed = time.perf_counter() - started
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", "replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", "replace")
        log_base = out_dir / "logs" / f"{index:02d}_tissueagent"
        log_base.with_suffix(".stdout").write_text(stdout)
        log_base.with_suffix(".stderr").write_text(stderr)
        return {
            "status": "error",
            "exit_code": None,
            "prompt": prompt,
            "answer": None,
            "raw_completion": "",
            "num_calls": 0,
            "model_used": None,
            "final_answer": None,
            "project_id": None,
            "elapsed_s": round(elapsed, 2),
            "route": None,
            "assigned_agents": [],
            "recruited": False,
            "tool_fired": False,
            "metrics_path": None,
            "raw_artifact": None,
            "error": f"TissueAgent exceeded the {timeout}s timeout.",
            "error_type": "TimeoutExpired",
        }
    elapsed = time.perf_counter() - started

    log_base = out_dir / "logs" / f"{index:02d}_tissueagent"
    log_base.with_suffix(".stdout").write_text(proc.stdout)
    log_base.with_suffix(".stderr").write_text(proc.stderr)

    payload = _parse_json_stdout(proc.stdout)
    metrics_path = Path(str(payload.get("metrics_path") or ""))
    if not metrics_path.is_file():
        fallback = _REPO / "workspace" / "project" / "metrics.json"
        metrics_path = fallback if fallback.is_file() else Path()
    metrics = json.loads(metrics_path.read_text()) if metrics_path.is_file() else {}
    project_dir = metrics_path.parent if metrics_path.is_file() else _REPO / "workspace" / "project"
    assigned, recruited = _plan_evidence(metrics)
    tool_path, tool_result = _find_tool_result(project_dir, question, prior_tool_results)

    copied_tool_path = None
    if tool_path:
        copied = out_dir / "raw" / f"{index:02d}_tissueagent_genegpt.json"
        shutil.copy2(tool_path, copied)
        copied_tool_path = str(copied)

    status = "ok" if proc.returncode == 0 and tool_result.get("status") == "ok" else "error"
    return {
        "status": status,
        "exit_code": proc.returncode,
        "prompt": prompt,
        "answer": tool_result.get("answer"),
        "raw_completion": tool_result.get("raw_completion") or "",
        "num_calls": tool_result.get("num_calls", 0),
        "model_used": tool_result.get("model_used"),
        "final_answer": payload.get("answer"),
        "project_id": payload.get("project_id"),
        "elapsed_s": round(elapsed, 2),
        "route": (metrics.get("outcome") or {}).get("route"),
        "assigned_agents": assigned,
        "recruited": recruited,
        "tool_fired": bool(tool_path),
        "metrics_path": str(metrics_path) if metrics_path.is_file() else None,
        "raw_artifact": copied_tool_path,
        "error": tool_result.get("error") or (proc.stderr[-2000:] if proc.returncode else None),
        "error_type": tool_result.get("error_type"),
    }


def _checkpoint(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text(json.dumps(records, indent=2))


def _summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    for record in records:
        for arm in ("direct", "tissueagent"):
            result = record.get(arm) or {}
            pred, score = _score(result.get("raw_completion") or "", record["gold"], record["task"])
            result["normalised_pred"] = pred
            result["score"] = score
        record["normalised_answer_agreement"] = (
            record["direct"]["normalised_pred"]
            == record["tissueagent"]["normalised_pred"]
        )

    n = len(records)
    direct_accuracy = sum(row["direct"]["score"] for row in records) / n
    tissue_accuracy = sum(row["tissueagent"]["score"] for row in records) / n
    return {
        "n": n,
        "direct_accuracy": direct_accuracy,
        "tissueagent_accuracy": tissue_accuracy,
        "accuracy_difference": tissue_accuracy - direct_accuracy,
        "normalised_answer_agreement": sum(
            row["normalised_answer_agreement"] for row in records
        ) / n,
        "recruitment_rate": sum(row["tissueagent"].get("recruited", False) for row in records) / n,
        "tool_execution_rate": sum(
            row["tissueagent"].get("tool_fired", False) for row in records
        ) / n,
        "direct_success_rate": sum(row["direct"].get("status") == "ok" for row in records) / n,
        "tissueagent_success_rate": sum(
            row["tissueagent"].get("status") == "ok" for row in records
        ) / n,
        "direct_wall_time_s": sum(row["direct"].get("elapsed_s", 0) for row in records),
        "tissueagent_wall_time_s": sum(
            row["tissueagent"].get("elapsed_s", 0) for row in records
        ),
    }


def main() -> int:
    """Run or preview the paired pilot."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=_HERE / "genegpt_paired_pilot",
    )
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    subset = _select_subset()
    print(f"Paired GeneGPT pilot: {len(subset)} questions")
    for index, (task, question, gold) in enumerate(subset, 1):
        print(f"  {index:02d}. [{task}] {question[:76]} -> {gold}")
        if args.dry_run:
            print(f"      TissueAgent: {_tissueagent_prompt(question)[:150]}...")
    if args.dry_run:
        return 0

    if not os.environ.get("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY is not set.", file=sys.stderr)
        return 2

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "raw").mkdir(exist_ok=True)
    (args.out_dir / "logs").mkdir(exist_ok=True)
    records_path = args.out_dir / "records.json"

    if records_path.is_file() and not args.force:
        records = json.loads(records_path.read_text())
    else:
        records = [
            {"index": i, "task": task, "question": question, "gold": gold}
            for i, (task, question, gold) in enumerate(subset, 1)
        ]

    for record in records:
        index = record["index"]
        print(f"\n[{index:02d}/10] {record['task']}: {record['question'][:90]}")
        if args.force or (record.get("direct") or {}).get("status") != "ok":
            record["direct"] = _run_direct(index, record["question"], args.out_dir)
            _checkpoint(records_path, records)
        print(f"  direct: {record['direct'].get('status')} {record['direct'].get('answer')}")

        if args.force or (record.get("tissueagent") or {}).get("status") != "ok":
            record["tissueagent"] = _run_tissueagent(
                index,
                record["question"],
                args.out_dir,
                args.timeout,
            )
            _checkpoint(records_path, records)
        tissue = record["tissueagent"]
        print(
            f"  TissueAgent: {tissue.get('status')} recruited={tissue.get('recruited')} "
            f"fired={tissue.get('tool_fired')} {tissue.get('answer')}"
        )

    summary = _summarize(records)
    _checkpoint(records_path, records)
    (args.out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    (args.out_dir / "run_status.json").write_text(
        json.dumps(
            {
                "status": "completed",
                "valid_paired_results": summary["n"],
                "recruitment_rate": summary["recruitment_rate"],
                "tool_execution_rate": summary["tool_execution_rate"],
                "summary_path": "summary.json",
                "records_path": "records.json",
            },
            indent=2,
        )
    )
    print("\n" + json.dumps(summary, indent=2))
    print(f"Artifacts: {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
