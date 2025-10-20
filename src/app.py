import anthropic
import json
import logging
import openai
import os
import shutil
from datetime import datetime
from pathlib import Path
import streamlit as st
import streamlit_nested_layout  

from functools import partial
from copy import deepcopy
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.messages.utils import messages_from_dict
from langgraph.errors import GraphRecursionError
from pydantic import SecretStr
from streamlit_file_browser import st_file_browser
from queue import Queue
import queue
import base64
import mimetypes
from html import escape
from typing import Any
from app_utils import LLMOptions, render_conversation_history as util_render_conversation_history
from agents.manager_agent.tools import ManagerToolNames
from agents.agent_utils import PythonREPLObj
from graph.graph import create_tissueagent_graph
from graph.graph_utils import log_message
from config import DATA_DIR, DATASET_DIR, PDF_UPLOADS_DIR, RECURSION_LIMIT, SESSIONS_DIR, UPLOADS_DIR

def clear_queue(q: queue.Queue):
    """Remove everything from a Queue in a thread-safe way."""
    try:
        while True:
            q.get_nowait()
    except queue.Empty:
        pass

def _safe_escape(value: Any, fallback: str = "") -> str:
    """HTML-escape arbitrary values, substituting a fallback for None."""
    if value is None:
        return escape(fallback)
    return escape(str(value))

def _file_to_data_url(file_path: Path) -> str:
    """Convert a local file to a Base64 data URL for multimodal chat."""
    mime, _ = mimetypes.guess_type(file_path.name)
    if mime is None:
        mime = "application/octet-stream"
    b64 = base64.b64encode(file_path.read_bytes()).decode("utf-8")
    return f"data:{mime};base64,{b64}"

def _next_available_path(directory: Path, filename: str) -> Path:
    """Return a unique path inside directory by suffixing an index if needed."""
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

def _reset_data_directories() -> None:
    """Clear the entire data directory tree and recreate known subdirectories."""
    shutil.rmtree(DATA_DIR, ignore_errors=True)
    for directory in (
        DATA_DIR,
        DATASET_DIR,
        UPLOADS_DIR,
        PDF_UPLOADS_DIR,
        SESSIONS_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)

SESSION_FILENAME_PREFIX = "session_"
SESSION_FILENAME_SUFFIX = ".json"


def _message_to_serializable(message):
    data = message.model_dump()
    data.pop("type", None)
    return {"type": message.type, "data": data}


def _format_session_label(session_path: Path) -> str:
    stem = session_path.stem
    if stem.startswith(SESSION_FILENAME_PREFIX):
        stem = stem[len(SESSION_FILENAME_PREFIX):]
    try:
        saved_at = datetime.strptime(stem, "%Y-%m-%d_%H-%M-%S")
        return saved_at.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return stem


def _session_option_label(session_path: Path) -> str:
    return f"{_format_session_label(session_path)} ({session_path.name})"


def _save_current_session():
    messages = st.session_state.get("agent_state", {}).get("messages", [])
    if not messages:
        st.toast("No conversation history to save yet.", icon="ℹ️")
        return

    payload = {
        "saved_at": datetime.now().strftime("%Y-%m-%d_%H-%M-%S"),
        "messages": [_message_to_serializable(m) for m in messages],
        "subagent_states": st.session_state.get("subagent_states", {}),
    }

    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    file_name = f"{SESSION_FILENAME_PREFIX}{payload['saved_at']}{SESSION_FILENAME_SUFFIX}"
    target_path = SESSIONS_DIR / file_name

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
    st.session_state["selected_session_label"] = _session_option_label(target_path)
    st.session_state["session_loader_select"] = st.session_state["selected_session_label"]


def _load_session_from_path(path: Path | None):
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
    st.session_state["state_queue"] = Queue()
    st.session_state["selected_session_label"] = _session_option_label(path)
    st.session_state["session_loader_select"] = st.session_state["selected_session_label"]
    st.toast(f"Loaded session from {path.name}", icon="📂")

def _format_message_content_for_html(content) -> str:
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


def _build_session_html(messages, subagent_states) -> str:
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
            if tool_id is not None and tool_id in subagent_states:
                agent_name, final_state = subagent_states[tool_id]
                rows.append("<details><summary>Subagent State</summary>")
                rows.append(f"<p><strong>Agent:</strong> {escape(str(agent_name))}</p>")
                rows.append(f"<pre>{escape(_safe_pretty_json(final_state))}</pre>")
                rows.append("</details>")

        rows.append("</div>")

    rows.extend(["</body>", "</html>"])
    return "\n".join(rows)


# Strip images from messages when rendering the chat history (display-only)
def _strip_images_for_display(messages):
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
    return util_render_conversation_history(
        _strip_images_for_display(all_messages),
        subagent_states,
        enable_debug=enable_debug
    )

# One-turn attachments live here until the user sends a message
if "pending_images" not in st.session_state:
    st.session_state["pending_images"] = []

if "uploaded_pdfs" not in st.session_state:
    st.session_state["uploaded_pdfs"] = []  # ← track saved PDF uploads

# Modal for image upload (opened by the ➕ button)
# image_modal = Modal("Add image(s)", key="image_modal", max_width=500)


if "api_keys" not in st.session_state:
    st.session_state["api_keys"] = {
        "llm": "",
        "openai": "",
        "serp": "",
        "email": "",
    }

# file_browser_modal = Modal("File Browser", key="file_browser_modal")
if "show_file_browser" not in st.session_state:
    st.session_state.show_file_browser = False

if "model_selected" not in st.session_state:
    st.session_state.model_selected = False

with st.sidebar:
    llm_option = st.selectbox(
        "LLM Model",
        LLMOptions.keys(),
        disabled=st.session_state.model_selected,
    )

    local_openai_api_key = os.getenv("OPENAI_API_KEY", "")
    openai_api_key = SecretStr(st.text_input(
        "OpenAI API Key:",
        type="password",
        value=local_openai_api_key,
        disabled=st.session_state.model_selected,
    ))

    local_anthropic_api_key = os.getenv("ANTHROPIC_API_KEY", "")
    anthropic_api_key = SecretStr(st.text_input(
        "Anthropic API Key:",
        type="password",
        value=local_anthropic_api_key,
        help="not required if selected model is from OpenAI",
        disabled=st.session_state.model_selected,
    ))

    local_serp_api_key = os.getenv("SERP_API_KEY", "")
    serp_api_key = SecretStr(st.text_input(
        "SerpAPI Key:",
        type="password",
        value=local_serp_api_key,
        disabled=st.session_state.model_selected,
    ))

    email = st.text_input(
        "Email (optional):",
        help="used for PubMed API",
        disabled=st.session_state.model_selected,
    )

    def submit_form():
        if not serp_api_key.get_secret_value() or not openai_api_key.get_secret_value():
            st.toast("Invalid form responses, please try again.", icon="🚨")
            return
        st.session_state.model_selected = True

    st.button(
        "☑️ Start the Agent",
        on_click=submit_form,
        disabled=st.session_state.model_selected,
    )

    st.sidebar.markdown("---")

    uploaded_files = st.file_uploader("Upload Dataset:", accept_multiple_files=True)

    col1, col2 = st.columns(2)

    with col1:
        def toggle_file_browser():
            st.session_state.show_file_browser = not st.session_state.show_file_browser
        button_status = "Close" if st.session_state.show_file_browser else "Open"
        st.button(f"📁 {button_status} File Browser", on_click=toggle_file_browser)

    with col2:
        enable_debug = st.checkbox("Enable Debug Output", value=True)
    ########## Image Uploader ##########
    st.markdown("---")
    st.caption("Attach image(s) to send with your next message.")
    image_files = st.file_uploader(
        "Upload Image Attachments:",
        type=["png", "jpg", "jpeg", "webp", "gif"],
        accept_multiple_files=True,
        key="sidebar_image_uploader",
    )

    if image_files:
        existing = {
            img["name"]: img["path"]
            for img in st.session_state.get("pending_images", [])
        }
        saved_images = []
        for image in image_files:
            if image.name in existing and Path(existing[image.name]).exists():
                saved_images.append({
                    "name": image.name,
                    "path": existing[image.name],
                })
                continue

            target_path = _next_available_path(UPLOADS_DIR, image.name)
            target_path.write_bytes(image.getvalue())
            saved_images.append({
                "name": image.name,
                "path": target_path,
            })

        st.session_state["pending_images"] = saved_images

    if st.session_state.get("pending_images"):
        pending_names = ", ".join(img["name"] for img in st.session_state["pending_images"])
        st.caption(f"Pending images: {pending_names}")
    else:
        st.caption("No images attached yet.")
    
    ########## PDF Uploader ##########
    st.markdown("---")
    st.caption("Upload PDF document(s) for the agent to reference.")
    pdf_files = st.file_uploader(
        "Upload PDF Inputs:",
        type=["pdf"],
        accept_multiple_files=True,
        key="sidebar_pdf_uploader",
    )  # ← new PDF uploader lives under dataset/image sections

    if pdf_files:
        existing_pdfs = {
            pdf_info["name"]: pdf_info["path"]
            for pdf_info in st.session_state.get("uploaded_pdfs", [])
            if Path(pdf_info["path"]).exists()
        }
        saved_pdfs = []
        for pdf in pdf_files:
            if pdf.name in existing_pdfs:
                saved_pdfs.append({
                    "name": pdf.name,
                    "path": existing_pdfs[pdf.name],
                })
                continue

            pdf_path = _next_available_path(PDF_UPLOADS_DIR, pdf.name)
            pdf_path.write_bytes(pdf.getvalue())
            saved_pdfs.append({
                "name": pdf.name,
                "path": str(pdf_path),
            })

        st.session_state["uploaded_pdfs"] = saved_pdfs

    if st.session_state.get("uploaded_pdfs"):
        pdf_names = ", ".join(pdf["name"] for pdf in st.session_state["uploaded_pdfs"])
        st.caption(f"Saved PDFs: {pdf_names}")
    else:
        st.caption("No PDFs uploaded yet.")

    ########### Session Saver/Loader ##########
    st.markdown("---")
    st.caption("Save or load full chat sessions.")
    st.button(
        "💾 Save Current Session",
        on_click=_save_current_session,
        use_container_width=True,
    )

    session_files = sorted(
        SESSIONS_DIR.glob(f"{SESSION_FILENAME_PREFIX}*{SESSION_FILENAME_SUFFIX}"),
        reverse=True,
    )
    session_map = {_session_option_label(path): path for path in session_files}

    options = ["—"] + list(session_map.keys())
    current_selection = st.session_state.get(
        "session_loader_select",
        st.session_state.get("selected_session_label", "—"),
    )
    if current_selection not in options:
        current_selection = "—"
    default_index = options.index(current_selection)
    selected_label = st.selectbox(
        "Saved Sessions:",
        options,
        index=default_index,
        key="session_loader_select",
        help="Sessions are saved with timestamps so you can revisit any conversation.",
    )
    selected_path = session_map.get(selected_label)

    st.button(
        "📂 Load Selected Session",
        on_click=_load_session_from_path,
        args=(selected_path,),
        disabled=selected_path is None,
        use_container_width=True,
    )

    if not session_files:
        st.caption("No saved sessions yet.")

    current_messages = st.session_state.get("agent_state", {}).get("messages", [])
    if current_messages:
        session_html = _build_session_html(
            current_messages,
            st.session_state.get("subagent_states", {}),
        )
        download_name = (
            f"{SESSION_FILENAME_PREFIX}{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.html"
        )
        st.download_button(
            "⬇️ Download Session as HTML",
            data=session_html.encode("utf-8"),
            file_name=download_name,
            mime="text/html",
            use_container_width=True,
        )
    else:
        st.caption("Chat history will appear here for HTML export once available.")


# ╔═══════════════════════╗
# ║ File Browser          ║
# ╚═══════════════════════╝

# if "processed_files" not in st.session_state:
#     # shutil.rmtree(DATA_DIR, ignore_errors=True)
#     shutil.rmtree(DATASET_DIR, ignore_errors=True)
#     st.session_state["processed_files"] = set()
#     DATA_DIR.mkdir(parents=True, exist_ok=True)
#     DATASET_DIR.mkdir(parents=True, exist_ok=True)
#     UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
#     PDF_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
#     SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
if "data_initialized" not in st.session_state:
    _reset_data_directories()
    st.session_state["data_initialized"] = True
    st.session_state["processed_files"] = set()
else:
    for directory in (
        DATA_DIR,
        DATASET_DIR,
        UPLOADS_DIR,
        PDF_UPLOADS_DIR,
        SESSIONS_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)
    st.session_state.setdefault("processed_files", set())

if uploaded_files:
    for uploaded_file in uploaded_files:
        if uploaded_file.name not in st.session_state["processed_files"]:
            st.session_state["processed_files"].add(uploaded_file.name)
            # file_path = DATA_DIR / uploaded_file.name
            file_path = DATASET_DIR / uploaded_file.name
            file_path.write_bytes(uploaded_file.getvalue())

if st.session_state.show_file_browser:
    st.markdown(
        """
        <style>
        .block-container { max-width: 1200px; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.caption(f"Browsing data files in: `{DATA_DIR}`")
    _ = st_file_browser(
        str(DATA_DIR),
        key="file_browser_modal",
        show_preview=True,
        show_delete_file=True,
        show_download_file=True,
        show_upload_file=True
    )
    # st.stop()
else:
    st.markdown(
        """
        <style>
        .block-container { max-width: 720px; }
        </style>
        """,
        unsafe_allow_html=True,
    )



# ╔═══════════════════════╗
# ║ Disabled Chat UI      ║
# ╚═══════════════════════╝

st.title("🧬 TissueAgent")

if not st.session_state.model_selected:
    st.chat_input("Select in the sidebar!", disabled=True)
    st.stop()


# ╔═══════════════════════╗
# ║ Initialize Agent      ║
# ╚═══════════════════════╝

model_ctor, model_name = LLMOptions[llm_option]


if "state_queue" not in st.session_state:
    st.session_state["state_queue"] = Queue()
state_queue = st.session_state["state_queue"]

if "agent" not in st.session_state:
    bind_retry_fn = lambda model: model.with_retry(
        retry_if_exception_type=(openai.RateLimitError, anthropic.RateLimitError),
        stop_after_attempt = 3,
    )
    graph = create_tissueagent_graph(
        state_queue,
        bind_retry_fn
    )
    st.session_state["agent"] = graph.compile()
agent = st.session_state["agent"]

if "agent_state" not in st.session_state:
    st.session_state["agent_state"] = {"messages": []}
    st.session_state["subagent_states"] = {}


# ╔═══════════════════════╗
# ║ Chat UI               ║
# ╚═══════════════════════╝

# Initial render (text-only copy)
render_conversation_history_display(
    st.session_state["agent_state"]["messages"],
    st.session_state["subagent_states"],
    enable_debug
)

# chat_input must be at the root (not inside columns/containers)
prompt = st.chat_input("Ask the agent:")

# Build and send a multimodal HumanMessage when user submits text
if prompt:
    content_parts = [{"type": "text", "text": prompt}]

    # attach any pending images
    for f in st.session_state.get("pending_images", []):
        content_parts.append({
            "type": "image_url",
            "image_url": {"url": _file_to_data_url(f["path"])}
        })

    user_message = HumanMessage(content=content_parts)
    PythonREPLObj.add_text(f"[User]: {prompt}")
    log_message(user_message)

    st.session_state["agent_state"]["messages"].append(user_message)

    # Re-render the just-sent message in text-only mode
    render_conversation_history_display([user_message], {}, enable_debug)

    # clear one-shot attachments after sending
    st.session_state["pending_images"] = []

    rendered_prefix = len(st.session_state["agent_state"]["messages"])

    try:
        with st.spinner("SpatialAgent is Thinking...", show_time=True):
            st.session_state["agent_state"] = agent.invoke(
                st.session_state["agent_state"],
                {"recursion_limit": RECURSION_LIMIT}
            )
    except GraphRecursionError as e:
        st.error(f"Graph Recursion Error: {e}", icon="⚠️")
        logging.error("GraphRecursionError", exc_info=e)
    except (anthropic.BadRequestError, openai.BadRequestError) as e:
        st.error(f"Bad Request Error: {e}", icon="⚠️")
        logging.error("BadRequestError", exc_info=e)
    except Exception as e:
        st.exception(e)
        logging.error("Unexpected error", exc_info=e)

    for message in st.session_state["agent_state"]["messages"]:
        if not isinstance(message, ToolMessage):
            continue
        if message.name in ManagerToolNames:
            pass
        else:
            tool_id = message.id
            if tool_id in st.session_state["subagent_states"]:
                continue
            if getattr(message, "status", None) == "error":
                st.session_state["subagent_states"][tool_id] = (message.name, message.content)
            elif state_queue.empty():
                logging.error(f"No agent state found for following message {message}")
                st.session_state["subagent_states"][tool_id] = ("agent not found", None)
            else:
                agent_name, final_state = state_queue.get()
                st.session_state["subagent_states"][tool_id] = (agent_name, final_state)

    if not state_queue.empty():
        st.exception("Display Error: This is likely caused by a concurrency or a parallelization issue.")
        logging.error("Display Error: This is likely caused by a concurrency or a parallelization issue.")
        clear_queue(state_queue)

    # Final render of new messages (text-only copy)
    render_conversation_history_display(
        st.session_state["agent_state"]["messages"][rendered_prefix:],
        st.session_state["subagent_states"], enable_debug
    )