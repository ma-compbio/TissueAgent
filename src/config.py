import os
from datetime import datetime
from zoneinfo import ZoneInfo

os.environ["TOKENIZERS_PARALLELISM"] = "false"

from pathlib import Path

ROOT             = Path(__file__).parent.parent
DATA_DIR         = ROOT / "data"
NOTEBOOK_DIR     = DATA_DIR / "notebook"
DATASET_DIR      = DATA_DIR / "dataset"
UPLOADS_DIR      = DATA_DIR / "uploads"
RECURSION_LIMIT  = 50
LOG_TO_TERMINAL  = True
LOG_TO_FILE      = ROOT / "logs" / (datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d_%H-%M-%S") + "_tissueagent.log")