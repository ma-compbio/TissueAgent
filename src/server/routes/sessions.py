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
import re
import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import List, Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse
from pydantic import BaseModel
from starlette.background import BackgroundTask

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


def _flush_active_session_to_disk() -> None:
    """Persist the in-memory session to its project's ``.chat.json``.

    Called before parking/switching/deleting so the outgoing project's file
    reflects the latest in-memory state — crucially ``subagent_states``, which
    ``switch_active_project`` would otherwise strand: it parks by *renaming the
    folder*, so whatever stale ``.chat.json`` is on disk becomes the parked
    copy. Without this flush, sub-agent traces linked after the last auto-save
    are lost on switch. Best-effort: never raises (a failed flush must not block
    the switch itself).
    """
    if not session.project_id:
        return
    messages = session.agent_state.get("messages", [])
    if not messages:
        return
    try:
        from server.plan_store import plan_store
        from server.utils import collect_prompts_snapshot

        save_session(
            messages=messages,
            subagent_states=session.subagent_states,
            uploaded_pdfs=session.uploaded_pdfs,
            replan_count=session.agent_state.get("replan_count", 0),
            replan_history=session.agent_state.get("replan_history", []),
            recruiter_retry_count=session.agent_state.get("recruiter_retry_count", 0),
            mode=session.mode,
            plan_markdown=plan_store.read_markdown(),
            prompts_snapshot=collect_prompts_snapshot(),
            project_id=session.project_id,
            # Keep an already-generated (LLM) title; don't clobber on re-save.
            title=session.project_title if session.project_title_generated else None,
        )
    except Exception as e:
        logging.warning(f"Pre-switch flush failed for {session.project_id}: {e}")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/clear")
async def clear_current_session():
    """Start a new project: park the current one, reset to a clean slate.

    "Start a new project" must (1) preserve the current conversation +
    outputs as a standalone project in the list, and (2) leave the session
    ready to mint a *fresh* project on the next prompt. So we flush the
    in-memory state to disk, then ``switch_active_project(None)`` to park
    ``workspace/project/`` → ``projects/<old_id>/`` and recreate an empty
    active shell (which also clears ``session.project_id``). Without the
    park + id-clear, the next prompt would reuse the old id and overwrite
    the just-saved project in place. Refuses while the agent is running.
    """
    if session.is_running:
        raise HTTPException(
            status_code=409,
            detail=(
                "The agent is currently running. Wait for the run to finish "
                "(or cancel it) before clearing."
            ),
        )

    # 1. Flush the current project's in-memory state (esp. subagent traces)
    #    to its .chat.json so the parked copy is complete.
    _flush_active_session_to_disk()

    # 2. Park the current project (→ projects/<old_id>/) and stand up a fresh
    #    empty active shell. Only meaningful when a project is actually active
    #    with a saved conversation; a blank shell has nothing to park.
    had_project = bool(session.project_id and session.agent_state.get("messages"))
    if had_project:
        try:
            switch_active_project(None)
        except Exception as e:
            logging.warning(f"Park-on-new-project failed: {e}")

    # 3. Wipe the in-memory session and plan for the fresh start.
    session.reset()
    # switch_active_project(None) clears session.project_id; ensure it's None
    # even on the no-project path so the next prompt mints a new one.
    session.project_id = None
    session.project_title = ""
    session.project_title_generated = False

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
    active_pid = read_active_project_id()
    result: List[SessionInfo] = []
    for chat_path in list_project_chat_files():
        # The active project's chat lives under ACTIVE_PROJECT_DIR (folder name
        # "project"), so parent.name is NOT its real id — resolve that from the
        # active .project_id. Parked projects' folder name IS their id.
        if chat_path.parent == ACTIVE_PROJECT_DIR and active_pid:
            project_id = active_pid
        else:
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

    # Flush the outgoing project's in-memory state (esp. subagent traces) to its
    # .chat.json BEFORE parking — switch_active_project parks by renaming the
    # folder, so an unsaved in-memory delta would be stranded/lost otherwise.
    _flush_active_session_to_disk()

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


def _slugify(text: str, fallback: str) -> str:
    """A filesystem/download-safe slug from a project title."""
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "_", (text or "").strip()).strip("_")
    return slug[:80] or fallback


@router.get("/{filename}/download")
async def download_project(filename: str):
    """Download a whole project (chat + uploads + outputs) as a single zip.

    Bundles everything on disk for the project: the ``chat.json`` transcript,
    the ``uploads/`` inputs, and the ``outputs/`` the agent produced (tables,
    figures, reports, gene_agent artifacts, …). Works for both the active
    project and any parked one — ``_project_dir_safe`` resolves + sandboxes the id.
    """
    project_dir = _project_dir_safe(filename)
    if not project_dir.exists() or not project_dir.is_dir():
        raise HTTPException(status_code=404, detail="Project not found.")

    project_id = _normalize_project_id(filename)

    # Name the download after the project's title when we have one.
    title = ""
    chat_path = project_dir / PROJECT_CHAT_FILENAME
    if chat_path.exists():
        try:
            title = read_session_title(chat_path)
        except Exception:
            title = ""
    slug = _slugify(title, fallback=project_id)
    zip_name = f"{slug}.zip"

    # Build the archive in a temp file, then stream it and delete afterwards.
    tmp = tempfile.NamedTemporaryFile(prefix="project_", suffix=".zip", delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()
    try:
        with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(project_dir.rglob("*")):
                if path.is_file():
                    # Store under a top-level folder named for the project so the
                    # archive extracts into one tidy directory.
                    arcname = Path(slug) / path.relative_to(project_dir)
                    zf.write(path, arcname.as_posix())
    except OSError as e:
        tmp_path.unlink(missing_ok=True)
        logging.warning(f"Project download zip failed for {project_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to build project archive.")

    return FileResponse(
        path=str(tmp_path),
        media_type="application/zip",
        filename=zip_name,
        background=BackgroundTask(lambda: tmp_path.unlink(missing_ok=True)),
    )
