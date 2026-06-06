"""Prompt templates and description for the reporter agent."""

from pathlib import Path

from config import DATA_DIR

_DIR = Path(__file__).parent

_TEMPLATE = (_DIR / "prompt.txt").read_text()

ReporterDescription = """
Package results into a human-readable report with clear artifact paths, versioning, and minimal narrative.
""".strip()

ReporterPrompt = _TEMPLATE.replace("{data_dir}", str(DATA_DIR))
