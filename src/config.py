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

# Top-level workspace. ``DATA_DIR`` is the agent-visible filesystem —
# everything inside it is reachable through agent tools and the Jupyter
# kernel. Anything that should NOT be visible to agents lives outside.
#
#   workspace/library/datasets/      — curated reference datasets.
#   workspace/library/files/         — persistent reference files.
#   workspace/project/               — the ONLY active project. Always
#       ├── .chat.json                 exists (empty shell pre-mint).
#       ├── .project_id                Kernel CWD is the workspace root
#       ├── uploads/                   (/workspace), so paths line up with
#       └── outputs/                   the workspace file tools.
#   workspace/notebook/              — process-wide notebook scratch.
#
# Parked projects and the in-flight plan store live OUTSIDE workspace
# (sibling of it), so agents can't reach them at all:
#   projects/<id>/                   — parked, ready to be activated.
#   plan_scratch/                    — per-process plan markdown store.
#
# Legacy ``SESSIONS_DIR`` is preserved only for the one-shot migration
# at startup; everything else writes to ``PROJECTS_DIR``.
DATA_DIR = ROOT / "workspace"
NOTEBOOK_DIR = DATA_DIR / "notebook"

LIBRARY_DIR = DATA_DIR / "library"
DATASET_DIR = LIBRARY_DIR / "datasets"  # curated reference data
LIBRARY_FILES_DIR = LIBRARY_DIR / "files"  # persistent reference uploads

# Parked-project storage lives OUTSIDE workspace so the agent has no
# path into it through DATA_DIR. Switching the active project is a
# rename between ACTIVE_PROJECT_DIR and PROJECTS_DIR/<id>.
PROJECTS_DIR = ROOT / "projects"
PROJECT_CHAT_FILENAME = ".chat.json"
PROJECT_OUTPUTS_DIRNAME = "outputs"
PROJECT_UPLOADS_DIRNAME = "uploads"
PROJECT_SKILLS_DIRNAME = "skills"

# The active project's stable on-disk home. Always exists (empty shell
# when no project is active). Kernel cwd is unconditionally
# ACTIVE_PROJECT_DIR / outputs.
ACTIVE_PROJECT_DIR = DATA_DIR / "project"
ACTIVE_PROJECT_ID_FILE = ".project_id"


def active_project_root() -> Path:
    """The active project's root — always ACTIVE_PROJECT_DIR.

    Independent of session state: the active project's identity is
    encoded by what lives at this path on disk (with its ``.project_id``
    file), not by a session variable.
    """
    return ACTIVE_PROJECT_DIR


def active_project_outputs() -> Path:
    """The directory the agent writes outputs into by default."""
    return ACTIVE_PROJECT_DIR / PROJECT_OUTPUTS_DIRNAME


def active_project_skills() -> Path:
    """The read-only per-plan snapshot of recruiter-assigned skill folders."""
    return ACTIVE_PROJECT_DIR / PROJECT_SKILLS_DIRNAME


# Back-compat aliases. ``UPLOADS_DIR`` / ``PDF_UPLOADS_DIR`` historically
# held *chat attachments* (images and PDFs); those now live per-project
# under ``uploads/``. The aliases keep older import sites compiling
# while we migrate.
UPLOADS_DIR = LIBRARY_FILES_DIR  # legacy alias — prefer LIBRARY_FILES_DIR
PDF_UPLOADS_DIR = LIBRARY_FILES_DIR  # legacy alias — see above

# Ephemeral process-wide scratch for the currently-running plan. Lives
# outside the agent-visible workspace because nothing here is for the
# agent to read; the autosave snapshots its markdown into the project's
# .chat.json (plan_markdown field).
PLAN_SCRATCH_DIR = ROOT / "plan_scratch"

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
CONTAINER_SKILLS_ROOT = f"{CONTAINER_DATA_DIR}/project/{PROJECT_SKILLS_DIRNAME}"

MAX_OUTPUT_CHARS = 3000
MAX_REPLANS = 2
MAX_RECRUITER_RETRIES = 2
MAX_PLANNER_RETRIES = 2

# Retry budgets for the three execution-control loops (smaller than the global
# RECURSION_LIMIT so a stuck loop fails fast instead of burning the whole graph
# budget). See graph.evaluator (replan), manager_agent.tools (retry_step), and
# coding_agent.model (executor inner loop).
#
# ``MAX_EXECUTOR_RETRIES`` is the number of *consecutive* failed code
# executions (Python/R traceback, timeout, or unreachable kernel) a coding
# sub-agent may accumulate within a single step before the code tools refuse
# to run more code and tell it to stop and summarize. A successful execution
# resets the counter. See coding_agent.model.
MAX_EXECUTOR_RETRIES = 15
# Hard LangGraph backstop for a coding sub-agent's inner loop — well below the
# global RECURSION_LIMIT so a runaway loop fails fast, but high enough for a
# legitimately multi-tool step (search docs -> run -> inspect -> rerun) plus
# the retry budget above. Each tool call ≈ two graph turns.
EXECUTOR_RECURSION_LIMIT = 60
# ``MAX_STEP_RETRIES`` is how many times the manager may ``retry_step`` a single
# plan step before the retry is refused and it must advance or replan.
MAX_STEP_RETRIES = 3
