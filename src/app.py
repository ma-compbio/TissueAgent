"""Streamlit application entry-point for TissueAgent.

Launches the chat UI, manages sidebar controls (dataset upload, image/PDF
attachments, session save/load, file browser), and drives the LangGraph
agent loop.  Each user message is fed into the compiled TissueAgent graph;
intermediate sub-agent states are streamed back to the UI in near-real-time
via thread-safe queues.

Run with::

    PYTHONPATH=$(pwd)/src python -m streamlit run src/app.py
"""

import anthropic
import base64
import json
import logging
import mimetypes
import openai
import shutil
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from datetime import datetime
from pathlib import Path
import streamlit as st
from streamlit.delta_generator import DeltaGenerator
from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.errors import GraphRecursionError
from streamlit_file_browser import st_file_browser
from queue import Queue
from typing import Any, Deque, Set

import warnings
warnings.filterwarnings("ignore", category=FutureWarning)

from app_utils import (
    save_current_session,
    load_session_from_path,
    _session_option_label,
    build_session_html,
    render_conversation_history_display,
)
from agents.manager_agent.tools import ManagerToolNames
from graph.graph import create_tissueagent_graph
from graph.graph_utils import (
    log_message,
    record_user_message,
    register_ui_event_queue,
)
from memori_integration import initialize_memori_context, memori_enabled
from config import (
    DATA_DIR,
    DATASET_DIR,
    PDF_UPLOADS_DIR,
    RECURSION_LIMIT,
    SESSIONS_DIR,
    UPLOADS_DIR,
)


def _file_to_data_url(file_path: Path) -> str:
    """Convert a local file to a Base64 data URL for multimodal chat."""
    mime, _ = mimetypes.guess_type(file_path.name)
    if mime is None:
        mime = "application/octet-stream"
    b64 = base64.b64encode(file_path.read_bytes()).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def _upload_pdf_to_openai(pdf_path: Path) -> str:
    """Upload PDF to OpenAI Files API and return file_id."""
    try:
        file = openai.files.create(file=open(pdf_path, "rb"), purpose="user_data")
        logging.info(f"Uploaded PDF {pdf_path.name} to OpenAI, file_id: {file.id}")
        return file.id
    except Exception as e:
        logging.error(f"Failed to upload PDF {pdf_path.name}: {e}")
        raise


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
    """Clear and keep explicitly listed runtime folders, and delete all other subdirectories.

    - Keeps (but clears): data/dataset, data/uploads, data/pdfs, sessions/
    - Deletes entirely: any other subdirectories under data/
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    keep_and_clear = {DATASET_DIR, UPLOADS_DIR, PDF_UPLOADS_DIR}

    for child in DATA_DIR.iterdir():
        if child.name == "memori" or not child.is_dir():
            continue
        if child in keep_and_clear:
            shutil.rmtree(child, ignore_errors=True)
            child.mkdir(parents=True, exist_ok=True)
        else:
            shutil.rmtree(child, ignore_errors=True)
    shutil.rmtree(SESSIONS_DIR, ignore_errors=True)
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


initialize_memori_context()


def _message_identity(message: Any) -> str:
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


def _should_hide_message(message: Any) -> bool:
    """Return True for internal transfer-tool messages that should not be shown."""
    from langchain_core.messages import ToolMessage as _ToolMessage

    if isinstance(message, _ToolMessage):
        name = getattr(message, "name", "") or ""
        return name.endswith("_transfer_tool")
    return False


def _ensure_display_state():
    """Synchronise ``display_messages`` with the canonical agent message list."""
    existing_messages = [
        msg for msg in st.session_state["agent_state"]["messages"] if not _should_hide_message(msg)
    ]
    display_messages = st.session_state.setdefault("display_messages", existing_messages)
    if display_messages is not existing_messages:
        display_messages[:] = existing_messages
    ids = st.session_state.setdefault("display_message_ids", set())
    if not ids:
        ids.update(_message_identity(msg) for msg in display_messages)


def _render_conversation(
    placeholder: DeltaGenerator,
    enable_debug: bool,
):
    """Clear and re-render the full conversation into *placeholder*."""
    placeholder.empty()
    with placeholder.container():
        render_conversation_history_display(
            st.session_state["display_messages"],
            st.session_state["subagent_states"],
            enable_debug,
        )

def _append_display_message(
    message: Any,
    placeholder: DeltaGenerator,
    enable_debug: bool,
) -> bool:
    """Append *message* to the display list if it is new, then re-render."""
    if _should_hide_message(message):
        return False
    msg_key = _message_identity(message)
    ids: Set[str] = st.session_state["display_message_ids"]
    if msg_key in ids:
        return False
    ids.add(msg_key)
    st.session_state["display_messages"].append(message)
    _render_conversation(placeholder, enable_debug)
    return True


def _drain_event_queue(
    event_queue: Queue,
    placeholder: DeltaGenerator,
    enable_debug: bool,
) -> None:
    """Flush all pending UI events from the queue into the display."""
    while not event_queue.empty():
        message = event_queue.get()
        _append_display_message(message, placeholder, enable_debug)


def _drain_subagent_queue(
    state_queue: Queue,
    pending_states: Deque[Any],
) -> None:
    """Move completed sub-agent states from the queue into the pending deque."""
    while not state_queue.empty():
        pending_states.append(state_queue.get())


SESSION_FILENAME_PREFIX = "session_"
SESSION_FILENAME_SUFFIX = ".json"

if "pending_images" not in st.session_state:
    st.session_state["pending_images"] = []

if "uploaded_pdfs" not in st.session_state:
    st.session_state["uploaded_pdfs"] = []

if "show_file_browser" not in st.session_state:
    st.session_state.show_file_browser = False

with st.sidebar:
    memori_status = (
        "🧠 Memori long-term memory: enabled"
        if memori_enabled()
        else "🧠 Memori long-term memory: disabled"
    )
    st.caption(memori_status)

    ### Upload Dataset

    uploaded_files = st.file_uploader("Upload Dataset:", accept_multiple_files=True)

    ### File Browser / Trace

    col1, col2 = st.columns(2)
    with col1:

        def toggle_file_browser():
            """Toggle the file browser visibility in session state."""
            st.session_state.show_file_browser = not st.session_state.show_file_browser

        button_status = "Close" if st.session_state.show_file_browser else "Open"
        st.button(f"📁 {button_status} File Browser", on_click=toggle_file_browser)
    with col2:
        enable_debug = st.checkbox("Enable Trace", value=True)
    st.markdown("---")

    ### Upload Images

    st.caption("Attach image(s) to send with your next message.")
    image_files = st.file_uploader(
        "Upload Image Attachments:",
        type=["png", "jpg", "jpeg", "webp", "gif"],
        accept_multiple_files=True,
        key="sidebar_image_uploader",
    )

    if image_files:
        existing = {img["name"]: img["path"] for img in st.session_state.get("pending_images", [])}
        saved_images = []
        for image in image_files:
            if image.name in existing and Path(existing[image.name]).exists():
                saved_images.append(
                    {
                        "name": image.name,
                        "path": existing[image.name],
                    }
                )
                continue

            target_path = _next_available_path(UPLOADS_DIR, image.name)
            target_path.write_bytes(image.getvalue())
            saved_images.append(
                {
                    "name": image.name,
                    "path": target_path,
                }
            )

        st.session_state["pending_images"] = saved_images

    if st.session_state.get("pending_images"):
        pending_names = ", ".join(img["name"] for img in st.session_state["pending_images"])
        st.caption(f"Pending images: {pending_names}")
    else:
        st.caption("No images attached yet.")

    ### Upload PDFs

    st.markdown("---")
    st.caption("Upload PDF document(s) for the agent to reference.")
    pdf_files = st.file_uploader(
        "Upload PDF Inputs:",
        type=["pdf"],
        accept_multiple_files=True,
        key="sidebar_pdf_uploader",
    )

    if pdf_files:
        # Build lookup of existing PDFs with full metadata (not just path)
        existing_pdfs = {
            pdf_info["name"]: pdf_info
            for pdf_info in st.session_state.get("uploaded_pdfs", [])
            if Path(pdf_info["path"]).exists()
        }
        saved_pdfs = []
        for pdf in pdf_files:
            if pdf.name in existing_pdfs:
                # Preserve existing PDF entry with all metadata (file_id, attached_to_conversation)
                saved_pdfs.append(existing_pdfs[pdf.name])
                continue

            pdf_path = _next_available_path(PDF_UPLOADS_DIR, pdf.name)
            pdf_path.write_bytes(pdf.getvalue())
            saved_pdfs.append(
                {
                    "name": pdf.name,
                    "path": str(pdf_path),
                }
            )

        st.session_state["uploaded_pdfs"] = saved_pdfs

    if st.session_state.get("uploaded_pdfs"):
        pdf_names = ", ".join(pdf["name"] for pdf in st.session_state["uploaded_pdfs"])
        st.caption(f"📄 Saved PDFs: {pdf_names}")
        # Show upload status for each PDF
        for pdf in st.session_state["uploaded_pdfs"]:
            if "file_id" in pdf:
                st.caption(f"✅ {pdf['name']} ready (OpenAI file_id: {pdf['file_id'][:12]}...)")
    else:
        st.caption("No PDFs uploaded yet.")

    ### Save / Load Sessions

    st.markdown("---")
    st.caption("Save or load full chat sessions.")
    st.button(
        "💾 Save Current Session",
        on_click=lambda: save_current_session(
            SESSIONS_DIR, SESSION_FILENAME_PREFIX, SESSION_FILENAME_SUFFIX
        ),
        use_container_width=True,
    )

    session_files = sorted(
        SESSIONS_DIR.glob(f"{SESSION_FILENAME_PREFIX}*{SESSION_FILENAME_SUFFIX}"),
        reverse=True,
    )
    session_map = {
        _session_option_label(path, SESSION_FILENAME_PREFIX): path for path in session_files
    }

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
        on_click=load_session_from_path,
        args=(selected_path,),
        disabled=selected_path is None,
        use_container_width=True,
    )

    if not session_files:
        st.caption("No saved sessions yet.")

    current_messages = st.session_state.get("agent_state", {}).get("messages", [])
    if current_messages:
        session_html = build_session_html(
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


### File Browser

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
        show_upload_file=True,
    )
else:
    st.markdown(
        """
        <style>
        .block-container { max-width: 720px; }
        </style>
        """,
        unsafe_allow_html=True,
    )


st.title("🧬 TissueAgent")

if "state_queue" not in st.session_state:
    st.session_state["state_queue"] = Queue()
state_queue = st.session_state["state_queue"]

if "ui_event_queue" not in st.session_state:
    st.session_state["ui_event_queue"] = Queue()
register_ui_event_queue(st.session_state["ui_event_queue"])
event_queue = st.session_state["ui_event_queue"]


def _bind_retry(model):
    """Wrap a model with retry logic for rate-limit errors."""
    return model.with_retry(
        retry_if_exception_type=(openai.RateLimitError, anthropic.RateLimitError),
        stop_after_attempt=6,
    )


if "agent" not in st.session_state:
    graph = create_tissueagent_graph(state_queue, _bind_retry)
    st.session_state["agent"] = graph.compile()
agent = st.session_state["agent"]

if "agent_state" not in st.session_state:
    st.session_state["agent_state"] = {
        "messages": [],
        "replan_count": 0,
        "replan_history": [],
    }
    st.session_state["subagent_states"] = {}
    st.session_state["pending_subagent_states"] = deque()
    st.session_state["display_messages"] = []
    st.session_state["display_message_ids"] = set()
else:
    st.session_state.setdefault("subagent_states", {})
    st.session_state.setdefault("pending_subagent_states", deque())
    st.session_state.setdefault("display_messages", [])
    st.session_state.setdefault("display_message_ids", set())

_ensure_display_state()


### Chat UI

# Initial render (text-only copy)
conversation_placeholder = st.empty()
_render_conversation(conversation_placeholder, enable_debug)

# chat_input must be at the root (not inside columns/containers)
prompt = st.chat_input("Ask the agent:")

if prompt:
    content_parts = [{"type": "text", "text": prompt}]

    # Add image attachments
    for f in st.session_state.get("pending_images", []):
        content_parts.append(
            {  # type: ignore
                "type": "image_url",
                "image_url": {"url": _file_to_data_url(Path(f["path"]))},
            }
        )

    for pdf in st.session_state.get("uploaded_pdfs", []):
        if "file_id" not in pdf:
            try:
                file_id = _upload_pdf_to_openai(Path(pdf["path"]))
                pdf["file_id"] = file_id  # Cache the file_id
                pdf["attached_to_conversation"] = False  # Mark as not yet attached
            except Exception as e:
                st.error(f"Failed to upload PDF {pdf['name']}: {e}")
                continue

        if not pdf.get("attached_to_conversation", False):
            content_parts.append(
                {  # type: ignore
                    "type": "file",
                    "file": {"file_id": pdf["file_id"]},
                }
            )
            pdf["attached_to_conversation"] = True

    user_message = HumanMessage(content=content_parts)  # type: ignore
    record_user_message(user_message)
    log_message(user_message)

    st.session_state["agent_state"]["messages"].append(user_message)
    _drain_event_queue(event_queue, conversation_placeholder, enable_debug)

    st.session_state["pending_images"] = []

    rendered_prefix = len(st.session_state["agent_state"]["messages"])

    start_time = time.perf_counter()
    try:
        with st.spinner("TissueAgent is Thinking..."):
            st.session_state["agent_state"].setdefault("replan_count", 0)
            st.session_state["agent_state"].setdefault("replan_history", [])
            executor = ThreadPoolExecutor(max_workers=1)
            future = executor.submit(
                agent.invoke,
                st.session_state["agent_state"],
                {"recursion_limit": RECURSION_LIMIT},
            )
            try:
                while True:
                    try:
                        st.session_state["agent_state"] = future.result(timeout=0.1)
                        break
                    except TimeoutError:
                        _drain_event_queue(event_queue, conversation_placeholder, enable_debug)
                        _drain_subagent_queue(
                            state_queue,
                            st.session_state["pending_subagent_states"],
                        )
            finally:
                executor.shutdown(wait=False)
    except GraphRecursionError as e:
        st.error(f"Graph Recursion Error: {e}", icon="⚠️")
        logging.error("GraphRecursionError", exc_info=e)
    except (anthropic.BadRequestError, openai.BadRequestError) as e:
        st.error(f"Bad Request Error: {e}", icon="⚠️")
        logging.error("BadRequestError", exc_info=e)
    except Exception as e:
        st.exception(e)
        logging.error("Unexpected error", exc_info=e)
    else:
        elapsed_seconds = time.perf_counter() - start_time
        st.caption(f"SpatialAgent finished in {elapsed_seconds:.1f} s.")
    finally:
        _drain_event_queue(event_queue, conversation_placeholder, enable_debug)
        _drain_subagent_queue(
            state_queue,
            st.session_state["pending_subagent_states"],
        )

    new_messages = st.session_state["agent_state"]["messages"][rendered_prefix:]
    pending_state_queue = st.session_state["pending_subagent_states"]
    for message in new_messages:
        if not isinstance(message, ToolMessage):
            continue
        if message.name in ManagerToolNames:
            continue

        # Only linkage between tool output and sub-agent state should occur for transfer tools.
        if not str(message.name or "").endswith("_transfer_tool"):
            continue

        tool_id = message.id
        if tool_id in st.session_state["subagent_states"]:
            continue
        if getattr(message, "status", None) == "error":
            st.session_state["subagent_states"][tool_id] = (
                message.name,
                message.content,
            )
        elif not pending_state_queue:
            logging.error(f"No agent state found for following message {message}")
            st.session_state["subagent_states"][tool_id] = ("agent not found", None)
        else:
            agent_name, final_state = pending_state_queue.popleft()
            st.session_state["subagent_states"][tool_id] = (agent_name, final_state)

    _render_conversation(conversation_placeholder, enable_debug)
    if pending_state_queue:
        logging.warning("Unmatched subagent states remaining after render; clearing queue.")
        pending_state_queue.clear()
