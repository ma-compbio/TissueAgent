"""Prompt templates and description for the manager agent."""

from pathlib import Path

from agents.agent_utils import format_agent_id_descriptions

_DIR = Path(__file__).parent

_TEMPLATE = (_DIR / "prompt.txt").read_text()

ManagerDescription = """
Coordinate the Executor Team composed of expert agents to execute each step in the Plan.
""".strip()

def ManagerPrompt(agent_id_descriptions: dict[str, str]) -> str:
    """Build the manager agent system prompt with the agent registry filled."""
    return _TEMPLATE.replace(
        "{agent_registry}", format_agent_id_descriptions(agent_id_descriptions)
    )
