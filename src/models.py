"""Model registry and runtime-configurable selection for TissueAgent.

Defines the supported OpenAI and Anthropic chat models, the global
selection state (which model the *orchestration* agents and the *worker*
sub-agents should use), and a factory that produces a fresh
``BaseChatModel`` instance for each agent invocation.

The selection is mutable at runtime: the FastAPI ``/api/models`` route
writes to :data:`_selection`, and every ``model_ctor`` callable resolves
the active model lazily at call time. The graph is rebuilt between user
messages so a change takes effect on the next turn.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Literal, Optional

from langchain_core.language_models.chat_models import BaseChatModel


Provider = Literal["openai", "anthropic"]
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

# Order matters: first entry per provider is shown first in the UI.
SUPPORTED_MODELS: List[ModelSpec] = [
    # --- OpenAI ---
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
    # --- Anthropic ---
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
]

_MODELS_BY_ID: Dict[str, ModelSpec] = {m.id: m for m in SUPPORTED_MODELS}

DEFAULT_MODEL_ID = "gpt-5.1"


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
    with _selection_lock:
        return {
            "orchestration": _selection.orchestration,
            "worker": _selection.worker,
        }


def set_selection(orchestration: str, worker: str) -> Dict[str, str]:
    """Update the active model selection. Validates both ids."""
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
    with _selection_lock:
        return _revision


def get_model_id(role: Role) -> str:
    with _selection_lock:
        return _selection.orchestration if role == "orchestration" else _selection.worker


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def build_chat_model(model_id: str, **overrides: Any) -> BaseChatModel:
    """Instantiate a fresh chat model for *model_id*.

    ``overrides`` are forwarded to the underlying constructor. Provider-
    specific arguments not understood by the other provider are dropped.
    """
    spec = get_model_spec(model_id)

    if spec.provider == "openai":
        # Import lazily so a missing optional dependency only matters when used.
        from langchain_openai import ChatOpenAI

        kwargs: Dict[str, Any] = {"model": spec.api_model}
        if spec.reasoning_effort is not None:
            kwargs["reasoning_effort"] = spec.reasoning_effort
        kwargs.update(overrides)
        return ChatOpenAI(**kwargs)

    if spec.provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        kwargs = {"model": spec.api_model}
        # Drop OpenAI-only kwargs callers may pass.
        for key in ("reasoning_effort",):
            overrides.pop(key, None)
        kwargs.update(overrides)
        return ChatAnthropic(**kwargs)

    raise ValueError(f"Unsupported provider for model {model_id!r}: {spec.provider}")


def model_ctor_for_role(role: Role, **overrides: Any) -> Callable[..., BaseChatModel]:
    """Return a zero-argument callable that resolves the current model for *role*.

    The model id is looked up at *call time*, so changing the selection
    affects the next graph build without needing to re-wire ``model_ctor``
    fields on every agent definition.
    """

    def ctor() -> BaseChatModel:
        return build_chat_model(get_model_id(role), **overrides)

    return ctor
