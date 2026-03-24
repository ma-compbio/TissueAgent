"""Integration layer for the Memori long-term memory SDK.

Provides lazy initialization and lifecycle management of Memori instances,
keyed by (user_id, session_id).  When ``MEMORI_ENABLED`` is set in the
environment the module will create a SQLite-backed Memori store under
``DATA_DIR/memori/`` and register it with the OpenAI integration hook so
that all downstream LLM calls benefit from long-term memory.

The public API is intentionally small:

* :func:`initialize_memori_context` – ensure an instance exists and activate it.
* :func:`memori_enabled` – check whether memory is effectively on.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from threading import Lock
from typing import Dict, Optional, Tuple

from config import DATA_DIR

try:
    from memori import Memori
    from memori.integrations import openai_integration as _memori_openai
except ImportError:
    Memori = None
    set_active_memori_context = None  # type: ignore[assignment]
    register_memori_instance = None  # type: ignore[assignment]
else:
    set_active_memori_context = getattr(_memori_openai, "set_active_memori_context", None)
    register_memori_instance = getattr(_memori_openai, "register_memori_instance", None)

logger = logging.getLogger(__name__)


def _env_bool(key: str, default: bool = False) -> bool:
    """Normalize typical truthy/falsey env values."""
    raw = os.getenv(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _default_sqlite_url() -> str:
    """Place the default Memori database inside the project data directory."""
    default_dir = DATA_DIR / "memori"
    default_dir.mkdir(parents=True, exist_ok=True)
    db_path = (default_dir / "memori.db").resolve()
    return f"sqlite:///{db_path}"


@dataclass(frozen=True)
class _MemoriConfig:
    """Immutable snapshot of Memori-related environment configuration."""
    enabled: bool
    database_url: str
    conscious_ingest: bool
    auto_ingest: bool
    default_user_id: str
    default_session_id: str
    assistant_id: Optional[str]
    namespace: Optional[str]
    shared_memory: bool
    openai_api_key: Optional[str]


def _load_config() -> _MemoriConfig:
    """Read Memori settings from environment variables and return a frozen config."""
    return _MemoriConfig(
        enabled=_env_bool("MEMORI_ENABLED", False),
        database_url=os.getenv("MEMORI_DATABASE_URL", _default_sqlite_url()),
        conscious_ingest=_env_bool("MEMORI_CONSCIOUS_MODE", True),
        auto_ingest=_env_bool("MEMORI_AUTO_MODE", False),
        default_user_id=os.getenv("MEMORI_USER_ID", "tissueagent"),
        default_session_id=os.getenv("MEMORI_SESSION_ID", "default"),
        assistant_id=os.getenv("MEMORI_ASSISTANT_ID"),
        namespace=os.getenv("MEMORI_NAMESPACE"),
        shared_memory=_env_bool("MEMORI_SHARED_MEMORY", False),
        openai_api_key=os.getenv("MEMORI_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY"),
    )


_CONFIG = _load_config()


def _log_memori_sdk_status() -> None:
    """Emit a log line describing whether the SDK is discoverable."""
    try:
        dist = metadata.distribution("memorisdk")
    except metadata.PackageNotFoundError:
        logger.warning("Memori SDK not found via importlib.metadata (dist=memorisdk).")
        return

    location = Path(dist.locate_file("")).resolve()
    logger.warning("Memori SDK detected: memorisdk==%s (location=%s)", dist.version, location)


if _CONFIG.enabled:
    _log_memori_sdk_status()

if _CONFIG.enabled and Memori is None:  # pragma: no cover - log once for visibility
    logger.warning(
        "MEMORI_ENABLED is true but the Memori SDK is not installed. "
        "Run `uv add memorisdk` (or pip install memorisdk) to enable long-term memory."
    )


class _MemoriManager:
    """Lazy factory that keeps Memori instances keyed by (user_id, session_id)."""

    def __init__(self, config: _MemoriConfig):
        self._config = config
        self._instances: Dict[Tuple[str, str], Memori] = {}
        self._lock = Lock()

    @property
    def enabled(self) -> bool:
        """Return True when Memori is both configured and importable."""
        return self._config.enabled and Memori is not None

    def ensure_instance(
        self,
        *,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ):
        """Return an active Memori instance for the given user/session, creating one if needed."""
        if not self.enabled:
            return None

        resolved_user = (user_id or self._config.default_user_id or "default").strip() or "default"
        resolved_session = (
            session_id or self._config.default_session_id or "default"
        ).strip() or "default"
        key = (resolved_user, resolved_session)

        with self._lock:
            instance = self._instances.get(key)
            if instance is None:
                instance = self._create_instance(resolved_user, resolved_session)
                self._instances[key] = instance

        self._activate_context(instance)
        return instance

    def _create_instance(self, user_id: str, session_id: str):
        """Instantiate, enable, and return a new Memori object."""
        assert Memori is not None  # for type checkers

        try:
            memori = Memori(
                database_connect=self._config.database_url,
                conscious_ingest=self._config.conscious_ingest,
                auto_ingest=self._config.auto_ingest,
                user_id=user_id,
                namespace=self._config.namespace,
                shared_memory=self._config.shared_memory,
                openai_api_key=self._config.openai_api_key,
            )
            memori.enable()
            logger.info(
                "Enabled Memori long-term memory (user_id=%s, session_id=%s, db=%s)",
                user_id,
                session_id,
                self._config.database_url,
            )
            return memori
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception("Failed to enable Memori", exc_info=exc)
            raise

    def _activate_context(self, memori_instance) -> None:
        """Register the instance with the OpenAI integration hook, if available."""
        hook = set_active_memori_context or register_memori_instance
        if hook is None:
            return
        try:
            hook(memori_instance)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning("Unable to register Memori context: %s", exc)


_MANAGER: Optional[_MemoriManager] = None


def _get_manager() -> Optional[_MemoriManager]:
    """Return the singleton manager, lazily creating it when Memori is enabled."""
    global _MANAGER
    if _MANAGER is not None:
        return _MANAGER
    if not _CONFIG.enabled or Memori is None:
        return None
    _MANAGER = _MemoriManager(_CONFIG)
    return _MANAGER


def initialize_memori_context(
    *,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
):
    """Ensure Memori is enabled (if configured) and activate the context.

    Args:
        user_id: Override for the default user identifier.  Falls back to
            the ``MEMORI_USER_ID`` env var or ``"tissueagent"``.
        session_id: Override for the default session identifier.  Falls back
            to the ``MEMORI_SESSION_ID`` env var or ``"default"``.

    Returns:
        The active :class:`Memori` instance, or ``None`` when long-term
        memory is disabled or the SDK is not installed.
    """
    manager = _get_manager()
    if manager is None:
        return None
    return manager.ensure_instance(user_id=user_id, session_id=session_id)


def memori_enabled() -> bool:
    """Check whether Memori long-term memory is active.

    Returns:
        ``True`` when the ``MEMORI_ENABLED`` env var is truthy and the
        Memori SDK is importable; ``False`` otherwise.
    """
    manager = _get_manager()
    return bool(manager and manager.enabled)


__all__ = ["initialize_memori_context", "memori_enabled"]
