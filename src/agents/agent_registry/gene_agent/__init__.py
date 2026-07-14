"""External-agent definition export for gene_agent.

This file is the single import surface the rest of TissueAgent needs:
``agents.agent_registry.gene_agent.agent_definition``.

The metadata fields are sourced from ``manifest.yaml`` to keep the file
declarative; the prompt/tools/model_ctor wiring stays here so the import
is fully type-checked.
"""

from pathlib import Path

from agents.external_agent import ExternalAgentDefinition, load_manifest
from agents.agent_registry.gene_agent.prompt import (
    GeneAgentDescription,
    GeneAgentPrompt,
)
from agents.agent_registry.gene_agent.tool import GeneAgentTools
from models import model_ctor_for_role


_HERE = Path(__file__).resolve().parent
_manifest = load_manifest(_HERE)


agent_definition = ExternalAgentDefinition(
    id=_manifest["id"],
    name=_manifest["name"],
    description=GeneAgentDescription,
    prompt=GeneAgentPrompt,
    tools=GeneAgentTools,
    # The Gene Agent's ReAct loop (the LLM that decides when to call the
    # geneagent_analyze_gene_set_tool) follows TissueAgent's worker-model
    # selection. The cascade itself, invoked by the tool, is pinned to
    # OpenAI gpt-5.1 inside runner.py — see manifest.yaml `llm.pinned_model`.
    model_ctor=model_ctor_for_role("worker"),
    version=_manifest["version"],
    upstream_repo=(_manifest.get("upstream") or {}).get("repo"),
    upstream_commit=(_manifest.get("upstream") or {}).get("commit"),
    required_env_vars=(_manifest.get("llm") or {}).get("required_env_vars", []),
    data_subdir=_manifest.get("data_subdir"),
)
