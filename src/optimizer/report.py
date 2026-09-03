"""Optimization-round report + the round's git commit.

Reports land in ``optimizer_reports/`` at the repo root — outside
``knowledge/`` so the skill/template scanners never pick them up. The commit
stages only the files the round actually edited plus the report; never
``git add -A``, so even a guardrail bug cannot commit stray changes.
"""

from __future__ import annotations

import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from optimizer.guardrails import REPO_ROOT
from optimizer.loop import OptimizerResult

REPORTS_DIR = REPO_ROOT / "optimizer_reports"


def write_report(result: OptimizerResult, focus: str, *, propose_only: bool) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
    REPORTS_DIR.mkdir(exist_ok=True)
    path = REPORTS_DIR / f"{ts}_optimization.md"

    lines = [
        f"# Optimization round — {ts} UTC",
        "",
        f"- mode: {'propose-only' if propose_only else 'apply'}",
        f"- iterations: {result.iterations} | finished cleanly: {result.finished}",
        f"- optimizer cost: {result.usage['input_tokens']} in / "
        f"{result.usage['output_tokens']} out tokens over {result.usage['llm_calls']} calls",
        f"- git HEAD at round start: {git_head() or 'n/a'}",
        "",
        "## Focus",
        focus.strip(),
        "",
        "## Sessions analyzed",
    ]
    for d in result.digests:
        tok = d.usage_totals.get("total_tokens") if d.usage_totals else None
        lines.append(
            f"- `{d.session_dir}` — outcome: {d.terminal_state or 'unknown'}, "
            f"replans: {d.replan_count}, tokens: {tok if tok is not None else '?'}"
            + (f", score: {d.score}" if d.score else "")
        )

    lines += ["", f"## Edits ({len(result.edits)})"]
    if not result.edits:
        lines.append("_No edits made this round._")
    for rec in result.edits:
        lines += [
            "",
            f"### {rec.path.relative_to(REPO_ROOT)}",
            "```diff",
            rec.diff,
            "```",
        ]

    lines += ["", "## Optimizer report", result.final_report or "_(none — loop ended without finish())_", ""]
    path.write_text("\n".join(lines))
    return path


def git_head() -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10,
        )
        return out.stdout.strip() or None
    except Exception:
        return None


def commit_round(edited_paths: list[Path], report_path: Path, summary: str) -> str | None:
    """Commit the round's knowledge edits + report. Returns the new HEAD, or None."""
    to_stage = [str(p) for p in dict.fromkeys(edited_paths)] + [str(report_path)]
    try:
        subprocess.run(
            ["git", "-C", str(REPO_ROOT), "add", "--"] + to_stage,
            check=True, capture_output=True, text=True, timeout=30,
        )
        body = "\n".join(f"- {Path(p).relative_to(REPO_ROOT)}" for p in dict.fromkeys(edited_paths))
        subprocess.run(
            ["git", "-C", str(REPO_ROOT), "commit", "-m", f"optimizer: {summary}", "-m", body or "(report only)"],
            check=True, capture_output=True, text=True, timeout=30,
        )
    except subprocess.CalledProcessError as e:
        logging.error("optimizer git commit failed: %s", e.stderr or e)
        return None
    return git_head()


def knowledge_is_dirty() -> bool:
    """True if knowledge/ has uncommitted changes (preflight warning, not fatal)."""
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "status", "--porcelain", "--", "knowledge"],
            capture_output=True, text=True, timeout=10,
        )
        return bool(out.stdout.strip())
    except Exception:
        return False
