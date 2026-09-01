"""WebSocket endpoint for real-time agent chat.

Handles bidirectional communication: receives user messages, invokes the LangGraph agent, and streams back intermediate
traces and sub-agent states.
"""

import asyncio
import json
import logging
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime
from typing import Optional

import anthropic
import openai
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState
from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.errors import GraphRecursionError
from pathlib import Path

from agents.manager_agent.tools import ManagerTools
from config import DATA_DIR, RECURSION_LIMIT
from graph.ui_events import emit_message
from server.message_serializer import serialize_history, serialize_message, serialize_subagent_state
from server.session_manager import session
from server.usage_tracker import usage_tracker
from server.utils import (
    SUBAGENT_BADGES,
    SUBAGENT_DEFAULT_AVATAR,
    derive_session_title,
    file_to_data_url,
    project_outputs_dir,
    save_session,
    upload_pdf_to_openai,
    write_active_project_id,
)

router = APIRouter()

_executor = ThreadPoolExecutor(max_workers=1)

# Track the current in-flight graph invocation so a WebSocket disconnect can
# cancel it (best-effort — the underlying compute already started may still
# run to completion, but we stop touching shared state from the finally block).
_current_run_future: Future | None = None

# Set when the user clicks Stop. The graph runs on a thread we can't forcibly
# kill once ``invoke`` has started, so this signals the async run loop to break
# out immediately: the UI stops, ``is_running`` clears, and the orphaned worker
# thread finishes silently with its output discarded. Cleared at the start of
# every run.
_cancel_requested = threading.Event()

# The background task running the current graph invocation. Kept so the receive
# loop can observe / clean it up. ``_run_graph`` is launched as a task (rather
# than awaited inline) so the receive loop stays free to process a cancel frame
# while a run is in flight.
_current_run_task: "asyncio.Task | None" = None

# Monotonic run id. Each run captures its own id; a cancelled/orphaned run whose
# id no longer matches ``_run_generation`` must NOT mutate shared session state
# (is_running, queues, run_complete) — otherwise, after Stop → new run, the old
# run's cleanup would clobber the new run's ``is_running`` and wedge the session
# so no further runs can start.
_run_generation: int = 0


def _ws_connected(ws: WebSocket) -> bool:
    """Return True when *ws* is still safe to send on."""
    return (
        ws.client_state == WebSocketState.CONNECTED
        and ws.application_state == WebSocketState.CONNECTED
    )


async def _safe_send_json(ws: WebSocket, payload: dict) -> None:
    """Send a JSON payload only if the connection is still open."""
    if not _ws_connected(ws):
        return
    try:
        await ws.send_json(payload)
    except (WebSocketDisconnect, RuntimeError) as exc:
        logging.debug("send_json skipped (socket closed): %s", exc)


# ---------------------------------------------------------------------------
# Auto-save — persist projects to disk as the run unfolds
# ---------------------------------------------------------------------------


def _ensure_project_id() -> str:
    """Mint the project on first prompt and handle one-time side effects.

    The active project dir (``workspace/project/``) always exists as an
    empty shell, so any files the user uploaded pre-prompt are already
    in their final location — no migration needed. We just have to:
      - Assign the project an id (recorded both in session and as a
        ``.project_id`` dotfile inside the active project dir).
      - Re-arm the kernel so the next code execution sees the canonical
        workspace root (``/workspace``) as its cwd.

    Idempotent on subsequent calls — already-minted projects no-op.
    """
    fresh = session.project_id is None
    project_id = session.ensure_project_id()
    if not fresh:
        return project_id

    try:
        write_active_project_id(project_id)
    except Exception as e:
        logging.warning(f"Failed to write .project_id: {e}")

    try:
        project_outputs_dir(project_id)  # ensure outputs dir exists
        from server.main import set_kernel_workspace
        set_kernel_workspace(DATA_DIR)
    except Exception as e:
        logging.warning(f"Failed to bind kernel workspace for new project: {e}")

    return project_id


def _persist_project(notify_ws: Optional[WebSocket] = None) -> None:
    """Write the current session to its project file. Best-effort."""
    messages = session.agent_state.get("messages", [])
    if not messages or not session.project_id:
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
            mode=session.mode,
            plan_markdown=plan_store.read_markdown(),
            prompts_snapshot=collect_prompts_snapshot(),
            project_id=session.project_id,
            # Preserve an already-generated (LLM) title across re-saves;
            # otherwise fall back to the cheap first-line derivation.
            title=session.project_title if session.project_title_generated else None,
        )
        if not session.project_title_generated:
            session.project_title = derive_session_title(messages)
    except Exception as e:
        # Auto-save must never break the run. Log + continue.
        logging.warning(f"Auto-save failed: {e}")


async def _emit_metrics(ws: WebSocket) -> None:
    """Send the current usage snapshot to the client."""
    await ws.send_json({"type": "metrics_updated", "data": usage_tracker.to_dict()})


async def _broadcast_project_saved(ws: WebSocket) -> None:
    """Tell the frontend its project list is now stale."""
    if not session.project_id:
        return
    await ws.send_json({
        "type": "project_saved",
        "data": {
            "project_id": session.project_id,
            "title": session.project_title,
        },
    })


async def _ensure_llm_title(ws: WebSocket) -> None:
    """Generate an LLM-summarized project title once, then persist + broadcast.

    No-op if there's no active project or a title was already generated. The
    generation is best-effort: failures fall back to the first-line title and
    never interrupt the run.
    """
    if not session.project_id or session.project_title_generated:
        return
    messages = session.agent_state.get("messages", [])
    if not messages:
        return
    try:
        from server.utils import generate_session_title

        title = await generate_session_title(messages)
        # Mark generated even if empty, so we don't retry every message.
        session.project_title_generated = True
        if title:
            session.project_title = title
            _persist_project()
            await _broadcast_project_saved(ws)
    except Exception as e:
        logging.warning(f"Title generation step failed: {e}")


@router.websocket("/ws/chat")
async def websocket_chat(ws: WebSocket):
    """Primary real-time chat channel.

    On connect, sends current conversation history. On receive, processes user messages and streams agent traces back.
    """
    await ws.accept()

    # Send current history on connect
    history = serialize_history(
        session.agent_state["messages"],
        session.subagent_states,
    )
    await ws.send_json({"type": "history", "data": history})

    # Send current execution mode on connect so the UI can render the
    # sidebar toggle in the correct position without an extra fetch.
    await ws.send_json({"type": "mode_updated", "data": {"mode": session.mode}})

    # Re-send the metrics snapshot so a page refresh preserves the Metrics page.
    await _emit_metrics(ws)

    try:
        while True:
            raw = await ws.receive_text()
            try:
                data = json.loads(raw)
            except (json.JSONDecodeError, TypeError) as exc:
                logging.warning("Ignoring malformed frame from client: %s", exc)
                await _safe_send_json(ws, {
                    "type": "run_error",
                    "error_type": "MalformedFrame",
                    "detail": f"Frame is not valid JSON: {exc}",
                })
                continue
            if not isinstance(data, dict):
                logging.warning("Ignoring non-object frame from client: %r", data)
                continue

            msg_type = data.get("type")
            if msg_type == "send_message":
                await _handle_user_message(ws, data)
            elif msg_type == "set_mode":
                await _handle_set_mode(ws, data)
            elif msg_type == "plan_approved":
                await _handle_resume(ws, expected_pause="before_recruiter")
            elif msg_type == "assignments_approved":
                await _handle_resume(ws, expected_pause="before_manager")
            elif msg_type == "plan_edited":
                await _handle_plan_edited(ws, data)
            elif msg_type == "assignments_edited":
                await _handle_assignments_edited(ws, data)
            elif msg_type == "plan_feedback":
                await _handle_plan_feedback(ws, data)
            elif msg_type == "assignments_feedback":
                await _handle_assignments_feedback(ws, data)
            elif msg_type == "run_cancelled":
                await _handle_run_cancelled(ws)
    except WebSocketDisconnect:
        logging.info("WebSocket client disconnected")
    except Exception as e:
        logging.error(f"WebSocket error: {e}", exc_info=True)
    finally:
        # Best-effort cancel of any in-flight graph invocation so it can't
        # continue mutating shared session state after the client has gone.
        # Signal the run loop (which polls _cancel_requested and _ws_connected)
        # and nudge the worker future.
        global _current_run_future
        _cancel_requested.set()
        pending = _current_run_future
        if pending is not None and not pending.done():
            pending.cancel()


async def _handle_set_mode(ws: WebSocket, data: dict):
    """Update the session execution mode and echo the new value back.

    Mode changes take effect on the *next* user prompt. A run that's already in flight keeps the mode it started with —
    ``_run_graph`` snapshots mode at invoke time, so toggling mid-run is safe and does not affect the current run's
    pause behavior.
    """
    requested = data.get("mode")
    if requested not in ("autopilot", "copilot"):
        await ws.send_json({
            "type": "run_error",
            "error_type": "InvalidMode",
            "detail": f"Unknown mode: {requested!r}",
        })
        return

    session.mode = requested  # type: ignore[assignment]
    await ws.send_json({"type": "mode_updated", "data": {"mode": session.mode}})


async def _handle_user_message(ws: WebSocket, data: dict):
    """Process a user message and stream the agent's response."""
    logging.info(
        "send_message received (is_running=%s, project_id=%s, mode=%s).",
        session.is_running, session.project_id, session.mode,
    )
    if session.is_running:
        logging.warning("Rejecting send_message: another run is already in flight.")
        await ws.send_json({
            "type": "run_error",
            "error_type": "AlreadyRunning",
            "detail": "Agent is already processing a message.",
        })
        return

    text = data.get("text", "")

    # Build multimodal content parts.
    # User-uploaded images are saved under the active project's
    # uploads/ dir by the file upload route; we reference them by
    # workspace-relative path so that agents can read them via the
    # standard read() tool.
    image_refs = []
    for img in session.pending_images:
        img_path = Path(img["path"])
        if img_path.exists():
            try:
                rel = img_path.relative_to(DATA_DIR)
            except ValueError:
                rel = img_path.name
            image_refs.append(str(rel))

    if image_refs:
        listing = ", ".join(image_refs)
        text += f"\n\n[Attached images (readable via the read tool): {listing}]"

    content_parts = [{"type": "text", "text": text}]

    # Add PDF attachments
    for pdf in session.uploaded_pdfs:
        if "file_id" not in pdf:
            try:
                # upload_pdf_to_openai does synchronous HTTP; run it off the
                # event loop so it doesn't stall every other WebSocket while
                # a large PDF uploads.
                file_id = await asyncio.to_thread(upload_pdf_to_openai, Path(pdf["path"]))
                pdf["file_id"] = file_id
                pdf["attached_to_conversation"] = False
            except Exception as e:
                await _safe_send_json(ws, {
                    "type": "run_error",
                    "error_type": "PDFUploadError",
                    "detail": f"Failed to upload PDF {pdf['name']}: {e}",
                })
                continue

        if not pdf.get("attached_to_conversation", False):
            content_parts.append({
                "type": "file",
                "file": {"file_id": pdf["file_id"]},
            })
            pdf["attached_to_conversation"] = True

    # Create and record the user message
    user_message = HumanMessage(content=content_parts)
    emit_message(user_message)

    session.agent_state["messages"].append(user_message)
    session.agent_state["original_user_request"] = text
    session.agent_state.setdefault("replan_count", 0)
    session.agent_state.setdefault("replan_history", [])
    session.agent_state.setdefault("recruiter_retry_count", 0)

    # New user turn → fresh checkpointer thread, clear any stale plan + pause.
    from server.plan_store import plan_store as _plan_store
    from server.session_manager import _new_thread_id
    _plan_store.reset()
    session.thread_id = _new_thread_id()
    session.paused_at = None
    session.gates_fired = set()

    # Send the user message back to client for display
    await ws.send_json({
        "type": "message",
        "data": serialize_message(user_message),
    })
    # Register for dedup so _drain_queues won't re-send from ui_event_queue
    session.append_display_message(user_message)

    # Clear pending images after sending
    session.pending_images = []

    # Auto-save: on the first user message of the conversation, mint a
    # stable project_id and write the initial file. Subsequent calls
    # update the same file in place so the project list shows the run
    # progressing in real time. All best-effort: never let auto-save
    # block or break the actual agent invocation.
    try:
        _ensure_project_id()
        _persist_project()
        await _broadcast_project_saved(ws)
        # Summarize the first prompt into a concise project title (once).
        await _ensure_llm_title(ws)
    except Exception as e:
        logging.warning(f"Auto-save (pre-run) failed: {e}")

    # Rebuild the agent graph if the user changed the model since the last turn.
    logging.info("Invoking agent graph for user message (mode=%s).", session.mode)
    from server.main import ensure_graph_current
    ensure_graph_current()

    # First invocation of this turn: pass the current message state in.
    # Launched as a background task so the receive loop can still handle a
    # Stop (run_cancelled) frame while the run streams.
    _launch_run(ws, graph_input=session.agent_state)


# ---------------------------------------------------------------------------
# Graph driver — shared by initial invoke and copilot resume
# ---------------------------------------------------------------------------

# Node IDs where copilot pauses. Match `assign_agent_node_id` in graph.py.
_PAUSE_BEFORE_NODES = ["recruiter_agent", "manager_agent"]

# Each gate's user-facing label. Keep in sync with ``_interrupt_label``.
_NODE_TO_GATE: dict[str, str] = {
    "recruiter_agent": "before_recruiter",
    "manager_agent":   "before_manager",
}


def _interrupt_label(next_nodes) -> Optional[str]:
    """Map LangGraph's ``next`` tuple onto our pause-name vocabulary."""
    if not next_nodes:
        return None
    if "recruiter_agent" in next_nodes:
        return "before_recruiter"
    if "manager_agent" in next_nodes:
        return "before_manager"
    return None


def _pending_interrupt_nodes() -> list[str]:
    """Nodes that should pause on the *next* invoke for this run.

    LangGraph's ``interrupt_before`` is sticky — a node listed there pauses every time the graph is about to enter it,
    including inner-loop returns (e.g. ``manager_tools`` → ``manager_agent``). We want each gate to fire **at most
    once** per turn, so we exclude gates that have already fired (tracked on ``session.gates_fired``).
    """
    return [
        node
        for node in _PAUSE_BEFORE_NODES
        if _NODE_TO_GATE[node] not in session.gates_fired
    ]


def _launch_run(ws: WebSocket, graph_input) -> None:
    """Run the graph as a background task so the receive loop stays responsive.

    ``_run_graph`` is long-lived; awaiting it inline would block the WebSocket
    receive loop, so a ``run_cancelled`` frame couldn't be read until the run
    finished — making a Stop button useless. Launching it as a task lets the
    loop keep reading frames (Stop, mode changes) while the run streams.
    """
    global _current_run_task

    def _on_done(task: "asyncio.Task") -> None:
        global _current_run_task
        if _current_run_task is task:
            _current_run_task = None
        # Surface (but don't crash on) any error the detached task raised.
        if not task.cancelled():
            exc = task.exception()
            if exc is not None:
                logging.error("Background run task failed", exc_info=exc)

    _current_run_task = asyncio.create_task(_run_graph(ws, graph_input))
    _current_run_task.add_done_callback(_on_done)


async def _run_graph(ws: WebSocket, graph_input):
    """Invoke or resume the graph, then process the outcome.

    *graph_input* is the initial state dict for a fresh turn, or ``None``
    to resume from a checkpoint after a copilot pause.

    The session mode is **snapshotted** at the start of the run. A user
    that toggles autopilot/copilot mid-run will see the change take
    effect on the *next* prompt, not the current one. This keeps the
    pause-detection consistent: a run that started in copilot must
    finish in copilot, otherwise a paused state would be misread as a
    completion the moment the user flips to autopilot.
    """
    run_mode: str = session.mode
    config = {
        "recursion_limit": RECURSION_LIMIT,
        "configurable": {"thread_id": session.thread_id},
    }
    invoke_kwargs = {}
    if run_mode == "copilot":
        pending = _pending_interrupt_nodes()
        if pending:
            invoke_kwargs["interrupt_before"] = pending

    # Record prefix for post-run linkage. For resumes the canonical state
    # still tracks every message produced so far in this turn.
    rendered_prefix = len(session.agent_state["messages"])

    # Claim this run's identity. The finally block only tears down shared state
    # if we're still the current run — see _run_generation.
    global _run_generation
    _run_generation += 1
    my_run_id = _run_generation

    session.is_running = True
    _cancel_requested.clear()
    start_time = time.perf_counter()

    # On a resume (graph_input is None), the plan's on-disk status may
    # still read ``awaiting_*`` from the pause. Flip it to ``running`` so
    # the UI doesn't keep telling the user "your review is needed".
    # Downstream agents (recruiter's state_update_fn, etc.) may
    # overwrite this with a more specific status as they run.
    if graph_input is None:
        from server.plan_store import plan_store as _plan_store
        current = _plan_store.read().status
        if current in ("awaiting_plan_review", "awaiting_assignment_review"):
            await _set_plan_status_and_emit(ws, "running")

    future = _executor.submit(
        session.agent.invoke,
        graph_input,
        config,
        **invoke_kwargs,
    )
    # Expose to the outer handler so a WebSocketDisconnect can cancel us.
    global _current_run_future
    _current_run_future = future

    try:
        while not future.done():
            if not _ws_connected(ws):
                # Client gave up (tab closed / refresh / network blip). The
                # worker thread already running on the executor can't be
                # forcibly killed and will finish regardless, so rather than
                # discarding a run that may be seconds from done — and losing
                # its whole transcript — wait briefly for it to complete and
                # persist the result to disk. Persistence needs no socket; the
                # user can reopen the project and find the finished trace.
                logging.info(
                    "WebSocket disconnected mid-run; attempting to salvage + "
                    "persist the result."
                )
                try:
                    # Bounded wait: don't block the event loop indefinitely on
                    # a run that might still be minutes from finishing.
                    result = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: future.result(timeout=120)
                    )
                except Exception:
                    result = None
                if (
                    isinstance(result, dict)
                    and "messages" in result
                    and my_run_id == _run_generation
                    and not _cancel_requested.is_set()
                ):
                    session.agent_state = result
                    try:
                        # Link sub-agent transcripts so the persisted project
                        # shows the completed cards, then save.
                        _link_subagent_states(rendered_prefix)
                    except Exception as e:
                        logging.warning(f"Salvage link failed: {e}")
                    try:
                        _persist_project()
                        logging.info("Salvaged disconnected run persisted to disk.")
                    except Exception as e:
                        logging.warning(f"Salvage persist failed: {e}")
                else:
                    logging.info(
                        "Disconnected run not salvageable (still running, "
                        "cancelled, or superseded); abandoning invocation."
                    )
                return
            if _cancel_requested.is_set():
                # User clicked Stop. We can't kill the worker thread, but we
                # stop streaming its output and abandon the run now. The
                # orphaned thread finishes in the background; its result is
                # discarded because _handle_run_cancelled mints a fresh
                # thread_id for the next turn. Drain what's already queued so
                # partial output isn't lost, then bail before run_complete.
                # (_handle_run_cancelled owns plan reset + the run_cancelled ack.)
                future.cancel()
                logging.info("Run cancelled by user; abandoning invocation.")
                await _drain_queues(ws)
                return
            await _drain_queues(ws)
            await asyncio.sleep(0.05)

        # The worker finished. If Stop landed in the same tick (or a new run
        # superseded us), don't emit run_complete or mutate state — bail.
        if _cancel_requested.is_set() or my_run_id != _run_generation:
            logging.info("Run finished but was cancelled/superseded; discarding result.")
            return

        result = future.result()
        # Mirror back so the rest of the codebase can keep reading
        # ``session.agent_state`` as the canonical message list.
        if isinstance(result, dict) and "messages" in result:
            session.agent_state = result

        await _drain_queues(ws)

        # Did we land on a copilot interrupt? Inspect the checkpoint.
        # Use the *run-start* mode snapshot, not session.mode, so a
        # toggle mid-run can't be misread as "this run was autopilot".
        graph_state = session.agent.get_state(config)
        pause_label = (
            _interrupt_label(graph_state.next) if run_mode == "copilot" else None
        )

        if pause_label is not None:
            session.paused_at = pause_label
            # Record that this gate has fired so subsequent resumes drop
            # it from ``interrupt_before`` — otherwise the manager would
            # pause again on every loop-back from ``manager_tools`` to
            # ``manager_agent`` and the run would stall after each step.
            session.gates_fired.add(pause_label)
            await _emit_pause(ws, pause_label)
            await _emit_metrics(ws)
            try:
                _persist_project()
                await _broadcast_project_saved(ws)
            except Exception as e:
                logging.warning(f"Auto-save (pause) failed: {e}")
            # Don't link subagent states or send run_complete; we're paused.
            return

        # No pause → run finished. Link subagent transcripts as before.
        session.paused_at = None
        linked_ids = _link_subagent_states(rendered_prefix)
        for tool_id in linked_ids:
            agent_name, final_state, invocation_id = session.subagent_states[tool_id]
            data = serialize_subagent_state(tool_id, agent_name, final_state)
            data["invocation_id"] = invocation_id
            await ws.send_json({
                "type": "subagent_state",
                "data": data,
            })

        # Final plan status flip so the UI shows the pipeline as complete.
        await _set_plan_status_and_emit(ws, "done")

        elapsed = time.perf_counter() - start_time
        await ws.send_json({
            "type": "run_complete",
            "elapsed_seconds": round(elapsed, 1),
        })
        await _emit_metrics(ws)

        try:
            _persist_project()
            await _broadcast_project_saved(ws)
        except Exception as e:
            logging.warning(f"Auto-save (run_complete) failed: {e}")

    except GraphRecursionError as e:
        logging.error("GraphRecursionError", exc_info=e)
        await _safe_send_json(ws, {
            "type": "run_error",
            "error_type": "GraphRecursionError",
            "detail": str(e),
        })
    except (anthropic.BadRequestError, openai.BadRequestError) as e:
        logging.error("BadRequestError", exc_info=e)
        await _safe_send_json(ws, {
            "type": "run_error",
            "error_type": "BadRequestError",
            "detail": str(e),
        })
    except Exception as e:
        logging.error("Unexpected error during agent invocation", exc_info=e)
        await _safe_send_json(ws, {
            "type": "run_error",
            "error_type": type(e).__name__,
            "detail": str(e),
        })
    finally:
        # Only tear down shared state if we're still the current run. A run
        # that was Stopped (and possibly superseded by a new run) must not
        # clobber is_running or drain onto the new run's stream.
        if my_run_id == _run_generation:
            session.is_running = False
            if _current_run_future is future:
                _current_run_future = None
            if _ws_connected(ws):
                await _drain_queues(ws)


async def _emit_pause(ws: WebSocket, pause_label: str) -> None:
    """Flip plan_store status and notify the frontend that a review is due."""
    if pause_label == "before_recruiter":
        new_status = "awaiting_plan_review"
        event_type = "plan_review_requested"
    else:  # before_manager
        new_status = "awaiting_assignment_review"
        event_type = "assignment_review_requested"

    await _set_plan_status_and_emit(ws, new_status, only_if_present=True)
    await ws.send_json({"type": event_type, "data": {"pause": pause_label}})


async def _set_plan_status_and_emit(
    ws: WebSocket, new_status: str, *, only_if_present: bool = True
) -> None:
    """Flip the on-disk plan's top-level status and notify the frontend.

    No-op when the plan is empty (status ``"empty"``) — there's nothing to update, and we don't want to fabricate a plan
    document just to carry a status. Set ``only_if_present=False`` to force-write regardless.

    When transitioning to ``"done"``, any lingering ``"running"`` or ``"pending"`` step statuses
    are flipped to ``"done"`` too. The manager's ``next_step`` only marks a step done when the
    following step is dispatched, so the final step never receives that flip — without this
    cleanup its badge would keep pulsing after the run completes.
    """
    from server.plan_store import plan_store as _plan_store, serialize_plan

    doc = _plan_store.read()
    if only_if_present and doc.status == "empty":
        return

    changed = False
    if doc.status != new_status:
        doc.status = new_status  # type: ignore[assignment]
        changed = True

    if new_status == "done":
        for step in doc.steps:
            if step.status in ("running", "pending"):
                step.status = "done"  # type: ignore[assignment]
                changed = True

    if not changed:
        return  # Nothing to broadcast.

    _plan_store.write(doc)
    await ws.send_json({
        "type": "plan_updated",
        "data": {
            "markdown": _plan_store.read_markdown(),
            "plan": serialize_plan(doc),
        },
    })


async def _require_paused_at(ws: WebSocket, expected_pause: str) -> bool:
    """Validate that the session is paused at the expected gate.

    Returns ``True`` if the caller may proceed. On a mismatch, sends a ``run_error`` over *ws* and returns ``False``.
    """
    if session.paused_at is None:
        await ws.send_json({
            "type": "run_error",
            "error_type": "NotPaused",
            "detail": "No copilot run is awaiting review.",
        })
        return False
    if session.paused_at != expected_pause:
        await ws.send_json({
            "type": "run_error",
            "error_type": "WrongPauseGate",
            "detail": (
                f"Expected action for {expected_pause!r} "
                f"but the run is paused at {session.paused_at!r}."
            ),
        })
        return False
    return True


async def _handle_resume(ws: WebSocket, expected_pause: str) -> None:
    """Resume a copilot-paused run after the user approves as-is."""
    if not await _require_paused_at(ws, expected_pause):
        return
    session.paused_at = None
    # Resume with input=None — LangGraph reads the checkpoint and proceeds.
    _launch_run(ws, graph_input=None)


async def _handle_plan_edited(ws: WebSocket, data: dict) -> None:
    """Persist user-edited plan markdown, emit plan_updated, then resume."""
    if not await _require_paused_at(ws, "before_recruiter"):
        return
    markdown = data.get("markdown") or ""
    await _apply_user_plan_edit_and_resume(ws, markdown, pause="before_recruiter")


async def _handle_assignments_edited(ws: WebSocket, data: dict) -> None:
    """Persist user-edited assignment markdown and resume to manager."""
    if not await _require_paused_at(ws, "before_manager"):
        return
    markdown = data.get("markdown") or ""
    await _apply_user_plan_edit_and_resume(ws, markdown, pause="before_manager")


async def _apply_user_plan_edit_and_resume(
    ws: WebSocket, markdown: str, pause: str
) -> None:
    """Common path for plan_edited and assignments_edited.

    Validates and persists *markdown* via ``plan_store.apply_user_edit``, pushes a ``plan_updated`` event so the UI
    reflects the saved form, and resumes the graph with ``input=None``.
    """
    from server.plan_store import plan_store as _plan_store, PlanEditError, serialize_plan

    try:
        doc = _plan_store.apply_user_edit(markdown)
    except PlanEditError as e:
        await ws.send_json({
            "type": "run_error",
            "error_type": "PlanEditError",
            "detail": str(e),
        })
        return

    await ws.send_json({
        "type": "plan_updated",
        "data": {
            "markdown": _plan_store.read_markdown(),
            "plan": serialize_plan(doc),
        },
    })

    session.paused_at = None
    _launch_run(ws, graph_input=None)


async def _handle_plan_feedback(ws: WebSocket, data: dict) -> None:
    """Rewind to the planner with the user's feedback appended."""
    if not await _require_paused_at(ws, "before_recruiter"):
        return
    await _rewind_to_planner_with_feedback(ws, data.get("text") or "")


async def _handle_assignments_feedback(ws: WebSocket, data: dict) -> None:
    """Rewind to the planner with assignment-stage feedback.

    Both feedback paths re-enter at the planner (see Milestone 4 design): simpler, matches the existing REPLAN loop, and
    the planner can decide whether to actually re-plan or pass through.
    """
    if not await _require_paused_at(ws, "before_manager"):
        return
    await _rewind_to_planner_with_feedback(ws, data.get("text") or "")


async def _rewind_to_planner_with_feedback(ws: WebSocket, text: str) -> None:
    """Append feedback as a HumanMessage and re-invoke from the top.

    Cycles ``thread_id`` so the new run is a fresh checkpointer thread — the old interrupt state is orphaned, which is
    intentional. The feedback message is what the planner sees on its next pass.
    """
    feedback = (text or "").strip()
    if not feedback:
        await ws.send_json({
            "type": "run_error",
            "error_type": "EmptyFeedback",
            "detail": "Feedback text was empty; submit at least one character.",
        })
        return

    from server.plan_store import plan_store as _plan_store
    from server.session_manager import _new_thread_id

    feedback_message = HumanMessage(
        content=f"[Copilot feedback from user] {feedback}"
    )
    emit_message(feedback_message)
    session.agent_state["messages"].append(feedback_message)
    original_request = str(session.agent_state.get("original_user_request", "")).strip()
    session.agent_state["original_user_request"] = (
        f"{original_request}\n\n[Copilot feedback from user] {feedback}".strip()
    )
    session.append_display_message(feedback_message)
    await ws.send_json({
        "type": "message",
        "data": serialize_message(feedback_message),
    })

    # Fresh thread + cleared plan so the planner starts clean. Reset
    # ``gates_fired`` too — this is a brand-new run, both gates should
    # fire again.
    _plan_store.reset()
    session.thread_id = _new_thread_id()
    session.paused_at = None
    session.gates_fired = set()

    _launch_run(ws, graph_input=session.agent_state)


async def _handle_run_cancelled(ws: WebSocket) -> None:
    """Stop the current run, whether it's actively executing or copilot-paused.

    For an in-flight run: signals the async run loop to break out immediately
    (``_cancel_requested``) and cancels the worker future best-effort — the
    thread can't be force-killed, so it finishes silently and its output is
    discarded. For a copilot pause: just tears down the paused state.

    In both cases the checkpointer thread is abandoned (a fresh one is minted
    for the next turn) and the on-disk plan is wiped so the UI doesn't keep
    showing a stale review prompt.
    """
    if session.paused_at is None and not session.is_running:
        # Nothing to cancel — still acknowledge so the UI clears state.
        await ws.send_json({"type": "run_cancelled", "data": {}})
        return

    from server.plan_store import plan_store as _plan_store
    from server.session_manager import _new_thread_id

    # Signal the running loop to abandon streaming, and nudge the worker
    # future (only cancels if it hasn't started — otherwise it runs on).
    _cancel_requested.set()
    if _current_run_future is not None and not _current_run_future.done():
        _current_run_future.cancel()

    _plan_store.reset()
    session.paused_at = None
    session.thread_id = _new_thread_id()
    session.gates_fired = set()
    session.is_running = False

    await ws.send_json({"type": "run_cancelled", "data": {}})


async def _drain_queues(ws: WebSocket):
    """Drain both event and state queues, sending updates to client."""
    if not _ws_connected(ws):
        return
    # Drain UI event queue (now contains typed tuples)
    while not session.ui_event_queue.empty():
        event = session.ui_event_queue.get()

        if isinstance(event, tuple) and len(event) == 2:
            event_type, payload = event

            if event_type == "message":
                # plan_updated markers are emitted by the planner/recruiter
                # state_update_fn via emit_message(); route them to the plan
                # channel instead of the chat transcript.
                if getattr(payload, "name", None) == "plan_updated":
                    plan_payload = (
                        getattr(payload, "additional_kwargs", {}) or {}
                    ).get("plan_payload") or {}
                    from server.plan_store import plan_store as _plan_store
                    markdown = _plan_store.read_markdown()
                    await ws.send_json({
                        "type": "plan_updated",
                        "data": {
                            "markdown": markdown,
                            "plan": plan_payload,
                        },
                    })
                    continue

                # Regular main-agent message
                if session.append_display_message(payload):
                    await ws.send_json({
                        "type": "message",
                        "data": serialize_message(payload),
                    })

            elif event_type == "subagent_start":
                avatar = SUBAGENT_BADGES.get(
                    payload["agent_name"], SUBAGENT_DEFAULT_AVATAR
                )
                await ws.send_json({
                    "type": "subagent_start",
                    "data": {
                        "invocation_id": payload["invocation_id"],
                        "agent_name": payload["agent_name"],
                        "avatar": avatar,
                    },
                })

            elif event_type == "subagent_message":
                data = {
                    "invocation_id": payload["invocation_id"],
                    "agent_name": payload["agent_name"],
                    "message": serialize_message(payload["message"]),
                }
                if payload.get("stream_id") is not None:
                    data["stream_id"] = payload["stream_id"]
                if payload.get("source") is not None:
                    data["source"] = payload["source"]
                await ws.send_json({
                    "type": "subagent_message",
                    "data": data,
                })

            elif event_type == "subagent_token":
                await ws.send_json({"type": "subagent_token", "data": payload})

            elif event_type == "subagent_end":
                await ws.send_json({
                    "type": "subagent_end",
                    "data": {
                        "invocation_id": payload["invocation_id"],
                        "agent_name": payload["agent_name"],
                    },
                })

            elif event_type == "subagent_state":
                # Per-invocation subagent_state pushed from the manager's
                # tool_node right after emitting the wrapping ToolMessage,
                # so the completed sub-agent card appears inline before the
                # graph run finishes.
                tool_id = payload["tool_id"]
                if tool_id in session.subagent_states:
                    continue
                agent_name = payload["agent_name"]
                final_state = payload["final_state"]
                invocation_id = payload["invocation_id"]
                session.subagent_states[tool_id] = (
                    agent_name, final_state, invocation_id,
                )
                data = serialize_subagent_state(
                    tool_id, agent_name, final_state,
                )
                data["invocation_id"] = invocation_id
                await ws.send_json({"type": "subagent_state", "data": data})
        else:
            # Legacy bare-message format (shouldn't happen, but handle safely)
            if session.append_display_message(event):
                await ws.send_json({
                    "type": "message",
                    "data": serialize_message(event),
                })

    # Drain state queue (tuples now include invocation_id)
    while not session.state_queue.empty():
        item = session.state_queue.get()
        if len(item) == 3:
            agent_name, final_state, invocation_id = item
        else:
            agent_name, final_state = item
            invocation_id = None
        session.pending_subagent_states.append((agent_name, final_state, invocation_id))


# Manager tools that dispatch a sub-agent internally (via _invoke_via_transfer_tool),
# so their ToolMessage is the anchor a dispatched sub-agent state links to. The
# manager's OTHER tools (read, glob, plan_updated) don't dispatch — skip those.
_DISPATCHING_MANAGER_TOOLS = {"next_step", "retry_step"}


def _link_subagent_states(rendered_prefix: int) -> list[str]:
    """Link tool message IDs to pending sub-agent states after agent completion.

    A sub-agent is anchored to either a ``*_transfer_tool`` ToolMessage (direct
    dispatch) or a manager ``next_step``/``retry_step`` ToolMessage (the manager
    wraps its dispatch inside these — see ``manager_agent.tools``). Without the
    latter, sub-agents launched by the manager are never linked into
    ``session.subagent_states`` and their trace cards vanish on save/reload.

    Non-dispatching manager tools (``read``/``glob``/``plan_updated``) are skipped.
    A dispatching tool that did NOT actually run a sub-agent (e.g. ``next_step``
    that only reported "plan complete") is skipped too — it leaves ``pending``
    untouched, so we only consume a pending state when one exists.
    """
    new_messages = session.agent_state["messages"][rendered_prefix:]
    pending = session.pending_subagent_states
    linked: list[str] = []

    non_dispatch_manager = {
        t.name for t in ManagerTools if t.name not in _DISPATCHING_MANAGER_TOOLS
    }

    for message in new_messages:
        if not isinstance(message, ToolMessage):
            continue
        name = str(message.name or "")
        # Skip the manager's non-dispatching tools entirely.
        if name in non_dispatch_manager:
            continue
        is_dispatcher = name in _DISPATCHING_MANAGER_TOOLS
        is_transfer = name.endswith("_transfer_tool")
        if not (is_dispatcher or is_transfer):
            continue

        tool_id = message.id
        if tool_id in session.subagent_states:
            continue

        if getattr(message, "status", None) == "error":
            session.subagent_states[tool_id] = (message.name, message.content, None)
        elif not pending:
            # A dispatching tool with no pending state didn't actually run a
            # sub-agent this time (e.g. next_step hit "plan complete"). For a
            # transfer tool this is unexpected; log it, but don't fabricate a
            # bogus card for a next_step that simply advanced the cursor.
            if is_transfer:
                logging.error(f"No agent state found for message {message}")
                session.subagent_states[tool_id] = ("agent not found", None, None)
                linked.append(tool_id)
            continue
        else:
            agent_name, final_state, invocation_id = pending.popleft()
            session.subagent_states[tool_id] = (agent_name, final_state, invocation_id)
        linked.append(tool_id)

    if pending:
        logging.warning("Unmatched subagent states remaining; clearing queue.")
        pending.clear()

    return linked
