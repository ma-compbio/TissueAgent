"""Prompt templates and description for the evaluator agent."""

from pathlib import Path

_DIR = Path(__file__).parent


def _read(filename: str) -> str:
    return (_DIR / filename).read_text()


EvaluatorDescription = """
Evaluates the plan execution results and determines if the user query has been satisfactorily addressed.
""".strip()

EvaluatorPrompt = _read("prompt.txt")
