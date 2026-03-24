"""Global configuration constants and directory paths for TissueAgent.

Defines the canonical directory layout (data, dataset, uploads, PDFs,
notebooks, sessions, logs) and runtime settings such as the graph
recursion limit and log file location.
"""

import os
from datetime import datetime
from functools import partial
from zoneinfo import ZoneInfo

from langchain_openai import ChatOpenAI

os.environ["TOKENIZERS_PARALLELISM"] = "false"

from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
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

DefaultModelCtor = partial(ChatOpenAI, model="gpt-5", reasoning_effort="high")
