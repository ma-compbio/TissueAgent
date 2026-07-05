"""Prompt templates and description for the coding agent."""

from pathlib import Path

from agents.agent_utils import substitute_shared_prompts

_DIR = Path(__file__).parent


def _render(filename: str) -> str:
    """Read a coding-agent prompt file and substitute shared prompt blocks."""
    return substitute_shared_prompts((_DIR / filename).read_text())


def CodingAgentPrompt(sandbox_enabled: bool = True) -> str:
    """Build the coding agent system prompt.

    When ``sandbox_enabled`` is False the no-sandbox variant is used, which adds an explicit
    file-access policy restricting the agent to the workspace root.
    """
    filename = (
        "coding_agent_prompt.txt"
        if sandbox_enabled
        else "coding_agent_prompt_no_sandbox.txt"
    )
    return _render(filename)


CodingAgentDescription = (_DIR / "coding_agent_description.txt").read_text().strip()
