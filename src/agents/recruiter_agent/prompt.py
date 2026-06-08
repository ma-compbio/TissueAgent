"""Prompt templates and description for the recruiter agent."""

from pathlib import Path

from agents.agent_utils import format_agent_id_descriptions

_DIR = Path(__file__).parent

_TEMPLATE = (_DIR / "prompt.txt").read_text()

RecruiterDescription = """
Takes the global plan and match each step to the most suitable expert agent from the Agent Registry.
""".strip()

RecruiterPrompt = lambda agent_id_descriptions: _TEMPLATE.replace(
    "{agent_registry}", format_agent_id_descriptions(agent_id_descriptions)
)
