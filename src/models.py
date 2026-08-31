"""Model registry and runtime-configurable selection for TissueAgent.

Defines the supported OpenAI, Anthropic, OpenRouter and self-hosted chat
models, the
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
from dataclasses import dataclass, replace
from collections.abc import Callable
from typing import Any, Dict, List, Literal, Optional

from langchain_core.language_models.chat_models import BaseChatModel


Provider = Literal["openai", "anthropic", "openrouter", "local"]
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

# Self-hosted, OpenAI-API-compatible endpoint (vLLM, SGLang). Point this at the
# server with TISSUEAGENT_LOCAL_BASE_URL; the benchmark shards run on a CPU node
# and reach a GPU node over the cluster network, so the default localhost value
# is only right for a single-machine setup.
LOCAL_BASE_URL_ENV = "TISSUEAGENT_LOCAL_BASE_URL"
DEFAULT_LOCAL_BASE_URL = "http://127.0.0.1:8000/v1"

# langchain_anthropic's own default is 1024 tokens — low enough that ordinary
# agent turns truncate. Set well clear of that without streaming (the SDK guards
# non-streamed requests above ~16k to avoid HTTP timeouts).
ANTHROPIC_DEFAULT_MAX_TOKENS = 16000


def get_local_base_url() -> str:
    """Return the base URL for the `local` provider."""
    return (os.environ.get(LOCAL_BASE_URL_ENV) or "").strip() or DEFAULT_LOCAL_BASE_URL

# Order matters: first entry per provider is shown first in the UI.
SUPPORTED_MODELS: List[ModelSpec] = [
    # --- OpenAI (direct) ---
    ModelSpec(
        id="gpt-5.5",
        provider="openai",
        api_model="gpt-5.5",
        label="GPT-5.5 (default)",
        reasoning_effort="high",
    ),
    ModelSpec(
        id="gpt-5.1",
        provider="openai",
        api_model="gpt-5.1",
        label="GPT-5.1",
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
    #
    # Current generation first (the UI shows the first entry per provider first).
    # The 4.7 / 4.6 entries below are still valid API ids and stay for anyone
    # pinning them; they are simply a generation behind.
    ModelSpec(
        id="claude-opus-5",
        provider="anthropic",
        api_model="claude-opus-5",
        label="Claude Opus 5",
    ),
    ModelSpec(
        id="claude-sonnet-5",
        provider="anthropic",
        api_model="claude-sonnet-5",
        label="Claude Sonnet 5",
    ),
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
    # --- Self-hosted (vLLM / SGLang), OpenAI-API-compatible ---
    #
    # `api_model` must match the server's --served-model-name exactly; vLLM
    # rejects a request whose "model" field it does not recognise.
    #
    # reasoning_effort is deliberately None on every entry here. Two reasons,
    # both load-bearing:
    #   1. vLLM rejects `reasoning_effort` as an unknown field — it is an
    #      OpenAI-platform parameter, not part of the chat-completions schema
    #      these servers implement.
    #   2. get_model_spec() only applies TISSUEAGENT_REASONING_EFFORT to specs
    #      whose effort is not None, so leaving it None makes the EFFORT knob a
    #      no-op here rather than letting metrics.json claim a setting that
    #      never reached the model.
    # Qwen's thinking mode is a different knob entirely — pass it through
    # build_chat_model's **overrides as
    # extra_body={"chat_template_kwargs": {"enable_thinking": True}}.
    ModelSpec(
        id="local/qwen3-32b",
        provider="local",
        api_model="qwen3-32b",
        label="Qwen3 32B · self-hosted",
    ),
    ModelSpec(
        id="local/qwen3-vl-32b",
        provider="local",
        api_model="qwen3-vl-32b",
        label="Qwen3-VL 32B Instruct · self-hosted",
    ),
    ModelSpec(
        id="local/qwen3-235b",
        provider="local",
        api_model="qwen3-235b",
        label="Qwen3 235B-A22B · self-hosted",
    ),
]

_MODELS_BY_ID: Dict[str, ModelSpec] = {m.id: m for m in SUPPORTED_MODELS}

DEFAULT_MODEL_ID = "gpt-5.5"

# Map providers to the env-var name the underlying SDK consults.
PROVIDER_ENV_VAR: Dict[Provider, str] = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    # A self-hosted server needs no credential, but the OpenAI SDK refuses to
    # construct a client without one. build_chat_model falls back to a
    # placeholder, so this var only matters if you put the server behind auth.
    "local": "TISSUEAGENT_LOCAL_API_KEY",
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


REASONING_EFFORT_ENV = "TISSUEAGENT_REASONING_EFFORT"
ORCHESTRATION_REASONING_EFFORT_ENV = "TISSUEAGENT_ORCHESTRATION_REASONING_EFFORT"
WORKER_REASONING_EFFORT_ENV = "TISSUEAGENT_WORKER_REASONING_EFFORT"
# "none" is a real setting, not an absence: newer OpenAI reasoning models reject
# `reasoning_effort` outright when function tools are bound on
# /v1/chat/completions ("Function tools with reasoning_effort are not supported
# ... set reasoning_effort to 'none'"). Since every agent here binds tools, those
# models are unreachable unless the parameter can be suppressed. Selecting "none"
# omits the kwarg entirely -- see build_chat_model.
_VALID_REASONING_EFFORTS = ("none", "minimal", "low", "medium", "high")


def _reasoning_effort_for_role(role: Role | None) -> str | None:
    """Return the configured effort for a model role, if it has one.

    The orchestration agents make many short decisions, so medium reasoning is
    the latency-oriented default. Worker agents, including the coding agent,
    retain high reasoning for analysis and figure reproduction. The legacy
    global setting remains a fallback for installations that already use it.
    """
    if role is None:
        configured = (os.environ.get(REASONING_EFFORT_ENV) or "").strip().lower()
    else:
        role_env = (
            ORCHESTRATION_REASONING_EFFORT_ENV
            if role == "orchestration"
            else WORKER_REASONING_EFFORT_ENV
        )
        default = "medium" if role == "orchestration" else "high"
        configured = (
            os.environ.get(role_env)
            or os.environ.get(REASONING_EFFORT_ENV)
            or default
        ).strip().lower()
    if not configured:
        return None
    if configured not in _VALID_REASONING_EFFORTS:
        raise ValueError(
            f"reasoning effort {configured!r} is not one of {_VALID_REASONING_EFFORTS}"
        )
    return configured


def get_model_spec(model_id: str, role: Role | None = None) -> ModelSpec:
    """Return the ModelSpec for the given model_id, raising ValueError if unknown.

    Role-specific environment variables override the catalog's effort for models
    that have one: ``TISSUEAGENT_ORCHESTRATION_REASONING_EFFORT`` defaults to
    ``medium`` and ``TISSUEAGENT_WORKER_REASONING_EFFORT`` defaults to ``high``.
    ``TISSUEAGENT_REASONING_EFFORT`` remains their shared fallback. Applied here
    rather than in :func:`build_chat_model` so benchmark metrics record the
    effort a run actually used.

    Models whose catalog effort is ``None`` (Anthropic) are left alone: the
    provider ignores the argument, so recording one would assert a setting that
    never reached the API.
    """
    if model_id not in _MODELS_BY_ID:
        raise ValueError(f"Unknown model id: {model_id!r}")
    spec = _MODELS_BY_ID[model_id]

    override = _reasoning_effort_for_role(role)
    if override and spec.reasoning_effort is not None:
        spec = replace(spec, reasoning_effort=override)
    return spec


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
    """Per-provider status for the UI: env detected, UI-set flag, env-var name.

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

def build_chat_model(
    model_id: str,
    *,
    role: Role | None = None,
    **overrides: Any,
) -> BaseChatModel:
    """Instantiate a fresh chat model for *model_id*.

    ``overrides`` are forwarded to the underlying constructor. Provider- specific arguments not understood by the other
    provider are dropped.
    """
    spec = get_model_spec(model_id, role=role)

    if spec.provider == "openai":
        from langchain_openai import ChatOpenAI

        kwargs: Dict[str, Any] = {"model": spec.api_model}
        if spec.api_model == "gpt-5.5":
            kwargs["use_responses_api"] = True
        # "none" means "do not send the parameter at all" -- the only way to bind
        # function tools on models that refuse an explicit reasoning_effort.
        if spec.reasoning_effort is not None and spec.reasoning_effort != "none":
            kwargs["reasoning_effort"] = spec.reasoning_effort
        key = get_api_key("openai")
        if key:
            kwargs["api_key"] = key
        kwargs.update(overrides)
        return ChatOpenAI(**kwargs)

    if spec.provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        # langchain_anthropic defaults max_tokens to 1024, which truncates agent
        # turns that plan, call tools, and write reports mid-response. The OpenAI
        # path leaves the ceiling to the provider, so this only shows up on Claude.
        # Overridable via `overrides` below.
        kwargs = {"model": spec.api_model, "max_tokens": ANTHROPIC_DEFAULT_MAX_TOKENS}
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
        if spec.reasoning_effort is not None and spec.reasoning_effort != "none":
            kwargs["reasoning_effort"] = spec.reasoning_effort
        key = get_api_key("openrouter")
        if key:
            kwargs["api_key"] = key
        kwargs.update(overrides)
        return ChatOpenAI(**kwargs)

    if spec.provider == "local":
        # A self-hosted vLLM/SGLang server speaking the OpenAI chat-completions
        # API. Same shape as the openrouter branch, with two differences: the
        # base URL is read at call time (the server's host is only known once
        # slurm has placed the job), and reasoning_effort is never forwarded
        # because these servers reject the field outright.
        from langchain_openai import ChatOpenAI

        kwargs = {
            "model": spec.api_model,
            "base_url": get_local_base_url(),
        }
        overrides.pop("reasoning_effort", None)
        # vLLM ignores the value but the SDK requires a non-empty string.
        kwargs["api_key"] = get_api_key("local") or "EMPTY"
        kwargs.update(overrides)
        return ChatOpenAI(**kwargs)

    raise ValueError(f"Unsupported provider for model {model_id!r}: {spec.provider}")


def model_ctor_for_role(role: Role, **overrides: Any) -> Callable[..., BaseChatModel]:
    """Return a zero-argument callable that resolves the current model for *role*.

    The model id is looked up at *call time*, so changing the selection affects the next graph build without needing to
    re-wire ``model_ctor`` fields on every agent definition.
    """

    def ctor() -> BaseChatModel:
        return build_chat_model(get_model_id(role), role=role, **overrides)

    return ctor
