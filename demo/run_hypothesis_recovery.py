"""Standalone driver for the evidence-grounded hypothesis-recovery prototype.

Bypasses the full TissueAgent graph and invokes the Hypothesis Agent directly,
so we can iterate on the agent's three-phase prompt without the Manager /
Recruiter / Evaluator round-trip. Once the prompt is stable, the same setup
will plug into the full pipeline.

Usage:
    cd demo/
    python run_hypothesis_recovery.py --dataset lohoff
    python run_hypothesis_recovery.py --dataset farah
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from queue import Queue

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))
sys.path.insert(0, str(_REPO_ROOT / "demo"))

# Load secrets from repo-root .env (gitignored) before any module that reads
# environment variables.
try:
    from dotenv import load_dotenv

    load_dotenv(_REPO_ROOT / ".env")
except ImportError:
    pass

# These imports MUST come after the sys.path mutations above.
from config import DATA_DIR  # noqa: E402
from notebook_utils import _reset_data_directories  # noqa: E402
from agents.agent_registry.hypothesis_agent.model import create_hypothesis_agent  # noqa: E402


# (dataset_filename, background_filename) per recovery target.
_TARGETS = {
    "lohoff": (
        "dataset_lohoff_et_al_seqfish.h5ad",
        "lohoff_background.md",
    ),
    "farah": (
        "dataset_farah_heart_merfish.h5ad",
        "farah_background.md",
    ),
    "farah_anon": (
        "dataset_farah_anon.h5ad",
        "farah_anon_background.md",
    ),
}


def _stage_inputs(dataset_key: str) -> Path:
    """Copy dataset + limited background into DATA_DIR, return the dataset path."""
    if dataset_key not in _TARGETS:
        raise SystemExit(
            f"Unknown --dataset '{dataset_key}'. Choices: {sorted(_TARGETS)}"
        )
    dataset_filename, background_filename = _TARGETS[dataset_key]

    demo_data = Path(__file__).resolve().parent / "data"
    dataset_src = demo_data / dataset_filename
    background_src = demo_data / background_filename

    if not dataset_src.is_file():
        raise SystemExit(
            f"Dataset file missing: {dataset_src}\n"
            f"Place the .h5ad in demo/data/ before re-running."
        )
    if not background_src.is_file():
        raise SystemExit(
            f"Background file missing: {background_src}\n"
            f"Create demo/data/{background_filename} with the limited background."
        )

    _reset_data_directories()

    dataset_dst = DATA_DIR / "dataset" / dataset_filename
    dataset_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(dataset_src, dataset_dst)

    background_dst = DATA_DIR / "briefs" / "background.md"
    background_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(background_src, background_dst)

    (DATA_DIR / "hypotheses").mkdir(parents=True, exist_ok=True)

    return dataset_dst


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        choices=sorted(_TARGETS),
        default="lohoff",
        help="Which recovery target to run.",
    )
    args = parser.parse_args()

    dataset_path = _stage_inputs(args.dataset)

    print(f"Staged dataset at {dataset_path}")
    print(f"Staged background at {DATA_DIR / 'briefs' / 'background.md'}")
    print("Invoking Hypothesis Agent…\n")

    state_queue: Queue = Queue()
    tool = create_hypothesis_agent(state_queue)

    # The agent's prompt fully encodes the three-phase workflow. The Manager
    # would normally pass a one-line task description; mirror that.
    invocation_prompt = (
        "Run the evidence-grounded hypothesis-recovery workflow on the dataset "
        f"at {dataset_path.relative_to(DATA_DIR)} using the limited background "
        "at briefs/background.md. Complete all three phases (EXPLORE, "
        "HYPOTHESIZE, NARROW) and end with a final <response> block."
    )
    final_text = tool.func(invocation_prompt)

    print("\n\n===== FINAL <response> =====\n")
    print(final_text)
    print("\n===== ARTIFACTS =====")
    for p in sorted((DATA_DIR / "hypotheses").glob("*")):
        size = p.stat().st_size if p.is_file() else "-"
        print(f"  {p.relative_to(DATA_DIR)}  ({size} bytes)")


if __name__ == "__main__":
    main()
