"""Smoke test for the CellVoyager external-agent integration.

Calls the runner.py wrapper directly (bypassing the StructuredTool / Manager
wiring) so we can see raw output and verify the cross-conda-env subprocess
works end-to-end. Uses the small Lohoff dataset + minimal iteration count to
keep the test cheap.
"""

from __future__ import annotations

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

# Import after dotenv so DATA_DIR's env-aware imports resolve cleanly.
from agents.agent_registry.cellvoyager_agent.runner import (  # noqa: E402
    run_cellvoyager_analysis,
)


def main() -> int:
    dataset = _REPO_ROOT / "demo" / "data" / "dataset_lohoff_et_al_seqfish.h5ad"
    if not dataset.is_file():
        print(f"FAIL: dataset missing: {dataset}")
        return 1

    background = (
        "Mouse embryo seqFISH dataset (Lohoff et al.), ~350 genes, "
        "gastrulation / early organogenesis stage. Cell-type labels in `.obs` "
        "(see `celltype_mapped_refined`); 2D spatial coords in `.obsm['spatial']`. "
        "Scope: discover what is interesting about cell-type spatial organization. "
        "No specific finding is provided."
    )

    print("Invoking CellVoyager via isolated conda env …\n")
    result = run_cellvoyager_analysis(
        h5ad_path=str(dataset),
        background_text=background,
        analysis_name="lohoff_smoke",
        num_analyses=1,
        max_iterations=2,
        model_name="gpt-5.1",
    )

    print(f"\nreturncode: {result['returncode']}")
    print(f"model_used: {result['model_used']}")
    print(f"run_directory: {result['run_directory']}")
    print(f"notebook_path: {result['notebook_path']}")
    print(f"hypotheses parsed: {len(result['hypotheses'])}")
    print("\n--- stdout_tail (last 50 lines) ---")
    print(result["stdout_tail"])
    if result["stderr_tail"].strip():
        print("\n--- stderr_tail (last 20 lines) ---")
        print(result["stderr_tail"])

    if result["hypotheses"]:
        print("\n--- first parsed hypothesis ---")
        print(json.dumps(result["hypotheses"][0], indent=2)[:800])

    return 0 if result["returncode"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
