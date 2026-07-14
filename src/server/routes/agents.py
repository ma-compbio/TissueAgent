"""REST endpoint exposing the agent registry to the frontend.

The assignment-review UI in copilot mode uses this to populate the per-step "assigned agent"
dropdown so it stays in sync with whatever agents are actually registered in
:data:`agents.agent_defns.AgentDefns`.
"""

from typing import List

from fastapi import APIRouter
from pydantic import BaseModel

from agents.agent_defns import AgentDefns

router = APIRouter(prefix="/api/agents")


class AgentInfo(BaseModel):
    """Minimal agent description for the assignment dropdown."""

    id: str
    name: str
    description: str


@router.get("", response_model=List[AgentInfo])
def list_agents() -> List[AgentInfo]:
    """Return every specialist agent registered in ``AgentDefns``."""
    return [AgentInfo(id=a.id, name=a.name, description=a.description) for a in AgentDefns]
