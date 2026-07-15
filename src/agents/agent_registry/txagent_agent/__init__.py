"""External-agent definition export for txagent_agent.

This file is the single import surface the rest of TissueAgent needs:
``agents.agent_registry.txagent_agent.agent_definition``.
"""

from pathlib import Path

from agents.external_agent import ExternalAgentDefinition, load_manifest
from agents.agent_registry.txagent_agent.prompt import (
    TxAgentDescription,
    TxAgentPrompt,
)
from agents.agent_registry.txagent_agent.tool import TxAgentTools
from models import model_ctor_for_role


_HERE = Path(__file__).resolve().parent
_manifest = load_manifest(_HERE)


agent_definition = ExternalAgentDefinition(
    id=_manifest["id"],
    name=_manifest["name"],
    description=TxAgentDescription,
    prompt=TxAgentPrompt,
    tools=TxAgentTools,
    # The wrapper ReAct loop follows TissueAgent's worker-model selection.
    # The actual reasoning model is TxAgent's own fine-tuned 8B (served via
    # vLLM inside the isolated env), pinned in manifest.yaml.
    model_ctor=model_ctor_for_role("worker"),
    version=_manifest["version"],
    upstream_repo=(_manifest.get("upstream") or {}).get("repo"),
    upstream_commit=(_manifest.get("upstream") or {}).get("commit"),
    required_env_vars=(_manifest.get("llm") or {}).get("required_env_vars", []),
    data_subdir=_manifest.get("data_subdir"),
)
