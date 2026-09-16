"""UI event queue, sub-agent context tracking, and message logging."""

import logging
import threading
import uuid
from contextlib import contextmanager
from queue import Full, Queue
from typing import Any, cast

from langchain_core.messages import BaseMessage

from graph.message_utils import MessageContent, stringify_content
from logger import logger

_ui_event_queue: Queue | None = None
# Guards module-global _ui_event_queue registration so a concurrent session
# switch can't tear a partially-registered queue out from under a publisher.
_registration_lock = threading.Lock()

# Thread-local storage for tracking which sub-agent is currently executing. When emit_message() is
# called from within a sub-agent invocation, this context lets us tag the event so the UI can stream
# it into a live trace.
_subagent_context = threading.local()

# Thread-local hand-off for the most recently completed sub-agent invocation.
# The transfer tool stashes its final state here; the manager's tool_node
# reads it right after emitting the tool's ToolMessage so it can pair the
# ToolMessage.id with the sub-agent transcript and push a subagent_state
# UI event immediately, rather than waiting for run_complete.
_completed_subagent = threading.local()


def _get_ui_event_queue() -> Queue | None:
    """Return the currently registered UI queue (may be ``None``)."""
    with _registration_lock:
        return _ui_event_queue


def _get_subagent_context() -> tuple[str | None, str | None, int | None]:
    """Return ``(invocation_id, agent_name, step_id)`` if inside a sub-agent, else ``(None, None,
    None)``. ``step_id`` is the plan step that the manager dispatched this sub-agent to execute, or
    ``None`` when the call wasn't tied to a plan step (e.g. ad-hoc invocations)."""
    return (
        getattr(_subagent_context, "invocation_id", None),
        getattr(_subagent_context, "agent_name", None),
        getattr(_subagent_context, "step_id", None),
    )


@contextmanager
def subagent_invocation(agent_name: str, step_id: int | None = None):
    """Context manager that brackets a sub-agent invocation with start/end events.

    Sets thread-local context so that ``emit_message()`` calls within the sub-agent automatically
    route to the live-trace stream.  Pushes ``subagent_start`` and ``subagent_end`` events onto the
    UI queue. Yields the generated *invocation_id* (a UUID string).

    ``step_id`` is propagated via the thread-local context so inner LLM calls can be attributed to
    the plan step the manager dispatched on.
    """
    invocation_id = str(uuid.uuid4())

    # Set thread-locals BEFORE any queue.put so a Full queue can't leave us
    # inside the context without the caller ever seeing invocation_id set.
    _subagent_context.invocation_id = invocation_id
    _subagent_context.agent_name = agent_name
    _subagent_context.step_id = step_id

    queue = _get_ui_event_queue()
    if queue is not None:
        try:
            queue.put_nowait(
                (
                    "subagent_start",
                    {
                        "invocation_id": invocation_id,
                        "agent_name": agent_name,
                    },
                )
            )
        except Full:
            logging.debug("UI event queue full; dropping subagent_start event")

    try:
        yield invocation_id
    finally:
        _subagent_context.invocation_id = None
        _subagent_context.agent_name = None
        _subagent_context.step_id = None
        queue = _get_ui_event_queue()
        if queue is not None:
            try:
                queue.put_nowait(
                    (
                        "subagent_end",
                        {
                            "invocation_id": invocation_id,
                            "agent_name": agent_name,
                        },
                    )
                )
            except Full:
                logging.debug("UI event queue full; dropping subagent_end event")


def register_ui_event_queue(event_queue: Queue) -> None:
    """Set the global queue used to push messages to the Streamlit UI.

    Args:
        event_queue: Thread-safe queue that the UI layer drains to
            render new messages in near-real-time.
    """
    global _ui_event_queue
    with _registration_lock:
        _ui_event_queue = event_queue


def stash_completed_subagent(
    agent_name: str, final_state: Any, invocation_id: str
) -> None:
    """Record the just-completed sub-agent invocation on this thread.

    Called from the transfer-tool wrapper right after the sub-agent returns.
    The manager's tool_node pops this after it emits the wrapping ToolMessage
    (``next_step`` / ``retry_step``) so the sub-agent's final state can be
    linked to the ToolMessage.id and pushed to the UI as a ``subagent_state``
    event mid-run — otherwise the completed sub-agent card would only appear
    after the whole graph run finishes.
    """
    _completed_subagent.data = (agent_name, final_state, invocation_id)


def pop_completed_subagent() -> tuple[str, Any, str] | None:
    """Return and clear the most recently stashed sub-agent completion."""
    data = getattr(_completed_subagent, "data", None)
    _completed_subagent.data = None
    return data


def emit_subagent_state(
    tool_id: str, agent_name: str, final_state: Any, invocation_id: str
) -> None:
    """Push a ``subagent_state`` event tying a ToolMessage.id to a subagent's final state.

    Emitted from the manager's tool_node immediately after the corresponding
    ``next_step`` / ``retry_step`` ToolMessage so the UI can replace the live
    trace card with the completed sub-agent card inline instead of waiting for
    run_complete.
    """
    queue = _get_ui_event_queue()
    if queue is None:
        return
    payload = (
        "subagent_state",
        {
            "tool_id": tool_id,
            "agent_name": agent_name,
            "final_state": final_state,
            "invocation_id": invocation_id,
        },
    )
    try:
        queue.put_nowait(payload)
    except Full:
        logging.debug("UI event queue full; dropping subagent_state event")


def emit_subagent_token(stream_id: str, source: str, text: str) -> None:
    """Push a transient text token into the active sub-agent trace."""
    if not text:
        return
    invocation_id, agent_name, _ = _get_subagent_context()
    queue = _get_ui_event_queue()
    if invocation_id is None or queue is None:
        return
    try:
        queue.put_nowait(
            (
                "subagent_token",
                {
                    "invocation_id": invocation_id,
                    "agent_name": agent_name,
                    "stream_id": stream_id,
                    "source": source,
                    "text": text,
                },
            )
        )
    except Full:
        logging.debug("UI event queue full; dropping subagent_token event")


def emit_message(
    message: BaseMessage,
    *,
    stream_id: str | None = None,
    source: str | None = None,
) -> None:
    """Log a message's metadata and content, and push it to the UI queue.

    Writes a structured log entry with the message type, name, ID, content, and any tool calls. If a
    UI event queue has been registered via :func:`register_ui_event_queue`, the message is also
    enqueued for real-time display.

    Args:
        message: Any LangChain message (human, AI, tool, etc.).
        stream_id: Optional transient draft identity completed by this message.
        source: Optional main-agent or delegated-subagent label.
    """
    msg_type = getattr(message, "type", type(message).__name__)
    msg_name = getattr(message, "name", None)
    msg_id = getattr(message, "id", None)
    content = cast(MessageContent, getattr(message, "content", None))
    tool_calls = getattr(message, "tool_calls", [])

    lines = [
        "Message Info",
        f"Type: {msg_type}\n",
        f"Name: {msg_name}\n",
        f"ID:   {msg_id}\n",
    ]

    if content is not None:
        lines.append("Content:")
        lines += stringify_content(content)

    if tool_calls:
        lines.append("ToolCalls:")
        for idx, tc in enumerate(tool_calls, 1):
            lines.append(f"  {idx}. {tc}")

    full_message = "\n".join(lines)
    logger.info(full_message)
    queue = _get_ui_event_queue()
    if queue is None:
        return
    inv_id, sa_name, _ = _get_subagent_context()
    if inv_id is not None:
        data = {"invocation_id": inv_id, "agent_name": sa_name, "message": message}
        if stream_id is not None:
            data["stream_id"] = stream_id
        if source is not None:
            data["source"] = source
        payload = (
            "subagent_message",
            data,
        )
    else:
        payload = ("message", message)
    try:
        queue.put_nowait(payload)
    except Full:
        # A full queue is not fatal, but silently dropping UI updates hid
        # real backpressure issues in the past. Log at DEBUG so operators
        # can surface it with the right log level when investigating.
        logging.debug("UI event queue full; dropping %s event", payload[0])
