"""REST endpoints for listing and selecting the active chat models."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import models as model_registry

router = APIRouter(prefix="/api/models")


class Selection(BaseModel):
    """Active model selection for orchestration and worker agents."""

    orchestration: str
    worker: str


@router.get("/list")
def list_models() -> dict:
    """Return the catalog of selectable models plus the current selection."""
    return {
        "models": model_registry.list_models(),
        "selection": model_registry.get_selection(),
        "default": model_registry.DEFAULT_MODEL_ID,
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
