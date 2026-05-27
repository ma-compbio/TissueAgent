"""Prompt templates and description for the coding agent."""

from pathlib import Path

_DIR = Path(__file__).parent


def _read(filename: str) -> str:
    return (_DIR / filename).read_text()


RetrievalAgentPrompt = _read("retrieval_agent_prompt.txt")


def ExecutionAgentPrompt(retrieval_plan: str) -> str:
    """Build the execution agent system prompt with the retrieval plan injected."""
    template = _read("execution_agent_prompt.txt")
    return template.replace("{retrieval_plan}", retrieval_plan)


CodingAgentDescription = _read("coding_agent_description.txt").strip()
