"""External-agent definition export for genegpt_agent.

This file is the single import surface the rest of TissueAgent needs:
``agents.agent_registry.genegpt_agent.agent_definition``.
"""

from pathlib import Path

from agents.external_agent import ExternalAgentDefinition, load_manifest
from agents.agent_registry.genegpt_agent.prompt import (
    GeneGPTDescription,
    GeneGPTPrompt,
)
from agents.agent_registry.genegpt_agent.tool import GeneGPTTools
from models import model_ctor_for_role


_HERE = Path(__file__).resolve().parent
_manifest = load_manifest(_HERE)


agent_definition = ExternalAgentDefinition(
    id=_manifest["id"],
    name=_manifest["name"],
    description=GeneGPTDescription,
    prompt=GeneGPTPrompt,
    tools=GeneGPTTools,
    # The wrapper ReAct loop follows TissueAgent's worker-model selection.
    # GeneGPT's own NCBI tool-use loop is pinned to a current OpenAI model
    # inside runner.py (manifest.yaml `llm.pinned_model`) for reproducibility.
    model_ctor=model_ctor_for_role("worker"),
    version=_manifest["version"],
    upstream_repo=(_manifest.get("upstream") or {}).get("repo"),
    upstream_commit=(_manifest.get("upstream") or {}).get("commit"),
    required_env_vars=(_manifest.get("llm") or {}).get("required_env_vars", []),
    data_subdir=_manifest.get("data_subdir"),
)
