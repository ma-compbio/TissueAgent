"""External-agent definition export for cellvoyager_agent."""

from pathlib import Path

from agents.external_agent import ExternalAgentDefinition, load_manifest
from agents.agent_registry.cellvoyager_agent.prompt import (
    CellVoyagerDescription,
    CellVoyagerPrompt,
)
from agents.agent_registry.cellvoyager_agent.tool import CellVoyagerTools
from models import model_ctor_for_role


_HERE = Path(__file__).resolve().parent
_manifest = load_manifest(_HERE)


agent_definition = ExternalAgentDefinition(
    id=_manifest["id"],
    name=_manifest["name"],
    description=CellVoyagerDescription,
    prompt=CellVoyagerPrompt,
    tools=CellVoyagerTools,
    # The wrapper ReAct loop follows TissueAgent's worker-model selection;
    # the actual CellVoyager run is pinned inside runner.py for reproducibility.
    model_ctor=model_ctor_for_role("worker"),
    version=_manifest["version"],
    upstream_repo=(_manifest.get("upstream") or {}).get("repo"),
    upstream_commit=(_manifest.get("upstream") or {}).get("commit"),
    required_env_vars=(_manifest.get("llm") or {}).get("required_env_vars", []),
    data_subdir=_manifest.get("data_subdir"),
)
