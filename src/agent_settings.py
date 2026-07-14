"""Runtime-configurable agent settings for TissueAgent.

Holds settings that affect agent behaviour — distinct from model selection, which lives in models.py. Settings are
mutable at runtime via the /api/settings REST route; a revision counter lets the graph be rebuilt lazily before the next
user message, the same mechanism used by models.py.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass
class _AgentSettings:
    # Run code execution inside the Docker sandbox (Jupyter Kernel Gateway).
    # When False (the default), code runs locally via whatever Jupyter
    # instance is reachable at KERNEL_GATEWAY_URL and Docker is not started
    # — so the server can boot without the Docker daemon running. Flip to
    # True from the Settings page when sandboxing is needed.
    sandbox_enabled: bool = False


_settings = _AgentSettings()
_lock = threading.Lock()
_revision: int = 0


def get_settings() -> dict:
    """Return all settings as a JSON-friendly dict."""
    with _lock:
        return {"sandbox_enabled": _settings.sandbox_enabled}


def set_sandbox_enabled(enabled: bool) -> dict:
    """Set sandbox_enabled and bump the revision so the graph is rebuilt."""
    global _revision
    with _lock:
        _settings.sandbox_enabled = enabled
        _revision += 1
    return get_settings()


def get_sandbox_enabled() -> bool:
    """Return whether the Docker sandbox is currently enabled."""
    with _lock:
        return _settings.sandbox_enabled


def get_revision() -> int:
    """Revision counter; incremented on every settings change."""
    with _lock:
        return _revision
