"""Contract and helpers for external-agent integration.

An *external agent* is third-party code (often a published research
repository) that we adapt into TissueAgent through a thin wrapper. The
contract is intentionally small: each external agent ships a folder
under :mod:`agents.agent_registry` that:

1. Contains a ``manifest.yaml`` describing the agent declaratively.
2. Exports an :class:`ExternalAgentDefinition` named ``agent_definition``
   from its ``__init__.py``.
3. Provides ``prompt.py``, ``tool.py``, and ``runner.py`` matching the
   skeleton in ``_template_external_agent/``.

The manifest is the single source of truth for metadata (id, name,
version, upstream commit, required env vars, output directory). The
:class:`ExternalAgentDefinition` is what :mod:`agents.agent_defns`
consumes when wiring the LangGraph pipeline.

See ``INTEGRATING.md`` at the repo root for the contributor recipe and
``agent_registry/_template_external_agent/`` for the worked example.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from collections.abc import Callable
from typing import Any

from langchain.tools import StructuredTool
from langchain_core.language_models.chat_models import BaseChatModel


@dataclass(frozen=True)
class ExternalAgentDefinition:
    """Declarative definition of an external agent.

    Attributes mirror :class:`agents.agent_defns.ReActAgent` plus metadata fields that come from the manifest. Optional
    fields default to sensible empty values so contributors only have to populate what their agent actually uses.
    """

    id: str
    name: str
    description: str
    prompt: str | Callable[..., str]
    tools: list[StructuredTool]
    model_ctor: Callable[..., BaseChatModel]

    # Metadata sourced from manifest.yaml — not used by the graph but
    # exposed to other parts of the system (UI, docs, health checks).
    version: str = "0.0.0"
    upstream_repo: str | None = None
    upstream_commit: str | None = None
    required_env_vars: list[str] = field(default_factory=list)
    data_subdir: str | None = None


def load_manifest(folder: Path) -> dict[str, Any]:
    """Load and minimally validate a ``manifest.yaml`` from *folder*.

    Returns the parsed dict. Raises ``FileNotFoundError`` if the manifest is missing and ``ValueError`` for required-
    field violations.
    """
    manifest_path = folder / "manifest.yaml"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"manifest.yaml not found in {folder}")

    try:
        import yaml
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "PyYAML is required to load external-agent manifests; "
            "add `pyyaml` to your environment."
        ) from exc

    with manifest_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    if not isinstance(data, dict):
        raise ValueError(f"{manifest_path} did not parse to a mapping.")

    for field_name in ("id", "name", "version"):
        if field_name not in data or not data[field_name]:
            raise ValueError(
                f"{manifest_path}: required field '{field_name}' is missing."
            )
    return data
