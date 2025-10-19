import anthropic
import logging
import openai
import os
import shutil
import streamlit as st
import streamlit_nested_layout  

from functools import partial
from copy import deepcopy
from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.errors import GraphRecursionError
from pydantic import SecretStr
from streamlit_file_browser import st_file_browser
from streamlit_modal import Modal
from queue import Queue
import queue
import base64
import mimetypes

from app_utils import LLMOptions, render_conversation_history as util_render_conversation_history
from agents.manager_agent.tools import ManagerToolNames
from agents.agent_utils import PythonREPLObj
from graph.graph import create_tissueagent_graph
from graph.graph_utils import log_message
from config import DATA_DIR, RECURSION_LIMIT


def clear_queue(q: queue.Queue):
    """Remove everything from a Queue in a thread-safe way."""
    try:
        while True:
            q.get_nowait()
    except queue.Empty:
        pass


def _file_to_data_url(uploaded_file) -> str:
    """Convert a Streamlit UploadedFile to a Base64 data URL for multimodal chat."""
    mime, _ = mimetypes.guess_type(uploaded_file.name)
    if mime is None:
        mime = "application/octet-stream"
    b64 = base64.b64encode(uploaded_file.getvalue()).decode("utf-8")
    return f"data:{mime};base64,{b64}"


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


def render_conversation_history_display(all_messages, subagent_states):
    # Call your existing renderer but with text-only copies so the UI doesn't show huge data URLs
    return util_render_conversation_history(
        _strip_images_for_display(all_messages),
        subagent_states
    )


# One-turn attachments live here until the user sends a message
if "pending_images" not in st.session_state:
    st.session_state["pending_images"] = []

# Modal for image upload (opened by the ➕ button)
image_modal = Modal("Add image(s)", key="image_modal", max_width=500)


if "api_keys" not in st.session_state:
    st.session_state["api_keys"] = {
        "llm": "",
        "openai": "",
        "serp": "",
        "email": "",
    }

file_browser_modal = Modal("File Browser", key="file_browser_modal")
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


# ╔═══════════════════════╗
# ║ File Browser          ║
# ╚═══════════════════════╝

if "processed_files" not in st.session_state:
    shutil.rmtree(DATA_DIR, ignore_errors=True)
    st.session_state["processed_files"] = set()
    DATA_DIR.mkdir(parents=True, exist_ok=True)

if uploaded_files:
    for uploaded_file in uploaded_files:
        if uploaded_file.name not in st.session_state["processed_files"]:
            st.session_state["processed_files"].add(uploaded_file.name)
            file_path = DATA_DIR / uploaded_file.name
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
    _ = st_file_browser(
        DATA_DIR,
        key="file_browser_modal",
        show_preview=True,
        show_delete_file=True,
        show_download_file=True,
        show_upload_file=True
    )
    st.stop()
else:
    st.markdown(
        """
        <style>
        .block-container { max-width: 720px; }

        /* Pin the + button near the bottom-right corner of the chat input */
        .floating-plus {
        position: fixed;
        bottom: 88px; /* tweak to sit nicely next to your chat box */
        /* Align to the right edge of the centered 720px container */
        right: calc((100vw - 720px)/2 + 8px);
        z-index: 1000;
        }
        .floating-plus .stButton > button {
        border-radius: 999px;
        padding: 0.35rem 0.55rem;
        line-height: 1;
        font-size: 1.1rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.15);
        }

        /* On narrow screens, just stick to the viewport edge */
        @media (max-width: 760px) {
        .floating-plus {
            right: 16px;
            bottom: 72px; /* a bit tighter on phones */
        }
        }
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
    st.session_state["subagent_states"]
)

# Floating plus button (NOT wrapping chat_input)
plus_placeholder = st.empty()
with plus_placeholder.container():
    st.markdown('<div class="floating-plus">', unsafe_allow_html=True)
    if st.button("➕", key="attach_btn", help="Attach image(s)"):
        image_modal.open()
    st.markdown('</div>', unsafe_allow_html=True)

# Show the modal when open; pick images and keep them for the next send
if image_modal.is_open():
    with image_modal.container():
        images = st.file_uploader(
            "Select image(s) to attach",
            type=["png", "jpg", "jpeg", "webp", "gif"],
            accept_multiple_files=True,
            key="img_files"
        )
        if images is not None:
            st.session_state["pending_images"] = images

        st.caption("Images will be sent with your next message.")

        # ⬅️ No on_click callback here
        done = st.button("Done")
        if done:
            image_modal.close()   # fine to call here
            st.rerun()            # top-level rerun is OK; not inside a callback


# chat_input must be at the root (not inside columns/containers)
prompt = st.chat_input("Ask the agent:")

# Build and send a multimodal HumanMessage when user submits text
if prompt:
    content_parts = [{"type": "text", "text": prompt}]

    # attach any pending images
    for f in st.session_state.get("pending_images", []):
        content_parts.append({
            "type": "image_url",
            "image_url": {"url": _file_to_data_url(f)}
        })

    user_message = HumanMessage(content=content_parts)
    PythonREPLObj.add_text(f"[User]: {prompt}")
    log_message(user_message)

    st.session_state["agent_state"]["messages"].append(user_message)

    # Re-render the just-sent message in text-only mode
    render_conversation_history_display([user_message], {})

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
        st.session_state["subagent_states"]
    )
