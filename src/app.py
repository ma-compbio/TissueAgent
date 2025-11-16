import anthropic
import base64
import logging
import mimetypes
import openai
import queue
import shutil
import time
from datetime import datetime
from pathlib import Path
import streamlit as st
import streamlit_nested_layout  
from functools import partial
from html import escape
from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.errors import GraphRecursionError
from streamlit_file_browser import st_file_browser
from queue import Queue
from typing import Any

from app_utils import (
    render_conversation_history as util_render_conversation_history,
    save_current_session,
    load_session_from_path,
    _session_option_label,
    build_session_html,
    render_conversation_history_display,
)
from agents.manager_agent.tools import ManagerToolNames
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
        file = openai.files.create(
            file=open(pdf_path, "rb"),
            purpose="user_data"
        )
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


# One-turn attachments live here until the user sends a message
if "pending_images" not in st.session_state:
    st.session_state["pending_images"] = []

if "uploaded_pdfs" not in st.session_state:
    st.session_state["uploaded_pdfs"] = []

# Modal for image upload (opened by the ➕ button)
# image_modal = Modal("Add image(s)", key="image_modal", max_width=500)


if "show_file_browser" not in st.session_state:
    st.session_state.show_file_browser = False

with st.sidebar:

    ### Upload Dataset

    uploaded_files = st.file_uploader("Upload Dataset:", accept_multiple_files=True)

    ### File Browser / Trace

    col1, col2 = st.columns(2)
    with col1:
        def toggle_file_browser():
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
            saved_pdfs.append({
                "name": pdf.name,
                "path": str(pdf_path),
            })

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
        on_click=lambda: save_current_session(SESSIONS_DIR, SESSION_FILENAME_PREFIX, SESSION_FILENAME_SUFFIX),
        use_container_width=True,
    )

    session_files = sorted(
        SESSIONS_DIR.glob(f"{SESSION_FILENAME_PREFIX}*{SESSION_FILENAME_SUFFIX}"),
        reverse=True,
    )
    session_map = {_session_option_label(path, SESSION_FILENAME_PREFIX): path for path in session_files}

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
        show_upload_file=True
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

if "agent" not in st.session_state:
    bind_retry_fn = lambda model: model.with_retry(
        retry_if_exception_type=(openai.RateLimitError, anthropic.RateLimitError),
        stop_after_attempt = 6,
    )
    graph = create_tissueagent_graph(
        state_queue,
        bind_retry_fn
    )
    st.session_state["agent"] = graph.compile()
agent = st.session_state["agent"]

if "agent_state" not in st.session_state:
    st.session_state["agent_state"] = {
        "messages": [],
        "replan_count": 0,
        "replan_history": [],
    }
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

if prompt:
    content_parts = [{"type": "text", "text": prompt}]

    # Add image attachments
    for f in st.session_state.get("pending_images", []):
        content_parts.append({  # type: ignore
            "type": "image_url",
            "image_url": {"url": _file_to_data_url(Path(f["path"]))}
        })

    # Add PDF attachments (only on first message after upload to avoid size limit)
    for pdf in st.session_state.get("uploaded_pdfs", []):
        # Check if already uploaded (has file_id cached)
        if "file_id" not in pdf:
            try:
                file_id = _upload_pdf_to_openai(Path(pdf["path"]))
                pdf["file_id"] = file_id  # Cache the file_id
                pdf["attached_to_conversation"] = False  # Mark as not yet attached
            except Exception as e:
                st.error(f"Failed to upload PDF {pdf['name']}: {e}")
                continue

        # Only attach PDF to first message after upload to avoid 32MB cumulative limit
        if not pdf.get("attached_to_conversation", False):
            content_parts.append({  # type: ignore
                "type": "file",
                "file": {"file_id": pdf["file_id"]}
            })
            pdf["attached_to_conversation"] = True  # Mark as attached

    user_message = HumanMessage(content=content_parts)  # type: ignore
    log_message(user_message)

    st.session_state["agent_state"]["messages"].append(user_message)

    # Re-render the just-sent message in text-only mode
    render_conversation_history_display([user_message], {}, enable_debug)

    # clear one-shot attachments after sending
    st.session_state["pending_images"] = []

    rendered_prefix = len(st.session_state["agent_state"]["messages"])

    start_time = time.perf_counter()
    try:
        with st.spinner("SpatialAgent is Thinking..."):
            st.session_state["agent_state"].setdefault("replan_count", 0)
            st.session_state["agent_state"].setdefault("replan_history", [])
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
    else:
        elapsed_seconds = time.perf_counter() - start_time
        st.caption(f"SpatialAgent finished in {elapsed_seconds:.1f} s.")

    new_messages = st.session_state["agent_state"]["messages"][rendered_prefix:]
    for message in new_messages:
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
        st.exception(Exception("Display Error: This is likely caused by a concurrency or a parallelization issue."))
        logging.error("Display Error: This is likely caused by a concurrency or a parallelization issue.")
        clear_queue(state_queue)

    render_conversation_history_display(
        st.session_state["agent_state"]["messages"][rendered_prefix:],
        st.session_state["subagent_states"], enable_debug
    )
