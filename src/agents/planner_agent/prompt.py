"""Prompt templates and description for the planner agent."""

from pathlib import Path

import yaml

from knowledge import PLANS_DIR

_DIR = Path(__file__).parent


def _read(filename: str) -> str:
    return (_DIR / filename).read_text()


def _build_template_index() -> str:
    """Build a compact template listing from YAML frontmatter in .md files."""
    lines: list[str] = []
    for p in sorted(PLANS_DIR.glob("*.md")):
        text = p.read_text()
        if not text.startswith("---"):
            continue
        end = text.index("---", 3)
        frontmatter = yaml.safe_load(text[3:end])
        if frontmatter.get("status") != "enabled":
            continue
        name = frontmatter.get("name", p.stem)
        desc = frontmatter.get("description", "").strip()
        lines.append(f"- **{name}**: {desc}")
    return "\n".join(lines)


def _build_planner_prompt() -> str:
    base = _read("prompt.txt")
    return base.replace("{{plan_template_registry}}", _build_template_index())


PlannerDescription = """
Turn a user query into a minimal, quality-gated multi-step plan by retrieving/adapting a template from the Plan Registry; if none fits, instantiate a new plan from a generic template.
Return ONLY a human-readable Planning Checklist. Do NOT assign agents or tools.
""".strip()

PlannerPrompt = _build_planner_prompt()
