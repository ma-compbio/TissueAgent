"""REST endpoint for the evolving plan.

Phase 1: read-only. The UI fetches the current plan on connect; subsequent
updates arrive via WebSocket as ``plan_updated`` events emitted by the
``write_plan`` and ``assign_agents`` tools.
"""

from dataclasses import asdict

from fastapi import APIRouter

from server.plan_store import plan_store

router = APIRouter(prefix="/api/plan")


@router.get("")
def get_plan() -> dict:
    """Return the current plan as both markdown and structured payload."""
    doc = plan_store.read()
    return {
        "markdown": plan_store.read_markdown(),
        "plan": {
            "status": doc.status,
            "user_request": doc.user_request,
            "steps": [asdict(s) for s in doc.steps],
        },
    }
