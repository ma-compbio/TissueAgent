"""UI event queue, sub-agent context tracking, and message logging."""

import threading
import uuid
from contextlib import contextmanager
from queue import Queue
from typing import cast

from langchain_core.messages import BaseMessage

from graph.message_utils import MessageContent, stringify_content
from logger import logger

_ui_event_queue: Queue | None = None

# Thread-local storage for tracking which sub-agent is currently executing. When emit_message() is
# called from within a sub-agent invocation, this context lets us tag the event so the UI can stream
# it into a live trace.
_subagent_context = threading.local()


def _get_subagent_context() -> tuple[str | None, str | None]:
    """Return (invocation_id, agent_name) if inside a sub-agent, else (None, None)."""
    return (
        getattr(_subagent_context, "invocation_id", None),
        getattr(_subagent_context, "agent_name", None),
    )


@contextmanager
def subagent_invocation(agent_name: str):
    """Context manager that brackets a sub-agent invocation with start/end events.

    Sets thread-local context so that ``emit_message()`` calls within the sub-agent automatically
    route to the live-trace stream.  Pushes ``subagent_start`` and ``subagent_end`` events onto the
    UI queue. Yields the generated *invocation_id* (a UUID string).
    """
    invocation_id = str(uuid.uuid4())

    if _ui_event_queue is not None:
        _ui_event_queue.put_nowait(
            (
                "subagent_start",
                {
                    "invocation_id": invocation_id,
                    "agent_name": agent_name,
                },
            )
        )

    _subagent_context.invocation_id = invocation_id
    _subagent_context.agent_name = agent_name
    try:
        yield invocation_id
    finally:
        _subagent_context.invocation_id = None
        _subagent_context.agent_name = None
        if _ui_event_queue is not None:
            _ui_event_queue.put_nowait(
                (
                    "subagent_end",
                    {
                        "invocation_id": invocation_id,
                        "agent_name": agent_name,
                    },
                )
            )


def register_ui_event_queue(event_queue: Queue) -> None:
    """Set the global queue used to push messages to the Streamlit UI.

    Args:
        event_queue: Thread-safe queue that the UI layer drains to
            render new messages in near-real-time.
    """
    global _ui_event_queue
    _ui_event_queue = event_queue


def emit_message(message: BaseMessage) -> None:
    """Log a message's metadata and content, and push it to the UI queue.

    Writes a structured log entry with the message type, name, ID, content, and any tool calls. If a
    UI event queue has been registered via :func:`register_ui_event_queue`, the message is also
    enqueued for real-time display.

    Args:
        message: Any LangChain message (human, AI, tool, etc.).
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
    if _ui_event_queue is not None:
        try:
            inv_id, sa_name = _get_subagent_context()
            if inv_id is not None:
                _ui_event_queue.put_nowait(
                    (
                        "subagent_message",
                        {
                            "invocation_id": inv_id,
                            "agent_name": sa_name,
                            "message": message,
                        },
                    )
                )
            else:
                _ui_event_queue.put_nowait(("message", message))
        except Exception:
            pass
