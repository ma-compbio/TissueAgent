"""Model registry and runtime-configurable selection for TissueAgent.

Defines the supported OpenAI, Anthropic, and OpenRouter chat models, the
global selection state (which model the *orchestration* agents and the
*worker* sub-agents should use), the per-provider API key store, and a
factory that produces a fresh ``BaseChatModel`` instance for each agent
invocation.

The selection is mutable at runtime: the FastAPI ``/api/models`` route
writes to :data:`_selection`, and every ``model_ctor`` callable resolves
the active model lazily at call time. The graph is rebuilt between user
messages so a change takes effect on the next turn.

API keys can come from two sources:
  1. An environment variable (``OPENAI_API_KEY``, ``ANTHROPIC_API_KEY``,
     ``OPENROUTER_API_KEY``).
  2. A value the user types into the UI, which is held in
     :data:`_api_keys` for the lifetime of the server process.

The UI value, when set, takes precedence over the env var.
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Literal, Optional

from langchain_core.language_models.chat_models import BaseChatModel


Provider = Literal["openai", "anthropic", "openrouter"]
Role = Literal["orchestration", "worker"]


@dataclass(frozen=True)
class ModelSpec:
    """A user-selectable model option."""

    id: str                  # canonical identifier used over the wire
    provider: Provider
    api_model: str           # value passed to the provider SDK
    label: str               # human-readable label for the dropdown
    reasoning_effort: Optional[str] = None  # OpenAI-only; "low"|"medium"|"high"


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Order matters: first entry per provider is shown first in the UI.
SUPPORTED_MODELS: List[ModelSpec] = [
    # --- OpenAI (direct) ---
    ModelSpec(
        id="gpt-5.1",
        provider="openai",
        api_model="gpt-5.1",
        label="GPT-5.1 (default)",
        reasoning_effort="high",
    ),
    ModelSpec(
        id="gpt-5.4",
        provider="openai",
        api_model="gpt-5.4",
        label="GPT-5.4",
        reasoning_effort="high",
    ),
    ModelSpec(
        id="gpt-5",
        provider="openai",
        api_model="gpt-5",
        label="GPT-5",
        reasoning_effort="high",
    ),
    ModelSpec(
        id="gpt-5-mini",
        provider="openai",
        api_model="gpt-5-mini",
        label="GPT-5 mini",
        reasoning_effort="medium",
    ),
    # --- Anthropic (direct) ---
    ModelSpec(
        id="claude-opus-4-7",
        provider="anthropic",
        api_model="claude-opus-4-7",
        label="Claude Opus 4.7",
    ),
    ModelSpec(
        id="claude-sonnet-4-6",
        provider="anthropic",
        api_model="claude-sonnet-4-6",
        label="Claude Sonnet 4.6",
    ),
    # --- OpenRouter (same OpenAI + Claude models via OpenRouter gateway) ---
    ModelSpec(
        id="openrouter/gpt-5.1",
        provider="openrouter",
        api_model="openai/gpt-5.1",
        label="GPT-5.1 · via OpenRouter",
        reasoning_effort="high",
    ),
    ModelSpec(
        id="openrouter/gpt-5.4",
        provider="openrouter",
        api_model="openai/gpt-5.4",
        label="GPT-5.4 · via OpenRouter",
        reasoning_effort="high",
    ),
    ModelSpec(
        id="openrouter/gpt-5",
        provider="openrouter",
        api_model="openai/gpt-5",
        label="GPT-5 · via OpenRouter",
        reasoning_effort="high",
    ),
    ModelSpec(
        id="openrouter/gpt-5-mini",
        provider="openrouter",
        api_model="openai/gpt-5-mini",
        label="GPT-5 mini · via OpenRouter",
        reasoning_effort="medium",
    ),
    ModelSpec(
        id="openrouter/claude-opus-4-7",
        provider="openrouter",
        api_model="anthropic/claude-opus-4-7",
        label="Claude Opus 4.7 · via OpenRouter",
    ),
    ModelSpec(
        id="openrouter/claude-sonnet-4-6",
        provider="openrouter",
        api_model="anthropic/claude-sonnet-4-6",
        label="Claude Sonnet 4.6 · via OpenRouter",
    ),
]

_MODELS_BY_ID: Dict[str, ModelSpec] = {m.id: m for m in SUPPORTED_MODELS}

DEFAULT_MODEL_ID = "gpt-5.1"

# Map providers to the env-var name the underlying SDK consults.
PROVIDER_ENV_VAR: Dict[Provider, str] = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}


def list_models() -> List[Dict[str, Any]]:
    """Return the catalog as a JSON-friendly list for the frontend."""
    return [
        {
            "id": m.id,
            "provider": m.provider,
            "label": m.label,
        }
        for m in SUPPORTED_MODELS
    ]


def get_model_spec(model_id: str) -> ModelSpec:
    """Return the ModelSpec for the given model_id, raising ValueError if unknown."""
    if model_id not in _MODELS_BY_ID:
        raise ValueError(f"Unknown model id: {model_id!r}")
    return _MODELS_BY_ID[model_id]


# ---------------------------------------------------------------------------
# Selection state (mutable, thread-safe)
# ---------------------------------------------------------------------------

@dataclass
class Selection:
    """Active model selection for both agent roles."""

    orchestration: str = DEFAULT_MODEL_ID
    worker: str = DEFAULT_MODEL_ID


_selection = Selection()
_selection_lock = threading.Lock()

# Bumped whenever the selection changes. The server compares the value
# observed when the graph was last compiled against the current value to
# decide whether to rebuild the graph before the next user message.
_revision: int = 0


def get_selection() -> Dict[str, str]:
    """Return the active model selection as a JSON-friendly dict."""
    with _selection_lock:
        return {
            "orchestration": _selection.orchestration,
            "worker": _selection.worker,
        }


def set_selection(orchestration: str, worker: str) -> Dict[str, str]:
    """Update the active model selection.

    Validates both ids.
    """
    # Validate before mutating so a bad request leaves state unchanged.
    get_model_spec(orchestration)
    get_model_spec(worker)
    global _revision
    with _selection_lock:
        _selection.orchestration = orchestration
        _selection.worker = worker
        _revision += 1
    return get_selection()


def get_revision() -> int:
    """Return the revision counter, bumped on every selection change."""
    with _selection_lock:
        return _revision


def get_model_id(role: Role) -> str:
    """Return the model ID for the given role ('orchestration' or 'worker')."""
    with _selection_lock:
        return _selection.orchestration if role == "orchestration" else _selection.worker


# ---------------------------------------------------------------------------
# API key store (mutable, thread-safe)
# ---------------------------------------------------------------------------

_api_keys: Dict[Provider, str] = {}
_api_keys_lock = threading.Lock()


def _env_key(provider: Provider) -> Optional[str]:
    name = PROVIDER_ENV_VAR.get(provider)
    if not name:
        return None
    val = os.environ.get(name)
    return val.strip() if val and val.strip() else None


def get_api_key(provider: Provider) -> Optional[str]:
    """Return the API key for *provider*: UI-stored value, else env var."""
    with _api_keys_lock:
        ui_val = _api_keys.get(provider)
    if ui_val:
        return ui_val
    return _env_key(provider)


def set_api_key(provider: Provider, key: Optional[str]) -> None:
    """Store *key* in memory.

    Pass ``None`` or empty to clear and fall back to env.
    """
    if provider not in PROVIDER_ENV_VAR:
        raise ValueError(f"Unknown provider: {provider!r}")
    clean = key.strip() if key else ""
    with _api_keys_lock:
        if clean:
            _api_keys[provider] = clean
        else:
            _api_keys.pop(provider, None)


def get_key_status() -> Dict[str, Dict[str, Any]]:
    """
    Per-provider status for the UI: env detected, UI-set flag, env-var name.

    Never returns the actual key values.
    """
    result: Dict[str, Dict[str, Any]] = {}
    with _api_keys_lock:
        ui_set = {p: bool(_api_keys.get(p)) for p in PROVIDER_ENV_VAR}
    for provider, env_name in PROVIDER_ENV_VAR.items():
        env_val = os.environ.get(env_name)
        result[provider] = {
            "env_var": env_name,
            "env_set": bool(env_val and env_val.strip()),
            "ui_set": ui_set[provider],
            "effective": ui_set[provider]
            or bool(env_val and env_val.strip()),
        }
    return result


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def build_chat_model(model_id: str, **overrides: Any) -> BaseChatModel:
    """Instantiate a fresh chat model for *model_id*.

    ``overrides`` are forwarded to the underlying constructor. Provider- specific arguments not understood by the other
    provider are dropped.
    """
    spec = get_model_spec(model_id)

    if spec.provider == "openai":
        from langchain_openai import ChatOpenAI

        kwargs: Dict[str, Any] = {"model": spec.api_model}
        if spec.reasoning_effort is not None:
            kwargs["reasoning_effort"] = spec.reasoning_effort
        key = get_api_key("openai")
        if key:
            kwargs["api_key"] = key
        kwargs.update(overrides)
        return ChatOpenAI(**kwargs)

    if spec.provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        kwargs = {"model": spec.api_model}
        # Drop OpenAI-only kwargs callers may pass.
        for k in ("reasoning_effort",):
            overrides.pop(k, None)
        key = get_api_key("anthropic")
        if key:
            kwargs["api_key"] = key
        kwargs.update(overrides)
        return ChatAnthropic(**kwargs)

    if spec.provider == "openrouter":
        # OpenRouter is OpenAI-API-compatible. Use ChatOpenAI with a custom
        # base URL and the OpenRouter key.
        from langchain_openai import ChatOpenAI

        kwargs = {
            "model": spec.api_model,
            "base_url": OPENROUTER_BASE_URL,
        }
        if spec.reasoning_effort is not None:
            kwargs["reasoning_effort"] = spec.reasoning_effort
        key = get_api_key("openrouter")
        if key:
            kwargs["api_key"] = key
        kwargs.update(overrides)
        return ChatOpenAI(**kwargs)

    raise ValueError(f"Unsupported provider for model {model_id!r}: {spec.provider}")


def model_ctor_for_role(role: Role, **overrides: Any) -> Callable[..., BaseChatModel]:
    """Return a zero-argument callable that resolves the current model for *role*.

    The model id is looked up at *call time*, so changing the selection affects the next graph build without needing to
    re-wire ``model_ctor`` fields on every agent definition.
    """

    def ctor() -> BaseChatModel:
        return build_chat_model(get_model_id(role), **overrides)

    return ctor
