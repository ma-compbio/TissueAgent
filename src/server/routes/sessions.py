"""REST endpoints for project save/load/list/export.

A "project" is one folder under ``projects/<id>/`` containing
``chat.json`` (the saved conversation) and ``outputs/`` (the agent's
per-project working directory). The endpoints here all key off the
project id, which doubles as the on-disk folder name.

The route is still mounted at ``/api/sessions`` because the frontend
historical contract talks about "sessions"; the disk layout underneath
is the new projects layout.
"""

import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel

from config import (
    ACTIVE_PROJECT_DIR,
    PROJECT_CHAT_FILENAME,
    PROJECT_OUTPUTS_DIRNAME,
    PROJECTS_DIR,
)
from server.session_manager import session
from server.utils import (
    SESSION_FILENAME_PREFIX,
    SESSION_FILENAME_SUFFIX,
    SwitchCollisionError,
    SwitchMissingError,
    build_session_html,
    build_session_markdown,
    derive_session_title,
    list_project_chat_files,
    project_dir_for,
    read_active_project_id,
    read_session_title,
    rehydrate_session_from_chat,
    save_session,
    session_option_label,
    switch_active_project,
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
    """Metadata for a saved project.

    ``filename`` is the project_id (also the on-disk folder name); kept
    under the legacy field name so the frontend type contract didn't
    have to change in lockstep.
    """

    filename: str
    label: str
    path: str
    title: str = ""
    project_id: str = ""
    saved_at: str = ""


class SaveResult(BaseModel):
    """Result of saving a session."""

    filename: str
    label: str
    title: str = ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalize_project_id(raw: str) -> str:
    """Accept legacy ``session_<id>.json`` filenames as well as bare ids."""
    if not raw:
        return ""
    if raw.endswith(SESSION_FILENAME_SUFFIX):
        raw = raw[: -len(SESSION_FILENAME_SUFFIX)]
    if raw.startswith(SESSION_FILENAME_PREFIX):
        raw = raw[len(SESSION_FILENAME_PREFIX):]
    return raw


def _project_dir_safe(project_id: str) -> Path:
    """Return the project's on-disk folder, guarding against traversal.

    The id may resolve to either ACTIVE_PROJECT_DIR (when ``project_id``
    matches the currently-bound project) or ``PROJECTS_DIR/<id>/``.
    Both are valid; reject anything else as an attempted escape.
    """
    project_id = _normalize_project_id(project_id)
    if not project_id or "/" in project_id or "\\" in project_id:
        raise HTTPException(status_code=400, detail="Invalid project id.")
    candidate = project_dir_for(project_id)
    try:
        resolved = candidate.resolve()
        allowed = (PROJECTS_DIR.resolve(), ACTIVE_PROJECT_DIR.resolve())
        if not any(resolved.is_relative_to(root) or resolved == root for root in allowed):
            raise HTTPException(status_code=403, detail="Access denied.")
    except (ValueError, OSError):
        raise HTTPException(status_code=400, detail="Invalid project id.")
    return candidate


def _saved_at_str(path: Path) -> str:
    """File-mtime formatted for the projects list."""
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    except OSError:
        return ""


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/clear")
async def clear_current_session():
    """Wipe the current in-memory session.

    Clears chat history, sub-agent traces, file metadata, the on-disk
    plan, and the LangGraph thread state. The on-disk project file (if
    any) is left alone — this is "start a new project", not "delete the
    current one". Refuses while the agent is running; the caller should
    cancel an in-flight run first. Returns the cleared mode so the client
    can update its toggle if it cares (mode itself is preserved, since it's a user preference).
    """
    if session.is_running:
        raise HTTPException(
            status_code=409,
            detail=(
                "The agent is currently running. Wait for the run to finish "
                "(or cancel it) before clearing."
            ),
        )

    session.reset()

    from server.plan_store import plan_store
    plan_store.reset()

    return {"status": "cleared", "mode": session.mode}


@router.post("/save", response_model=SaveResult)
async def save_current_session():
    """Save the current chat session to its project folder on disk."""
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
            project_id=session.project_id,
        )
    except Exception as e:
        logging.error("Failed to save session", exc_info=e)
        raise HTTPException(status_code=500, detail="Failed to save session.")

    title = read_session_title(path)
    # ``filename`` here is the project_id (also the parent folder name).
    project_id = path.parent.name
    return SaveResult(
        filename=project_id,
        label=session_option_label(path, title),
        title=title,
    )


class CurrentProject(BaseModel):
    """The project currently bound to the in-memory session, if any."""

    project_id: str = ""
    title: str = ""


@router.get("/current", response_model=CurrentProject)
async def current_project() -> CurrentProject:
    """Return the active project id so the sidebar can highlight it on load."""
    return CurrentProject(
        project_id=session.project_id or "",
        title=session.project_title or "",
    )


@router.get("/list", response_model=List[SessionInfo])
async def list_sessions():
    """List all saved projects, most recently modified first."""
    result: List[SessionInfo] = []
    for chat_path in list_project_chat_files():
        project_id = chat_path.parent.name
        title = read_session_title(chat_path)
        result.append(
            SessionInfo(
                filename=project_id,  # legacy field name, see SessionInfo doc
                label=session_option_label(chat_path, title),
                path=str(chat_path),
                title=title,
                project_id=project_id,
                saved_at=_saved_at_str(chat_path),
            )
        )
    return result


@router.post("/load")
async def load_selected_session(filename: str):
    """Load a saved project by id. ``filename`` is the project_id.

    Swaps the active project on disk (renames the parked folder into
    ``workspace/project/``, parks whatever was previously active), then
    rehydrates the in-memory session from the now-active ``.chat.json``.
    """
    if session.is_running:
        raise HTTPException(
            status_code=409,
            detail="Cannot load a project while the agent is running.",
        )

    project_id = _normalize_project_id(filename)
    if not project_id or "/" in project_id or "\\" in project_id:
        raise HTTPException(status_code=400, detail="Invalid project id.")

    # No-op when it's already active; otherwise the parked folder must exist.
    if read_active_project_id() != project_id and not (PROJECTS_DIR / project_id).exists():
        raise HTTPException(status_code=404, detail="Project not found.")

    try:
        switch_active_project(project_id)
    except SwitchCollisionError as e:
        logging.error("Switch collision while loading", exc_info=e)
        raise HTTPException(status_code=500, detail="Project switch collided on disk.")
    except SwitchMissingError:
        raise HTTPException(status_code=404, detail="Project not found.")
    except Exception as e:
        logging.error("Failed to switch projects", exc_info=e)
        raise HTTPException(status_code=500, detail="Failed to load project.")

    chat_path = ACTIVE_PROJECT_DIR / PROJECT_CHAT_FILENAME
    if not chat_path.exists():
        raise HTTPException(status_code=404, detail="Project chat file missing.")

    try:
        rehydrate_session_from_chat(chat_path)
    except Exception as e:
        logging.error("Failed to load session", exc_info=e)
        raise HTTPException(status_code=500, detail="Failed to load project file.")

    return {
        "status": "loaded",
        "filename": project_id,
        "mode": session.mode,
    }


@router.delete("/{filename}")
async def delete_session(filename: str):
    """Delete a project folder (chat + outputs). Refuses during a run.

    If the project is currently active, it's first parked
    (``switch_active_project(None)``) so the rmtree operates on a stable
    parked folder rather than the live workspace.
    """
    if session.is_running:
        raise HTTPException(
            status_code=409,
            detail="Cannot delete projects while the agent is running.",
        )

    project_id = _normalize_project_id(filename)
    if not project_id or "/" in project_id or "\\" in project_id:
        raise HTTPException(status_code=400, detail="Invalid project id.")

    # If active, park it so the rmtree below targets a parked folder.
    if read_active_project_id() == project_id:
        try:
            switch_active_project(None)
        except Exception as e:
            logging.error("Failed to park before delete", exc_info=e)
            raise HTTPException(status_code=500, detail="Failed to park project for delete.")

    parked = PROJECTS_DIR / project_id
    if not parked.exists():
        raise HTTPException(status_code=404, detail="Project not found.")

    try:
        shutil.rmtree(parked)
    except Exception as e:
        logging.error("Failed to delete project", exc_info=e)
        raise HTTPException(status_code=500, detail="Failed to delete project.")

    return {"status": "deleted", "filename": project_id}


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
