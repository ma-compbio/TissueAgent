"""Prompt templates and description for the planner agent."""

from pathlib import Path

_DIR = Path(__file__).parent


def _read(filename: str) -> str:
    return (_DIR / filename).read_text()


PlannerDescription = """
Turn a user query into a minimal, quality-gated multi-step plan by retrieving/adapting a template from the Plan Registry; if none fits, instantiate a new plan from a generic template.
Return ONLY a human-readable Planning Checklist. Do NOT assign agents or tools.
""".strip()

PlannerPrompt = _read("prompt.txt")
