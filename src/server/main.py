"""FastAPI application entry-point for TissueAgent.

Replaces the Streamlit app as the web server. Compiles the LangGraph agent
on startup, registers event queues, and mounts REST + WebSocket routes.

Run with::

    cd src && uvicorn server.main:app --reload --host 0.0.0.0 --port 8000
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

import anthropic
import openai
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from graph.graph import create_tissueagent_graph
from graph.graph_utils import register_ui_event_queue
from server.routes import chat, files, sessions
from server.session_manager import session
from server.utils import reset_data_directories


def _bind_retry(model):
    """Wrap a model with retry logic for rate-limit errors."""
    return model.with_retry(
        retry_if_exception_type=(openai.RateLimitError, anthropic.RateLimitError),
        stop_after_attempt=6,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: reset dirs, compile graph, register queues."""
    reset_data_directories()

    # Register the UI event queue so log_message() can push to it
    register_ui_event_queue(session.ui_event_queue)

    # Compile the agent graph
    graph = create_tissueagent_graph(session.state_queue, _bind_retry)
    session.agent = graph.compile()

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
app.include_router(chat.router)
app.include_router(files.router)
app.include_router(sessions.router)

# Serve React build in production (if dist/ exists)
_frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if _frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")
