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

import models as model_registry
from graph.graph import create_tissueagent_graph
from graph.graph_utils import register_ui_event_queue
from server.rate_limit import with_header_retry
from server.routes import (
    agents as agents_route,
    chat,
    files,
    models as models_route,
    plan,
    sessions,
)
from server.session_manager import session
from server.utils import reset_data_directories


def _bind_retry(model):
    """Wrap a model with header-driven rate-limit retry (strategy 1A).

    Honors provider Retry-After / retry-after-ms headers on 429s so the
    wait time tracks the actual rate-limit window instead of guessing
    via exponential backoff.
    """
    return with_header_retry(model, max_attempts=6)


def _compile_graph() -> None:
    """(Re)compile the agent graph using the currently-selected models.

    Compiles with an in-memory checkpointer so copilot mode can pause via
    ``interrupt_before`` and resume by invoking with ``input=None`` against
    the same ``thread_id``. Autopilot ignores both — it never passes
    ``interrupt_before`` and never resumes — so the checkpointer is
    effectively no-op overhead for autopilot runs.
    """
    graph = create_tissueagent_graph(session.state_queue, _bind_retry)
    session.agent = graph.compile(checkpointer=MemorySaver())
    session.model_revision = model_registry.get_revision()
    logging.info(
        "TissueAgent graph compiled with selection=%s (rev %d).",
        model_registry.get_selection(),
        session.model_revision,
    )


def ensure_graph_current() -> None:
    """Rebuild the graph if the model selection changed since the last compile."""
    if getattr(session, "model_revision", None) != model_registry.get_revision():
        _compile_graph()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: reset dirs, compile graph, register queues."""
    reset_data_directories()

    # Register the UI event queue so log_message() can push to it
    register_ui_event_queue(session.ui_event_queue)

    # Compile the agent graph
    _compile_graph()

    logging.info("TissueAgent graph compiled and ready.")
    yield


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

# Serve React build in production (if dist/ exists)
_frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if _frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")
