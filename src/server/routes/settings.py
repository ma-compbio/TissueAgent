"""REST endpoints for runtime agent settings."""

import logging

from fastapi import APIRouter
from pydantic import BaseModel

import agent_settings
from agents.agent_registry.coding_agent_cache.sandbox import ContainerManager

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
    result = agent_settings.set_sandbox_enabled(payload.sandbox_enabled)

    # Actually start the Docker container when the user enables the sandbox.
    if payload.sandbox_enabled:
        try:
            container_mgr = ContainerManager()
            container_mgr.ensure_running()
            logging.info("Docker sandbox started via settings toggle.")
        except Exception as e:
            logging.error("Failed to start Docker sandbox: %s", e)
            # Roll back the setting so the UI reflects reality.
            agent_settings.set_sandbox_enabled(False)
            from fastapi import HTTPException
            raise HTTPException(status_code=500, detail=f"Failed to start sandbox: {e}")

    return result
