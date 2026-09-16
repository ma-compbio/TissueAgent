"""Prompt templates and description for the planner agent.

See create_planner_state_update() in graph/plan_output.py for output parsing and state transition
logic.
"""

from pathlib import Path

from agents.agent_utils import parse_yaml_frontmatter, substitute_shared_prompts
from knowledge import PLANS_DIR

_DIR = Path(__file__).parent


def _build_template_index() -> str:
    """Build a compact template listing from YAML frontmatter in .md files."""
    lines: list[str] = []
    for p in sorted(PLANS_DIR.glob("*.md")):
        frontmatter = parse_yaml_frontmatter(p.read_text())
        if frontmatter is None:
            continue
        # Accept both spellings: plans conventionally use "enabled", skills "enable".
        # Absent status defaults to enabled so a new template is never silently dropped.
        if str(frontmatter.get("status", "enabled")).strip().lower() not in ("enabled", "enable"):
            continue
        name = frontmatter.get("name", p.stem)
        desc = frontmatter.get("description", "").strip()
        lines.append(f"- **{name}**: {desc}")
    return "\n".join(lines)


def _render(filename: str) -> str:
    """Read a planner prompt file and substitute the template registry + shared blocks."""
    base = (_DIR / filename).read_text()
    base = base.replace("{{plan_template_registry}}", _build_template_index())
    return substitute_shared_prompts(base)


PlannerPrompt = _render("prompt.txt")
PlannerReplanPrompt = _render("replan_prompt.txt")
