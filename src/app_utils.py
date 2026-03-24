"""Streamlit helper utilities for rendering agent conversations.

This module centralises the presentation logic used by the TissueAgent chat
UI.  It covers three main areas:

1. **Session persistence** – saving / loading full chat sessions to JSON files
   and exporting them as standalone HTML documents.
2. **Agent identity metadata** – avatar and label lookups for main agents and
   recruited sub-agents so the UI can badge each message consistently.
3. **Conversation rendering** – functions that walk a LangChain message list
   and emit the corresponding Streamlit widgets (or raw HTML for export).
"""

from __future__ import annotations
import json
from collections import deque
import logging
import streamlit as st
import re
from copy import deepcopy
from datetime import datetime
from html import escape
from pathlib import Path
from typing import (
    Any,
    Dict,
    Iterable,
    List,
    Mapping,
    MutableMapping,
    Optional,
    Sequence,
    Tuple,
)

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.messages.utils import messages_from_dict
from langgraph.graph import MessagesState
from agents.manager_agent.tools import ManagerToolNames


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


def _preserve_newlines(text: str) -> str:
    """Return text formatted so Streamlit respects intentional line breaks."""
    return text.replace("\n", "  \n") if text else ""


def _message_to_serializable(message):
    """Convert a message to a serializable format for saving."""
    data = message.model_dump()
    data.pop("type", None)
    return {"type": message.type, "data": data}


def _format_session_label(session_path: Path, session_filename_prefix: str = "session_") -> str:
    """Format a session path into a human-readable label."""
    stem = session_path.stem
    if stem.startswith(session_filename_prefix):
        stem = stem[len(session_filename_prefix) :]
    try:
        saved_at = datetime.strptime(stem, "%Y-%m-%d_%H-%M-%S")
        return saved_at.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return stem


def _session_option_label(session_path: Path, session_filename_prefix: str = "session_") -> str:
    """Create a label for session selection dropdown."""
    return f"{_format_session_label(session_path, session_filename_prefix)} ({session_path.name})"


def save_current_session(
    sessions_dir: Path,
    session_filename_prefix: str = "session_",
    session_filename_suffix: str = ".json",
):
    """Save the current chat session to a JSON file on disk.

    Reads messages, subagent states, uploaded PDFs, and replan metadata from
    ``st.session_state`` and writes them to a timestamped JSON file inside
    *sessions_dir*.

    Args:
        sessions_dir: Directory where session files are stored.
        session_filename_prefix: Prefix prepended to the timestamp in the
            generated filename.
        session_filename_suffix: File extension appended to the filename.
    """
    messages = st.session_state.get("agent_state", {}).get("messages", [])
    if not messages:
        st.toast("No conversation history to save yet.", icon="ℹ️")
        return

    payload = {
        "saved_at": datetime.now().strftime("%Y-%m-%d_%H-%M-%S"),
        "messages": [_message_to_serializable(m) for m in messages],
        "subagent_states": st.session_state.get("subagent_states", {}),
        "uploaded_pdfs": st.session_state.get("uploaded_pdfs", []),
        "replan_count": st.session_state.get("agent_state", {}).get("replan_count", 0),
        "replan_history": st.session_state.get("agent_state", {}).get("replan_history", []),
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
    st.session_state["selected_session_label"] = _session_option_label(
        target_path, session_filename_prefix
    )
    st.session_state["session_loader_select"] = st.session_state["selected_session_label"]


def load_session_from_path(path: Path | None):
    """Load a chat session from a JSON file and restore it into session state.

    Deserialises messages via :func:`messages_from_dict`, restores subagent
    states, uploaded PDFs, and replan metadata, then reinitialises the display
    and event queues.

    Args:
        path: Path to the session JSON file.  If ``None``, the function
            returns immediately without side effects.
    """
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
    st.session_state["agent_state"].setdefault("replan_count", 0)
    st.session_state["agent_state"].setdefault("replan_history", [])
    if "replan_count" in payload:
        st.session_state["agent_state"]["replan_count"] = payload["replan_count"]
    if "replan_history" in payload:
        st.session_state["agent_state"]["replan_history"] = payload["replan_history"]
    st.session_state["subagent_states"] = payload.get("subagent_states", {})
    st.session_state["pending_subagent_states"] = deque()
    st.session_state["display_messages"] = list(restored_messages)
    st.session_state["display_message_ids"] = set()
    st.session_state["pending_images"] = []
    # Restore uploaded_pdfs from saved session (preserves file_id and attached_to_conversation flags)
    st.session_state["uploaded_pdfs"] = payload.get("uploaded_pdfs", [])
    from queue import Queue

    st.session_state["state_queue"] = Queue()
    st.session_state["ui_event_queue"] = Queue()
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
                        '<div><em>Image Attachment:</em><br/>'
                        '<img src="{}" alt="image attachment"'
                        ' style="max-width: 100%; height: auto;"/>'
                        "</div>".format(escape(image_url))
                    )
            else:
                html_parts.append(f"<pre>{escape(_safe_pretty_json(part))}</pre>")
        return "\n".join(html_parts)

    return f"<pre>{escape(repr(content))}</pre>"


def build_session_html(messages, subagent_states) -> str:
    """Build a self-contained HTML document from a chat session.

    The output mirrors the Streamlit view with styled message blocks for
    user, AI, and tool messages, including embedded sub-agent transcripts.

    Args:
        messages: Sequence of LangChain messages comprising the session.
        subagent_states: Mapping of tool message IDs to ``(agent_name,
            final_state)`` tuples for recruited sub-agents.

    Returns:
        A complete HTML string suitable for writing to a file or serving
        as a download.
    """
    rendered_blocks = _render_conversation_history_html(messages, subagent_states)
    return "\n".join(
        [
            "<html>",
            "<head>",
            '<meta charset="utf-8" />',
            "<title>TissueAgent Session Export</title>",
            "<style>",
            "body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 2rem; }",
            ".message { margin-bottom: 1.5rem; padding: 1rem; border-radius: 0.75rem; border: 1px solid #e0e0e0; }",
            ".role-user { background-color: #f0f4ff; }",
            ".role-ai { background-color: #f4fff0; }",
            ".role-tool { background-color: #fffaf0; }",
            ".message h3 { margin-top: 0; margin-bottom: 0.5rem; }",
            ".message p { margin: 0.3rem 0; }",
            (
                ".subagent-block { background-color: #ffffff;"
                " border: 1px dashed #d0d0d0; padding: 0.75rem;"
                " border-radius: 0.5rem; margin-top: 0.5rem; }"
            ),
            ".subagent-block h4 { margin: 0 0 0.35rem 0; }",
            (
                ".route-pill { display: inline-block;"
                " padding: 0.2rem 0.6rem; border-radius: 999px;"
                " background: #e0e7ff; color: #1f2a44;"
                " font-size: 0.85rem; margin-top: 0.4rem; }"
            ),
            (
                ".tag-label { font-weight: 600;"
                " text-transform: capitalize;"
                " display: block; margin-top: 0.4rem; }"
            ),
            (
                "pre { white-space: pre-wrap; word-break: break-word;"
                " background: #fafafa; padding: 0.5rem;"
                " border-radius: 0.4rem; border: 1px solid #e3e3e3; }"
            ),
            "</style>",
            "</head>",
            "<body>",
            f"<h1>TissueAgent Session Export — {escape(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}</h1>",
            rendered_blocks,
            "</body>",
            "</html>",
        ]
    )


def strip_images_for_display(messages):
    """Return deep-copied messages with image content blocks removed.

    Multi-part content lists are collapsed to their text-only portions so
    the display layer does not attempt to render raw image data.

    Args:
        messages: Iterable of LangChain messages, potentially containing
            multi-part content with image entries.

    Returns:
        A new list of deep-copied messages where each message's content is
        a plain string with images stripped out.
    """
    cleaned = []
    for m in messages:
        if hasattr(m, "model_copy"):
            m2 = m.model_copy(deep=True)
        else:
            m2 = deepcopy(m)
        if hasattr(m, "name"):
            setattr(m2, "name", getattr(m, "name", None))
        c = getattr(m2, "content", None)
        if isinstance(c, list):
            texts = []
            for part in c:
                if isinstance(part, dict) and part.get("type") in (
                    "text",
                    "output_text",
                ):
                    texts.append(part.get("text", ""))
            m2.content = "\n".join(texts).strip()
        cleaned.append(m2)
    return cleaned


def render_conversation_history_display(all_messages, subagent_states, enable_debug):
    """Render conversation history in Streamlit with images stripped.

    A convenience wrapper that calls :func:`strip_images_for_display` before
    delegating to :func:`render_conversation_history`.

    Args:
        all_messages: Full list of LangChain messages from the agent state.
        subagent_states: Mapping of tool message IDs to ``(agent_name,
            final_state)`` tuples.
        enable_debug: When ``True``, tool messages are rendered with
            expandable input/output blocks.
    """
    return render_conversation_history(
        strip_images_for_display(all_messages),
        subagent_states,
        enable_debug=enable_debug,
    )


def _html_preserve_newlines(text: str) -> str:
    """Escape *text* for HTML and convert newlines to ``<br/>`` tags."""
    if not text:
        return ""
    return "<br/>".join(escape(text).splitlines())


def _subagent_state_to_html(agent_name: str, final_state: Any) -> str:
    """Render a sub-agent's final state as an HTML block for session export."""
    header = f'<div class="subagent-block"><h4>{escape(agent_name or "Subagent")}</h4>'
    if not isinstance(final_state, Mapping):
        return header + f"<p>{escape(str(final_state))}</p></div>"
    messages = final_state.get("messages")
    if not messages:
        return header + "<p>No transcript available.</p></div>"
    rows = []
    for msg in messages:
        role = getattr(msg, "type", "message").title()
        body = _html_preserve_newlines(_stringify_chat_content(getattr(msg, "content", "")))
        rows.append(f"<p><strong>{escape(role)}</strong>: {body}</p>")
    return header + "".join(rows) + "</div>"


def _render_conversation_history_html(
    messages: Sequence[BaseMessage],
    subagent_state: Mapping[str, Tuple[str, MessagesState]],
) -> str:
    """Convert a full message history into styled HTML blocks for session export."""
    blocks: List[str] = []
    for idx, message in enumerate(messages, start=1):
        if isinstance(message, HumanMessage):
            content = _html_preserve_newlines(_stringify_chat_content(message.content))
            body = f"<p>{content}</p>"
            blocks.append(f'<div class="message role-user"><h3>{idx}. User</h3>{body}</div>')
            continue

        if isinstance(message, AIMessage):
            content_raw = _stringify_chat_content(message.content)
            if not content_raw:
                continue
            avatar, role_label = _lookup_agent_badge(message.name)
            route_caption, body_text = _split_route_and_body(content_raw)
            body_parts = []
            html_tags = _extract_html_tags(body_text)
            if html_tags:
                for tag, text in html_tags.items():
                    body_parts.append(f'<span class="tag-label">{escape(tag)}</span>')
                    body_parts.append(f"<p>{_html_preserve_newlines(text)}</p>")
            else:
                body_parts.append(f"<p>{_html_preserve_newlines(body_text)}</p>")
            if route_caption:
                body_parts.append(f'<div class="route-pill">{escape(route_caption)}</div>')
            header = f"<h3>{idx}. {escape(role_label)}</h3>"
            blocks.append(f'<div class="message role-ai">{header}{"".join(body_parts)}</div>')
            continue

        if isinstance(message, ToolMessage):
            tool_name = getattr(message, "name", "") or "Tool"
            header = f"<h3>{idx}. Tool — {escape(tool_name)}</h3>"
            body_parts = [
                f"<p>{_html_preserve_newlines(_stringify_chat_content(message.content))}</p>"
            ]
            tool_id = getattr(message, "id", None)
            if tool_id is not None and str(tool_id) in subagent_state:
                agent_name, final_state = subagent_state[str(tool_id)]
                body_parts.append(_subagent_state_to_html(agent_name, final_state))
            blocks.append(f'<div class="message role-tool">{header}{"".join(body_parts)}</div>')
    return "\n".join(blocks)


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
    "Gene Agent": "🧬",
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


def _extract_html_tags(content: str) -> Optional[Dict[str, str]]:
    """Check for HTML tags <execute>, <response>, <scratchpad>, or <plan> (case insensitive).

    Returns a dictionary mapping tag name to content, or None if no tags found.
    Handles unclosed tags by taking content to the end of the string.
    """
    allowed_tags = ["execute", "response", "scratchpad", "plan"]

    pattern = r"<(" + "|".join(re.escape(tag) for tag in allowed_tags) + r")>(.*?)(?:</\1>|$)"
    pattern = re.compile(pattern, re.IGNORECASE | re.DOTALL)

    matches = pattern.findall(content)

    if not matches:
        return None

    result = {}
    for tag, content_text in matches:
        result[tag.lower()] = content_text.strip()

    return result


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------


def render_subagent_history(messages: Sequence[BaseMessage]) -> None:
    """Render the message transcript for a recruited sub-agent.

    AI messages are displayed as agent labels with optional tool-call
    summaries, and tool messages are shown inside collapsible expanders
    with their input and output.

    Args:
        messages: Ordered sequence of messages from the sub-agent's
            conversation history.
    """
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
            tool_input = tool_input_map.get(
                str(tool_call_id) if tool_call_id is not None else "",
                "No captured input",
            )
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
    """Render the full chat transcript as Streamlit chat widgets.

    Iterates over *messages* and emits the appropriate Streamlit elements
    for each message type (user, AI, tool).  Manager and sub-agent tool
    messages are rendered with their own specialised widgets when
    *enable_debug* is ``True``.

    Args:
        messages: Ordered sequence of LangChain messages to display.
        subagent_state: Mapping of tool message IDs to ``(agent_name,
            final_state)`` tuples for recruited sub-agents.
        enable_debug: When ``True``, tool messages are rendered with
            expandable trace blocks.  When ``False``, they are hidden.
    """
    for message in messages:
        content = _stringify_chat_content(message.content)

        if isinstance(message, HumanMessage):
            with st.chat_message("user", avatar=USER_AVATAR):
                st.markdown(_preserve_newlines(content))

        elif isinstance(message, AIMessage):
            if not content:
                continue
            avatar, role_label = _lookup_agent_badge(message.name)
            with st.chat_message("assistant", avatar=avatar):
                st.markdown(f"**{role_label}**")
                route_caption, body = _split_route_and_body(content)
                html_tags = _extract_html_tags(body)
                if html_tags:
                    for tag, content in html_tags.items():
                        st.markdown(f"**{tag}**")
                        st.markdown(_preserve_newlines(content))
                else:
                    st.markdown(_preserve_newlines(body))
                if route_caption:
                    st.caption(f"Route → {route_caption}")

        elif isinstance(message, ToolMessage) and enable_debug:
            if message.name in ManagerToolNames:
                _render_manager_tool_message(message)
            else:
                _render_subagent_tool_message(message, subagent_state)
