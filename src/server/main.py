"""FastAPI application entry-point for TissueAgent.

Compiles the LangGraph agent on startup, registers event queues, and mounts REST + WebSocket routes.

Run from the repo root with::

    python -m uvicorn server.main:app --reload --reload-dir src --host 0.0.0.0 --port 8000

``python -m`` (from the repo root) puts the repo root on ``sys.path`` so the top-level
``knowledge`` package imports; the editable install already exposes ``src/`` for
``server``/``agents``/``graph``. Do NOT use ``--app-dir src`` — it replaces the repo
root on the path rather than adding to it, breaking ``import knowledge``.

``--reload-dir src`` is important: it scopes the autoreloader to application code only.
Without it uvicorn watches the whole repo, and since ``*.py`` is the only thing the
reloader tracks, every agent run that materializes a folder skill shipping a bundled
script (e.g. ``knowledge/skills/ccc-aggregate/scripts/ccc_aggregate.py`` gets copied
into ``workspace/project/skills/``) — or that writes any ``.py`` under ``workspace/`` —
restarts the backend mid-run.
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
import models as model_registry
from config import ACTIVE_PROJECT_DIR, KERNEL_GATEWAY_URL, PROJECT_CHAT_FILENAME
from agents.agent_registry.coding_agent_cache.sandbox import (
    ContainerManager,
    KernelClient,
    LocalKernelGateway,
)
from graph.graph import create_tissueagent_graph
from graph.ui_events import register_ui_event_queue
from server.rate_limit import with_header_retry
from server.routes import (
    agents as agents_route,
)
from server.routes import (
    chat,
    files,
    plan,
    sessions,
    skills,
)
from server.routes import (
    models as models_route,
)
from server.routes import (
    settings as settings_route,
)
from server.session_manager import session
from server.utils import (
    migrate_chat_json_to_dotfile,
    migrate_legacy_library_layout,
    migrate_legacy_sessions,
    migrate_plan_scratch_out_of_workspace,
    migrate_projects_out_of_workspace,
    migrate_scratch_into_active_project,
    recover_active_project,
    rehydrate_session_from_chat,
    reset_data_directories,
)


def _bind_retry(model):
    """Wrap a model with header-driven rate-limit retry.

    Honors provider Retry-After / retry-after-ms headers on 429s so the wait time tracks the actual
    rate-limit window instead of guessing via exponential backoff.
    """
    return with_header_retry(model, max_attempts=6)


_kernel_client: KernelClient | None = None
_settings_revision: int | None = None


def _compile_graph(
    kernel_client: KernelClient,
    domain_agents: list | None = None,
) -> None:
    """(Re)compile the agent graph using the currently-selected models.

    Compiles with an in-memory checkpointer so copilot mode can pause via ``interrupt_before`` and
    resume by invoking with ``input=None`` against the same ``thread_id``. Autopilot ignores both -
    it never passes ``interrupt_before`` and never resumes - so the checkpointer is effectively no-op overhead for autopilot runs.

    Args:
        kernel_client: Shared Jupyter kernel client for the coding agent.
        domain_agents: Optional recruitable-agent list override (benchmark ablations).
    """
    graph = create_tissueagent_graph(
        session.state_queue,
        _bind_retry,
        domain_agents=domain_agents,
        kernel_client=kernel_client,
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
    if (
        getattr(session, "model_revision", None) != model_registry.get_revision()
        or _settings_revision != agent_settings.get_revision()
    ):
        assert _kernel_client is not None, "kernel_client not initialized"
        _compile_graph(_kernel_client)


def set_kernel_workspace(path: Path, *, force_restart: bool = False) -> None:
    """Point the running kernel client at *path* as the active workspace.

    Called by the chat handler when a project is minted/loaded and by the
    active-project switch protocol. Pass ``force_restart=True`` when the
    on-disk contents of *path* changed but the path string itself didn't
    (e.g. the active-project rename swap — kernel cwd remains the workspace
    root, ``/workspace``, across switches).

    No-op when the kernel client isn't initialized yet (e.g. very early
    in startup), to keep the boot path simple.
    """
    if _kernel_client is None:
        return
    _kernel_client.set_workspace(path, force_restart=force_restart)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: reset dirs, optionally start sandbox, compile graph, register queues."""
    reset_data_directories()
    migrate_legacy_sessions()
    migrate_legacy_library_layout()
    migrate_projects_out_of_workspace()
    migrate_plan_scratch_out_of_workspace()
    migrate_chat_json_to_dotfile()
    migrate_scratch_into_active_project()
    recovered_pid = recover_active_project()
    if recovered_pid is not None:
        session.project_id = recovered_pid
        # Rehydrate the conversation + traces from the active project's chat
        # file so a page refresh after a server restart replays history
        # instead of showing a blank view. Best-effort: a missing/corrupt
        # chat file must not block startup.
        chat_path = ACTIVE_PROJECT_DIR / PROJECT_CHAT_FILENAME
        if chat_path.exists():
            try:
                rehydrate_session_from_chat(chat_path)
            except Exception as e:
                logging.warning(
                    "Failed to rehydrate active project %s at startup: %s",
                    recovered_pid,
                    e,
                )

    # Provide a code-execution backend. With the Docker sandbox enabled we
    # start (or reuse) the container; otherwise we auto-start a local Jupyter
    # Kernel Gateway so code execution works without a manual third process.
    # Both managers expose ``.stop()`` for shutdown. Best-effort: a failure
    # here must not prevent the server from booting — the coding agent will
    # surface a clear KernelUnavailableError on first use instead.
    code_backend: ContainerManager | LocalKernelGateway | None = None
    try:
        if agent_settings.get_sandbox_enabled():
            code_backend = ContainerManager()
            code_backend.ensure_running()
            logging.info("Docker sandbox started.")
        else:
            code_backend = LocalKernelGateway()
            code_backend.ensure_running()
            logging.info("Local Kernel Gateway ready at %s.", KERNEL_GATEWAY_URL)
    except Exception as e:
        code_backend = None
        logging.warning(
            "Could not start a code backend at startup (%s). Code execution "
            "will fail until a Kernel Gateway is available at %s.",
            e,
            KERNEL_GATEWAY_URL,
        )

    kernel_client = KernelClient()

    # Register the UI event queue so emit_message() can push to it
    register_ui_event_queue(session.ui_event_queue)

    # Compile the agent graph
    global _kernel_client
    _kernel_client = kernel_client
    _compile_graph(kernel_client)

    logging.info("TissueAgent graph compiled and ready.")
    yield

    # Shutdown: stop whichever code backend we started.
    if code_backend is not None:
        code_backend.stop()


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
app.include_router(skills.router)

# Serve React build in production (if dist/ exists)
_frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if _frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")
