"""FastAPI application entry-point for TissueAgent.

Replaces the Streamlit app as the web server. Compiles the LangGraph agent
on startup, registers event queues, and mounts REST + WebSocket routes.

Run with::

    cd src && uvicorn server.main:app --reload --host 0.0.0.0 --port 8000
"""

import matplotlib
matplotlib.use("Agg")

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from langgraph.checkpoint.memory import MemorySaver

import agent_settings
from agents.agent_registry.coding_agent.sandbox import ContainerManager, KernelClient
import models as model_registry
from graph.graph import create_tissueagent_graph
from graph.ui_events import register_ui_event_queue
from server.rate_limit import with_header_retry
from server.routes import (
    agents as agents_route,
    chat,
    files,
    models as models_route,
    plan,
    sessions,
    settings as settings_route,
)
from server.session_manager import session
from server.utils import (
    migrate_legacy_library_layout,
    migrate_legacy_sessions,
    reset_data_directories,
)


def _bind_retry(model):
    """Wrap a model with header-driven rate-limit retry (strategy 1A).

    Honors provider Retry-After / retry-after-ms headers on 429s so the wait time tracks the actual rate-limit window
    instead of guessing via exponential backoff.
    """
    return with_header_retry(model, max_attempts=6)


_kernel_client: KernelClient | None = None
_settings_revision: int | None = None


def _compile_graph(kernel_client: KernelClient) -> None:
    """(Re)compile the agent graph using the currently-selected models.

    Compiles with an in-memory checkpointer so copilot mode can pause via ``interrupt_before`` and resume by invoking
    with ``input=None`` against the same ``thread_id``. Autopilot ignores both — it never passes ``interrupt_before``
    and never resumes — so the checkpointer is effectively no-op overhead for autopilot runs.
    """
    graph = create_tissueagent_graph(
        session.state_queue, _bind_retry, kernel_client=kernel_client
    )
    session.agent = graph.compile(checkpointer=MemorySaver())
    session.model_revision = model_registry.get_revision()
    global _settings_revision
    _settings_revision = agent_settings.get_revision()
    logging.info(
        "TissueAgent graph compiled with selection=%s (rev %d), settings=%s.",
        model_registry.get_selection(),
        session.model_revision,
        agent_settings.get_settings(),
    )


def ensure_graph_current() -> None:
    """Rebuild the graph if the model selection or agent settings changed."""
    if (getattr(session, "model_revision", None) != model_registry.get_revision()
            or _settings_revision != agent_settings.get_revision()):
        assert _kernel_client is not None, "kernel_client not initialized"
        _compile_graph(_kernel_client)


def set_kernel_workspace(path: Path) -> None:
    """Point the running kernel client at *path* as the active workspace.

    Called by the chat handler when a project is minted or loaded so
    every Python/R execution lands inside ``projects/<id>/outputs/``.
    No-op when the kernel client isn't initialized yet (e.g. very early
    in startup), to keep the boot path simple.
    """
    if _kernel_client is None:
        return
    _kernel_client.set_workspace(path)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: reset dirs, optionally start sandbox, compile graph, register queues."""
    reset_data_directories()
    migrate_legacy_sessions()
    migrate_legacy_library_layout()

    # Start the Docker sandbox only when sandbox_enabled is set at startup.
    container_mgr: ContainerManager | None = None
    if agent_settings.get_sandbox_enabled():
        container_mgr = ContainerManager()
        container_mgr.ensure_running()
        logging.info("Docker sandbox started.")
    else:
        logging.info(
            "Docker sandbox disabled at startup — expecting a local Jupyter "
            "Kernel Gateway at %s.", "KERNEL_GATEWAY_URL"
        )

    kernel_client = KernelClient()

    # Register the UI event queue so log_message() can push to it
    register_ui_event_queue(session.ui_event_queue)

    # Compile the agent graph
    global _kernel_client
    _kernel_client = kernel_client
    _compile_graph(kernel_client)

    logging.info("TissueAgent graph compiled and ready.")
    yield

    # Shutdown: stop the sandbox container if it was started
    if container_mgr is not None:
        container_mgr.stop()


app = FastAPI(
    title="TissueAgent",
    description="AI agent for spatial transcriptomics research",
    lifespan=lifespan,
)

# CORS for React dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routes
app.include_router(agents_route.router)
app.include_router(chat.router)
app.include_router(files.router)
app.include_router(models_route.router)
app.include_router(plan.router)
app.include_router(sessions.router)
app.include_router(settings_route.router)

# Serve React build in production (if dist/ exists)
_frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if _frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")
