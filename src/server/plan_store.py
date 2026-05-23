"""Plan store: reads, writes, and parses the evolving plan markdown file.

The "evolving plan" is the single artifact that describes what TissueAgent
is about to do or is currently doing. It is authored cooperatively:

* The **planner** writes the skeleton via the ``write_plan`` tool. Each
  step carries a title, description, reasoning, and expected artifacts.
* The **recruiter** annotates each step via the ``assign_agents`` tool,
  adding an ``assigned_agent`` and an ``assignment_rationale``.
* The **manager** (phase 2) updates each step's ``status`` and records
  the ``actual_outputs`` as work completes.

On disk the plan is a markdown file under ``sessions/active/plan.md``.
Each step is a ``## Step N — <title>`` heading followed by a YAML code
fence holding the structured fields, then prose ``Description:`` and
``Reasoning:`` paragraphs. This format is human-readable in any editor
and machine-parseable without regex gymnastics.

A single global :class:`PlanStore` is exposed as :data:`plan_store`.
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

import yaml

from config import SESSIONS_DIR


PlanDocStatus = Literal[
    "empty",     # no plan yet
    "draft",     # planner has written; recruiter has not annotated
    "recruited", # recruiter has annotated all steps
    "approved",  # user has reviewed and approved (phase 2)
    "running",   # manager is executing (phase 2)
    "paused",    # user paused execution (phase 3)
    "done",
    "failed",
]

StepStatus = Literal[
    "pending", "running", "done", "skipped", "failed",
]


@dataclass
class PlanStep:
    """One step of the evolving plan."""

    id: int
    title: str
    description: str = ""
    reasoning: str = ""
    expected_artifacts: List[str] = field(default_factory=list)
    assigned_agent: Optional[str] = None
    assignment_rationale: Optional[str] = None
    status: StepStatus = "pending"
    actual_outputs: List[str] = field(default_factory=list)


@dataclass
class PlanDocument:
    """The whole plan as a structured object."""

    status: PlanDocStatus = "empty"
    user_request: str = ""
    steps: List[PlanStep] = field(default_factory=list)

    def to_markdown(self) -> str:
        """Serialise to the on-disk markdown form."""
        out: List[str] = []
        out.append("# Plan")
        out.append("")
        header = {
            "status": self.status,
            "user_request": _block_string(self.user_request),
        }
        out.append("```yaml")
        out.append(yaml.safe_dump(
            header, sort_keys=False, allow_unicode=True
        ).rstrip())
        out.append("```")
        out.append("")
        for step in self.steps:
            out.append(f"## Step {step.id} — {step.title}")
            out.append("")
            step_yaml = {
                "status": step.status,
                "assigned_agent": step.assigned_agent,
                "assigned_rationale": step.assignment_rationale,
                "expected_artifacts": list(step.expected_artifacts),
                "actual_outputs": list(step.actual_outputs),
            }
            out.append("```yaml")
            out.append(yaml.safe_dump(
                step_yaml, sort_keys=False, allow_unicode=True
            ).rstrip())
            out.append("```")
            if step.description:
                out.append("")
                out.append(f"**Description:** {step.description}")
            if step.reasoning:
                out.append("")
                out.append(f"**Reasoning:** {step.reasoning}")
            out.append("")
        return "\n".join(out).rstrip() + "\n"


def _block_string(s: str) -> str:
    """Trim trailing whitespace so YAML serialises cleanly."""
    return s.strip()


# --- parsing ---------------------------------------------------------

_HEADER_FENCE = re.compile(r"```yaml\s*\n(.*?)\n```", re.DOTALL)
_STEP_PATTERN = re.compile(
    r"^## Step\s+(\d+)\s*—\s*(.+?)$",
    re.MULTILINE,
)


def _parse_markdown(text: str) -> PlanDocument:
    """Parse the markdown form back into a :class:`PlanDocument`.

    Best-effort: missing fields are filled with defaults. Errors don't
    raise — they're surfaced via ``status="failed"`` so the UI can show
    something rather than crash.
    """
    doc = PlanDocument()
    if not text.strip():
        return doc

    # 1. Header YAML (first fenced block before any step heading).
    first_step_match = _STEP_PATTERN.search(text)
    head_end = first_step_match.start() if first_step_match else len(text)
    head_text = text[:head_end]
    header_match = _HEADER_FENCE.search(head_text)
    if header_match:
        try:
            header = yaml.safe_load(header_match.group(1)) or {}
            doc.status = str(header.get("status", "empty"))  # type: ignore[assignment]
            doc.user_request = str(header.get("user_request", ""))
        except yaml.YAMLError:
            pass

    # 2. Steps.
    step_iter = list(_STEP_PATTERN.finditer(text))
    for i, m in enumerate(step_iter):
        step_id = int(m.group(1))
        title = m.group(2).strip()
        start = m.end()
        end = step_iter[i + 1].start() if i + 1 < len(step_iter) else len(text)
        section = text[start:end]

        step = PlanStep(id=step_id, title=title)
        fence = _HEADER_FENCE.search(section)
        if fence:
            try:
                data = yaml.safe_load(fence.group(1)) or {}
            except yaml.YAMLError:
                data = {}
            step.status = data.get("status", "pending")  # type: ignore[assignment]
            step.assigned_agent = data.get("assigned_agent")
            step.assignment_rationale = data.get("assigned_rationale")
            step.expected_artifacts = list(data.get("expected_artifacts") or [])
            step.actual_outputs = list(data.get("actual_outputs") or [])

        # Description / Reasoning paragraphs.
        desc_match = re.search(
            r"\*\*Description:\*\*\s*(.+?)(?=\n\*\*|\Z)",
            section,
            re.DOTALL,
        )
        if desc_match:
            step.description = desc_match.group(1).strip()
        rsn_match = re.search(
            r"\*\*Reasoning:\*\*\s*(.+?)(?=\n\*\*|\Z)",
            section,
            re.DOTALL,
        )
        if rsn_match:
            step.reasoning = rsn_match.group(1).strip()

        doc.steps.append(step)

    return doc


# --- store -----------------------------------------------------------

# For phase 1 we keep a single "active" plan. Later this becomes
# sessions/<session_id>/plan.md once sessions gain stable IDs.
_DEFAULT_PLAN_DIR = SESSIONS_DIR / "active"


class PlanStore:
    """Thread-safe accessor for the on-disk plan document.

    Phase 1 keeps a single plan in ``sessions/active/plan.md``.
    """

    def __init__(self, plan_dir: Path = _DEFAULT_PLAN_DIR) -> None:
        self._lock = threading.Lock()
        self._dir = plan_dir
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        """Create the plan directory if missing.

        The FastAPI lifespan calls ``reset_data_directories()`` at startup
        which wipes ``sessions/`` — including the directory this store
        created at import time. Every read/write/reset must therefore
        re-create the directory rather than assume it exists.
        """
        self._dir.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self._dir / "plan.md"

    def read(self) -> PlanDocument:
        """Load the plan from disk; returns an empty document if absent."""
        with self._lock:
            if not self.path.is_file():
                return PlanDocument()
            text = self.path.read_text(encoding="utf-8", errors="replace")
        return _parse_markdown(text)

    def read_markdown(self) -> str:
        """Return the raw markdown (empty string if no plan yet)."""
        with self._lock:
            if not self.path.is_file():
                return ""
            return self.path.read_text(encoding="utf-8", errors="replace")

    def write(self, doc: PlanDocument) -> str:
        """Persist *doc* to disk and return the markdown that was written."""
        markdown = doc.to_markdown()
        with self._lock:
            self._ensure_dir()
            self.path.write_text(markdown, encoding="utf-8")
        return markdown

    def write_markdown(self, markdown: str) -> None:
        """Persist arbitrary markdown text (used when the user edits)."""
        with self._lock:
            self._ensure_dir()
            self.path.write_text(markdown, encoding="utf-8")

    def reset(self) -> None:
        """Drop the current plan. Called at the start of each new run."""
        with self._lock:
            self._ensure_dir()
            if self.path.is_file():
                self.path.unlink()


# Singleton instance — the rest of the codebase imports this.
plan_store = PlanStore()


def serialize_plan(doc: PlanDocument) -> Dict[str, Any]:
    """Return *doc* as a JSON-friendly dict for the wire format."""
    return {
        "status": doc.status,
        "user_request": doc.user_request,
        "steps": [asdict(s) for s in doc.steps],
    }
