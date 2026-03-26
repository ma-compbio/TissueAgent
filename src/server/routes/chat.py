"""WebSocket endpoint for real-time agent chat.

Handles bidirectional communication: receives user messages, invokes the
LangGraph agent, and streams back intermediate traces and sub-agent states.
"""

import asyncio
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor

import anthropic
import openai
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.errors import GraphRecursionError
from pathlib import Path

from agents.manager_agent.tools import ManagerToolNames
from config import RECURSION_LIMIT
from graph.graph_utils import log_message, record_user_message
from server.message_serializer import serialize_history, serialize_message, serialize_subagent_state
from server.session_manager import session
from server.utils import file_to_data_url, upload_pdf_to_openai

router = APIRouter()

_executor = ThreadPoolExecutor(max_workers=1)


@router.websocket("/ws/chat")
async def websocket_chat(ws: WebSocket):
    """Primary real-time chat channel.

    On connect, sends current conversation history.
    On receive, processes user messages and streams agent traces back.
    """
    await ws.accept()

    # Send current history on connect
    history = serialize_history(
        session.agent_state["messages"],
        session.subagent_states,
    )
    await ws.send_json({"type": "history", "data": history})

    try:
        while True:
            raw = await ws.receive_text()
            data = json.loads(raw)

            if data.get("type") == "send_message":
                await _handle_user_message(ws, data)
    except WebSocketDisconnect:
        logging.info("WebSocket client disconnected")
    except Exception as e:
        logging.error(f"WebSocket error: {e}", exc_info=True)


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
    image_ids = data.get("image_ids", [])
    pdf_ids = data.get("pdf_ids", [])

    # Build multimodal content parts
    content_parts = [{"type": "text", "text": text}]

    # Add image attachments
    for img in session.pending_images:
        img_path = Path(img["path"])
        if img_path.exists():
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": file_to_data_url(img_path)},
            })

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
    record_user_message(user_message)
    log_message(user_message)

    session.agent_state["messages"].append(user_message)
    session.agent_state.setdefault("replan_count", 0)
    session.agent_state.setdefault("replan_history", [])

    # Send the user message back to client for display
    await ws.send_json({
        "type": "message",
        "data": serialize_message(user_message),
    })
    # Register for dedup so _drain_queues won't re-send from ui_event_queue
    session.append_display_message(user_message)

    # Clear pending images after sending
    session.pending_images = []

    # Record prefix for post-run linkage
    rendered_prefix = len(session.agent_state["messages"])

    # Invoke agent in background thread
    session.is_running = True
    start_time = time.perf_counter()

    loop = asyncio.get_event_loop()
    future = _executor.submit(
        session.agent.invoke,
        session.agent_state,
        {"recursion_limit": RECURSION_LIMIT},
    )

    try:
        # Drain queues while agent runs
        while not future.done():
            await _drain_queues(ws)
            await asyncio.sleep(0.05)

        # Get result (may raise)
        session.agent_state = future.result()

        # Final drain
        await _drain_queues(ws)

        # Link tool messages to sub-agent states and send them
        linked_ids = _link_subagent_states(rendered_prefix)
        for tool_id in linked_ids:
            agent_name, final_state = session.subagent_states[tool_id]
            await ws.send_json({
                "type": "subagent_state",
                "data": serialize_subagent_state(tool_id, agent_name, final_state),
            })

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
        # Final drain in case of error
        await _drain_queues(ws)


async def _drain_queues(ws: WebSocket):
    """Drain both event and state queues, sending updates to client."""
    # Drain UI event queue
    while not session.ui_event_queue.empty():
        message = session.ui_event_queue.get()
        if session.append_display_message(message):
            await ws.send_json({
                "type": "message",
                "data": serialize_message(message),
            })

    # Drain state queue
    while not session.state_queue.empty():
        agent_name, final_state = session.state_queue.get()
        session.pending_subagent_states.append((agent_name, final_state))
        await ws.send_json({
            "type": "subagent_state",
            "data": serialize_subagent_state("pending", agent_name, final_state),
        })


def _link_subagent_states(rendered_prefix: int) -> list[str]:
    """Link tool message IDs to pending sub-agent states after agent completion."""
    new_messages = session.agent_state["messages"][rendered_prefix:]
    pending = session.pending_subagent_states
    linked: list[str] = []

    for message in new_messages:
        if not isinstance(message, ToolMessage):
            continue
        if message.name in ManagerToolNames:
            continue
        if not str(message.name or "").endswith("_transfer_tool"):
            continue

        tool_id = message.id
        if tool_id in session.subagent_states:
            continue

        if getattr(message, "status", None) == "error":
            session.subagent_states[tool_id] = (message.name, message.content)
        elif not pending:
            logging.error(f"No agent state found for message {message}")
            session.subagent_states[tool_id] = ("agent not found", None)
        else:
            agent_name, final_state = pending.popleft()
            session.subagent_states[tool_id] = (agent_name, final_state)
        linked.append(tool_id)

    if pending:
        logging.warning("Unmatched subagent states remaining; clearing queue.")
        pending.clear()

    return linked
