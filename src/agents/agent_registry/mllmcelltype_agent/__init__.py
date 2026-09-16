"""External-agent definition export for mllmcelltype_agent.

This file is the single import surface the rest of TissueAgent needs:
``agents.agent_registry.mllmcelltype_agent.agent_definition``.
"""

from pathlib import Path

from agents.external_agent import ExternalAgentDefinition, load_manifest
from agents.agent_registry.mllmcelltype_agent.prompt import (
    MLLMCelltypeDescription,
    MLLMCelltypePrompt,
)
from agents.agent_registry.mllmcelltype_agent.tool import MLLMCelltypeTools
from models import model_ctor_for_role


_HERE = Path(__file__).resolve().parent
_manifest = load_manifest(_HERE)


agent_definition = ExternalAgentDefinition(
    id=_manifest["id"],
    name=_manifest["name"],
    description=MLLMCelltypeDescription,
    prompt=MLLMCelltypePrompt,
    tools=MLLMCelltypeTools,
    # The wrapper ReAct loop (which decides when to call the annotate tool)
    # follows TissueAgent's worker-model selection. The annotation LLM(s) are
    # chosen inside runner.py based on the available provider key(s).
    model_ctor=model_ctor_for_role("worker"),
    version=_manifest["version"],
    upstream_repo=(_manifest.get("upstream") or {}).get("repo"),
    upstream_commit=(_manifest.get("upstream") or {}).get("commit"),
    required_env_vars=(_manifest.get("llm") or {}).get("required_env_vars", []),
    data_subdir=_manifest.get("data_subdir"),
)
