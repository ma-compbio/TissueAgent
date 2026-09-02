#!/usr/bin/env python3
"""Run every vendored GeneGPT benchmark question through both paired arms."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Any

from run_genegpt_paired_pilot import _checkpoint, _run_direct, _run_tissueagent, _score

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent
_UPSTREAM = _REPO / "src/agents/agent_registry/genegpt_agent/upstream"
_PILOT_RECORDS = _HERE / "genegpt_paired_pilot/records.json"
_SCOREABLE_TASKS = {
    "Gene alias",
    "Gene disease association",
    "Gene location",
    "Human genome DNA aligment",
    "Multi-species DNA aligment",
    "Gene name conversion",
    "Protein-coding genes",
    "Gene SNP association",
    "SNP location",
    "Disease gene location",
}


def _load_questions(suite_filter: str | None = None) -> list[dict[str, Any]]:
    """Load the selected vendored GeneGPT benchmark questions in source order."""
    suites = OrderedDict(
        [
            ("GeneTuring", _UPSTREAM / "data/geneturing.json"),
            ("GeneHop", _UPSTREAM / "data/genehop.json"),
        ]
    )
    records: list[dict[str, Any]] = []
    for suite, path in suites.items():
        if suite_filter is not None and suite != suite_filter:
            continue
        data = json.loads(path.read_text())
        for task, questions in data.items():
            for question, gold in questions.items():
                records.append(
                    {
                        "index": len(records) + 1,
                        "suite": suite,
                        "task": task,
                        "question": question,
                        "gold": gold,
                        "scoreable": task in _SCOREABLE_TASKS,
                    }
                )
    return records


def _seed_pilot(records: list[dict[str, Any]], path: Path) -> int:
    """Reuse matching completed pilot arms without changing their results."""
    if not path.is_file():
        return 0
    pilot = json.loads(path.read_text())
    by_question = {(row["task"], row["question"]): row for row in pilot}
    seeded = 0
    for record in records:
        source = by_question.get((record["task"], record["question"]))
        if not source:
            continue
        for arm in ("direct", "tissueagent"):
            if (source.get(arm) or {}).get("status") == "ok":
                record[arm] = copy.deepcopy(source[arm])
        if "direct" in record and "tissueagent" in record:
            seeded += 1
    return seeded


def _normalise_unscored(raw: str, task: str) -> Any:
    """Apply upstream normalization without inventing an accuracy rule."""
    sys.path.insert(0, str(_UPSTREAM))
    try:
        from evaluate import get_answer  # type: ignore[import-not-found]
    finally:
        sys.path.remove(str(_UPSTREAM))
    return get_answer(raw or "", task)


def _score_record(record: dict[str, Any]) -> None:
    """Attach normalized predictions, scores, and paired agreement."""
    if "direct" not in record or "tissueagent" not in record:
        return
    for arm in ("direct", "tissueagent"):
        result = record[arm]
        raw = result.get("raw_completion") or ""
        try:
            if record["scoreable"]:
                pred, score = _score(raw, record["gold"], record["task"])
            else:
                pred, score = _normalise_unscored(raw, record["task"]), None
        except (IndexError, TypeError, ValueError):
            pred = raw.strip()
            score = 0.0 if record["scoreable"] else None
        result["normalised_pred"] = pred
        result["score"] = score
    record["normalised_answer_agreement"] = (
        record["direct"]["normalised_pred"] == record["tissueagent"]["normalised_pred"]
    )


def _mean(values: list[float]) -> float | None:
    """Return a mean or None for an empty collection."""
    return sum(values) / len(values) if values else None


def _summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize partial or complete full-corpus records."""
    paired = [row for row in records if "direct" in row and "tissueagent" in row]
    for row in paired:
        _score_record(row)
    scoreable = [row for row in paired if row["scoreable"]]
    per_task: dict[str, dict[str, Any]] = {}
    for task in OrderedDict.fromkeys(row["task"] for row in records):
        task_rows = [row for row in records if row["task"] == task]
        task_paired = [row for row in paired if row["task"] == task]
        task_scored = [row for row in task_paired if row["scoreable"]]
        per_task[task] = {
            "n_total": len(task_rows),
            "n_paired": len(task_paired),
            "scoreable": task in _SCOREABLE_TASKS,
            "direct_accuracy": _mean(
                [float(row["direct"]["score"]) for row in task_scored]
            ),
            "tissueagent_accuracy": _mean(
                [float(row["tissueagent"]["score"]) for row in task_scored]
            ),
            "answer_agreement": _mean(
                [float(row["normalised_answer_agreement"]) for row in task_paired]
            ),
        }
    direct_scores = [float(row["direct"]["score"]) for row in scoreable]
    tissue_scores = [float(row["tissueagent"]["score"]) for row in scoreable]
    direct_accuracy = _mean(direct_scores)
    tissue_accuracy = _mean(tissue_scores)
    return {
        "n_total": len(records),
        "n_scoreable_total": sum(row["scoreable"] for row in records),
        "n_direct_attempted": sum("direct" in row for row in records),
        "n_tissueagent_attempted": sum("tissueagent" in row for row in records),
        "n_paired": len(paired),
        "n_scoreable_paired": len(scoreable),
        "direct_accuracy": direct_accuracy,
        "tissueagent_accuracy": tissue_accuracy,
        "accuracy_difference": (
            tissue_accuracy - direct_accuracy
            if direct_accuracy is not None and tissue_accuracy is not None
            else None
        ),
        "normalised_answer_agreement": _mean(
            [float(row["normalised_answer_agreement"]) for row in paired]
        ),
        "recruitment_rate": _mean(
            [float(row["tissueagent"].get("recruited", False)) for row in paired]
        ),
        "tool_execution_rate": _mean(
            [float(row["tissueagent"].get("tool_fired", False)) for row in paired]
        ),
        "direct_success_rate": _mean(
            [float(row["direct"].get("status") == "ok") for row in paired]
        ),
        "tissueagent_success_rate": _mean(
            [float(row["tissueagent"].get("status") == "ok") for row in paired]
        ),
        "direct_wall_time_s": sum(
            float(row["direct"].get("elapsed_s", 0)) for row in paired
        ),
        "tissueagent_wall_time_s": sum(
            float(row["tissueagent"].get("elapsed_s", 0)) for row in paired
        ),
        "per_task": per_task,
    }


def _percent(value: float | None) -> str:
    """Format an optional ratio as a percentage."""
    return "N/A" if value is None else f"{value:.1%}"


def _cell(value: Any, limit: int = 120) -> str:
    """Make a compact Markdown-table cell."""
    if isinstance(value, list):
        text = ", ".join(str(item) for item in value)
    else:
        text = str(value or "")
    text = " ".join(text.split()).replace("|", "\\|")
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _write_report(
    path: Path,
    records: list[dict[str, Any]],
    summary: dict[str, Any],
    status: str,
) -> None:
    """Write an incremental Markdown report, with full rows on completion."""
    suites = list(OrderedDict.fromkeys(row["suite"] for row in records))
    suite_label = " and ".join(suites)
    unscored_total = summary["n_total"] - summary["n_scoreable_total"]
    lines = [
        "# Full TissueAgent-recruited GeneGPT benchmark",
        "",
        f"Status: **{status}**",
        "",
        "## Design",
        "",
        f"Every vendored {suite_label} question is run once through direct GeneGPT and ",
        "once through TissueAgent with explicit `genegpt_agent` recruitment. Both GeneGPT arms ",
        "use `gpt-4o`, mask `111111`, and live NCBI APIs. TissueAgent orchestration uses its ",
        "separately configured control-plane model.",
        "",
        (
            f"The upstream scorer covers all {summary['n_scoreable_total']} selected questions."
            if unscored_total == 0
            else (
                f"The upstream scorer covers {summary['n_scoreable_total']} selected questions. "
                f"The other {unscored_total} questions are included for answer agreement but are "
                "not assigned an invented accuracy score."
            )
        ),
        "",
        "## Progress and aggregate results",
        "",
        "| Metric | Result |",
        "| --- | ---: |",
        f"| Paired questions | {summary['n_paired']}/{summary['n_total']} |",
        (
            "| Scoreable paired questions | "
            f"{summary['n_scoreable_paired']}/{summary['n_scoreable_total']} |"
        ),
        f"| Direct GeneGPT accuracy | {_percent(summary['direct_accuracy'])} |",
        f"| TissueAgent + GeneGPT accuracy | {_percent(summary['tissueagent_accuracy'])} |",
        f"| Normalized answer agreement | {_percent(summary['normalised_answer_agreement'])} |",
        f"| Recruitment rate | {_percent(summary['recruitment_rate'])} |",
        f"| GeneGPT tool-execution rate | {_percent(summary['tool_execution_rate'])} |",
        "",
        "## Per-task results",
        "",
        "| Task | Paired | Direct accuracy | Recruited accuracy | Agreement |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for task, result in summary["per_task"].items():
        lines.append(
            f"| {_cell(task)} | {result['n_paired']}/{result['n_total']} | "
            f"{_percent(result['direct_accuracy'])} | "
            f"{_percent(result['tissueagent_accuracy'])} | "
            f"{_percent(result['answer_agreement'])} |"
        )
    if status.startswith("completed"):
        lines.extend(
            [
                "",
                "## Question-level results",
                "",
                (
                    "| # | Suite | Task | Direct | Recruited | Direct score | "
                    "Recruited score | Agreement |"
                ),
                "| ---: | --- | --- | --- | --- | ---: | ---: | :---: |",
            ]
        )
        for row in records:
            direct = row.get("direct") or {}
            tissue = row.get("tissueagent") or {}
            direct_score = direct.get("score")
            tissue_score = tissue.get("score")
            lines.append(
                f"| {row['index']} | {_cell(row['suite'])} | {_cell(row['task'])} | "
                f"{_cell(direct.get('normalised_pred') or direct.get('answer'))} | "
                f"{_cell(tissue.get('normalised_pred') or tissue.get('answer'))} | "
                f"{'N/A' if direct_score is None else f'{direct_score:.2f}'} | "
                f"{'N/A' if tissue_score is None else f'{tissue_score:.2f}'} | "
                f"{'Yes' if row.get('normalised_answer_agreement') else 'No'} |"
            )
    lines.extend(
        [
            "",
            "Machine-readable records, summary, status, raw GeneGPT traces, and TissueAgent logs ",
            "are stored beside this report. Raw traces and logs are intentionally gitignored.",
            "",
        ]
    )
    path.write_text("\n".join(lines))


def _persist(
    out_dir: Path,
    records: list[dict[str, Any]],
    status: str,
) -> dict[str, Any]:
    """Checkpoint records, summary, status, and Markdown report."""
    summary = _summarize(records)
    _checkpoint(out_dir / "records.json", records)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    run_status = {
        "status": status,
        "total_questions": summary["n_total"],
        "direct_attempted": summary["n_direct_attempted"],
        "tissueagent_attempted": summary["n_tissueagent_attempted"],
        "paired_results": summary["n_paired"],
        "report_path": "report.md",
        "summary_path": "summary.json",
        "records_path": "records.json",
    }
    (out_dir / "run_status.json").write_text(json.dumps(run_status, indent=2))
    _write_report(out_dir / "report.md", records, summary, status)
    return summary


def _run_arm(
    record: dict[str, Any],
    arm: str,
    out_dir: Path,
    timeout: int,
) -> None:
    """Run one arm and update its attempt count."""
    attempts_key = f"{arm}_attempts"
    record[attempts_key] = int(record.get(attempts_key, 0)) + 1
    if arm == "direct":
        record[arm] = _run_direct(record["index"], record["question"], out_dir)
    else:
        record[arm] = _run_tissueagent(
            record["index"], record["question"], out_dir, timeout
        )


def main() -> int:
    """Run, resume, or preview the full paired benchmark."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-dir", type=Path, default=_HERE / "genegpt_full_benchmark"
    )
    parser.add_argument("--pilot-records", type=Path, default=_PILOT_RECORDS)
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--max-attempts", type=int, default=2)
    parser.add_argument("--suite", choices=("GeneTuring", "GeneHop"))
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    expected = _load_questions(args.suite)
    if args.limit is not None:
        expected = expected[: args.limit]
    task_counts: dict[str, int] = {}
    for row in expected:
        task_counts[row["task"]] = task_counts.get(row["task"], 0) + 1
    print(
        f"Full paired GeneGPT benchmark: {len(expected)} questions "
        f"({sum(row['scoreable'] for row in expected)} scoreable)"
    )
    for task, count in task_counts.items():
        print(f"  {task}: {count}")
    if args.dry_run:
        return 0
    if not args.out_dir.is_absolute():
        args.out_dir = (_REPO / args.out_dir).resolve()
    if not args.force and (args.out_dir / "records.json").is_file():
        records = json.loads((args.out_dir / "records.json").read_text())
        expected_identity = [(row["suite"], row["task"], row["question"]) for row in expected]
        actual_identity = [(row["suite"], row["task"], row["question"]) for row in records]
        if actual_identity != expected_identity:
            raise RuntimeError("Existing records do not match the requested corpus and limit.")
        seeded = 0
    else:
        records = expected
        seeded = _seed_pilot(records, args.pilot_records)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "raw").mkdir(exist_ok=True)
    (args.out_dir / "logs").mkdir(exist_ok=True)
    print(f"Reused {seeded} completed pilot pairs.")
    _persist(args.out_dir, records, "running")

    total = len(records)
    for record in records:
        index = record["index"]
        print(f"\n[{index:03d}/{total}] {record['task']}: {record['question'][:90]}")
        for arm in ("direct", "tissueagent"):
            while (
                (record.get(arm) or {}).get("status") != "ok"
                and int(record.get(f"{arm}_attempts", 0)) < args.max_attempts
            ):
                _run_arm(record, arm, args.out_dir, args.timeout)
                _persist(args.out_dir, records, "running")
            result = record.get(arm) or {}
            print(
                f"  {arm}: {result.get('status')} "
                f"recruited={result.get('recruited')} fired={result.get('tool_fired')} "
                f"{str(result.get('answer'))[:160]}"
            )
        _persist(args.out_dir, records, "running")

    failures = sum(
        (row.get(arm) or {}).get("status") != "ok"
        for row in records
        for arm in ("direct", "tissueagent")
    )
    status = "completed" if failures == 0 else "completed_with_failures"
    summary = _persist(args.out_dir, records, status)
    print("\n" + json.dumps(summary, indent=2))
    print(f"Artifacts: {args.out_dir}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
