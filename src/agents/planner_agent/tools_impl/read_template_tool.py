"""Tool that reads a plan template by name from the registry."""

from __future__ import annotations

from langchain.tools import StructuredTool
from pydantic import BaseModel, Field

from knowledge import PLANS_DIR

DEFAULT_REGISTRY_DIR = PLANS_DIR


class ReadTemplateArgs(BaseModel):
    """Input schema for the read_template tool."""

    name: str = Field(
        ..., description="Snake_case template name (e.g. 'lr_analysis')."
    )


def _read_template(*, name: str) -> str:
    """Return the full markdown content of the named plan template."""
    path = DEFAULT_REGISTRY_DIR / f"{name}.md"
    if not path.exists():
        available = sorted(
            p.stem for p in DEFAULT_REGISTRY_DIR.glob("*.md")
            if p.read_text().startswith("---")
        )
        return (
            f"Error: template '{name}' not found. "
            f"Available templates: {', '.join(available)}"
        )
    return path.read_text()


read_template_tool = StructuredTool.from_function(
    name="read_template",
    func=_read_template,
    args_schema=ReadTemplateArgs,
    description="Read the full content of a plan template by its snake_case name.",
    return_direct=False,
)
