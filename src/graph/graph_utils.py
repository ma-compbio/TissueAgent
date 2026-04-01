"""Graph node and tool factories for the TissueAgent LangGraph pipeline.

Provides reusable builders for agent nodes, tool nodes, and sub-agent
invocation tools, as well as message logging and user-state tracking
helpers used across the graph.
"""

import logging
import threading
import uuid
from contextlib import contextmanager
from copy import deepcopy
from queue import Queue
from typing import Any, Callable, Dict, List, Optional, Tuple, cast

from langchain.tools import StructuredTool
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.graph import MessagesState
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from logger import logger

_ui_event_queue: Optional[Queue] = None
_latest_user_message_content: Optional[List[Any]] = None

# Thread-local storage for tracking which sub-agent is currently executing.
# When log_message() is called from within a sub-agent invocation, this
# context lets us tag the event so the UI can stream it into a live trace.
_subagent_context = threading.local()


def _get_subagent_context() -> Tuple[Optional[str], Optional[str]]:
    """Return (invocation_id, agent_name) if inside a sub-agent, else (None, None)."""
    return (
        getattr(_subagent_context, "invocation_id", None),
        getattr(_subagent_context, "agent_name", None),
    )


@contextmanager
def subagent_invocation(agent_name: str):
    """Context manager that brackets a sub-agent invocation with start/end events.

    Sets thread-local context so that ``log_message()`` calls within the
    sub-agent automatically route to the live-trace stream.  Pushes
    ``subagent_start`` and ``subagent_end`` events onto the UI queue.

    Yields the generated *invocation_id* (a UUID string).
    """
    invocation_id = str(uuid.uuid4())

    if _ui_event_queue is not None:
        _ui_event_queue.put_nowait(("subagent_start", {
            "invocation_id": invocation_id,
            "agent_name": agent_name,
        }))

    _subagent_context.invocation_id = invocation_id
    _subagent_context.agent_name = agent_name
    try:
        yield invocation_id
    finally:
        _subagent_context.invocation_id = None
        _subagent_context.agent_name = None
        if _ui_event_queue is not None:
            _ui_event_queue.put_nowait(("subagent_end", {
                "invocation_id": invocation_id,
                "agent_name": agent_name,
            }))


def register_ui_event_queue(event_queue: Queue) -> None:
    """Set the global queue used to push messages to the Streamlit UI.

    Args:
        event_queue: Thread-safe queue that the UI layer drains to
            render new messages in near-real-time.
    """
    global _ui_event_queue
    _ui_event_queue = event_queue


def record_user_message(message: BaseMessage) -> None:
    """Persist the latest user message content for downstream access.

    Stores a deep copy of multimodal content (text + image parts) in a
    module-level global so that sub-agent invocation tools can forward
    user-attached images without re-reading session state.

    Args:
        message: The most recent user message from the conversation.
    """
    global _latest_user_message_content
    content = getattr(message, "content", None)
    if isinstance(content, list):
        _latest_user_message_content = deepcopy(content)
    else:
        _latest_user_message_content = None


def get_latest_user_image_parts() -> List[Dict[str, Any]]:
    """Return deep copies of image parts from the latest user message.

    Returns:
        A list of image content-part dicts (``{"type": "image_url", …}``).
        Returns an empty list when no images are attached or no user
        message has been recorded.
    """
    if not isinstance(_latest_user_message_content, list):
        return []
    parts: List[Dict[str, Any]] = []
    for part in _latest_user_message_content:
        if isinstance(part, dict) and part.get("type") in {"image_url", "image"}:
            parts.append(deepcopy(part))
    return parts


def standardize_message_format(message: AIMessage) -> AIMessage:
    """Normalize an AI message into a consistent text + tool_calls format.

    Provider responses may encode tool calls inline within the content
    list.  This function separates text parts from tool-call parts and
    returns a new :class:`AIMessage` with plain-text content and an
    explicit ``tool_calls`` list.

    Args:
        message: The raw AI message to normalize.

    Returns:
        A new :class:`AIMessage` with standardized content, or the
        original message unchanged if content is already a string.
    """
    if isinstance(message.content, list):
        text_parts = []
        tool_calls = []
        other_parts = []

        for item in message.content:
            if not isinstance(item, dict):
                other_parts.append(item)
                continue
            itype = item.get("type")
            if itype in ("text", "output_text"):
                text_parts.append(item.get("text", ""))
            elif itype in ("tool_use", "tool_call"):
                tool_call = {
                    "name": item.get("name"),
                    "args": item.get("input") or item.get("args") or {},
                    "id": item.get("id"),
                    "type": "tool_call",
                }
                tool_calls.append(tool_call)
            else:
                other_parts.append(item)

        if other_parts:
            return AIMessage(message.content, id=message.id, tool_calls=tool_calls)
        return AIMessage("\n".join(text_parts).strip(), id=message.id, tool_calls=tool_calls)
    return message


def _stringify_content(content: Any) -> List[str]:
    """Turn content into printable lines for logging.

    Handles str or multimodal (list) content.
    """
    lines: List[str] = []
    if isinstance(content, str):
        lines.extend(content.splitlines())
    elif isinstance(content, list):
        for idx, part in enumerate(content, 1):
            if not isinstance(part, dict):
                lines.append(f"[{idx}] {part}")
                continue
            ptype = part.get("type")
            if ptype in ("text", "output_text"):
                lines.append(f"[{idx}] (text) {part.get('text', '')}")
            elif ptype in ("image_url", "image"):
                url = part.get("image_url")
                if isinstance(url, dict):
                    url = url.get("url")
                lines.append(
                    f"[{idx}] (image) {str(url)[:80]}{'...' if url and len(str(url)) > 80 else ''}"
                )
            elif ptype in ("tool_use", "tool_call"):
                lines.append(f"[{idx}] (tool_call) {part.get('name')}")
            else:
                lines.append(f"[{idx}] ({ptype}) {part}")
    else:
        lines.append(str(content))
    return lines


def log_message(message: BaseMessage) -> None:
    """Log a message's metadata and content, and push it to the UI queue.

    Writes a structured log entry with the message type, name, ID, content,
    and any tool calls.  If a UI event queue has been registered via
    :func:`register_ui_event_queue`, the message is also enqueued for
    real-time display.

    Args:
        message: Any LangChain message (human, AI, tool, etc.).
    """
    # Some message types may not have .name; default to None
    msg_type = getattr(message, "type", type(message).__name__)
    msg_name = getattr(message, "name", None)
    msg_id = getattr(message, "id", None)
    content = getattr(message, "content", None)
    tool_calls = getattr(message, "tool_calls", [])

    lines = [
        "Message Info",
        f"Type: {msg_type}\n",
        f"Name: {msg_name}\n",
        f"ID:   {msg_id}\n",
    ]

    if content is not None:
        lines.append("Content:")
        lines += _stringify_content(content)

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
                _ui_event_queue.put_nowait(("subagent_message", {
                    "invocation_id": inv_id,
                    "agent_name": sa_name,
                    "message": message,
                }))
            else:
                _ui_event_queue.put_nowait(("message", message))
        except Exception:
            pass


def create_agent_node(
    agent_node_id: str,
    agent_model: BaseChatModel,
    prompt: str,
    tool_node_id: str,
    exit_node_id: Optional[str] = None,
    exit_node_id_fn: Optional[Callable[[AIMessage, MessagesState], str]] = None,
    state_update_fn: Optional[
        Callable[[AIMessage, MessagesState], Optional[Dict[str, Any]]]
    ] = None,
) -> Callable[[MessagesState], Command]:
    """Build a LangGraph agent node that invokes an LLM and routes the result.

    The returned callable prepends a system prompt, invokes *agent_model*,
    normalises the response, logs it, and returns a :class:`Command` that
    either routes to the tool node (when tool calls are present) or to the
    configured exit node.

    Args:
        agent_node_id: Unique node identifier; also set as the message's
            ``name`` attribute for UI display.
        agent_model: Bound chat model (with tools already attached).
        prompt: System prompt injected before the conversation messages.
        tool_node_id: Node to route to when the response contains tool
            calls.
        exit_node_id: Static node to route to when no tool calls are
            present.  Mutually exclusive with *exit_node_id_fn*.
        exit_node_id_fn: Callable that receives ``(response, state)`` and
            returns the next node ID.  Used for conditional routing
            (e.g. planner/evaluator routers).
        state_update_fn: Optional callable that receives
            ``(response, state)`` and returns a dict of extra state updates
            to merge into the command payload.

    Returns:
        A callable suitable for use as a LangGraph node function.
    """

    def agent_node(state: MessagesState) -> Command:
        messages = state["messages"]
        system_prompt = SystemMessage(prompt)
        response = cast(AIMessage, agent_model.invoke([system_prompt] + messages))
        response = standardize_message_format(response)
        response.name = agent_node_id
        log_message(response)

        extra_update: Dict[str, Any] = {}
        if state_update_fn:
            maybe_update = state_update_fn(response, state) or {}
            if maybe_update:
                extra_update.update(maybe_update)

        next_node: Optional[str] = tool_node_id if getattr(response, "tool_calls", []) else None
        if not next_node:
            if exit_node_id:
                next_node = exit_node_id
            elif exit_node_id_fn:
                next_node = exit_node_id_fn(response, state)

        update_payload: Dict[str, Any] = {"messages": [response]}
        if extra_update:
            update_payload.update(extra_update)
        if next_node is not None:
            return Command(goto=next_node, update=update_payload)
        return Command(update=update_payload)

    return agent_node


def create_tool_node(
    tools: List[StructuredTool],
) -> Callable[[MessagesState], MessagesState]:
    """Build a LangGraph tool-execution node from a list of tools.

    The returned callable reads the last AI message's ``tool_calls``,
    invokes each tool by name, wraps the results as
    :class:`~langchain_core.messages.ToolMessage` objects, and logs them.

    Args:
        tools: The tool instances available for invocation.  Each tool's
            ``name`` must be unique within the list.

    Returns:
        A callable suitable for use as a LangGraph node function.
    """
    tools_by_name = {tool.name: tool for tool in tools}

    def tool_node(state: MessagesState) -> MessagesState:
        result = []
        last_message = cast(AIMessage, state["messages"][-1])
        for tool_call in last_message.tool_calls:
            tool = tools_by_name[tool_call["name"]]
            observation = tool.invoke(tool_call["args"])
            message = ToolMessage(content=observation, tool_call_id=tool_call["id"])
            message.name = tool_call["name"]
            log_message(message)
            result.append(message)
        return {"messages": result}

    return tool_node


def create_agent_invocation_tool(
    agent_node_id: str,
    agent_name: str,
    agent: CompiledStateGraph,
    state_queue: Queue,
    supports_pdf: bool = False,
    forward_user_images: bool = False,
) -> StructuredTool:
    """Create a LangChain tool that delegates a prompt to a compiled sub-agent.

    The returned :class:`~langchain.tools.StructuredTool` accepts a text
    prompt (and optional PDF file IDs when *supports_pdf* is ``True``),
    invokes the sub-agent graph, pushes the final state onto
    *state_queue* for UI rendering, and returns the last message's content.

    Args:
        agent_node_id: Node ID of the sub-agent (used in the tool name).
        agent_name: Human-readable agent name shown in UI badges.
        agent: The compiled sub-agent graph to invoke.
        state_queue: Queue where ``(agent_name, final_state)`` tuples are
            placed after each invocation.
        supports_pdf: When ``True``, the generated tool accepts an
            additional ``pdf_file_ids`` parameter.
        forward_user_images: When ``True``, the latest user-attached
            images are included in the prompt sent to the sub-agent.

    Returns:
        A :class:`~langchain.tools.StructuredTool` named
        ``"{agent_node_id}_transfer_tool"``.
    """

    def _build_multimodal_message(
        prompt: str, extra_parts: Optional[List[Dict[str, Any]]] = None
    ) -> HumanMessage:
        """Assemble a HumanMessage from text, optional extras, and user images."""
        if forward_user_images:
            image_parts = get_latest_user_image_parts()
        else:
            image_parts = []
        parts: list[str | dict[str, Any]] = [{"type": "text", "text": prompt}]
        if extra_parts:
            parts.extend(extra_parts)
        if image_parts:
            parts.extend(image_parts)
            return HumanMessage(content=parts)
        if extra_parts:
            return HumanMessage(content=parts)
        return HumanMessage(prompt)

    if supports_pdf:

        def _pdf_agent_invocation_tool(prompt: str, pdf_file_ids: str = "") -> str:
            """Invoke agent with optional PDF file IDs.

            Args:
                prompt: Task instructions for the agent
                pdf_file_ids: Comma-separated list of OpenAI file IDs (e.g. "file-abc123,file-def456")

            Returns:
                Agent's response
            """
            logging.info(f"Invoking PDF-capable agent `{agent_node_id}`")

            # Build multimodal content if PDFs provided
            content: List[Dict[str, Any]] = []

            if pdf_file_ids and pdf_file_ids.strip():
                file_ids = [fid.strip() for fid in pdf_file_ids.split(",") if fid.strip()]
                logging.info(f"Attaching {len(file_ids)} PDF file(s) to agent invocation")
                for file_id in file_ids:
                    content.append({"type": "file", "file": {"file_id": file_id}})

            message = _build_multimodal_message(prompt, extra_parts=content)
            with subagent_invocation(agent_name) as invocation_id:
                final_state = agent.invoke({"messages": [message]})
            state_queue.put((agent_name, final_state, invocation_id))
            logging.info(f"Finished invoking PDF-capable agent `{agent_node_id}`")
            return final_state["messages"][-1].content

        agent_invocation_tool = _pdf_agent_invocation_tool
    else:

        def _basic_agent_invocation_tool(prompt: str) -> str:
            """Invoke the sub-agent with a text prompt and return its response."""
            logging.info(f"Invoking agent `{agent_node_id}`")
            message = _build_multimodal_message(prompt)
            with subagent_invocation(agent_name) as invocation_id:
                final_state = agent.invoke({"messages": [message]})
            state_queue.put((agent_name, final_state, invocation_id))
            logging.info(f"Finished invoking agent `{agent_node_id}`")
            return final_state["messages"][-1].content

        agent_invocation_tool = _basic_agent_invocation_tool

    return StructuredTool.from_function(
        func=agent_invocation_tool,
        name=f"{agent_node_id}_transfer_tool",
        description=f"Transfer control to {agent_name}",
    )
