"""Serialize LangChain messages to JSON dicts for WebSocket transport.

Each serialized message includes parsed metadata (agent badge, route header,
HTML tags) so the React frontend can render without duplicating parsing logic.
"""

from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage

from server.utils import (
    extract_html_tags,
    extract_tool_inputs,
    lookup_agent_badge,
    split_route_and_body,
    stringify_chat_content,
    strip_images_for_display,
    SUBAGENT_BADGES,
    SUBAGENT_DEFAULT_AVATAR,
    USER_AVATAR,
)


def serialize_message(message: BaseMessage, *, strip_images: bool = True) -> Dict[str, Any]:
    """Convert a LangChain message to a JSON-serializable dict.

    Args:
        message: A LangChain message object.
        strip_images: If True, remove base64 image data from content.

    Returns:
        Dict ready for JSON serialization and WebSocket transport.
    """
    if strip_images:
        stripped = strip_images_for_display([message])
        message = stripped[0]

    content_text = stringify_chat_content(message.content)
    msg_type = message.type  # "human", "ai", "tool"
    name = getattr(message, "name", None)

    result: Dict[str, Any] = {
        "id": getattr(message, "id", None),
        "type": msg_type,
        "name": name,
        "content": content_text,
    }

    if isinstance(message, HumanMessage):
        result["avatar"] = USER_AVATAR
        result["label"] = "You"

    elif isinstance(message, AIMessage):
        avatar, label = lookup_agent_badge(name)
        result["avatar"] = avatar
        result["label"] = label

        # Parse route header
        route, body = split_route_and_body(content_text)
        result["route"] = route
        result["body"] = body

        # Parse HTML tags
        tags = extract_html_tags(body)
        result["tags"] = tags

        # Tool calls
        tool_calls = getattr(message, "tool_calls", None)
        if tool_calls:
            result["tool_calls"] = [
                {
                    "id": tc.get("id"),
                    "name": tc.get("name"),
                    "args": tc.get("args"),
                }
                for tc in tool_calls
            ]

    elif isinstance(message, ToolMessage):
        result["tool_call_id"] = getattr(message, "tool_call_id", None)
        result["status"] = getattr(message, "status", None)

    return result


def serialize_subagent_state(
    tool_id: str, agent_name: str, final_state: Any
) -> Dict[str, Any]:
    """Serialize a sub-agent's completed state for WebSocket transport.

    Args:
        tool_id: The tool message ID this state corresponds to.
        agent_name: Display name of the sub-agent.
        final_state: The sub-agent's final state (typically a MessagesState dict).

    Returns:
        Dict with agent metadata and serialized transcript.
    """
    avatar = SUBAGENT_BADGES.get(agent_name, SUBAGENT_DEFAULT_AVATAR)

    transcript: Optional[List[Dict]] = None
    if isinstance(final_state, dict) and final_state.get("messages"):
        transcript = [serialize_message(msg) for msg in final_state["messages"]]

    return {
        "tool_id": tool_id,
        "agent_name": agent_name,
        "avatar": avatar,
        "transcript": transcript,
        "raw_state": str(final_state) if not isinstance(final_state, dict) else None,
    }


def serialize_history(
    messages: List[BaseMessage],
    subagent_states: Dict[str, Any],
) -> Dict[str, Any]:
    """Serialize full conversation history for initial WebSocket handshake.

    Args:
        messages: All messages in the conversation.
        subagent_states: Mapping of tool IDs to (agent_name, state) tuples.

    Returns:
        Dict with serialized messages and subagent states.
    """
    serialized_messages = [serialize_message(msg) for msg in messages]

    serialized_states = {}
    for tool_id, (agent_name, state) in subagent_states.items():
        serialized_states[tool_id] = serialize_subagent_state(tool_id, agent_name, state)

    return {
        "messages": serialized_messages,
        "subagent_states": serialized_states,
    }
