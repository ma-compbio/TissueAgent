"""REST endpoints for session save/load/list/export."""

import logging
from datetime import datetime
from pathlib import Path
from typing import List, Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel

from config import SESSIONS_DIR
from server.session_manager import session
from server.utils import (
    SESSION_FILENAME_PREFIX,
    SESSION_FILENAME_SUFFIX,
    build_session_html,
    build_session_markdown,
    derive_session_title,
    load_session,
    read_session_title,
    save_session,
    session_option_label,
)

router = APIRouter(prefix="/api/sessions")


# ---------------------------------------------------------------------------
# Mode (autopilot / copilot)
# ---------------------------------------------------------------------------


class ModeInfo(BaseModel):
    """Current execution mode for the session."""

    mode: Literal["autopilot", "copilot"]


@router.get("/mode", response_model=ModeInfo)
async def get_mode() -> ModeInfo:
    """Return the current execution mode."""
    return ModeInfo(mode=session.mode)


@router.post("/mode", response_model=ModeInfo)
async def set_mode(payload: ModeInfo) -> ModeInfo:
    """Update the execution mode."""
    session.mode = payload.mode
    return ModeInfo(mode=session.mode)


class SessionInfo(BaseModel):
    """Metadata for a saved session."""

    filename: str
    label: str
    path: str
    title: str = ""


class SaveResult(BaseModel):
    """Result of saving a session."""

    filename: str
    label: str
    title: str = ""


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/clear")
async def clear_current_session():
    """Wipe the current in-memory session.

    Clears the message history, sub-agent traces, file metadata, the
    on-disk plan, and the LangGraph thread state. Refuses while the
    agent is running — the caller should cancel an in-flight run first.
    Returns the cleared mode so the client can update its toggle if it
    cares (mode itself is preserved, since it's a user preference).
    """
    if session.is_running:
        raise HTTPException(
            status_code=409,
            detail=(
                "The agent is currently running. Wait for the run to finish "
                "(or cancel it) before clearing."
            ),
        )

    # Reset in-memory session state. ``reset()`` preserves the compiled
    # agent graph and the user's mode preference; everything else goes.
    session.reset()

    # The plan store is a separate on-disk file; wipe it too.
    from server.plan_store import plan_store
    plan_store.reset()

    return {"status": "cleared", "mode": session.mode}


@router.post("/save", response_model=SaveResult)
async def save_current_session():
    """Save the current chat session to disk."""
    if session.is_running:
        raise HTTPException(
            status_code=409,
            detail=(
                "The agent is currently running. Wait for the run to finish "
                "(or cancel it) before saving."
            ),
        )

    messages = session.agent_state.get("messages", [])
    if not messages:
        raise HTTPException(status_code=400, detail="No conversation history to save.")

    from server.plan_store import plan_store
    from server.utils import collect_prompts_snapshot
    plan_markdown = plan_store.read_markdown()
    prompts_snapshot = collect_prompts_snapshot()

    try:
        path = save_session(
            messages=messages,
            subagent_states=session.subagent_states,
            uploaded_pdfs=session.uploaded_pdfs,
            replan_count=session.agent_state.get("replan_count", 0),
            replan_history=session.agent_state.get("replan_history", []),
            recruiter_retry_count=session.agent_state.get("recruiter_retry_count", 0),
            mode=session.mode,
            plan_markdown=plan_markdown,
            prompts_snapshot=prompts_snapshot,
        )
    except Exception as e:
        logging.error("Failed to save session", exc_info=e)
        raise HTTPException(status_code=500, detail="Failed to save session.")

    title = read_session_title(path)
    return SaveResult(
        filename=path.name,
        label=session_option_label(path, title),
        title=title,
    )


@router.get("/list", response_model=List[SessionInfo])
async def list_sessions():
    """List all saved sessions sorted by timestamp (newest first)."""
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(
        SESSIONS_DIR.glob(f"{SESSION_FILENAME_PREFIX}*{SESSION_FILENAME_SUFFIX}"),
        reverse=True,
    )
    result: List[SessionInfo] = []
    for f in files:
        title = read_session_title(f)
        result.append(
            SessionInfo(
                filename=f.name,
                label=session_option_label(f, title),
                path=str(f),
                title=title,
            )
        )
    return result


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
    session.agent_state["recruiter_retry_count"] = data.get("recruiter_retry_count", 0)
    session.subagent_states = data["subagent_states"]
    session.pending_subagent_states.clear()
    session.uploaded_pdfs = data["uploaded_pdfs"]
    session.pending_images = []
    session.mode = data["mode"]  # type: ignore[assignment]
    session.ensure_display_state()

    # Restore the plan markdown so the panel and HTML exports stay in
    # sync with what the saved conversation produced. ``write_markdown``
    # bypasses the normalising round-trip so the user's saved content is
    # written verbatim.
    from server.plan_store import plan_store
    plan_markdown = data.get("plan_markdown", "") or ""
    if plan_markdown.strip():
        plan_store.write_markdown(plan_markdown)
    else:
        plan_store.reset()

    return {"status": "loaded", "filename": filename, "mode": session.mode}


@router.delete("/{filename}")
async def delete_session(filename: str):
    """Delete a saved session file. Refuses while a run is in progress."""
    if session.is_running:
        raise HTTPException(
            status_code=409,
            detail="Cannot delete sessions while the agent is running.",
        )

    path = SESSIONS_DIR / filename
    # Path traversal guard — refuse anything that escapes SESSIONS_DIR.
    try:
        if not path.resolve().is_relative_to(SESSIONS_DIR.resolve()):
            raise HTTPException(status_code=403, detail="Access denied.")
    except (ValueError, OSError):
        raise HTTPException(status_code=400, detail="Invalid filename.")

    if not path.exists():
        raise HTTPException(status_code=404, detail="Session file not found.")

    # Sanity check: only allow deleting our own session files, not
    # arbitrary files that may happen to live under SESSIONS_DIR.
    if not (
        path.name.startswith(SESSION_FILENAME_PREFIX)
        and path.name.endswith(SESSION_FILENAME_SUFFIX)
    ):
        raise HTTPException(
            status_code=400,
            detail="Refusing to delete files that don't look like session exports.",
        )

    try:
        path.unlink()
    except Exception as e:
        logging.error("Failed to delete session", exc_info=e)
        raise HTTPException(status_code=500, detail="Failed to delete session.")

    return {"status": "deleted", "filename": filename}


@router.get("/export/html")
async def export_session_html():
    """Export the current session as a standalone HTML document."""
    messages = session.agent_state.get("messages", [])
    if not messages:
        raise HTTPException(status_code=400, detail="No conversation history to export.")

    from server.plan_store import plan_store, annotate_steps_with_params
    from server.utils import collect_prompts_snapshot
    plan_markdown = plan_store.read_markdown()
    plan_doc = plan_store.read()
    annotate_steps_with_params(plan_doc, messages)
    prompts_snapshot = collect_prompts_snapshot()

    html = build_session_html(
        messages,
        session.subagent_states,
        plan_markdown,
        prompts_snapshot=prompts_snapshot,
        plan_doc=plan_doc,
    )
    filename = f"{SESSION_FILENAME_PREFIX}{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.html"

    return HTMLResponse(
        content=html,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export/markdown")
async def export_session_markdown():
    """Export the current session as a plain markdown document."""
    messages = session.agent_state.get("messages", [])
    if not messages:
        raise HTTPException(status_code=400, detail="No conversation history to export.")

    from server.plan_store import plan_store, annotate_steps_with_params
    from server.utils import collect_prompts_snapshot
    plan_markdown = plan_store.read_markdown()
    plan_doc = plan_store.read()
    annotate_steps_with_params(plan_doc, messages)
    title = derive_session_title(messages)
    prompts_snapshot = collect_prompts_snapshot()

    body = build_session_markdown(
        messages, plan_markdown, title,
        prompts_snapshot=prompts_snapshot,
        plan_doc=plan_doc,
    )
    filename = f"{SESSION_FILENAME_PREFIX}{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.md"

    return PlainTextResponse(
        content=body,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
