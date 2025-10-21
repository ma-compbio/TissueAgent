"""Streamlit helper utilities for rendering agent conversations."""

from __future__ import annotations
import json
import logging
import streamlit as st
from copy import deepcopy
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.messages.utils import messages_from_dict
from langchain_openai import ChatOpenAI
from langgraph.graph import MessagesState 
from agents.manager_agent.tools import ManagerToolNames


# ---------------------------------------------------------------------------
# Chat Log Save/Load Functionality
# ---------------------------------------------------------------------------

def _safe_escape(value: Any, fallback: str = "") -> str:
    """HTML-escape arbitrary values, substituting a fallback for None."""
    if value is None:
        return escape(fallback)
    return escape(str(value))


def _safe_pretty_json(obj: Any) -> str:
    """Safely format an object as pretty JSON, handling non-serializable values."""
    try:
        return json.dumps(obj, indent=2, ensure_ascii=False, default=str)
    except Exception:
        return str(obj)


def _message_to_serializable(message):
    """Convert a message to a serializable format for saving."""
    data = message.model_dump()
    data.pop("type", None)
    return {"type": message.type, "data": data}


def _format_session_label(session_path: Path, session_filename_prefix: str = "session_") -> str:
    """Format a session path into a human-readable label."""
    stem = session_path.stem
    if stem.startswith(session_filename_prefix):
        stem = stem[len(session_filename_prefix):]
    try:
        saved_at = datetime.strptime(stem, "%Y-%m-%d_%H-%M-%S")
        return saved_at.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return stem


def _session_option_label(session_path: Path, session_filename_prefix: str = "session_") -> str:
    """Create a label for session selection dropdown."""
    return f"{_format_session_label(session_path, session_filename_prefix)} ({session_path.name})"


def save_current_session(sessions_dir: Path, session_filename_prefix: str = "session_", session_filename_suffix: str = ".json"):
    """Save the current chat session to a file."""
    messages = st.session_state.get("agent_state", {}).get("messages", [])
    if not messages:
        st.toast("No conversation history to save yet.", icon="ℹ️")
        return

    payload = {
        "saved_at": datetime.now().strftime("%Y-%m-%d_%H-%M-%S"),
        "messages": [_message_to_serializable(m) for m in messages],
        "subagent_states": st.session_state.get("subagent_states", {}),
    }

    sessions_dir.mkdir(parents=True, exist_ok=True)
    file_name = f"{session_filename_prefix}{payload['saved_at']}{session_filename_suffix}"
    target_path = sessions_dir / file_name

    try:
        target_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
    except Exception as exc:
        logging.error("Failed to save session", exc_info=exc)
        st.error("Failed to save session history.", icon="⚠️")
        return

    st.toast(f"Session saved as {file_name}", icon="💾")
    st.session_state["selected_session_label"] = _session_option_label(target_path, session_filename_prefix)
    st.session_state["session_loader_select"] = st.session_state["selected_session_label"]


def load_session_from_path(path: Path | None):
    """Load a chat session from a file path."""
    if path is None:
        return

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logging.error("Failed to read session file", exc_info=exc)
        st.error("Unable to read the selected session file.", icon="⚠️")
        return

    try:
        restored_messages = messages_from_dict(payload.get("messages", []))
    except Exception as exc:
        logging.error("Failed to parse session messages", exc_info=exc)
        st.error("Session file is corrupted or incompatible.", icon="⚠️")
        return

    st.session_state.setdefault("agent_state", {})
    st.session_state["agent_state"]["messages"] = restored_messages
    st.session_state["subagent_states"] = payload.get("subagent_states", {})
    st.session_state["pending_images"] = []
    st.session_state["uploaded_pdfs"] = st.session_state.get("uploaded_pdfs", [])
    from queue import Queue
    st.session_state["state_queue"] = Queue()
    st.session_state["selected_session_label"] = _session_option_label(path)
    st.session_state["session_loader_select"] = st.session_state["selected_session_label"]
    st.toast(f"Loaded session from {path.name}", icon="📂")


def _format_message_content_for_html(content) -> str:
    """Format message content for HTML export."""
    if isinstance(content, str):
        return f"<p>{escape(content)}</p>"

    if isinstance(content, list):
        html_parts = []
        for part in content:
            if not isinstance(part, dict):
                html_parts.append(f"<p>{escape(str(part))}</p>")
                continue

            part_type = part.get("type")
            if part_type in {"text", "output_text"}:
                html_parts.append(f"<p>{escape(part.get('text', ''))}</p>")
            elif part_type == "image_url":
                image_url = part.get("image_url", {}).get("url")
                if image_url:
                    html_parts.append(
                        "<div><em>Image Attachment:</em><br/><img src=\"{}\" alt=\"image attachment\" style=\"max-width: 100%; height: auto;\"/></div>".format(
                            escape(image_url)
                        )
                    )
            else:
                html_parts.append(f"<pre>{escape(_safe_pretty_json(part))}</pre>")
        return "\n".join(html_parts)

    return f"<pre>{escape(repr(content))}</pre>"


def build_session_html(messages, subagent_states) -> str:
    """Build HTML export of a chat session."""
    rows = [
        "<html>",
        "<head>",
        "<meta charset=\"utf-8\" />",
        "<title>TissueAgent Session Export</title>",
        "<style>",
        "body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 2rem; }",
        ".message { margin-bottom: 1.5rem; padding: 1rem; border-radius: 0.75rem; }",
        ".role-user { background-color: #f0f4ff; }",
        ".role-ai { background-color: #f4fff0; }",
        ".role-tool { background-color: #fef9e7; }",
        ".message h3 { margin-top: 0; }",
        "pre { white-space: pre-wrap; word-break: break-word; }",
        "img { margin-top: 0.5rem; border: 1px solid #ccc; padding: 0.25rem; border-radius: 0.5rem; }",
        "</style>",
        "</head>",
        "<body>",
        f"<h1>TissueAgent Session Export — {escape(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}</h1>",
    ]

    for idx, message in enumerate(messages, start=1):
        role = getattr(message, "type", "unknown")
        role_class = {
            "human": "role-user",
            "ai": "role-ai",
            "tool": "role-tool",
        }.get(role, "role-unknown")

        tool_title = f"Tool — {_safe_escape(getattr(message, 'name', None), 'unknown')}"

        title = {
            "human": "User",
            "ai": "TissueAgent",
            "tool": tool_title,
        }.get(role, escape(role.title()))

        rows.append(f"<div class=\"message {role_class}\">")
        rows.append(f"<h3>{idx}. {title}</h3>")
        rows.append(_format_message_content_for_html(getattr(message, "content", "")))

        if role == "tool":
            tool_id = getattr(message, "id", None)
            if tool_id is not None and str(tool_id) in subagent_states:
                agent_name, final_state = subagent_states[str(tool_id)]
                rows.append("<details><summary>Subagent State</summary>")
                rows.append(f"<p><strong>Agent:</strong> {escape(str(agent_name))}</p>")
                rows.append(f"<pre>{escape(_safe_pretty_json(final_state))}</pre>")
                rows.append("</details>")

        rows.append("</div>")

    rows.extend(["</body>", "</html>"])
    return "\n".join(rows)


def strip_images_for_display(messages):
    """Return deep-copied messages where list-style content is collapsed to text only."""
    cleaned = []
    for m in messages:
        m2 = deepcopy(m)
        c = getattr(m2, "content", None)
        if isinstance(c, list):
            texts = []
            for part in c:
                if isinstance(part, dict) and part.get("type") in ("text", "output_text"):
                    texts.append(part.get("text", ""))
            m2.content = "\n".join(texts).strip()
        cleaned.append(m2)
    return cleaned


def render_conversation_history_display(all_messages, subagent_states, enable_debug):
    """Render conversation history for display, stripping images."""
    return render_conversation_history(
        strip_images_for_display(all_messages),
        subagent_states,
        enable_debug=enable_debug
    )


# ---------------------------------------------------------------------------
# Agent identity metadata
# ---------------------------------------------------------------------------

AvatarLabel = Tuple[str, str]

MAIN_AGENT_BADGES: Dict[str, AvatarLabel] = {
    "planner_agent": ("🧠", "Planner"),
    "recruiter_agent": ("🧑\u200d🤝\u200d🧑", "Recruiter"),
    "manager_agent": ("🧭", "Manager"),
    "evaluator_agent": ("🧪", "Evaluator"),
    "reporter_agent": ("📝", "Reporter"),
}

SUBAGENT_BADGES: Dict[str, str] = {
    "Coding Agent": "💻",
    "Searcher Agent": "🔍",
    "Single Cell Agent": "🧫",
}

DEFAULT_AGENT_AVATAR = "🤖"
DEFAULT_AGENT_LABEL = "Assistant"
SUBAGENT_DEFAULT_AVATAR = "🧩"
USER_AVATAR = "🧑\u200d🔬"


def _lookup_agent_badge(agent_name: Optional[str]) -> AvatarLabel:
    """Return the avatar and label for the given agent name."""

    if not agent_name:
        return DEFAULT_AGENT_AVATAR, DEFAULT_AGENT_LABEL
    if agent_name in MAIN_AGENT_BADGES:
        return MAIN_AGENT_BADGES[agent_name]
    friendly = agent_name.replace("_agent", "").replace("_", " ").title()
    return DEFAULT_AGENT_AVATAR, friendly or DEFAULT_AGENT_LABEL


# ---------------------------------------------------------------------------
# Content helpers
# ---------------------------------------------------------------------------

def _flatten_text_chunks(chunks: Sequence[Any]) -> str:
    """Return human-readable text extracted from LangChain content chunks."""

    texts: List[str] = []
    for part in chunks:
        if isinstance(part, dict):
            if part.get("type") in {"text", "output_text"}:
                texts.append(part.get("text", ""))
        elif isinstance(part, str):
            texts.append(part)
    return "\n".join(t for t in texts if t).strip()


def _stringify_chat_content(content: Any) -> str:
    """Convert message content into a plain-text representation."""

    if isinstance(content, str):
        return content
    if isinstance(content, Sequence):
        return _flatten_text_chunks(content)
    if content is None:
        return ""
    return str(content)


def _extract_tool_inputs(
    tool_calls: Optional[Iterable[Mapping[str, Any]]],
    sink: MutableMapping[str, str],
    ) -> List[str]:
    """Collect tool inputs keyed by call id and return a list of tool names."""

    names: List[str] = []
    if not tool_calls:
        return names

    for call in tool_calls:
        name = str(call.get("name", ""))
        tool_id = str(call.get("id", "")) or None
        raw_args = call.get("args", {})

        if isinstance(raw_args, str):
            try:
                parsed_args = json.loads(raw_args)
            except json.JSONDecodeError:
                parsed_args = raw_args
        else:
            parsed_args = raw_args

        if tool_id:
            sink[tool_id] = json.dumps(parsed_args, indent=2, ensure_ascii=False)
        names.append(name)
    return names

def _split_route_and_body(content: str) -> Tuple[Optional[str], str]:
    """Separate the optional ROUTE header from the remaining message body."""

    lines = [line for line in content.strip().splitlines() if line.strip()]
    if lines and lines[0].upper().startswith("ROUTE:"):
        route_caption = lines[0].split(":", 1)[-1].strip()
        body = "\n".join(lines[1:]).strip()
        return route_caption or None, body
    return None, content.strip()


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------

def render_subagent_history(messages: Sequence[BaseMessage]) -> None:
    """Render the message transcript for a recruited sub-agent."""

    tool_input_map: Dict[str, str] = {}
 
    for message in messages:

        content = _stringify_chat_content(message.content)
 
        if isinstance(message, AIMessage):
            agent_name = message.name or "Agent"
            tool_names = _extract_tool_inputs(message.tool_calls, tool_input_map)

            if tool_names:
                tool_list = ", ".join(tool_names)
                st.text(f"**[{agent_name}]** → `{tool_list}`")
            elif content:
                st.text(f"**[{agent_name}]**:\n\n{content}")
 
        elif isinstance(message, ToolMessage):
            tool_call_id = getattr(message, "tool_call_id", None)
            tool_input = tool_input_map.get(str(tool_call_id) if tool_call_id is not None else "", "No captured input")
            tool_output = _stringify_chat_content(message.content)

            with st.expander(f"Tool Call · {message.name}", expanded=False):
                st.write("**Input**")
                st.code(tool_input or "<empty>", language="json")
                st.write("**Output**")
                st.code(tool_output or "<empty>")

 
def _render_manager_tool_message(message: ToolMessage) -> None:
    """Render a manager tool invocation with an expandable output block."""

    avatar, role_label = _lookup_agent_badge("manager_agent")
    with st.chat_message("assistant", avatar=avatar):
        st.text(f"**{role_label} Tool:** `{message.name}`")
        tool_output = _stringify_chat_content(message.content)
        with st.expander("Output", expanded=False):
            st.code(tool_output or "<empty>")


def _render_subagent_tool_message(
    message: ToolMessage,
    subagent_state: Mapping[str, Tuple[str, MessagesState]],
) -> None:
    """Render the transcript for a tool executed by a recruited sub-agent."""
    tool_id = str(getattr(message, "id", "")) if getattr(message, "id", None) is not None else ""
    agent_name, agent_state = subagent_state.get(tool_id, ("Unknown Agent", None))
    avatar = SUBAGENT_BADGES.get(agent_name, SUBAGENT_DEFAULT_AVATAR)

    with st.chat_message("assistant", avatar=avatar):
        st.text(f"**{agent_name}**")

        if isinstance(agent_state, Mapping) and agent_state.get("messages"):
            render_subagent_history(agent_state["messages"])
        else:
            st.warning(f"{agent_name}: {agent_state}", icon="⚠️")

def render_conversation_history(
    messages: Sequence[BaseMessage],
    subagent_state: Mapping[str, Tuple[str, MessagesState]],
    *,
    enable_debug: bool = True,
) -> None:
    """Render the full chat transcript for the Streamlit UI."""
    for message in messages:
        content = _stringify_chat_content(message.content)

        if isinstance(message, HumanMessage):

            with st.chat_message("user", avatar=USER_AVATAR):
                st.text(content or "")
            continue
 
        if isinstance(message, AIMessage):
            if not content:
                continue
            avatar, role_label = _lookup_agent_badge(message.name)
            with st.chat_message("assistant", avatar=avatar):
                st.text(f"**{role_label}**")
                route_caption, body = _split_route_and_body(content)
                st.text(body)
                if route_caption:
                    st.caption(f"Route → {route_caption}")
            continue

        if isinstance(message, ToolMessage) and enable_debug:
            if message.name in ManagerToolNames:
                _render_manager_tool_message(message)
            else:
                _render_subagent_tool_message(message, subagent_state)