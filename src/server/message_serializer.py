"""Serialize LangChain messages to JSON dicts for WebSocket transport.

Each serialized message includes parsed metadata (agent badge, route header, HTML tags) so the React frontend can render
without duplicating parsing logic.
"""

from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage

from server.utils import (
    extract_html_tags,
    lookup_agent_badge,
    should_hide_message,
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

    # Trace plot references: project-relative paths to images spilled by the
    # coding agent. Carried in additional_kwargs (not content) so they survive
    # the image-stripping above; the frontend loads pixels from the file API.
    extra = getattr(message, "additional_kwargs", None) or {}
    trace_image_paths = extra.get("trace_image_paths")
    if trace_image_paths:
        result["image_paths"] = list(trace_image_paths)

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

    # Skills assigned to the plan step this sub-agent executed, stashed onto the
    # state dict by ``node_factories._agent_invocation_tool``. Absent for legacy
    # sessions and for non-dict raw states — default to an empty list.
    skills: List[str] = []
    if isinstance(final_state, dict):
        raw_skills = final_state.get("step_skills")
        if isinstance(raw_skills, list):
            skills = [str(s) for s in raw_skills]

    # Fully-rendered system prompt the sub-agent ran with, written into state by
    # ``create_agent_node`` (and the hypothesis agent's node). Absent for legacy
    # sessions and non-dict raw states.
    system_prompt: Optional[str] = None
    if isinstance(final_state, dict):
        raw_prompt = final_state.get("system_prompt")
        if isinstance(raw_prompt, str) and raw_prompt:
            system_prompt = raw_prompt

    transcript: Optional[List[Dict]] = None
    if isinstance(final_state, dict) and final_state.get("messages"):
        # Guard against non-BaseMessage entries. Legacy sessions saved before
        # sub-agent transcripts were round-tripped properly hold the lossy
        # ``str(BaseMessage)`` repr instead of message objects; serializing
        # those would raise ``'str' object has no attribute 'content'`` and
        # take down the whole WebSocket handshake. Skip them instead.
        transcript = [
            serialize_message(msg)
            for msg in final_state["messages"]
            if isinstance(msg, BaseMessage)
        ]

    return {
        "tool_id": tool_id,
        "agent_name": agent_name,
        "avatar": avatar,
        "transcript": transcript,
        "skills": skills,
        "system_prompt": system_prompt,
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
    serialized_messages = [
        serialize_message(msg) for msg in messages if not should_hide_message(msg)
    ]

    serialized_states = {}
    for tool_id, entry in subagent_states.items():
        # Support both (agent_name, state) and (agent_name, state, invocation_id)
        if len(entry) == 3:
            agent_name, state, invocation_id = entry
        else:
            agent_name, state = entry
            invocation_id = None
        data = serialize_subagent_state(tool_id, agent_name, state)
        data["invocation_id"] = invocation_id
        serialized_states[tool_id] = data

    return {
        "messages": serialized_messages,
        "subagent_states": serialized_states,
    }
