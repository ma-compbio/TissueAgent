#!/usr/bin/env python3
"""Grade BioMysteryBench-Expression runs against ``answer_rubric`` with an LLM judge.

The rubrics are all-or-nothing ("Do not award partial credit"), so ``correct``
is binary. They cannot be graded by string equality: answers are prose and
free-form lists, and a run that answered ``Sample_10_Group2`` against a rubric
saying ``Sample_10`` is right, while ``Sample_25`` against ``Sample_10`` is
wrong. Hence a judge model.

**Use a judge that is not one of the contestants.** Asking a model to grade its
own answers is a conflict of interest; ``--judge-model`` makes the choice
explicit and it is recorded in every grade.json for audit.

Writes ``grade.json`` beside each run's ``metrics.json`` and prints an aggregate
table. Grading is idempotent — a run that already has a grade.json is skipped
unless ``--force``.

Usage::

    python grade.py --runs runs/                     # grade everything ungraded
    python grade.py --runs tissueagent_runs/         # flat layout works too
    python grade.py --runs runs/ --judge-model gpt-5 --force
    python grade.py --runs runs/ --summary-csv grades.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

_BENCH = Path(__file__).resolve().parent
# benchmark/biomysterybench/biomysterybench_expr/ -> repo root is three levels up. Depth-derived,
# so it breaks silently if this file moves; the 2026-07-25 consolidation from
# benchmark/BioMysteryBench-Expression/ already cost it one level.
_REPO = _BENCH.parents[2]
sys.path.insert(0, str(_REPO / "src"))

JUDGE_PROMPT = """You are grading one answer from a computational-biology benchmark.

The rubric below is ALL-OR-NOTHING. Award 1 only if the answer satisfies it in
full; otherwise award 0. There is no partial credit.

Grade the substance, not the presentation. In particular:
- Extra detail, hedging, caveats, or a long report around a correct answer do
  NOT make it wrong.
- A more specific label that unambiguously contains the required one is correct
  (e.g. rubric "Sample_10", answer "Sample_10_Group2").
- A refusal, a "cannot determine", or an answer that never commits to the
  required claim is INCORRECT (0), however well reasoned.
- If the answer states the required conclusion but attributes it to the wrong
  evidence, still award 1 — the rubric grades the conclusion.

QUESTION:
{question}

RUBRIC:
{rubric}

ANSWER UNDER TEST:
{answer}

Reply with a JSON object and nothing else:
{{"correct": 0 or 1, "rationale": "<one or two sentences citing what decided it>"}}
"""


def load_problems() -> dict[str, dict]:
    with open(_BENCH / "problems.csv") as f:
        return {r["id"]: r for r in csv.DictReader(f)}


def find_runs(root: Path) -> list[Path]:
    """Every directory holding a metrics.json, in either archive layout."""
    return sorted(p.parent for p in root.rglob("metrics.json"))


def _parse_verdict(text: str) -> tuple[int | None, str]:
    """Pull the JSON verdict out of a judge reply, tolerating code fences."""
    blob = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", blob, re.S)
    if fenced:
        blob = fenced.group(1)
    else:
        brace = re.search(r"\{.*\}", blob, re.S)
        if brace:
            blob = brace.group(0)
    try:
        data = json.loads(blob)
    except Exception:
        return None, f"unparseable judge reply: {text[:200]}"
    correct = data.get("correct")
    if correct not in (0, 1, True, False):
        return None, f"judge returned no usable verdict: {text[:200]}"
    return int(bool(correct)), str(data.get("rationale", ""))


def grade_run(run_dir: Path, problems: dict[str, dict], judge, judge_model: str) -> dict | None:
    metrics = json.loads((run_dir / "metrics.json").read_text())
    task_id = metrics["run"].get("task_id")
    problem = problems.get(task_id)
    if problem is None:
        print(f"  !! {run_dir}: task_id {task_id!r} not in problems.csv — skipped")
        return None

    answer = metrics["outcome"].get("final_answer") or ""
    terminal = metrics["outcome"].get("terminal_state")
    if not answer.strip():
        # A crashed run has no answer to grade. Record it as incorrect but keep
        # the terminal state so §7 can exclude infra failures from the rate.
        verdict, rationale = 0, f"no final answer (terminal_state={terminal})"
    else:
        reply = judge.invoke(
            JUDGE_PROMPT.format(
                question=problem["question"],
                rubric=problem["answer_rubric"],
                answer=answer,
            )
        )
        content = getattr(reply, "content", reply)
        if isinstance(content, list):  # multimodal-style content blocks
            content = "".join(
                part.get("text", "") if isinstance(part, dict) else str(part) for part in content
            )
        verdict, rationale = _parse_verdict(str(content))
        if verdict is None:
            print(f"  !! {run_dir}: {rationale}")
            return None

    # Trial bookkeeping. `seed` is a replicate (another sample of the model);
    # `attempt` is a re-launch after an infra failure and is NOT another sample.
    # Keeping them in separate columns is what stops retries inflating pass@k.
    attempts_log = run_dir / "attempts.jsonl"
    attempts_total, attempts_failed = None, None
    if attempts_log.is_file():
        lines = [json.loads(x) for x in attempts_log.read_text().splitlines() if x.strip()]
        attempts_total = len(lines)
        attempts_failed = sum(1 for x in lines if x.get("outcome") != "completed")

    grade = {
        "task_id": task_id,
        "bucket": problem.get("bucket"),
        "human_solvable": problem.get("human_solvable"),
        "seed": metrics["run"].get("seed"),
        "attempt": metrics["run"].get("attempt"),
        "attempts_total": attempts_total,
        "attempts_failed": attempts_failed,
        "orchestration_model": metrics["models"]["orchestration"]["model_id"],
        "worker_model": metrics["models"]["worker"]["model_id"],
        "correct": verdict,
        "grader": "llm-judge",
        "judge_model": judge_model,
        "grader_rationale": rationale,
        "terminal_state": terminal,
        "route": metrics["outcome"].get("route"),
        "degraded_to_direct": metrics["outcome"].get("degraded_to_direct"),
        "total_tokens": metrics["usage"].get("total_tokens"),
        "wall_time_s": metrics["run"].get("wall_time_s"),
        "replans_triggered": metrics["loops"].get("replans_triggered"),
        "replans_successful": metrics["loops"].get("replans_successful"),
        "retry_step_calls": (metrics["loops"].get("manager") or {}).get("retry_step_calls"),
        "run_dir": str(run_dir),
    }
    (run_dir / "grade.json").write_text(json.dumps(grade, indent=2), encoding="utf-8")
    return grade


def summarize(grades: list[dict]) -> None:
    if not grades:
        print("\nno grades to summarize")
        return

    def rate(rows: list[dict]) -> str:
        if not rows:
            return "     -    "
        n_correct = sum(r["correct"] for r in rows)
        return f"{n_correct}/{len(rows)} = {n_correct / len(rows):.0%}"

    print(f"\n{'=' * 64}\nOVERALL  {rate(grades)}")

    by_model: dict[str, list[dict]] = {}
    for g in grades:
        by_model.setdefault(g["orchestration_model"] or "?", []).append(g)
    if len(by_model) > 1 or True:
        print("\nby model:")
        for model, rows in sorted(by_model.items()):
            tokens = sum(r["total_tokens"] or 0 for r in rows)
            n_correct = sum(r["correct"] for r in rows) or 0
            per = f"{tokens / n_correct:,.0f}" if n_correct else "n/a"
            print(f"  {model:24} {rate(rows):>14}   tokens/correct: {per}")

    print("\nby bucket:")
    by_bucket: dict[str, list[dict]] = {}
    for g in grades:
        by_bucket.setdefault(g["bucket"] or "?", []).append(g)
    for bucket, rows in sorted(by_bucket.items()):
        print(f"  {bucket:24} {rate(rows):>14}")

    print("\nby human_solvable:")
    by_hs: dict[str, list[dict]] = {}
    for g in grades:
        by_hs.setdefault(str(g["human_solvable"]), []).append(g)
    for hs, rows in sorted(by_hs.items()):
        print(f"  {hs:24} {rate(rows):>14}")

    # pass@1 / pass@k need multiple seeds per (task, model).
    by_key: dict[tuple, list[dict]] = {}
    for g in grades:
        by_key.setdefault((g["task_id"], g["orchestration_model"]), []).append(g)
    multi = {k: v for k, v in by_key.items() if len(v) > 1}
    if multi:
        k = max(len(v) for v in multi.values())
        pass1 = sum(sum(r["correct"] for r in v) / len(v) for v in by_key.values()) / len(by_key)
        passk = sum(any(r["correct"] for r in v) for v in by_key.values()) / len(by_key)
        print(f"\npass@1 {pass1:.0%}   pass@{k} {passk:.0%}   ({len(multi)} of {len(by_key)} cells have >1 seed)")
    else:
        print("\npass@1 / pass@k: need >1 seed per (task, model) — single-seed corpus")

    # Re-launches are infrastructure cost, not model behaviour. Surfaced
    # separately so a sweep that needed many retries can't be read as a clean one.
    retried = [g for g in grades if (g.get("attempts_total") or 1) > 1]
    if retried:
        extra = sum((g.get("attempts_failed") or 0) for g in grades)
        print(
            f"\nre-launches: {len(retried)} of {len(grades)} run(s) needed >1 attempt "
            f"({extra} failed launch(es) — timeouts/crashes, not model failures)"
        )
        for g in sorted(retried, key=lambda g: -(g.get("attempts_total") or 0)):
            print(f"  {g['task_id']:24} seed={g['seed']}  attempts={g['attempts_total']}")

    degraded = [g for g in grades if g.get("degraded_to_direct")]
    crashed = [g for g in grades if g["terminal_state"] not in (None, "completed")]
    if degraded:
        print(f"\n!! {len(degraded)} run(s) degraded to DIRECT (forced by planner retry exhaustion)")
    if crashed:
        print(f"!! {len(crashed)} run(s) did not complete: "
              f"{', '.join(sorted({g['terminal_state'] for g in crashed}))} "
              "— exclude infra failures from the success rate")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--runs", default="runs", help="Directory to scan for runs (default: runs/)")
    p.add_argument("--judge-model", default="gpt-5", help="Model id used to grade (default: gpt-5)")
    p.add_argument("--force", action="store_true", help="Re-grade runs that already have grade.json")
    p.add_argument("--summary-csv", default=None, help="Also write one row per graded run to this CSV")
    args = p.parse_args()

    root = Path(args.runs)
    if not root.is_absolute():
        root = _BENCH / root
    if not root.is_dir():
        sys.exit(f"error: no such directory: {root}")

    run_dirs = find_runs(root)
    if not run_dirs:
        sys.exit(f"error: no metrics.json found under {root}")

    problems = load_problems()
    from models import build_chat_model

    judge = None  # built lazily so a fully-cached pass needs no API key
    grades: list[dict] = []
    print(f"scanning {root} — {len(run_dirs)} run(s) with metrics.json")
    for run_dir in run_dirs:
        existing = run_dir / "grade.json"
        if existing.is_file() and not args.force:
            grades.append(json.loads(existing.read_text()))
            print(f"  = {run_dir.relative_to(root)} (already graded)")
            continue
        if judge is None:
            judge = build_chat_model(args.judge_model)
        grade = grade_run(run_dir, problems, judge, args.judge_model)
        if grade is not None:
            grades.append(grade)
            mark = "✓" if grade["correct"] else "✗"
            print(f"  {mark} {run_dir.relative_to(root)}  {grade['grader_rationale'][:80]}")

    if args.summary_csv:
        out = Path(args.summary_csv)
        if not out.is_absolute():
            out = _BENCH / out
        fields = [k for k in grades[0] if k != "grader_rationale"] + ["grader_rationale"]
        with open(out, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(grades)
        print(f"\nwrote {out}")

    summarize(grades)
    return 0


if __name__ == "__main__":
    sys.exit(main())
