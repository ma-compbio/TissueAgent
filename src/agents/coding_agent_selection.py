"""Select the coding-agent implementation for this process."""

from __future__ import annotations

import os
from collections.abc import Callable


def coding_agent_implementation() -> str:
    """Return the normalized coding-agent implementation name."""
    value = os.environ.get("TISSUEAGENT_CODING_AGENT", "").strip().lower()
    if value in ("", "deepagent"):
        return "deepagent"
    if value in ("cache", "stock"):
        return "cache"
    raise ValueError(
        "Unsupported TISSUEAGENT_CODING_AGENT="
        f"{value!r}; expected 'deepagent', 'cache', or 'stock'"
    )


def coding_agent_ctor() -> Callable:
    """Return the selected coding-agent constructor."""
    if coding_agent_implementation() == "cache":
        from agents.agent_registry.coding_agent_cache.model import create_coding_agent

        return create_coding_agent

    from agents.agent_registry.coding_agent.model import create_coding_agent

    return create_coding_agent
