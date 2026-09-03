"""Deterministic compression of an archived session into a failure-mode digest.

A session directory is ``projects/<id>/`` (or a harness copy of it): a
``.chat.json`` conversation archive, an ``outputs/`` artifact tree, and —
when the harness captured it via ``--metrics-out`` — a ``metrics.json``.
The digest is built entirely in code (no LLM) and hard-capped in size so a
handful of sessions fit comfortably in the optimizer's opening prompt; the
model drills into specifics with its paged ``read_trace`` tool.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

_YAML_FENCE = re.compile(r"```yaml\n(.*?)```", re.S)
_STEP_HEADING = re.compile(r"^## Step (\d+)\s*[—-]\s*(.+)$", re.M)

_ERROR_MARKERS = ("Traceback (most recent call last)", "ERROR", "Error:", "error:")
_EXCERPT_CHARS = 400
_MAX_FAILURES = 8
_MAX_LIST_ITEMS = 30


@dataclass
class SessionDigest:
    session_dir: Path
    project_id: str
    prompt: str = ""
    template_names: list[str] = field(default_factory=list)
    terminal_state: str | None = None
    plan_status: str | None = None
    plan_steps: list[dict] = field(default_factory=list)
    replan_count: int = 0
    replan_reasons: list[str] = field(default_factory=list)
    evaluator_verdicts: list[str] = field(default_factory=list)
    executor_failures: list[dict] = field(default_factory=list)
    usage_totals: dict = field(default_factory=dict)
    artifacts_present: list[str] = field(default_factory=list)
    artifacts_missing: list[str] = field(default_factory=list)
    score: dict | None = None  # injected by the benchmark harness, not loaded


def load_session_digest(session_dir: Path) -> SessionDigest:
    session_dir = Path(session_dir)
    chat_path = session_dir / ".chat.json"
    if not chat_path.is_file():
        raise FileNotFoundError(
            f"{session_dir} has no .chat.json — not a TissueAgent session directory"
        )
    chat = json.loads(chat_path.read_text())

    d = SessionDigest(session_dir=session_dir, project_id=session_dir.name)
    d.prompt = _first_human_text(chat.get("messages", []))
    d.replan_count = int(chat.get("replan_count") or 0)

    header, steps = _parse_plan_markdown(chat.get("plan_markdown") or "")
    d.plan_status = header.get("status")
    provenance = header.get("provenance") or {}
    d.template_names = [str(t) for t in (provenance.get("template_names") or [])]
    d.plan_steps = steps

    metrics_path = session_dir / "metrics.json"
    if metrics_path.is_file():
        _fold_in_metrics(d, json.loads(metrics_path.read_text()))
    else:
        d.terminal_state = d.plan_status

    d.executor_failures = _mine_failures(chat.get("subagent_states") or {})
    d.artifacts_present, d.artifacts_missing = _artifact_audit(session_dir, steps)

    score_path = session_dir / "score.json"  # benchmark harness drops this in
    if score_path.is_file():
        try:
            d.score = json.loads(score_path.read_text())
        except (OSError, json.JSONDecodeError):
            pass
    return d


def render_digest(d: SessionDigest, max_chars: int = 5000) -> str:
    """One session as compact markdown, hard-capped at ``max_chars``."""
    lines: list[str] = [f"### Session {d.project_id}"]
    lines.append(f"- prompt: {_clip(d.prompt, 300)}")
    lines.append(f"- template(s): {', '.join(d.template_names) or '(none recorded)'}")
    lines.append(
        f"- outcome: {d.terminal_state or 'unknown'} | replans: {d.replan_count}"
    )
    if d.usage_totals:
        u = d.usage_totals
        lines.append(
            f"- tokens: {u.get('total_tokens', '?')} total "
            f"({u.get('input_tokens', '?')} in / {u.get('output_tokens', '?')} out), "
            f"{u.get('llm_calls', '?')} LLM calls"
        )
    if d.score:
        lines.append(f"- benchmark score: {json.dumps(d.score)}")

    if d.plan_steps:
        lines.append("- steps (id | title | agent | skills | status | retries | tokens):")
        for s in d.plan_steps:
            tok = s.get("total_tokens")
            lines.append(
                f"  - {s.get('id')} | {_clip(s.get('title', ''), 60)} | "
                f"{s.get('assigned_agent', '?')} | {','.join(s.get('skills') or []) or '-'} | "
                f"{s.get('status', '?')} | r{s.get('retry_count', 0)}"
                + (f" | {tok} tok" if tok is not None else "")
            )

    if d.replan_reasons:
        lines.append("- replan reasons:")
        lines.extend(f"  - {_clip(r, 200)}" for r in d.replan_reasons[:5])
    if d.evaluator_verdicts:
        lines.append(f"- evaluator verdicts: {', '.join(d.evaluator_verdicts[:12])}")

    if d.executor_failures:
        lines.append("- error excerpts from sub-agent transcripts:")
        for f_ in d.executor_failures:
            lines.append(f"  - [{f_['agent']}] {_clip(f_['excerpt'], _EXCERPT_CHARS)}")

    if d.artifacts_missing:
        lines.append(f"- MISSING expected artifacts: {', '.join(d.artifacts_missing[:15])}")
    lines.append(
        f"- artifacts present ({len(d.artifacts_present)}): "
        f"{', '.join(d.artifacts_present[:_MAX_LIST_ITEMS])}"
        + (" …" if len(d.artifacts_present) > _MAX_LIST_ITEMS else "")
    )

    text = "\n".join(lines)
    return text[: max_chars - 2] + " …" if len(text) > max_chars else text


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _first_human_text(messages: list[dict]) -> str:
    for m in messages:
        if m.get("type") == "human":
            return _content_text(m.get("data", {}).get("content"))
    return ""


def _content_text(content) -> str:
    """LangChain message content is either a string or a list of blocks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "\n".join(parts)
    return str(content or "")


def _parse_plan_markdown(pm: str) -> tuple[dict, list[dict]]:
    """Split plan.md into (header dict, step dicts with titles).

    The plan carries one ```yaml fence for the header (status, user_request,
    provenance) and one per step, each preceded by a ``## Step N — title``
    heading. YAML that fails to parse is skipped rather than fatal — the
    digest degrades, it never crashes on a malformed plan.
    """
    if not pm:
        return {}, []
    fences = [(m.start(), m.group(1)) for m in _YAML_FENCE.finditer(pm)]
    headings = [(m.start(), int(m.group(1)), m.group(2).strip()) for m in _STEP_HEADING.finditer(pm)]

    header: dict = {}
    steps: list[dict] = []
    for pos, raw in fences:
        try:
            data = yaml.safe_load(raw)
        except yaml.YAMLError:
            continue
        if not isinstance(data, dict):
            continue
        preceding = [(hpos, hid, htitle) for hpos, hid, htitle in headings if hpos < pos]
        if not preceding:
            header = data
            continue
        _, step_id, title = preceding[-1]
        steps.append(
            {
                "id": step_id,
                "title": title,
                "status": data.get("status"),
                "retry_count": data.get("retry_count", 0),
                "assigned_agent": data.get("assigned_agent"),
                "skills": list(data.get("skills") or []),
                "expected_artifacts": list(data.get("expected_artifacts") or []),
                "actual_outputs": list(data.get("actual_outputs") or []),
            }
        )
    return header, steps


def _fold_in_metrics(d: SessionDigest, metrics: dict) -> None:
    outcome = metrics.get("outcome") or {}
    d.terminal_state = outcome.get("terminal_state") or d.plan_status

    usage = metrics.get("usage") or {}
    d.usage_totals = {
        k: usage.get(k)
        for k in ("input_tokens", "output_tokens", "total_tokens", "llm_calls", "llm_time_seconds")
    }
    by_step = {s.get("step_id"): s for s in (usage.get("by_step") or []) if isinstance(s, dict)}
    for step in d.plan_steps:
        u = by_step.get(step["id"])
        if u:
            step["total_tokens"] = (u.get("input_tokens") or 0) + (u.get("output_tokens") or 0)
            step["llm_calls"] = u.get("llm_calls")

    loops = metrics.get("loops") or {}
    d.replan_count = loops.get("replans_triggered", d.replan_count)
    d.replan_reasons = [str(r) for r in (loops.get("replan_reasons") or [])][:5]
    verdicts = loops.get("evaluator_verdicts")
    if isinstance(verdicts, dict):
        d.evaluator_verdicts = [f"{k}×{v}" for k, v in verdicts.items()]
    elif isinstance(verdicts, list):
        d.evaluator_verdicts = [str(v) for v in verdicts][:12]


def _mine_failures(subagent_states: dict) -> list[dict]:
    """Last error-looking tool output per sub-agent invocation, truncated."""
    failures: list[dict] = []
    for entry in subagent_states.values():
        try:
            agent_name, final_state = entry[0], entry[1]
            messages = final_state.get("messages", [])
        except (TypeError, IndexError, AttributeError):
            continue
        excerpt = None
        for m in messages:
            if m.get("type") != "tool":
                continue
            data = m.get("data", {})
            text = _content_text(data.get("content"))
            if data.get("status") == "error" or any(mk in text for mk in _ERROR_MARKERS):
                excerpt = text[-_EXCERPT_CHARS:]
        if excerpt:
            failures.append({"agent": agent_name, "excerpt": excerpt})
        if len(failures) >= _MAX_FAILURES:
            break
    return failures


def _artifact_audit(session_dir: Path, steps: list[dict]) -> tuple[list[str], list[str]]:
    out_dir = session_dir / "outputs"
    present = (
        sorted(str(p.relative_to(out_dir)) for p in out_dir.rglob("*") if p.is_file())
        if out_dir.is_dir()
        else []
    )
    present_set = set(present)
    missing: list[str] = []
    for step in steps:
        for exp in step.get("expected_artifacts", []):
            rel = exp.removeprefix("project/outputs/")
            if rel not in present_set and exp not in present_set:
                missing.append(exp)
    return present, missing


def _clip(text: str, n: int) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= n else text[: n - 2] + " …"
