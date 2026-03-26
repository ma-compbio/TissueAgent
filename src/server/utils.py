"""Framework-agnostic utilities extracted from the Streamlit app.

Provides file handling, message identity, session persistence, HTML export,
and content-parsing helpers used by the FastAPI server layer.
"""

import base64
import json
import logging
import mimetypes
import re
import shutil
from collections import deque
from copy import deepcopy
from datetime import datetime
from html import escape
from pathlib import Path
from queue import Queue
from typing import (
    Any,
    Deque,
    Dict,
    Iterable,
    List,
    Mapping,
    MutableMapping,
    Optional,
    Sequence,
    Set,
    Tuple,
)

import openai
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.messages.utils import messages_from_dict
from langgraph.graph import MessagesState

from agents.manager_agent.tools import ManagerToolNames
from config import (
    DATA_DIR,
    DATASET_DIR,
    PDF_UPLOADS_DIR,
    SESSIONS_DIR,
    UPLOADS_DIR,
)

# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------


def file_to_data_url(file_path: Path) -> str:
    """Convert a local file to a Base64 data URL for multimodal chat."""
    mime, _ = mimetypes.guess_type(file_path.name)
    if mime is None:
        mime = "application/octet-stream"
    b64 = base64.b64encode(file_path.read_bytes()).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def upload_pdf_to_openai(pdf_path: Path) -> str:
    """Upload PDF to OpenAI Files API and return file_id."""
    try:
        file = openai.files.create(file=open(pdf_path, "rb"), purpose="user_data")
        logging.info(f"Uploaded PDF {pdf_path.name} to OpenAI, file_id: {file.id}")
        return file.id
    except Exception as e:
        logging.error(f"Failed to upload PDF {pdf_path.name}: {e}")
        raise


def next_available_path(directory: Path, filename: str) -> Path:
    """Return a unique path inside *directory* by suffixing an index if needed."""
    directory.mkdir(parents=True, exist_ok=True)
    candidate = directory / filename
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix
    for idx in range(1, 1000):
        candidate = directory / f"{stem}_{idx}{suffix}"
        if not candidate.exists():
            return candidate
    raise FileExistsError(f"Unable to allocate a unique filename for {filename}")


def reset_data_directories() -> None:
    """Clear and recreate runtime data folders."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    keep_and_clear = {DATASET_DIR, UPLOADS_DIR, PDF_UPLOADS_DIR}
    for child in DATA_DIR.iterdir():
        if not child.is_dir():
            continue
        if child in keep_and_clear:
            shutil.rmtree(child, ignore_errors=True)
            child.mkdir(parents=True, exist_ok=True)
        else:
            shutil.rmtree(child, ignore_errors=True)
    shutil.rmtree(SESSIONS_DIR, ignore_errors=True)
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Message identity & filtering
# ---------------------------------------------------------------------------


def message_identity(message: Any) -> str:
    """Return a stable string key for *message* used to de-duplicate display."""
    msg_id = getattr(message, "id", None)
    if msg_id:
        return str(msg_id)
    try:
        data = message.model_dump()
    except AttributeError:
        data = {
            "type": getattr(message, "type", type(message).__name__),
            "name": getattr(message, "name", None),
            "content": getattr(message, "content", None),
            "tool_calls": getattr(message, "tool_calls", None),
        }
    return json.dumps(data, sort_keys=True, default=str)


def should_hide_message(message: Any) -> bool:
    """Return True for messages that should not appear in the display stream."""
    if isinstance(message, HumanMessage):
        content = getattr(message, "content", "")
        if isinstance(content, str) and content.startswith("Python Output:\n"):
            return True
    return False


# ---------------------------------------------------------------------------
# Content helpers
# ---------------------------------------------------------------------------


def flatten_text_chunks(chunks: Sequence[Any]) -> str:
    """Return human-readable text extracted from LangChain content chunks."""
    texts: List[str] = []
    for part in chunks:
        if isinstance(part, dict):
            if part.get("type") in {"text", "output_text"}:
                texts.append(part.get("text", ""))
        elif isinstance(part, str):
            texts.append(part)
    return "\n".join(t for t in texts if t).strip()


def stringify_chat_content(content: Any) -> str:
    """Convert message content into a plain-text representation."""
    if isinstance(content, str):
        return content
    if isinstance(content, Sequence):
        return flatten_text_chunks(content)
    if content is None:
        return ""
    return str(content)


def extract_tool_inputs(
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


def split_route_and_body(content: str) -> Tuple[Optional[str], str]:
    """Separate the optional ROUTE header from the remaining message body."""
    lines = [line for line in content.strip().splitlines() if line.strip()]
    if lines and lines[0].upper().startswith("ROUTE:"):
        route_caption = lines[0].split(":", 1)[-1].strip()
        body = "\n".join(lines[1:]).strip()
        return route_caption or None, body
    return None, content.strip()


def extract_html_tags(content: str) -> Optional[Dict[str, str]]:
    """Extract <execute>, <response>, <scratchpad>, or <plan> tags (case insensitive)."""
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


def lookup_agent_badge(agent_name: Optional[str]) -> AvatarLabel:
    """Return the avatar and label for the given agent name."""
    if not agent_name:
        return DEFAULT_AGENT_AVATAR, DEFAULT_AGENT_LABEL
    if agent_name in MAIN_AGENT_BADGES:
        return MAIN_AGENT_BADGES[agent_name]
    friendly = agent_name.replace("_agent", "").replace("_", " ").title()
    return DEFAULT_AGENT_AVATAR, friendly or DEFAULT_AGENT_LABEL


# ---------------------------------------------------------------------------
# Image stripping
# ---------------------------------------------------------------------------


def strip_images_for_display(messages):
    """Return deep-copied messages with image content blocks removed."""
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
                if isinstance(part, dict) and part.get("type") in ("text", "output_text"):
                    texts.append(part.get("text", ""))
            m2.content = "\n".join(texts).strip()
        cleaned.append(m2)
    return cleaned


# ---------------------------------------------------------------------------
# Session persistence
# ---------------------------------------------------------------------------

SESSION_FILENAME_PREFIX = "session_"
SESSION_FILENAME_SUFFIX = ".json"


def message_to_serializable(message):
    """Convert a message to a serializable format for saving."""
    data = message.model_dump()
    data.pop("type", None)
    return {"type": message.type, "data": data}


def format_session_label(session_path: Path) -> str:
    """Format a session path into a human-readable label."""
    stem = session_path.stem
    if stem.startswith(SESSION_FILENAME_PREFIX):
        stem = stem[len(SESSION_FILENAME_PREFIX):]
    try:
        saved_at = datetime.strptime(stem, "%Y-%m-%d_%H-%M-%S")
        return saved_at.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return stem


def session_option_label(session_path: Path) -> str:
    """Create a label for session selection dropdown."""
    return f"{format_session_label(session_path)} ({session_path.name})"


def save_session(
    messages: List[BaseMessage],
    subagent_states: Dict,
    uploaded_pdfs: List[Dict],
    replan_count: int,
    replan_history: List,
) -> Path:
    """Save a chat session to a timestamped JSON file.

    Args:
        messages: The conversation message list.
        subagent_states: Mapping of tool IDs to (agent_name, state) tuples.
        uploaded_pdfs: List of uploaded PDF metadata dicts.
        replan_count: Current replan count.
        replan_history: List of replan timestamps.

    Returns:
        Path to the saved session file.

    Raises:
        ValueError: If there are no messages to save.
    """
    if not messages:
        raise ValueError("No conversation history to save.")

    payload = {
        "saved_at": datetime.now().strftime("%Y-%m-%d_%H-%M-%S"),
        "messages": [message_to_serializable(m) for m in messages],
        "subagent_states": subagent_states,
        "uploaded_pdfs": uploaded_pdfs,
        "replan_count": replan_count,
        "replan_history": replan_history,
    }

    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    file_name = f"{SESSION_FILENAME_PREFIX}{payload['saved_at']}{SESSION_FILENAME_SUFFIX}"
    target_path = SESSIONS_DIR / file_name
    target_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return target_path


def load_session(path: Path) -> Dict[str, Any]:
    """Load a chat session from a JSON file.

    Args:
        path: Path to the session JSON file.

    Returns:
        Dict with keys: messages, subagent_states, uploaded_pdfs,
        replan_count, replan_history.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    restored_messages = messages_from_dict(payload.get("messages", []))
    return {
        "messages": restored_messages,
        "subagent_states": payload.get("subagent_states", {}),
        "uploaded_pdfs": payload.get("uploaded_pdfs", []),
        "replan_count": payload.get("replan_count", 0),
        "replan_history": payload.get("replan_history", []),
    }


# ---------------------------------------------------------------------------
# HTML export
# ---------------------------------------------------------------------------


def _safe_pretty_json(obj: Any) -> str:
    """Safely format an object as pretty JSON."""
    try:
        return json.dumps(obj, indent=2, ensure_ascii=False, default=str)
    except Exception:
        return str(obj)


def _html_preserve_newlines(text: str) -> str:
    """Escape *text* for HTML and convert newlines to <br/> tags."""
    if not text:
        return ""
    return "<br/>".join(escape(text).splitlines())


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


def _subagent_state_to_html(agent_name: str, final_state: Any) -> str:
    """Render a sub-agent's final state as an HTML block."""
    header = f'<div class="subagent-block"><h4>{escape(agent_name or "Subagent")}</h4>'
    if not isinstance(final_state, Mapping):
        return header + f"<p>{escape(str(final_state))}</p></div>"
    messages = final_state.get("messages")
    if not messages:
        return header + "<p>No transcript available.</p></div>"
    rows = []
    for msg in messages:
        role = getattr(msg, "type", "message").title()
        body = _html_preserve_newlines(stringify_chat_content(getattr(msg, "content", "")))
        rows.append(f"<p><strong>{escape(role)}</strong>: {body}</p>")
    return header + "".join(rows) + "</div>"


def _render_conversation_history_html(
    messages: Sequence[BaseMessage],
    subagent_state: Mapping[str, Tuple[str, MessagesState]],
) -> str:
    """Convert a full message history into styled HTML blocks."""
    blocks: List[str] = []
    for idx, message in enumerate(messages, start=1):
        if isinstance(message, HumanMessage):
            content = _html_preserve_newlines(stringify_chat_content(message.content))
            body = f"<p>{content}</p>"
            blocks.append(f'<div class="message role-user"><h3>{idx}. User</h3>{body}</div>')
            continue
        if isinstance(message, AIMessage):
            content_raw = stringify_chat_content(message.content)
            if not content_raw:
                continue
            avatar, role_label = lookup_agent_badge(message.name)
            route_caption, body_text = split_route_and_body(content_raw)
            body_parts = []
            html_tags = extract_html_tags(body_text)
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
                f"<p>{_html_preserve_newlines(stringify_chat_content(message.content))}</p>"
            ]
            tool_id = getattr(message, "id", None)
            if tool_id is not None and str(tool_id) in subagent_state:
                entry = subagent_state[str(tool_id)]
                agent_name, final_state = entry[0], entry[1]
                body_parts.append(_subagent_state_to_html(agent_name, final_state))
            blocks.append(f'<div class="message role-tool">{header}{"".join(body_parts)}</div>')
    return "\n".join(blocks)


def build_session_html(messages, subagent_states) -> str:
    """Build a self-contained HTML document from a chat session.

    Args:
        messages: Sequence of LangChain messages comprising the session.
        subagent_states: Mapping of tool message IDs to (agent_name, final_state) tuples.

    Returns:
        A complete HTML string.
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
