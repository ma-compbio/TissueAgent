from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import yaml
from langchain.tools import StructuredTool


# ---------- internals ----------

def _load_templates(registry_dir: Path) -> List[Dict[str, Any]]:
    if not registry_dir.exists():
        return []
    docs: List[Dict[str, Any]] = []
    for p in sorted(registry_dir.glob("*.yaml")):
        doc = yaml.safe_load(p.read_text())
        if isinstance(doc, dict) and bool(doc.get("enabled", True)):
            docs.append(doc)
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

# Default registry directory: alongside this module under planner_agent/plan_registry
_DEFAULT_REGISTRY_DIR: Path = Path(__file__).resolve().parent.parent / "plan_registry"

def _plan_registry_tool(*, registry_dir: str | None = None) -> str:
    """Return a compact, human-readable index of plan templates.

    If ``registry_dir`` is None, uses the planner's default registry directory.
    """
    registry_path = Path(registry_dir) if registry_dir else _DEFAULT_REGISTRY_DIR
    templates = _load_templates(registry_path)
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
