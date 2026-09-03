"""The optimizer benchmark round loop.

Each round: run TissueAgent on the pinned datasets (starting from the minimal
``ccc_ensemble`` template), score every run against the expert reference, then
hand the sessions + scores to ``tissueagent optimize`` for one optimization
round (git-committed). Expected trend over rounds: accuracy up, tokens down.

Usage::

    python benchmark/optimizer_ccc/run_benchmark.py --rounds 3 --repeats 1 \
        [--datasets merfish ...] [--model ID] [--out DIR] [--timeout 7200]

Preconditions: staged inputs (prepare_inputs.py) and references
(make_reference.py) exist; knowledge/ is committed.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from datasets import BENCH_DIR, DATASETS, REFERENCE_DIR, REPO_ROOT, agent_prompt, staged_path  # noqa: E402
from score import aggregate_round, score_run, tokens_from_metrics  # noqa: E402

CLI = REPO_ROOT / "src" / "cli.py"
FULL_TEMPLATE = REPO_ROOT / "knowledge" / "plans" / "ccc_ensemble.md"
MINIMAL_TEMPLATE = REPO_ROOT / "knowledge" / "plans" / "ccc_ensemble_minimal.md"
PROJECTS_DIR = REPO_ROOT / "projects"
ACTIVE_PROJECT = REPO_ROOT / "workspace" / "project"


# ---------------------------------------------------------------------------
# Template mode toggling (exactly one enabled `ccc_ensemble` at any time)
# ---------------------------------------------------------------------------


def _set_status(path: Path, status: str) -> bool:
    """Rewrite the frontmatter ``status:`` line. Returns True if changed."""
    text = path.read_text()
    end = text.index("---", 3)
    head, rest = text[:end], text[end:]
    lines = head.splitlines()
    for i, line in enumerate(lines):
        if line.strip().startswith("status:"):
            if line.split(":", 1)[1].strip() == status:
                return False
            lines[i] = f"status: {status}"
            path.write_text("\n".join(lines) + rest)
            return True
    raise SystemExit(f"{path}: no status line in frontmatter")


def _git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(REPO_ROOT), *args], capture_output=True, text=True, check=check
    )


def set_template_mode(minimal: bool) -> None:
    changed = _set_status(FULL_TEMPLATE, "disabled" if minimal else "enabled")
    changed |= _set_status(MINIMAL_TEMPLATE, "enabled" if minimal else "disabled")
    if changed:
        _git("add", "--", str(FULL_TEMPLATE), str(MINIMAL_TEMPLATE))
        mode = "enter" if minimal else "exit"
        _git("commit", "-m", f"benchmark: {mode} minimal ccc_ensemble template mode")
    print(f"[mode] minimal template {'ON' if minimal else 'OFF'}", flush=True)


# ---------------------------------------------------------------------------
# One agent run
# ---------------------------------------------------------------------------


def run_agent(name: str, round_i: int, rep: int, out_round: Path, *, model: str | None, timeout: int) -> dict:
    tag = f"{name}_{rep}"
    run_dir = out_round / tag
    session_dst = run_dir / "session"
    session_dst.mkdir(parents=True, exist_ok=True)
    metrics_out = run_dir / "metrics.json"

    cmd = [
        sys.executable, str(CLI),
        "--no-docker", "--json", "--quiet",
        "--task-id", f"opt_ccc_{name}",
        "--seed", f"r{round_i}s{rep}",
        "--metrics-out", str(metrics_out),
    ]
    if model:
        cmd += ["--model", model]
    cmd.append(agent_prompt(name))

    print(f"[run] round {round_i} {tag} …", flush=True)
    record: dict = {"dataset": name, "repeat": rep, "session_dir": str(session_dst)}
    stdout_path, stderr_path = run_dir / "stdout.txt", run_dir / "stderr.txt"
    try:
        with stdout_path.open("w") as fo, stderr_path.open("w") as fe:
            proc = subprocess.run(cmd, cwd=REPO_ROOT, stdout=fo, stderr=fe, timeout=timeout)
        record["returncode"] = proc.returncode
    except subprocess.TimeoutExpired:
        record.update(returncode=None, timeout=True)
        print(f"[run] {tag} TIMED OUT after {timeout}s", flush=True)

    result = _parse_result_json(stdout_path)
    (run_dir / "result.json").write_text(json.dumps(result, indent=2))
    record["project_id"] = result.get("project_id")

    _copy_session(result.get("project_id"), metrics_out, session_dst)

    ref_csv = REFERENCE_DIR / name / "ccc_ensemble.csv"
    score = score_run(session_dst / "outputs" / "ccc_ensemble.csv", ref_csv)
    score.update(tokens_from_metrics(session_dst / "metrics.json"))
    record.update(score)
    # Drop the score next to the session so the optimizer's digest can see it.
    (session_dst / "score.json").write_text(json.dumps(score, indent=2))
    print(
        f"[run] {tag}: valid={score['valid']} spearman={score.get('spearman')} "
        f"jaccard={score.get('topk_jaccard')} tokens={score.get('total_tokens')}",
        flush=True,
    )
    return record


def _parse_result_json(stdout_path: Path) -> dict:
    """The CLI prints indented JSON last; parse from the last '{'-opening line."""
    lines = stdout_path.read_text(errors="ignore").splitlines()
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].startswith("{"):
            try:
                return json.loads("\n".join(lines[i:]))
            except json.JSONDecodeError:
                continue
    return {}


def _copy_session(project_id: str | None, metrics_out: Path, dst: Path) -> None:
    """Copy .chat.json + outputs/ + metrics into one self-contained session dir.

    The archive location depends on parking timing: .chat.json goes to
    projects/<id>/ at save time, but outputs/ may still live in the active
    workspace/project/ until the next run parks it — check both.
    """
    candidates = []
    if project_id:
        candidates.append(PROJECTS_DIR / project_id)
    candidates.append(ACTIVE_PROJECT)
    for src in candidates:
        if (src / ".chat.json").is_file() and not (dst / ".chat.json").is_file():
            shutil.copy2(src / ".chat.json", dst / ".chat.json")
        if (src / "outputs").is_dir() and not (dst / "outputs").is_dir():
            shutil.copytree(src / "outputs", dst / "outputs")
    if metrics_out.is_file():
        shutil.copy2(metrics_out, dst / "metrics.json")


# ---------------------------------------------------------------------------
# One optimizer round
# ---------------------------------------------------------------------------


def run_optimizer_round(records: list[dict], round_i: int, out_round: Path, *, model: str | None) -> str | None:
    focus_lines = [
        "These sessions are benchmark runs of the CCC ensemble workflow, started from a",
        "deliberately minimal `ccc_ensemble` plan template. Improve (a) the accuracy of",
        "future runs against the fixed expert pipeline (the skills' shipped scripts, run",
        "in order with cross-step artifacts) and (b) their token usage. Do NOT rename",
        "templates/skills or flip any status fields; edit the enabled minimal template",
        "(knowledge/plans/ccc_ensemble_minimal.md) and the ccc-* skills as needed.",
        "",
        "Per-run scores vs the expert reference (spearman/jaccard: higher is better):",
        "",
        "| dataset | rep | valid | spearman | top20 jaccard | tokens | replans | reason |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in records:
        focus_lines.append(
            f"| {r['dataset']} | {r['repeat']} | {r.get('valid')} | {r.get('spearman')} "
            f"| {r.get('topk_jaccard')} | {r.get('total_tokens')} | {r.get('replans')} "
            f"| {r.get('reason') or ''} |"
        )
    focus = "\n".join(focus_lines)
    (out_round / "optimizer_focus.md").write_text(focus)

    sessions = [r["session_dir"] for r in records if Path(r["session_dir"], ".chat.json").is_file()]
    if not sessions:
        print("[opt] no usable sessions this round; skipping optimizer", flush=True)
        return None

    cmd = [sys.executable, str(CLI), "optimize", "--sessions", *sessions, "--focus", focus]
    if model:
        cmd += ["--model", model]
    print(f"[opt] round {round_i}: optimizing over {len(sessions)} session(s) …", flush=True)
    with (out_round / "optimizer.stdout.txt").open("w") as fo, (out_round / "optimizer.stderr.txt").open("w") as fe:
        subprocess.run(cmd, cwd=REPO_ROOT, stdout=fo, stderr=fe)
    head = _git("rev-parse", "HEAD").stdout.strip()
    print(f"[opt] knowledge at {head}", flush=True)
    return head


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--repeats", type=int, default=1, help="runs per dataset per round")
    ap.add_argument("--datasets", nargs="+", default=list(DATASETS), choices=list(DATASETS))
    ap.add_argument("--model", default=None)
    ap.add_argument("--timeout", type=int, default=7200, help="per-run timeout, seconds")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument(
        "--skip-final-optimize",
        action="store_true",
        help="don't run the optimizer after the last round (default: optimize every round)",
    )
    args = ap.parse_args(argv)

    for name in args.datasets:
        if not staged_path(name).is_file():
            raise SystemExit(f"{name}: staged input missing — run prepare_inputs.py first")
        if not (REFERENCE_DIR / name / "ccc_ensemble.csv").is_file():
            raise SystemExit(f"{name}: reference missing — run make_reference.py first")
    if _git("status", "--porcelain", "--", "knowledge").stdout.strip():
        raise SystemExit("knowledge/ has uncommitted changes; commit or stash before benchmarking")

    out = args.out or BENCH_DIR / "runs" / datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
    out.mkdir(parents=True, exist_ok=True)
    summary_path = out / "summary.csv"

    set_template_mode(minimal=True)
    try:
        for round_i in range(1, args.rounds + 1):
            out_round = out / f"round_{round_i}"
            out_round.mkdir(exist_ok=True)
            records = [
                run_agent(name, round_i, rep, out_round, model=args.model, timeout=args.timeout)
                for name in args.datasets
                for rep in range(1, args.repeats + 1)
            ]
            agg = aggregate_round(records)
            (out_round / "results.json").write_text(
                json.dumps({"round": round_i, "aggregate": agg, "runs": records}, indent=2)
            )

            knowledge_commit = None
            if round_i < args.rounds or not args.skip_final_optimize:
                knowledge_commit = run_optimizer_round(records, round_i, out_round, model=args.model)

            _append_summary(summary_path, round_i, agg, knowledge_commit)
            print(f"[round {round_i}] {agg}", flush=True)
    finally:
        set_template_mode(minimal=False)

    print(f"summary: {summary_path}", flush=True)
    return 0


def _append_summary(path: Path, round_i: int, agg: dict, knowledge_commit: str | None) -> None:
    fields = [
        "round", "n_runs", "valid_run_rate", "mean_spearman",
        "mean_topk_jaccard", "median_total_tokens", "knowledge_commit",
    ]
    new = not path.is_file()
    with path.open("a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        if new:
            w.writeheader()
        w.writerow({"round": round_i, "knowledge_commit": knowledge_commit, **{
            k: agg.get(k) for k in fields if k not in ("round", "knowledge_commit")
        }})


if __name__ == "__main__":
    sys.exit(main())
