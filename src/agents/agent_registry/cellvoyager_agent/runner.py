"""Adapter that runs upstream CellVoyager from inside TissueAgent.

CellVoyager exposes its entry point as a CLI (`run_cellvoyager.py`) rather
than a clean library API, so the simplest and most maintainable integration
is to invoke that CLI as a subprocess from the upstream directory. This keeps
us decoupled from any internal API churn in the upstream package and matches
the way the upstream is intended to be run.

The subprocess:
  - Sets CWD to the pinned upstream submodule (so its relative paths resolve).
  - Writes the biological-background text to a temp `.txt` file.
  - Invokes `python run_cellvoyager.py` with `--execution-mode legacy` (no
    Jupyter / Streamlit needed for headless integration).
  - Routes outputs to `data/cellvoyager_agent/<request_id>/`.
  - After completion, parses the generated `.ipynb` and any `analysis_*.json`
    summaries CellVoyager writes, and returns a structured dict.

The pinned model is read from `manifest.yaml` (`llm.pinned_model`) but a
caller can override via `model_name=`.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# These imports come from the parent TissueAgent app, not the upstream
# CellVoyager submodule.
from config import DATA_DIR

_HERE = Path(__file__).resolve().parent
_UPSTREAM_DIR = _HERE / "upstream"
_CLI_SCRIPT = _UPSTREAM_DIR / "run_cellvoyager.py"

_DEFAULT_MODEL = "claude-sonnet-4-6"
# Upstream pins litellm + instructor, both of which require openai >= 2.0;
# TissueAgent pins langchain-openai == 0.3.10 which requires openai < 2.0.
# Resolve the conflict by running CellVoyager in its own conda env. Create
# it once with `conda env create -n cellvoyager -f <upstream>/environment.yml`.
_CELLVOYAGER_ENV = "cellvoyager"


def _check_upstream() -> None:
    if not _UPSTREAM_DIR.is_dir():
        raise RuntimeError(
            f"CellVoyager upstream not found at {_UPSTREAM_DIR}. "
            "Run `git submodule update --init --recursive` from the repo root."
        )
    if not _CLI_SCRIPT.is_file():
        raise RuntimeError(
            f"CellVoyager CLI script missing: {_CLI_SCRIPT}. The upstream "
            "submodule appears corrupted."
        )


def _check_isolated_env() -> None:
    """Verify the `cellvoyager` conda env exists and can import the upstream."""
    if shutil.which("conda") is None:
        raise RuntimeError(
            "`conda` not found on PATH. CellVoyager runs in an isolated conda "
            "env to avoid an openai>=2.0 dependency conflict with the rest of "
            "TissueAgent."
        )
    # The upstream isn't a pip-installed package; it's a folder containing a
    # `cellvoyager` directory. Python finds it via cwd lookup, so we run the
    # probe with cwd set to the upstream directory (matches how the real
    # subprocess below invokes it).
    probe = subprocess.run(
        ["conda", "run", "-n", _CELLVOYAGER_ENV, "python", "-c", "import cellvoyager"],
        cwd=str(_UPSTREAM_DIR),
        capture_output=True,
        text=True,
        check=False,
    )
    if probe.returncode != 0:
        raise RuntimeError(
            f"Isolated env `{_CELLVOYAGER_ENV}` cannot import cellvoyager. "
            f"Create it with `conda env create -n {_CELLVOYAGER_ENV} -f "
            f"{_UPSTREAM_DIR}/environment.yml`. Probe stderr:\n{probe.stderr[-500:]}"
        )


def _check_api_keys() -> None:
    """At least one of (OPENAI, ANTHROPIC) must be present for CellVoyager."""
    if not (os.environ.get("OPENAI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")):
        raise RuntimeError(
            "Neither OPENAI_API_KEY nor ANTHROPIC_API_KEY is set; "
            "CellVoyager cannot run."
        )


def _parse_notebook_for_findings(notebook_path: Path) -> list[dict]:
    """Extract the agent-generated analysis cells from CellVoyager's notebook.

    CellVoyager writes markdown cells containing hypothesis statements above
    each code cell. We scan markdown cells whose first line mentions
    `Analysis` or `Hypothesis` and pair them with the next code cell.
    """
    if not notebook_path.is_file():
        return []
    try:
        nb = json.loads(notebook_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []

    findings: list[dict] = []
    pending_header: Optional[str] = None
    for cell in nb.get("cells", []):
        src = "".join(cell.get("source", []))
        first_line = src.splitlines()[0] if src.splitlines() else ""
        if cell.get("cell_type") == "markdown" and (
            "Analysis" in first_line or "Hypothesis" in first_line
        ):
            pending_header = src
        elif cell.get("cell_type") == "code" and pending_header is not None:
            findings.append({"header": pending_header.strip(), "code_excerpt": src[:500]})
            pending_header = None
    return findings


def run_cellvoyager_analysis(
    h5ad_path: str,
    background_text: str,
    analysis_name: str,
    num_analyses: int = 1,
    max_iterations: int = 6,
    model_name: Optional[str] = None,
    request_id: Optional[str] = None,
) -> dict:
    """Run CellVoyager on a single dataset + background-text pair.

    Args:
        h5ad_path: Absolute path to the AnnData file.
        background_text: Biological context the agent should see. In a
            recovery-benchmark run this is the LIMITED background with the
            target claim withheld.
        analysis_name: Short snake-case name for this run (becomes a
            sub-folder name).
        num_analyses: How many independent analyses CellVoyager should
            propose. Default 1 (fastest); 3–5 is typical for benchmarks.
        max_iterations: Max self-refinement iterations per analysis.
        model_name: Override the manifest's pinned model. Default uses
            CellVoyager's own default (claude-sonnet-4-6).
        request_id: Optional identifier for the run artifact directory.

    Returns:
        A dict with keys:
          - request_id, run_directory, model_used
          - notebook_path (str or None if not produced)
          - hypotheses: list of {header, code_excerpt}
          - stdout_tail: last ~50 lines of CellVoyager output
          - stderr_tail: last ~20 lines of CellVoyager stderr
          - returncode: subprocess exit code (0 = success)
    """
    _check_upstream()
    _check_isolated_env()
    _check_api_keys()

    h5ad_path_p = Path(h5ad_path).resolve()
    if not h5ad_path_p.is_file():
        raise FileNotFoundError(f"h5ad file not found: {h5ad_path_p}")
    if not background_text.strip():
        raise ValueError("background_text must be non-empty.")

    run_identifier = request_id or datetime.now(timezone.utc).strftime(
        "run_%Y%m%d_%H%M%S"
    )
    run_dir = DATA_DIR / "cellvoyager_agent" / run_identifier
    run_dir.mkdir(parents=True, exist_ok=True)

    background_path = run_dir / "background.txt"
    background_path.write_text(background_text, encoding="utf-8")

    # Invoke through the isolated `cellvoyager` env so the upstream's
    # litellm/instructor (openai>=2.0) coexists with TissueAgent's pinned
    # langchain-openai (openai<2.0).
    cmd = [
        "conda", "run", "-n", _CELLVOYAGER_ENV, "--live-stream",
        "python", str(_CLI_SCRIPT),
        "--h5ad-path", str(h5ad_path_p),
        "--paper-path", str(background_path),
        "--analysis-name", analysis_name,
        "--execution-mode", "legacy",
        "--num-analyses", str(num_analyses),
        "--max-iterations", str(max_iterations),
        "--output-home", str(run_dir),
        "--log-home", str(run_dir / "logs"),
        "--no-vlm",  # skip the OpenAI VLM step to keep dependencies minimal
    ]
    if model_name:
        cmd.extend(["--model-name", model_name])

    proc = subprocess.run(
        cmd,
        cwd=str(_UPSTREAM_DIR),
        capture_output=True,
        text=True,
        env={**os.environ},
        check=False,
        timeout=3600,  # 60 min hard cap; CellVoyager on 228k-cell data needs margin
    )

    stdout_tail = "\n".join(proc.stdout.splitlines()[-50:])
    stderr_tail = "\n".join(proc.stderr.splitlines()[-20:])

    # CellVoyager writes one notebook per analysis under
    # <output_home>/<analysis_name>/<analysis_name>_analysis_{1,2,3,...}.ipynb.
    # We aggregate findings across ALL produced notebooks; otherwise a
    # num_analyses > 1 run would be undersampled.
    candidates = sorted(run_dir.rglob("*.ipynb"))
    notebook_path = str(candidates[0].resolve()) if candidates else None
    findings: list[dict] = []
    for nb in candidates:
        for h in _parse_notebook_for_findings(nb):
            h["source_notebook"] = nb.name
            findings.append(h)

    return {
        "request_id": run_identifier,
        "run_directory": str(run_dir.resolve()),
        "model_used": model_name or _DEFAULT_MODEL,
        "notebook_path": notebook_path,
        "hypotheses": findings,
        "stdout_tail": stdout_tail,
        "stderr_tail": stderr_tail,
        "returncode": proc.returncode,
    }
