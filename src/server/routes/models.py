"""REST endpoints for listing and selecting the active chat models."""

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import models as model_registry

router = APIRouter(prefix="/api/models")


class Selection(BaseModel):
    """Active model selection for orchestration and worker agents."""

    orchestration: str
    worker: str


class ApiKeyPayload(BaseModel):
    """Set or clear the API key for a single provider."""

    provider: str
    key: Optional[str] = None  # empty / None clears the UI value (falls back to env)


@router.get("/list")
def list_models() -> dict:
    """Return the catalog of selectable models plus the current selection."""
    return {
        "models": model_registry.list_models(),
        "selection": model_registry.get_selection(),
        "default": model_registry.DEFAULT_MODEL_ID,
        "keys": model_registry.get_key_status(),
    }


@router.post("/set")
def set_models(payload: Selection) -> dict:
    """Update the active model selection.

    The change takes effect on the next user message — the chat handler
    rebuilds the graph lazily before invoking the agent.
    """
    try:
        new_selection = model_registry.set_selection(
            orchestration=payload.orchestration,
            worker=payload.worker,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"selection": new_selection, "revision": model_registry.get_revision()}


@router.get("/keys")
def get_keys() -> dict:
    """Return per-provider API key status (never the key values)."""
    return {"keys": model_registry.get_key_status()}


@router.post("/keys")
def set_key(payload: ApiKeyPayload) -> dict:
    """Set or clear the in-memory API key for a provider.

    A non-empty key takes precedence over the corresponding env var. Pass
    an empty string (or omit ``key``) to clear and fall back to the env.
    """
    try:
        model_registry.set_api_key(payload.provider, payload.key)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    # Bump the revision so the next user message rebuilds the graph,
    # which causes the new key to be picked up at model instantiation.
    # We piggy-back on the selection lock by setting the current
    # selection to itself.
    sel = model_registry.get_selection()
    model_registry.set_selection(sel["orchestration"], sel["worker"])
    return {"keys": model_registry.get_key_status()}
