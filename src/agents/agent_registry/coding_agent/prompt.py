"""Prompt templates and description for the coding agent."""

from pathlib import Path

_DIR = Path(__file__).parent


def _read(filename: str) -> str:
    return (_DIR / filename).read_text()


def CodingAgentPrompt(sandbox_enabled: bool = True) -> str:
    """Build the coding agent system prompt.

    When ``sandbox_enabled`` is False the no-sandbox variant is used, which
    adds an explicit file-access policy restricting the agent to /workspace.
    """
    template_file = (
        "coding_agent_prompt.txt"
        if sandbox_enabled
        else "coding_agent_prompt_no_sandbox.txt"
    )
    return _read(template_file)


CodingAgentDescription = _read("coding_agent_description.txt").strip()
