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


_TITLE_MAX_LEN = 60


def derive_session_title(messages: Sequence[BaseMessage]) -> str:
    """Pick a short title for a saved session from its first user message.

    Returns an empty string when no usable text is found. The caller
    decides how to fall back (typically to the timestamp).
    """
    for m in messages:
        if isinstance(m, HumanMessage):
            text = stringify_chat_content(m.content).strip()
            if not text:
                continue
            # Single line, ellipsised at TITLE_MAX_LEN chars.
            first_line = text.splitlines()[0].strip()
            if len(first_line) > _TITLE_MAX_LEN:
                first_line = first_line[: _TITLE_MAX_LEN - 1].rstrip() + "…"
            return first_line
    return ""


def format_session_label(session_path: Path) -> str:
    """Format a session path into a human-readable timestamp label."""
    stem = session_path.stem
    if stem.startswith(SESSION_FILENAME_PREFIX):
        stem = stem[len(SESSION_FILENAME_PREFIX):]
    try:
        saved_at = datetime.strptime(stem, "%Y-%m-%d_%H-%M-%S")
        return saved_at.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return stem


def session_option_label(session_path: Path, title: str = "") -> str:
    """Create a label for the session selection dropdown.

    Combines the title (when available) with the timestamp. Falls back
    to the raw timestamp when no title was saved.
    """
    ts = format_session_label(session_path)
    return f"{title} — {ts}" if title else ts


def save_session(
    messages: List[BaseMessage],
    subagent_states: Dict,
    uploaded_pdfs: List[Dict],
    replan_count: int,
    replan_history: List,
    mode: str = "autopilot",
    plan_markdown: str = "",
) -> Path:
    """Save a chat session to a timestamped JSON file.

    Args:
        messages: The conversation message list.
        subagent_states: Mapping of tool IDs to (agent_name, state) tuples.
        uploaded_pdfs: List of uploaded PDF metadata dicts.
        replan_count: Current replan count.
        replan_history: List of replan timestamps.
        mode: Execution mode at save time ("autopilot" or "copilot").
        plan_markdown: The current evolving plan as on-disk markdown.
            Saved verbatim so it can be restored on load and rendered in
            HTML exports.

    Returns:
        Path to the saved session file.

    Raises:
        ValueError: If there are no messages to save.
    """
    if not messages:
        raise ValueError("No conversation history to save.")

    payload = {
        "saved_at": datetime.now().strftime("%Y-%m-%d_%H-%M-%S"),
        "title": derive_session_title(messages),
        "messages": [message_to_serializable(m) for m in messages],
        "subagent_states": subagent_states,
        "uploaded_pdfs": uploaded_pdfs,
        "replan_count": replan_count,
        "replan_history": replan_history,
        "mode": mode,
        "plan_markdown": plan_markdown,
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
    mode = payload.get("mode", "autopilot")
    if mode not in ("autopilot", "copilot"):
        mode = "autopilot"
    return {
        "messages": restored_messages,
        "subagent_states": payload.get("subagent_states", {}),
        "uploaded_pdfs": payload.get("uploaded_pdfs", []),
        "replan_count": payload.get("replan_count", 0),
        "replan_history": payload.get("replan_history", []),
        "mode": mode,
        "plan_markdown": payload.get("plan_markdown", "") or "",
        "title": payload.get("title", "") or "",
    }


def read_session_title(path: Path) -> str:
    """Cheap title lookup without parsing the whole message list.

    Used by the list endpoint so we don't deserialise every saved
    session's messages just to render the dropdown.
    """
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return str(payload.get("title", "") or "")
    except Exception:
        return ""


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


def _render_plan_html(plan_markdown: str) -> str:
    """Render a saved plan markdown blob as a top-of-document HTML block.

    Returns an empty string when there is no plan — callers should
    elide the section entirely in that case rather than print an empty
    box.
    """
    if not plan_markdown or not plan_markdown.strip():
        return ""

    # Parse via plan_store so the HTML matches what the UI shows.
    # Imported lazily so this module stays import-cheap.
    from server.plan_store import _parse_markdown

    doc = _parse_markdown(plan_markdown)
    if not doc.steps:
        return ""

    rows: List[str] = []
    rows.append('<section class="plan-export">')
    rows.append("<h2>Plan</h2>")
    rows.append(
        f'<div class="plan-meta">'
        f'<span class="plan-status-pill plan-status-{escape(doc.status)}">'
        f"{escape(doc.status)}</span>"
        + (
            f' <span class="plan-edited">edited by you</span>'
            if doc.last_edited_by == "user"
            else ""
        )
        + "</div>"
    )
    if doc.user_request:
        rows.append(
            f'<div class="plan-request"><strong>Request:</strong> '
            f"{escape(doc.user_request)}</div>"
        )

    rows.append('<ol class="plan-steps">')
    for step in doc.steps:
        rows.append('<li class="plan-step">')
        rows.append(
            f'<div class="plan-step-head">'
            f'<span class="plan-step-num">Step {step.id}</span> '
            f'<span class="plan-step-title">{escape(step.title)}</span> '
            f'<span class="plan-step-badge plan-status-{escape(step.status)}">'
            f"{escape(step.status)}</span>"
            "</div>"
        )
        if step.description:
            rows.append(
                f'<p><strong>Description:</strong> {escape(step.description)}</p>'
            )
        if step.reasoning:
            rows.append(
                f'<p><strong>Reasoning:</strong> {escape(step.reasoning)}</p>'
            )
        if step.assigned_agent:
            rationale = (
                f' — {escape(step.assignment_rationale)}'
                if step.assignment_rationale
                else ""
            )
            rows.append(
                f'<p><strong>Assigned:</strong> '
                f'<code>{escape(step.assigned_agent)}</code>{rationale}</p>'
            )
        if step.expected_artifacts:
            items = "".join(
                f"<li><code>{escape(a)}</code></li>" for a in step.expected_artifacts
            )
            rows.append(
                f'<div class="plan-step-artifacts">'
                f'<strong>Expected artifacts:</strong><ul>{items}</ul></div>'
            )
        if step.actual_outputs:
            items = "".join(
                f"<li><code>{escape(a)}</code></li>" for a in step.actual_outputs
            )
            rows.append(
                f'<div class="plan-step-artifacts">'
                f'<strong>Outputs:</strong><ul>{items}</ul></div>'
            )
        rows.append("</li>")
    rows.append("</ol>")
    rows.append("</section>")
    return "\n".join(rows)


def build_session_markdown(
    messages, plan_markdown: str = "", title: str = ""
) -> str:
    """Build a self-contained markdown document from a chat session.

    Unlike the HTML export, this one is plain prose designed for
    copy/paste into a notebook, paper draft, or issue tracker. No
    avatars, no styles, no sub-agent ReAct scratchpads.

    Args:
        messages: Sequence of LangChain messages from the session.
        plan_markdown: The evolving plan as on-disk markdown. Inlined
            verbatim at the top of the document when non-empty.
        title: Optional session title shown in the heading.

    Returns:
        A complete markdown string.
    """
    lines: List[str] = []
    when = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header_title = f"TissueAgent session — {title}" if title else "TissueAgent session"
    lines.append(f"# {header_title}")
    lines.append("")
    lines.append(f"*Exported {when}*")
    lines.append("")

    if plan_markdown and plan_markdown.strip():
        lines.append("## Plan")
        lines.append("")
        # The on-disk plan markdown already has its own ``# Plan`` heading
        # plus ``## Step N`` subheadings; demote each ``#`` so the export's
        # outline is consistent.
        lines.append(_demote_markdown_headings(plan_markdown, by=1))
        lines.append("")

    lines.append("## Conversation")
    lines.append("")
    for idx, message in enumerate(messages, start=1):
        if isinstance(message, HumanMessage):
            text = stringify_chat_content(message.content).strip()
            if not text:
                continue
            lines.append(f"### {idx}. User")
            lines.append("")
            lines.append(text)
            lines.append("")
        elif isinstance(message, AIMessage):
            text = stringify_chat_content(message.content).strip()
            if not text:
                continue
            _, role_label = lookup_agent_badge(message.name)
            lines.append(f"### {idx}. {role_label}")
            lines.append("")
            route, body = split_route_and_body(text)
            if route:
                lines.append(f"_ROUTE: {route}_")
                lines.append("")
            lines.append(body or text)
            lines.append("")
        elif isinstance(message, ToolMessage):
            tool_name = getattr(message, "name", "") or "tool"
            body = stringify_chat_content(message.content).strip()
            if not body:
                continue
            lines.append(f"### {idx}. Tool — `{tool_name}`")
            lines.append("")
            lines.append("```")
            lines.append(body)
            lines.append("```")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _demote_markdown_headings(md: str, *, by: int) -> str:
    """Shift every ATX-style heading by *by* levels (max 6).

    Used so an inlined plan markdown that starts at ``# Plan`` becomes
    ``## Plan`` inside the export's outline.
    """
    if by <= 0:
        return md

    def shift(match: "re.Match[str]") -> str:
        hashes, rest = match.group(1), match.group(2)
        new = "#" * min(6, len(hashes) + by)
        return f"{new}{rest}"

    return re.sub(r"^(#{1,6})( .*)", shift, md, flags=re.MULTILINE)


def build_session_html(messages, subagent_states, plan_markdown: str = "") -> str:
    """Build a self-contained HTML document from a chat session.

    Args:
        messages: Sequence of LangChain messages comprising the session.
        subagent_states: Mapping of tool message IDs to (agent_name, final_state) tuples.
        plan_markdown: The evolving plan as on-disk markdown. Rendered
            as the first block in the export when non-empty.

    Returns:
        A complete HTML string.
    """
    plan_html = _render_plan_html(plan_markdown)
    rendered_blocks = _render_conversation_history_html(messages, subagent_states)
    return "\n".join(
        [
            "<html>",
            "<head>",
            '<meta charset="utf-8" />',
            "<title>TissueAgent Session Export</title>",
            "<style>",
            "body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 2rem; max-width: 1100px; }",
            "h1 { font-size: 1.5rem; }",
            "h2 { margin-top: 2rem; }",
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
            # Plan-export styles
            (
                ".plan-export { background: #fafbff; border: 1px solid #d0d7ff;"
                " border-radius: 0.75rem; padding: 1rem 1.25rem; margin-bottom: 2rem; }"
            ),
            ".plan-export h2 { margin-top: 0; }",
            ".plan-meta { margin-bottom: 0.5rem; }",
            (
                ".plan-status-pill { display: inline-block; padding: 0.15rem 0.55rem;"
                " border-radius: 999px; font-size: 0.75rem;"
                " background: #e0e7ff; color: #1f2a44; font-weight: 600; }"
            ),
            ".plan-status-done, .plan-status-recruited { background: #d6f5d6; color: #1f4d1f; }",
            ".plan-status-failed { background: #ffe0e0; color: #6b1f1f; }",
            ".plan-status-running { background: #fff3cd; color: #5a4500; }",
            (
                ".plan-edited { display: inline-block; margin-left: 0.4rem;"
                " padding: 0.05rem 0.4rem; font-size: 0.7rem; font-weight: 600;"
                " background: #fef3c7; color: #7a4e00; border-radius: 0.35rem; }"
            ),
            ".plan-request { font-size: 0.9rem; margin-bottom: 0.8rem; }",
            ".plan-steps { padding-left: 1.25rem; }",
            ".plan-step { margin: 0.6rem 0; padding-bottom: 0.6rem; border-bottom: 1px solid #eaeaea; }",
            ".plan-step:last-child { border-bottom: none; }",
            ".plan-step-head { font-weight: 600; margin-bottom: 0.3rem; }",
            ".plan-step-num { color: #6b7280; margin-right: 0.4rem; }",
            (
                ".plan-step-badge { display: inline-block; margin-left: 0.4rem;"
                " padding: 0.05rem 0.4rem; font-size: 0.7rem; font-weight: 600;"
                " border-radius: 0.35rem; background: #e5e7eb; color: #374151; }"
            ),
            ".plan-step-artifacts { font-size: 0.85rem; }",
            ".plan-step-artifacts ul { margin: 0.2rem 0 0.5rem 1rem; padding: 0; }",
            "</style>",
            "</head>",
            "<body>",
            f"<h1>TissueAgent Session Export — {escape(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}</h1>",
            plan_html,
            "<h2>Conversation</h2>",
            rendered_blocks,
            "</body>",
            "</html>",
        ]
    )
