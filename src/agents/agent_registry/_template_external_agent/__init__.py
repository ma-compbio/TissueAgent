"""Skeleton ``__init__.py`` for a new external agent.

Rename the folder, fill in ``manifest.yaml``, write ``prompt.py``, ``tool.py``, and ``runner.py`` using the gene_agent
worked example, then update the imports below.

The rest of TissueAgent only needs the ``agent_definition`` symbol from this module.
"""

from pathlib import Path

from agents.external_agent import ExternalAgentDefinition, load_manifest

# from agents.agent_registry.my_agent.prompt import (
#     MyAgentDescription,
#     MyAgentPrompt,
# )
# from agents.agent_registry.my_agent.tool import MyAgentTools
from models import model_ctor_for_role


_HERE = Path(__file__).resolve().parent
_manifest = load_manifest(_HERE)


# agent_definition = ExternalAgentDefinition(
#     id=_manifest["id"],
#     name=_manifest["name"],
#     description=MyAgentDescription,
#     prompt=MyAgentPrompt,
#     tools=MyAgentTools,
#     model_ctor=model_ctor_for_role("worker"),
#     version=_manifest["version"],
#     upstream_repo=(_manifest.get("upstream") or {}).get("repo"),
#     upstream_commit=(_manifest.get("upstream") or {}).get("commit"),
#     required_env_vars=(_manifest.get("llm") or {}).get("required_env_vars", []),
#     data_subdir=_manifest.get("data_subdir"),
# )
