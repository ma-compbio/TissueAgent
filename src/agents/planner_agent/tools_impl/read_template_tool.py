"""Tool that reads a plan template by name from the registry."""

from __future__ import annotations

from langchain.tools import StructuredTool

from knowledge import PLANS_DIR


def _read_template(name: str) -> str:
    path = PLANS_DIR / f"{name}.md"
    if not path.exists():
        available = sorted(
            p.stem for p in PLANS_DIR.glob("*.md") if p.read_text().startswith("---")
        )
        return f"Error: template '{name}' not found. Available templates: {', '.join(available)}"
    return path.read_text()


read_template_tool = StructuredTool.from_function(
    name="read_template",
    func=_read_template,
    description="Read the full content of a plan template by its snake_case name.",
)
