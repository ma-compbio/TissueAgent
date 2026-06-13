"""Prompt templates and description for the planner agent.

See planner_state_update(response) in graph/plan_output.py for output parsing and state transition
logic.
"""

from pathlib import Path

from agents.agent_utils import parse_yaml_frontmatter
from knowledge import PLANS_DIR


def _build_template_index() -> str:
    """Build a compact template listing from YAML frontmatter in .md files."""
    lines: list[str] = []
    for p in sorted(PLANS_DIR.glob("*.md")):
        frontmatter = parse_yaml_frontmatter(p.read_text())
        if frontmatter is None or frontmatter.get("status") != "enabled":
            continue
        name = frontmatter.get("name", p.stem)
        desc = frontmatter.get("description", "").strip()
        lines.append(f"- **{name}**: {desc}")
    return "\n".join(lines)


def _build_planner_prompt() -> str:
    prompt_path = Path(__file__).parent / "prompt.txt"
    base = prompt_path.read_text()
    return base.replace("{{plan_template_registry}}", _build_template_index())


PlannerPrompt = _build_planner_prompt()
