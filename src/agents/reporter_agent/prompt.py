"""Prompt templates and description for the reporter agent."""

from pathlib import Path

from agents.agent_utils import substitute_shared_prompts

_DIR = Path(__file__).parent

ReporterDescription = """
Package results into a human-readable report with clear artifact paths, versioning, and minimal narrative.
""".strip()

ReporterPrompt = substitute_shared_prompts((_DIR / "prompt.txt").read_text())
