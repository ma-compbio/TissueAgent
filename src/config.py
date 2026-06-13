"""Global configuration constants and directory paths for TissueAgent.

Defines the canonical directory layout (workspace, dataset, uploads, PDFs, notebooks, sessions, logs) and runtime
settings such as the graph recursion limit and log file location.
"""

# TODO (dm): need to clean up this file. Most of these settings are either unnecessary or should be
# controlled through the UI

import os
from datetime import datetime
from zoneinfo import ZoneInfo

os.environ["TOKENIZERS_PARALLELISM"] = "false"

from pathlib import Path

ROOT = Path(__file__).parent.parent

# Top-level workspace. Everything the user or the agent reads/writes lives
# beneath this directory.
#
#   workspace/library/datasets/  — curated reference datasets. Persistent.
#   workspace/library/files/     — persistent reference files (PDFs the
#                                  user re-uses, screenshots they want
#                                  to keep). Survives across projects.
#   workspace/projects/<id>/
#       ├── chat.json            — saved conversation
#       ├── uploads/             — files the user dropped from the
#                                  sidebar into *this* project. Default
#                                  target for sidebar uploads.
#       ├── attachments/         — images / PDFs attached to *this*
#                                  project's chat (used for the
#                                  multimodal turn payloads).
#       └── outputs/             — agent's working directory for this
#                                  project. Everything the agent writes
#                                  lands here.
#   workspace/notebook/          — process-wide notebook scratch.
#   workspace/plan_scratch/      — in-flight plan store. Ephemeral.
#
# Legacy ``SESSIONS_DIR`` is preserved only for the one-shot migration
# at startup; everything else writes to ``PROJECTS_DIR``.
DATA_DIR = ROOT / "workspace"
NOTEBOOK_DIR = DATA_DIR / "notebook"

LIBRARY_DIR = DATA_DIR / "library"
DATASET_DIR = LIBRARY_DIR / "datasets"  # curated reference data
LIBRARY_FILES_DIR = LIBRARY_DIR / "files"  # persistent reference uploads

PROJECTS_DIR = DATA_DIR / "projects"
PROJECT_CHAT_FILENAME = "chat.json"
PROJECT_OUTPUTS_DIRNAME = "outputs"
PROJECT_ATTACHMENTS_DIRNAME = "attachments"
PROJECT_UPLOADS_DIRNAME = "uploads"


def active_project_root() -> Path:
    """Return the active project's root directory, or ``DATA_DIR`` if none.

    Resolution rule: ``session.project_id`` from the singleton when
    available; otherwise fall back to the global workspace. Imported
    lazily to avoid a circular import — config is the dependency floor
    that everyone else builds on, so it can't import session_manager
    at module-load time.
    """
    try:
        from server.session_manager import session  # local to break the cycle
    except Exception:
        return DATA_DIR
    pid = getattr(session, "project_id", None)
    if not pid:
        return DATA_DIR
    return PROJECTS_DIR / pid


def active_project_outputs() -> Path:
    """The directory the agent should write outputs into by default.

    Equals ``projects/<active>/outputs/`` when a project is active, or
    ``DATA_DIR`` as a fallback so writes never crash when no project
    exists yet (e.g. during agent self-tests). Caller is responsible
    for actually creating the directory; agents should not be in the
    business of mkdir-ing their own workspace.
    """
    pid = None
    try:
        from server.session_manager import session

        pid = getattr(session, "project_id", None)
    except Exception:
        pass
    if not pid:
        return DATA_DIR
    return PROJECTS_DIR / pid / PROJECT_OUTPUTS_DIRNAME


# Pre-project scratch: where uploads land *before* a project is minted.
# Contents are migrated into projects/<id>/uploads or .../attachments on
# the first user prompt, and wiped on session reset / new-project. The
# scratch directory is intentionally not surfaced in the projects list;
# it has no chat.json.
SCRATCH_DIR = DATA_DIR / "scratch"
SCRATCH_UPLOADS_DIR = SCRATCH_DIR / "uploads"
SCRATCH_ATTACHMENTS_DIR = SCRATCH_DIR / "attachments"

# Back-compat aliases. ``UPLOADS_DIR`` / ``PDF_UPLOADS_DIR`` historically
# held *chat attachments* (images and PDFs); those now live per-project
# under ``attachments/``. The aliases keep older import sites compiling
# while we migrate.
UPLOADS_DIR = LIBRARY_FILES_DIR  # legacy alias — prefer LIBRARY_FILES_DIR
PDF_UPLOADS_DIR = LIBRARY_FILES_DIR  # legacy alias — see above

# Ephemeral process-wide scratch for the currently-running plan. The
# plan_store needs *some* stable on-disk home at import time, before any
# project_id exists; we copy a snapshot into the project on save.
PLAN_SCRATCH_DIR = DATA_DIR / "plan_scratch"

# Legacy on-disk location for saved sessions. Used by the startup
# migration only — do not reference for new writes.
LEGACY_SESSIONS_DIR = ROOT / "sessions"
SESSIONS_DIR = LEGACY_SESSIONS_DIR  # back-compat alias for plan_store etc.
RECURSION_LIMIT = 100
LOG_TO_TERMINAL = True
LOG_TO_FILE = (
    ROOT
    / "logs"
    / (
        datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d_%H-%M-%S")
        + "_tissueagent.log"
    )
)

from models import model_ctor_for_role  # noqa: E402  (import after dotenv/env setup)

# Resolves the currently-selected orchestration model at call time so that
# updating the selection via the /api/models route takes effect on the
# next graph rebuild.
DefaultModelCtor = model_ctor_for_role("orchestration")

# ---------------------------------------------------------------------------
# Docker sandbox (Jupyter Kernel Gateway)
# ---------------------------------------------------------------------------
KERNEL_GATEWAY_HOST = "127.0.0.1"
KERNEL_GATEWAY_PORT = 8888
KERNEL_GATEWAY_URL = f"http://{KERNEL_GATEWAY_HOST}:{KERNEL_GATEWAY_PORT}"
DOCKER_IMAGE_NAME = "tissueagent-sandbox"
DOCKER_CONTAINER_NAME = "tissueagent-sandbox"
CONTAINER_DATA_DIR = "/workspace"
CONTAINER_NOTEBOOK_DIR = "/workspace/notebook"

MAX_OUTPUT_CHARS = 3000
MAX_REPLANS = 2
MAX_RECRUITER_RETRIES = 2
MAX_PLANNER_RETRIES = 2
