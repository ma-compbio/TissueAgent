"""LangChain tools for the optimizer loop.

Every tool closes over one :class:`OptimizerContext`. Reads are paged and
size-capped so the model can drill into multi-megabyte traces without blowing
its context; writes go through the guardrails in :mod:`optimizer.guardrails`
and are validated (and reverted on failure) immediately.
"""

from __future__ import annotations

import difflib
import json
from dataclasses import dataclass, field
from pathlib import Path

from langchain_core.tools import StructuredTool

from agents.agent_utils import parse_yaml_frontmatter
from knowledge import PLANS_DIR, SKILLS_DIR
from optimizer import guardrails
from optimizer.session_digest import SessionDigest, _content_text, render_digest

_READ_CAP = 3000  # max chars any read tool returns per call


@dataclass
class EditRecord:
    path: Path
    diff: str
    original_text: str  # full pre-edit content of the first edit to this path


@dataclass
class OptimizerContext:
    digests: list[SessionDigest]
    propose_only: bool = False
    edits: list[EditRecord] = field(default_factory=list)
    finished: bool = False
    final_report: str = ""
    _trace_cache: dict[int, str] = field(default_factory=dict)

    def session_dir(self, index: int) -> Path:
        if not 1 <= index <= len(self.digests):
            raise ValueError(f"session_index must be 1..{len(self.digests)}")
        return self.digests[index - 1].session_dir

    def revert_all_edits(self) -> None:
        """Restore every edited file to its pre-round content (propose-only mode)."""
        originals: dict[Path, str] = {}
        for rec in self.edits:
            originals.setdefault(rec.path, rec.original_text)
        for path, text in originals.items():
            path.write_text(text)


def build_tools(ctx: OptimizerContext) -> list[StructuredTool]:
    def list_sessions() -> str:
        return "\n\n".join(
            f"[{i}] " + render_digest(d, max_chars=2000) for i, d in enumerate(ctx.digests, 1)
        )

    def read_trace(
        session_index: int, query: str = "", offset: int = 0, limit_chars: int = _READ_CAP
    ) -> str:
        limit_chars = min(limit_chars, _READ_CAP)
        corpus = _trace_corpus(ctx, session_index)
        if query:
            lines = corpus.splitlines()
            hits = [i for i, ln in enumerate(lines) if query.lower() in ln.lower()]
            if not hits:
                return f"0 matches for {query!r} in session {session_index}'s trace."
            windows = []
            for i in hits[offset : offset + 5]:
                lo, hi = max(0, i - 3), min(len(lines), i + 4)
                windows.append(f"--- line {i} ---\n" + "\n".join(lines[lo:hi]))
            body = "\n".join(windows)[:limit_chars]
            return (
                f"{len(hits)} matches for {query!r} (showing {offset}..{offset + 5}; "
                f"pass offset={offset + 5} for more)\n{body}"
            )
        chunk = corpus[offset : offset + limit_chars]
        nxt = offset + limit_chars
        tail = f"\n[chars {offset}..{nxt} of {len(corpus)}; next offset={nxt}]" if nxt < len(corpus) else "\n[end of trace]"
        return chunk + tail

    def read_artifact(
        session_index: int, relpath: str, offset: int = 0, limit_chars: int = _READ_CAP
    ) -> str:
        limit_chars = min(limit_chars, _READ_CAP)
        out_dir = (ctx.session_dir(session_index) / "outputs").resolve()
        target = (out_dir / relpath.removeprefix("project/outputs/")).resolve()
        if not target.is_relative_to(out_dir):
            return f"error: '{relpath}' escapes the session's outputs/ directory."
        if not target.is_file():
            return f"error: '{relpath}' not found under outputs/."
        try:
            text = target.read_text(errors="replace")
        except OSError as e:
            return f"error reading '{relpath}': {e}"
        if target.suffix.lower() == ".csv":
            lines = text.splitlines()
            head = "\n".join(lines[:25])[:limit_chars]
            return f"CSV, {len(lines)} rows (incl. header). First rows:\n{head}"
        chunk = text[offset : offset + limit_chars]
        more = f"\n[chars {offset}..{offset + limit_chars} of {len(text)}]" if len(text) > offset + limit_chars else ""
        return chunk + more

    def list_knowledge() -> str:
        lines = ["## Plan templates (knowledge/plans/)"]
        for p in sorted(PLANS_DIR.glob("*.md")):
            if p.name.lower() == "readme.md":
                continue
            fm = _fm_or_empty(p)
            lines.append(
                f"- {p.relative_to(guardrails.REPO_ROOT)} | name={fm.get('name', p.stem)} "
                f"| status={fm.get('status', 'enabled')}"
            )
        lines.append("\n## Skills (knowledge/skills/)")
        for p in guardrails._skill_registry_markdown(SKILLS_DIR):
            fm = _fm_or_empty(p)
            lines.append(
                f"- {p.relative_to(guardrails.REPO_ROOT)} | name={fm.get('name', p.parent.name)} "
                f"| status={fm.get('status', 'enable')} | applies_to={fm.get('applies_to', [])}"
            )
        return "\n".join(lines)

    def read_knowledge_file(relpath: str) -> str:
        raw = Path(relpath)
        if not raw.is_absolute():
            raw = guardrails.REPO_ROOT / raw
        resolved = raw.resolve()
        # Reading is broader than editing: scripts/references may be read
        # (the optimizer needs them to document contracts correctly), just
        # never edited.
        if not any(resolved.is_relative_to(r) for r in guardrails.ALLOWED_ROOTS):
            return "error: only files under knowledge/skills/ and knowledge/plans/ are readable."
        if not resolved.is_file():
            return f"error: '{relpath}' not found."
        return resolved.read_text(errors="replace")

    def edit_knowledge_file(relpath: str, old_str: str, new_str: str) -> str:
        if len(ctx.edits) >= guardrails.MAX_EDITS_PER_ROUND:
            return (
                f"error: edit budget exhausted ({guardrails.MAX_EDITS_PER_ROUND} edits this "
                "round). Call finish() with your report."
            )
        try:
            path = guardrails.resolve_editable(relpath)
            guardrails.check_edit_size(old_str, new_str)
        except guardrails.GuardrailError as e:
            return f"error: {e}"
        original = path.read_text()
        n = original.count(old_str)
        if n == 0:
            return "error: old_str not found in file (must match exactly, including whitespace)."
        if n > 1:
            return f"error: old_str matches {n} times; add surrounding context to make it unique."
        updated = original.replace(old_str, new_str, 1)
        path.write_text(updated)
        problems = guardrails.validate_knowledge()
        if problems:
            path.write_text(original)  # revert — never leave the registry broken
            return "error: edit reverted, it broke the knowledge registry:\n" + "\n".join(problems)
        diff = "\n".join(
            difflib.unified_diff(
                original.splitlines(), updated.splitlines(),
                fromfile=str(path), tofile=str(path), lineterm="",
            )
        )
        ctx.edits.append(EditRecord(path=path, diff=diff, original_text=original))
        return f"ok: edit applied to {path.relative_to(guardrails.REPO_ROOT)} and registry re-validated."

    def finish(report_markdown: str) -> str:
        ctx.finished = True
        ctx.final_report = report_markdown
        return "done"

    return [
        StructuredTool.from_function(
            list_sessions,
            name="list_sessions",
            description="Summaries of every session under analysis (digest per session).",
        ),
        StructuredTool.from_function(
            read_trace,
            name="read_trace",
            description=(
                "Read a session's full conversation trace (main loop + sub-agent transcripts), "
                "paged. Pass query='...' to grep it (returns matching windows + total count), "
                "or offset/limit_chars to page sequentially. session_index is 1-based, "
                "as shown by list_sessions. Returns at most 3000 chars per call."
            ),
        ),
        StructuredTool.from_function(
            read_artifact,
            name="read_artifact",
            description=(
                "Read a file the run produced, by path relative to the session's outputs/ "
                "(e.g. 'ccc_ensemble.csv' or 'logs/ccc_data_prep.json'). CSVs show shape + head."
            ),
        ),
        StructuredTool.from_function(
            list_knowledge,
            name="list_knowledge",
            description="List all plan templates and skills with their file paths and status.",
        ),
        StructuredTool.from_function(
            read_knowledge_file,
            name="read_knowledge_file",
            description=(
                "Read a file under knowledge/skills/ or knowledge/plans/ (repo-relative path). "
                "Skill scripts may be read for context but are frozen — never editable."
            ),
        ),
        StructuredTool.from_function(
            edit_knowledge_file,
            name="edit_knowledge_file",
            description=(
                "Apply one exact str-replace to a skill or plan-template .md file "
                "(repo-relative path). old_str must occur exactly once. The knowledge "
                "registry is re-validated after every edit; a breaking edit is auto-reverted. "
                "Keep edits small and surgical."
            ),
        ),
        StructuredTool.from_function(
            finish,
            name="finish",
            description=(
                "End the optimization round. report_markdown: the failure modes found, each "
                "edit made and why, and the expected effect on success rate / token usage."
            ),
        ),
    ]


def _trace_corpus(ctx: OptimizerContext, session_index: int) -> str:
    if session_index in ctx._trace_cache:
        return ctx._trace_cache[session_index]
    chat = json.loads((ctx.session_dir(session_index) / ".chat.json").read_text())
    parts: list[str] = []
    for i, m in enumerate(chat.get("messages", [])):
        parts.append(f"[main #{i} {m.get('type')}] {_content_text(m.get('data', {}).get('content'))}")
    for tool_id, entry in (chat.get("subagent_states") or {}).items():
        try:
            agent_name, final_state = entry[0], entry[1]
            messages = final_state.get("messages", [])
        except (TypeError, IndexError, AttributeError):
            continue
        for i, m in enumerate(messages):
            parts.append(
                f"[subagent {agent_name}/{tool_id} #{i} {m.get('type')}] "
                f"{_content_text(m.get('data', {}).get('content'))}"
            )
    corpus = "\n".join(parts)
    ctx._trace_cache[session_index] = corpus
    return corpus


def _fm_or_empty(p: Path) -> dict:
    try:
        return parse_yaml_frontmatter(p.read_text()) or {}
    except Exception:
        return {}
