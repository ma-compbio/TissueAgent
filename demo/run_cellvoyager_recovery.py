"""Drive CellVoyager on a hypothesis-recovery target dataset.

Mirrors the structure of `run_hypothesis_recovery.py` but invokes the
CellVoyager external agent in its isolated `cellvoyager` conda env instead
of the in-process Hypothesis Agent. Same `--dataset` choices, same
limited-background.md files, so the two agents are scored on identical
inputs and can be compared head-to-head.

Usage:
    cd demo/
    python run_cellvoyager_recovery.py --dataset farah
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

try:
    from dotenv import load_dotenv

    load_dotenv(_REPO_ROOT / ".env")
except ImportError:
    pass

from agents.agent_registry.cellvoyager_agent.runner import (  # noqa: E402
    run_cellvoyager_analysis,
)


# Map recovery target id → (h5ad filename, background filename).
_TARGETS = {
    "lohoff": (
        "dataset_lohoff_et_al_seqfish.h5ad",
        "lohoff_background.md",
    ),
    "farah": (
        "dataset_farah_heart_merfish.h5ad",
        "farah_background.md",
    ),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        choices=sorted(_TARGETS),
        required=True,
        help="Which recovery target to run.",
    )
    parser.add_argument("--num-analyses", type=int, default=3)
    parser.add_argument("--max-iterations", type=int, default=6)
    parser.add_argument("--model-name", default="gpt-5.1")
    args = parser.parse_args()

    dataset_filename, background_filename = _TARGETS[args.dataset]
    demo_data = Path(__file__).resolve().parent / "data"
    dataset_path = demo_data / dataset_filename
    background_path = demo_data / background_filename

    if not dataset_path.is_file():
        print(f"FAIL: dataset missing: {dataset_path}")
        return 1
    if not background_path.is_file():
        print(f"FAIL: background missing: {background_path}")
        return 1

    background_text = background_path.read_text(encoding="utf-8")

    print(f"Invoking CellVoyager on {args.dataset}")
    print(f"  num_analyses={args.num_analyses}  max_iterations={args.max_iterations}")
    print(f"  model_name={args.model_name}")
    print()
    result = run_cellvoyager_analysis(
        h5ad_path=str(dataset_path),
        background_text=background_text,
        analysis_name=f"{args.dataset}_recovery",
        num_analyses=args.num_analyses,
        max_iterations=args.max_iterations,
        model_name=args.model_name,
    )

    print(f"\nreturncode: {result['returncode']}")
    print(f"run_directory: {result['run_directory']}")
    print(f"notebook_path: {result['notebook_path']}")
    print(f"hypotheses parsed: {len(result['hypotheses'])}")

    if result["hypotheses"]:
        print("\n--- All parsed hypotheses ---")
        for i, h in enumerate(result["hypotheses"], 1):
            print(f"\n### Hypothesis {i}")
            print(h["header"][:400])

    # Also dump the structured result for the eval harness to read.
    summary_path = Path(result["run_directory"]) / "cellvoyager_recovery_summary.json"
    summary_payload = {
        "dataset": args.dataset,
        "model_used": result["model_used"],
        "notebook_path": result["notebook_path"],
        "num_analyses": args.num_analyses,
        "max_iterations": args.max_iterations,
        "hypotheses": result["hypotheses"],
    }
    summary_path.write_text(json.dumps(summary_payload, indent=2), encoding="utf-8")
    print(f"\nSummary written: {summary_path}")

    return 0 if result["returncode"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
