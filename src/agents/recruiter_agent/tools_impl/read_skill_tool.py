"""Tool that reads a skill by name from the skill registry."""

from __future__ import annotations

from langchain.tools import StructuredTool
from pydantic import BaseModel, Field

from agents.recruiter_agent.prompt import get_skill_metadata


class ReadSkillArgs(BaseModel):
    """Input schema for the read_skill tool."""

    name: str = Field(
        ..., description="Kebab-case skill name (e.g. 'clean-anndata')."
    )


def _read_skill(*, name: str) -> str:
    """Return the full markdown content of the named skill."""
    skills = get_skill_metadata()
    meta = skills.get(name)
    if meta is None:
        available = sorted(skills.keys())
        return (
            f"Error: skill '{name}' not found. "
            f"Available skills: {', '.join(available) or '(none)'}"
        )
    return meta.path.read_text()


read_skill_tool = StructuredTool.from_function(
    name="read_skill",
    func=_read_skill,
    args_schema=ReadSkillArgs,
    description="Read the full content of a shared skill by its kebab-case name.",
    return_direct=False,
)
