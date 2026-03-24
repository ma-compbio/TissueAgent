"""Tool that lists available YAML plan templates from the plan registry."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import yaml
from langchain.tools import StructuredTool
from pydantic import BaseModel, Field

# Get the default registry directory relative to this file
DEFAULT_REGISTRY_DIR = Path(__file__).parent.parent / "plan_registry"


# ---------- internals ----------


def _load_templates(registry_dir: Path) -> List[Dict[str, Any]]:
    """Load all YAML plan templates from the given directory."""
    if not registry_dir.exists():
        return []
    docs: List[Dict[str, Any]] = []
    for p in sorted(registry_dir.glob("*.yaml")):
        docs.append(yaml.safe_load(p.read_text()))
    return docs


def _make_index(templates: List[Dict[str, Any]]) -> str:
    """Format templates into a compact human-readable index string."""
    lines: List[str] = []
    for t in templates:
        template_id = t.get("template_id", "<missing_id>")
        title = t.get("title", "")
        tags = ", ".join(t.get("tags", []))
        inputs = ", ".join(t.get("inputs", []))
        outputs = ", ".join(t.get("outputs", []))
        evals = ", ".join(t.get("eval", []))
        updated = str(t.get("last_updated", "unknown"))
        version = str(t.get("version", ""))
        sketch = t.get("step_sketch", "")
        lines.append(f"{template_id} — {title}; tags: {tags}; v{version} (updated: {updated})")
        lines.append(f"  inputs: {inputs}; outputs: {outputs}")
        lines.append(f"  steps: {sketch} (eval: {evals})")
        # Optional details list (bullet points)
        details = t.get("details", [])
        if isinstance(details, str):
            details = [details]
        if isinstance(details, list) and details:
            lines.append("  details:")
            for item in details:
                try:
                    text = str(item)
                except Exception:
                    text = repr(item)
                lines.append(f"    - {text}")
        lines.append("")
    return "\n".join(lines)


# ---------- tool ----------


class PlanRegistryArgs(BaseModel):
    """Input schema for the plan registry tool."""

    registry_dir: str = Field(
        default=str(DEFAULT_REGISTRY_DIR),
        description="Directory containing YAML plan templates.",
    )


def _plan_registry_tool(*, registry_dir: str = None) -> str:
    """Return a compact, human-readable index of plan templates."""
    if registry_dir is None:
        registry_dir = str(DEFAULT_REGISTRY_DIR)
    templates = _load_templates(Path(registry_dir))
    return _make_index(templates) if templates else ""


def _plan_registry_tool_noargs() -> str:
    """Wrapper exposing a no-arg tool interface with default registry."""
    return _plan_registry_tool()


plan_registry_tool = StructuredTool.from_function(
    name="plan_registry_tool",
    func=_plan_registry_tool_noargs,
    description=(
        "List available YAML plan templates (id, title, tags, inputs/outputs, step sketch, details, eval)."
    ),
    return_direct=False,
)
