"""Prompt templates and description for the reporter agent."""

from pathlib import Path

_DIR = Path(__file__).parent

_TEMPLATE = (_DIR / "prompt.txt").read_text()

ReporterDescription = """
Package results into a human-readable report with clear artifact paths, versioning, and minimal narrative.
""".strip()

# Note: the prompt content describes the project workspace layout
# (``library/...``, ``project/outputs/...``) rather than baking a
# specific ``DATA_DIR`` into the text, so no substitution is needed.
ReporterPrompt = _TEMPLATE
