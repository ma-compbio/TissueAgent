from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import yaml
from pydantic import BaseModel, Field
from langchain.tools import StructuredTool


# ---------- internals ----------

def _load_templates(registry_dir: Path) -> List[Dict[str, Any]]:
    if not registry_dir.exists():
        return []
    docs: List[Dict[str, Any]] = []
    for p in sorted(registry_dir.glob("*.yaml")):
        docs.append(yaml.safe_load(p.read_text()))
    return docs

def _make_index(templates: List[Dict[str, Any]]) -> str:
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
        lines.append(f"  steps: {sketch} (eval: {evals})\n")
    return "\n".join(lines)


# ---------- tool ----------

class PlanRegistryArgs(BaseModel):
    registry_dir: str = Field(
        default="plan_registry",
        description="Directory containing YAML plan templates."
    )

def _plan_registry_tool(*, registry_dir: str = "plan_registry") -> str:
    """Return a compact, human-readable index of plan templates."""
    templates = _load_templates(Path(registry_dir))
    return _make_index(templates) if templates else ""

plan_registry_tool = StructuredTool.from_function(
    name="plan_registry_tool",
    func=_plan_registry_tool,
    args_schema=PlanRegistryArgs,
    description=(
        "Load YAML templates from the plan registry and return a short index: "
        "template id, title, tags, inputs/outputs, step sketch, and eval hints."
    ),
    return_direct=False,
)
