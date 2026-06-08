"""WebSocket endpoint for real-time agent chat.

Handles bidirectional communication: receives user messages, invokes the LangGraph agent, and streams back intermediate
traces and sub-agent states.
"""

import asyncio
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import anthropic
import openai
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.errors import GraphRecursionError
from pathlib import Path

from agents.manager_agent.tools import ManagerTools
from config import RECURSION_LIMIT
from graph.ui_events import log_message
from server.message_serializer import serialize_history, serialize_message, serialize_subagent_state
from server.session_manager import session
from config import DATA_DIR
from server.utils import upload_pdf_to_openai, SUBAGENT_BADGES, SUBAGENT_DEFAULT_AVATAR

router = APIRouter()

_executor = ThreadPoolExecutor(max_workers=1)


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

    try:
        while True:
            raw = await ws.receive_text()
            data = json.loads(raw)

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
    if session.is_running:
        await ws.send_json({
            "type": "run_error",
            "error_type": "AlreadyRunning",
            "detail": "Agent is already processing a message.",
        })
        return

    text = data.get("text", "")

    # Build multimodal content parts.
    # User-uploaded images are saved to DATA_DIR/uploads/ by the file
    # upload route; we reference them by workspace-relative path so that
    # agents can read them via the standard read() tool.
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
                file_id = upload_pdf_to_openai(Path(pdf["path"]))
                pdf["file_id"] = file_id
                pdf["attached_to_conversation"] = False
            except Exception as e:
                await ws.send_json({
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
    log_message(user_message)

    session.agent_state["messages"].append(user_message)
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

    # Rebuild the agent graph if the user changed the model since the last turn.
    from server.main import ensure_graph_current
    ensure_graph_current()

    # First invocation of this turn: pass the current message state in.
    await _run_graph(ws, graph_input=session.agent_state)


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

    session.is_running = True
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

    try:
        while not future.done():
            await _drain_queues(ws)
            await asyncio.sleep(0.05)

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

    except GraphRecursionError as e:
        logging.error("GraphRecursionError", exc_info=e)
        await ws.send_json({
            "type": "run_error",
            "error_type": "GraphRecursionError",
            "detail": str(e),
        })
    except (anthropic.BadRequestError, openai.BadRequestError) as e:
        logging.error("BadRequestError", exc_info=e)
        await ws.send_json({
            "type": "run_error",
            "error_type": "BadRequestError",
            "detail": str(e),
        })
    except Exception as e:
        logging.error("Unexpected error during agent invocation", exc_info=e)
        await ws.send_json({
            "type": "run_error",
            "error_type": type(e).__name__,
            "detail": str(e),
        })
    finally:
        session.is_running = False
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
    """
    from server.plan_store import plan_store as _plan_store, serialize_plan

    doc = _plan_store.read()
    if only_if_present and doc.status == "empty":
        return
    if doc.status == new_status:
        return  # No change to broadcast.
    doc.status = new_status  # type: ignore[assignment]
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
    await _run_graph(ws, graph_input=None)


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
    await _run_graph(ws, graph_input=None)


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
    log_message(feedback_message)
    session.agent_state["messages"].append(feedback_message)
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

    await _run_graph(ws, graph_input=session.agent_state)


async def _handle_run_cancelled(ws: WebSocket) -> None:
    """Cancel an in-progress copilot run.

    The checkpointer thread is abandoned (a fresh one is generated for the next turn). The on-disk plan is wiped so the
    UI doesn't keep showing a stale review prompt.
    """
    if session.paused_at is None and not session.is_running:
        # Nothing to cancel — still acknowledge so the UI clears state.
        await ws.send_json({"type": "run_cancelled", "data": {}})
        return

    from server.plan_store import plan_store as _plan_store
    from server.session_manager import _new_thread_id

    _plan_store.reset()
    session.paused_at = None
    session.thread_id = _new_thread_id()
    session.gates_fired = set()
    session.is_running = False

    await ws.send_json({"type": "run_cancelled", "data": {}})


async def _drain_queues(ws: WebSocket):
    """Drain both event and state queues, sending updates to client."""
    # Drain UI event queue (now contains typed tuples)
    while not session.ui_event_queue.empty():
        event = session.ui_event_queue.get()

        if isinstance(event, tuple) and len(event) == 2:
            event_type, payload = event

            if event_type == "message":
                # plan_updated markers are emitted by the planner/recruiter
                # state_update_fn via log_message(); route them to the plan
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
                await ws.send_json({
                    "type": "subagent_message",
                    "data": {
                        "invocation_id": payload["invocation_id"],
                        "agent_name": payload["agent_name"],
                        "message": serialize_message(payload["message"]),
                    },
                })

            elif event_type == "subagent_end":
                await ws.send_json({
                    "type": "subagent_end",
                    "data": {
                        "invocation_id": payload["invocation_id"],
                        "agent_name": payload["agent_name"],
                    },
                })
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


def _link_subagent_states(rendered_prefix: int) -> list[str]:
    """Link tool message IDs to pending sub-agent states after agent completion."""
    new_messages = session.agent_state["messages"][rendered_prefix:]
    pending = session.pending_subagent_states
    linked: list[str] = []

    for message in new_messages:
        if not isinstance(message, ToolMessage):
            continue
        if message.name in {t.name for t in ManagerTools}:
            continue
        if not str(message.name or "").endswith("_transfer_tool"):
            continue

        tool_id = message.id
        if tool_id in session.subagent_states:
            continue

        if getattr(message, "status", None) == "error":
            session.subagent_states[tool_id] = (message.name, message.content, None)
        elif not pending:
            logging.error(f"No agent state found for message {message}")
            session.subagent_states[tool_id] = ("agent not found", None, None)
        else:
            agent_name, final_state, invocation_id = pending.popleft()
            session.subagent_states[tool_id] = (agent_name, final_state, invocation_id)
        linked.append(tool_id)

    if pending:
        logging.warning("Unmatched subagent states remaining; clearing queue.")
        pending.clear()

    return linked
