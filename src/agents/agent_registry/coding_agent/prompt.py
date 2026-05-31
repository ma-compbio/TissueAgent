"""Prompt templates and description for the coding agent."""

from pathlib import Path

_DIR = Path(__file__).parent


def _read(filename: str) -> str:
    return (_DIR / filename).read_text()


RetrievalAgentPrompt = _read("retrieval_agent_prompt.txt")


def ExecutionAgentPrompt(retrieval_plan: str, sandbox_enabled: bool = True) -> str:
    """Build the execution agent system prompt with the retrieval plan injected.

    When ``sandbox_enabled`` is False the no-sandbox variant is used, which
    adds an explicit file-access policy restricting the agent to /workspace.
    """
    template_file = (
        "execution_agent_prompt.txt"
        if sandbox_enabled
        else "execution_agent_prompt_no_sandbox.txt"
    )
    template = _read(template_file)
    return template.replace("{retrieval_plan}", retrieval_plan)


CodingAgentDescription = _read("coding_agent_description.txt").strip()
