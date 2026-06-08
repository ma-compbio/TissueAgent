"""REST endpoints for runtime agent settings."""

from fastapi import APIRouter
from pydantic import BaseModel

import agent_settings

router = APIRouter(prefix="/api/settings")


class SandboxPayload(BaseModel):
    """Request body for updating sandbox settings."""

    sandbox_enabled: bool


@router.get("")
def get_settings() -> dict:
    """Return the current agent settings."""
    return agent_settings.get_settings()


@router.post("")
def update_settings(payload: SandboxPayload) -> dict:
    """Update agent settings.

    Changes take effect on the next agent run.
    """
    return agent_settings.set_sandbox_enabled(payload.sandbox_enabled)
