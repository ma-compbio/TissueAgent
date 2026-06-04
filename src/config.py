"""Global configuration constants and directory paths for TissueAgent.

Defines the canonical directory layout (workspace, dataset, uploads, PDFs,
notebooks, sessions, logs) and runtime settings such as the graph
recursion limit and log file location.
"""

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
DATASET_DIR = LIBRARY_DIR / "datasets"     # curated reference data
LIBRARY_FILES_DIR = LIBRARY_DIR / "files"  # persistent reference uploads

PROJECTS_DIR = DATA_DIR / "projects"
PROJECT_CHAT_FILENAME = "chat.json"
PROJECT_OUTPUTS_DIRNAME = "outputs"
PROJECT_ATTACHMENTS_DIRNAME = "attachments"
PROJECT_UPLOADS_DIRNAME = "uploads"

# Back-compat aliases. ``UPLOADS_DIR`` / ``PDF_UPLOADS_DIR`` historically
# held *chat attachments* (images and PDFs); those now live per-project
# under ``attachments/``. The aliases keep older import sites compiling
# while we migrate.
UPLOADS_DIR = LIBRARY_FILES_DIR        # legacy alias — prefer LIBRARY_FILES_DIR
PDF_UPLOADS_DIR = LIBRARY_FILES_DIR    # legacy alias — see above

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
