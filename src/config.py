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
DATA_DIR = ROOT / "workspace"
NOTEBOOK_DIR = DATA_DIR / "notebook"
DATASET_DIR = DATA_DIR / "dataset"
UPLOADS_DIR = DATA_DIR / "uploads"
PDF_UPLOADS_DIR = DATA_DIR / "pdfs"
SESSIONS_DIR = ROOT / "sessions"
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
