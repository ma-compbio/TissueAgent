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

# Root of the process's *mutable state* — workspace/, projects/, plan_scratch/,
# sessions/ and nothing else (code and knowledge assets resolve from the package,
# not from here, so relocating this cannot break imports).
#
# ``TISSUEAGENT_STATE_ROOT`` exists so several agent processes can run at once.
# They would otherwise share one workspace/: the benchmark harness wipes
# workspace/library/datasets/ before every run, so two concurrent runs delete
# each other's inputs. Give each worker its own state root and they are
# independent. Unset — the normal case — this is the repo root, as before.
ROOT = Path(os.environ.get("TISSUEAGENT_STATE_ROOT") or Path(__file__).parent.parent)

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
# Figure reproduction routinely needs several inspect/render/compare passes. Keep
# the global budget finite, but make it large enough for that normal workflow and
# configurable for deployments with tighter latency or cost budgets.
# TEMPORARY (optimizer CCC benchmark, 2026-09): lowered 200 -> 100. Across the six
# archived CCC ensemble sessions the main graph peaked at 59 messages, so 100
# keeps ~1.7x headroom while failing runaway runs at half the old cost. Restore
# to 200 for figure-reproduction workloads.
RECURSION_LIMIT = int(os.environ.get("TISSUEAGENT_RECURSION_LIMIT", "100"))
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
# Overridable for the same reason as TISSUEAGENT_STATE_ROOT: concurrent workers
# each need their own gateway, and the second one to start would otherwise fail
# to bind 8888 — or, worse, silently attach to the first worker's kernels and
# execute its code in the wrong workspace. One port per worker.
KERNEL_GATEWAY_PORT = int(os.environ.get("TISSUEAGENT_GATEWAY_PORT") or 8888)
KERNEL_GATEWAY_URL = f"http://{KERNEL_GATEWAY_HOST}:{KERNEL_GATEWAY_PORT}"
DOCKER_IMAGE_NAME = "tissueagent-sandbox"
DOCKER_CONTAINER_NAME = "tissueagent-sandbox"
CONTAINER_DATA_DIR = "/workspace"
CONTAINER_NOTEBOOK_DIR = "/workspace/notebook"
CONTAINER_SKILLS_ROOT = f"{CONTAINER_DATA_DIR}/project/{PROJECT_SKILLS_DIRNAME}"

# Workspace-relative form of the same location, and the one to hand to agents.
# The sandbox bind-mounts DATA_DIR at CONTAINER_DATA_DIR and the kernel cwd is
# seeded to the workspace root, so this resolves with the sandbox on or off;
# the absolute container form above does not (the file tools reject absolute
# paths, and it is meaningless to a local kernel).
PROJECT_SKILLS_REL = f"project/{PROJECT_SKILLS_DIRNAME}"

MAX_OUTPUT_CHARS = 3000
# TEMPORARY (optimizer CCC benchmark, 2026-09): 1 -> 0, i.e. NO replans. The
# evaluator blocks when new_count > MAX_REPLANS (graph.py), so 0 rewrites the
# first REPLAN verdict to REPORT: a failed round must surface as a failure the
# optimizer can learn from, not be papered over by a replan. Restore to 2 for
# normal use (previous temporary value was 1 — see 2026-07 note in git history).
MAX_REPLANS = 0

# TEMPORARY (CCC benchmark, 2026-07): the coding agent burned its whole turn
# budget on search_documentation / runtime introspection (e.g. inspect.getsource
# on liana's AggregateClass instance -> TypeError) instead of executing. While
# disabled, the required API usage lives directly in the CCC skill files.
# Set back to True to fully restore the tool AND its prompt guidance in one flip:
# it re-registers the tool (coding_agent/model.py) and un-strips the
# <!--DOCSEARCH--> blocks in the coding-agent prompts (coding_agent/prompt.py).
DOC_SEARCH_ENABLED = False
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
# ``MAX_EXECUTOR_STEP_ERRORS`` is the same budget counted *per step* and NOT
# reset by a success. The consecutive counter above is blind to the failure
# mode that actually kills runs: a debug-thrash loop (execute -> fail -> glob ->
# read -> execute -> fail ...) never accumulates 15 failures in a row, because
# every interleaved success zeroes it. The loop then runs until LangGraph's
# recursion_limit aborts the whole step, losing the sub-agent's context and the
# partial work with it. This ceiling ends such a step deliberately instead, so
# it hands a summary back to the manager. Set well above MAX_EXECUTOR_RETRIES:
# a step legitimately debugging its way to a result must not trip it.
MAX_EXECUTOR_STEP_ERRORS = 25
# Hard LangGraph backstop for a coding sub-agent's inner loop — well below the
# global RECURSION_LIMIT so a runaway loop fails fast, but high enough for a
# legitimately multi-tool step (inspect -> run -> inspect -> rerun) plus the
# retry budget above. Each tool call ≈ two graph turns.
# Figure-reproduction steps need repeated inspection, rendering, and fidelity
# comparison, so their inner agent budget is deliberately independent from the
# top-level orchestration budget. Override it only when a deployment needs a
# stricter per-step cost ceiling.
# TEMPORARY (optimizer CCC benchmark, 2026-09): lowered 160 -> 140. The worst
# single sub-agent invocation across the archived CCC sessions used 124
# messages (a successful debug-heavy step); 140 keeps that step viable while
# trimming the runaway ceiling. Restore to 160 for normal use.
EXECUTOR_RECURSION_LIMIT = int(os.environ.get("TISSUEAGENT_EXECUTOR_RECURSION_LIMIT", "140"))
# ``MAX_STEP_RETRIES`` is how many times the manager may ``retry_step`` a single
# plan step before the retry is refused and it must advance or replan.
MAX_STEP_RETRIES = 3

# ---------------------------------------------------------------------------
# Graph step-budget reserves
# ---------------------------------------------------------------------------
# ``RECURSION_LIMIT`` is a budget of LangGraph *super-steps* shared by every node
# in the main graph, and each agent turn that calls a tool spends two of them
# (agent node -> tool node -> back). Nothing used to reserve any of it for the
# tail of the pipeline, so an agent that kept calling tools would spend the last
# super-step mid-loop and the run died with ``GraphRecursionError``: no
# evaluation, no report, no final answer, even when the deliverable was already
# on disk. Observed on both BioFigBench UnitedNet fig_7_c runs (2026-07-28) — one
# spent 49 of its 52 manager turns paging the same 1219-line script with ``read``.
#
# The reserves below are read against LangGraph's managed ``remaining_steps``
# value by the budget guards in ``graph.graph``. They are relative to whatever
# ``recursion_limit`` a caller passes, so raising the limit does not invalidate
# them.
#
# Keep enough for the evaluator to assess (one turn, plus a couple of tool
# round-trips) and the reporter to write the report.
MANAGER_STEP_RESERVE = 14
# Keep enough for the reporter alone: its own turn plus a tool round-trip or two.
EVALUATOR_STEP_RESERVE = 6
# The reporter is the last node, so it only needs to reserve its own final turn.
REPORTER_STEP_RESERVE = 3
# A replan restarts the whole planner -> recruiter -> manager -> evaluator cycle.
# Below this many remaining super-steps a REPLAN verdict cannot possibly finish,
# so the evaluator reports on what exists instead of burning the rest of the
# budget re-planning. Roughly: planner + recruiter (~6) + a couple of dispatched
# steps (~12) + the evaluator/reporter tail (``MANAGER_STEP_RESERVE``).
REPLAN_STEP_COST = 32
