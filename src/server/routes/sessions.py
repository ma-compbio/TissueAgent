"""REST endpoints for session save/load/list/export."""

import logging
from datetime import datetime
from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from config import SESSIONS_DIR
from server.session_manager import session
from server.utils import (
    SESSION_FILENAME_PREFIX,
    SESSION_FILENAME_SUFFIX,
    build_session_html,
    load_session,
    save_session,
    session_option_label,
)

router = APIRouter(prefix="/api/sessions")


class SessionInfo(BaseModel):
    """Metadata for a saved session."""

    filename: str
    label: str
    path: str


class SaveResult(BaseModel):
    """Result of saving a session."""

    filename: str
    label: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/save", response_model=SaveResult)
async def save_current_session():
    """Save the current chat session to disk."""
    messages = session.agent_state.get("messages", [])
    if not messages:
        raise HTTPException(status_code=400, detail="No conversation history to save.")

    try:
        path = save_session(
            messages=messages,
            subagent_states=session.subagent_states,
            uploaded_pdfs=session.uploaded_pdfs,
            replan_count=session.agent_state.get("replan_count", 0),
            replan_history=session.agent_state.get("replan_history", []),
        )
    except Exception as e:
        logging.error("Failed to save session", exc_info=e)
        raise HTTPException(status_code=500, detail="Failed to save session.")

    return SaveResult(
        filename=path.name,
        label=session_option_label(path),
    )


@router.get("/list", response_model=List[SessionInfo])
async def list_sessions():
    """List all saved sessions sorted by timestamp (newest first)."""
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(
        SESSIONS_DIR.glob(f"{SESSION_FILENAME_PREFIX}*{SESSION_FILENAME_SUFFIX}"),
        reverse=True,
    )
    return [
        SessionInfo(
            filename=f.name,
            label=session_option_label(f),
            path=str(f),
        )
        for f in files
    ]


@router.post("/load")
async def load_selected_session(filename: str):
    """Load a saved session by filename, restoring conversation state."""
    path = SESSIONS_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Session file not found.")
    if not path.resolve().is_relative_to(SESSIONS_DIR.resolve()):
        raise HTTPException(status_code=403, detail="Access denied.")

    try:
        data = load_session(path)
    except Exception as e:
        logging.error("Failed to load session", exc_info=e)
        raise HTTPException(status_code=500, detail="Failed to load session file.")

    # Restore state
    session.agent_state["messages"] = data["messages"]
    session.agent_state["replan_count"] = data["replan_count"]
    session.agent_state["replan_history"] = data["replan_history"]
    session.subagent_states = data["subagent_states"]
    session.pending_subagent_states.clear()
    session.uploaded_pdfs = data["uploaded_pdfs"]
    session.pending_images = []
    session.ensure_display_state()

    return {"status": "loaded", "filename": filename}


@router.get("/export/html")
async def export_session_html():
    """Export the current session as a standalone HTML document."""
    messages = session.agent_state.get("messages", [])
    if not messages:
        raise HTTPException(status_code=400, detail="No conversation history to export.")

    html = build_session_html(messages, session.subagent_states)
    filename = f"{SESSION_FILENAME_PREFIX}{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.html"

    return HTMLResponse(
        content=html,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
