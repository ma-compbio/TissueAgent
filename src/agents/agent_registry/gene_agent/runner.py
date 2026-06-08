"""Adapter that runs NCBI's GeneAgent cascade from inside TissueAgent.

The upstream package was written for the legacy ``openai==0.28`` SDK and
Azure-style endpoints. We bridge it through
:func:`agents.llm_compat.patch_openai_legacy_api`, which:

* installs a ``ChatCompletion.create``-shaped proxy onto the modern
  ``openai`` module,
* swallows the upstream's ``openai.api_type = "azure"`` assignments,
* pins the model to ``gpt-5.1`` (independent of the user's TissueAgent
  model selection — GeneAgent's behavior must be reproducible),
* and reads the OpenAI API key from TissueAgent's runtime key registry
  (env var or UI-pasted value).

The upstream entry point is ``main_cascade.GeneAgent(ID, genes_csv)``,
which writes artifacts to relative paths beneath the current working
directory. We isolate each invocation in ``data/gene_agent/<request_id>/``
and pre-create the output subdirectories the upstream code expects.
"""

from __future__ import annotations

import contextlib
import importlib
import io
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Sequence

from agents.llm_compat import patch_openai_legacy_api
from config import DATA_DIR, active_project_outputs

# The submodule path inside this folder.
_UPSTREAM_DIR = Path(__file__).resolve().parent / "upstream"

# Pinned model — independent of TissueAgent's UI selection by design.
# See manifest.yaml `llm.pinned_model`.
_PINNED_MODEL = "gpt-5.1"

# Output paths the upstream code writes to (relative to its CWD).
_FINAL_RESPONSE_REL = Path("Outputs/GeneAgent/Cascade/MsigDB_Final_Response_GeneAgent.txt")
_VERIFICATION_REL = Path("Verification Reports/Cascade/Claims_and_Verification_for_MsigDB.txt")
_GPT4_REL = Path("Outputs/GPT-4/MsigDB_Response_GPT4.txt")

_UPSTREAM_OUTPUT_DIRS = [
    "Outputs/GeneAgent/Cascade",
    "Outputs/GPT-4",
    "Verification Reports/Cascade",
]


def _ensure_upstream_on_path() -> None:
    """Add the upstream folder to ``sys.path`` so its modules import."""
    if not _UPSTREAM_DIR.is_dir():
        raise RuntimeError(
            f"GeneAgent upstream not found at {_UPSTREAM_DIR}. "
            "Run `git submodule update --init` from the repo root."
        )
    sys_path_str = str(_UPSTREAM_DIR)
    if sys_path_str not in sys.path:
        sys.path.insert(0, sys_path_str)


def _import_gene_agent_callable():
    """Import (or re-import) the upstream ``GeneAgent`` callable.

    Must be invoked *inside* :func:`patch_openai_legacy_api` so the
    upstream's module-top ``openai.api_type = "azure"`` lines execute
    against the patched module.
    """
    _ensure_upstream_on_path()
    # Force-reimport so module-top side effects re-run under the patch.
    for mod_name in ("main_cascade", "worker"):
        if mod_name in sys.modules:
            del sys.modules[mod_name]
    main_cascade = importlib.import_module("main_cascade")
    return main_cascade.GeneAgent


def _read_text_if_exists(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _last_block(text: str, delimiter: str = "//") -> str:
    parts = [part.strip() for part in text.split(delimiter) if part.strip()]
    return parts[-1] if parts else ""


def _extract_process_names(text: str) -> list[str]:
    """Parse unique ``Process: <name>`` lines."""
    matches = re.findall(r"^Process:\s*(.+)$", text, flags=re.MULTILINE)
    seen: set[str] = set()
    ordered: list[str] = []
    for name in matches:
        cleaned = name.strip()
        key = cleaned.lower()
        if cleaned and key not in seen:
            seen.add(key)
            ordered.append(cleaned)
    return ordered


def run_geneagent_cascade(
    gene_list: Sequence[str],
    request_id: str | None = None,
) -> dict:
    """Run the GeneAgent cascade on a list of gene symbols.

    Args:
        gene_list: Iterable of gene symbols (case-insensitive; blanks ignored).
        request_id: Optional identifier recorded with the run artifacts.
            Defaults to a UTC timestamp.

    Returns:
        A JSON-serialisable dictionary with the normalised cascade outputs.

    Raises:
        ValueError: if ``gene_list`` is empty.
        RuntimeError: if the upstream submodule is missing or
            ``OPENAI_API_KEY`` is unavailable.
    """
    genes = [g.strip() for g in gene_list if g and g.strip()]
    if not genes:
        raise ValueError("gene_list must contain at least one non-empty gene symbol.")

    run_identifier = request_id or datetime.utcnow().strftime("run_%Y%m%d_%H%M%S")
    # Per-project: drop runs under the active project's outputs/ so they
    # show up in the user's Files panel and travel with the project.
    run_directory = active_project_outputs() / "gene_agent" / run_identifier
    run_directory.mkdir(parents=True, exist_ok=True)

    # The upstream code writes to relative paths; pre-create them so it
    # doesn't crash on its first `open(...,"a")`.
    for rel in _UPSTREAM_OUTPUT_DIRS:
        (run_directory / rel).mkdir(parents=True, exist_ok=True)

    prev_cwd = Path.cwd()
    stdout_buffer = io.StringIO()
    raw_result = None
    try:
        os.chdir(run_directory)
        with patch_openai_legacy_api(pinned_model=_PINNED_MODEL):
            cascade_fn = _import_gene_agent_callable()
            with contextlib.redirect_stdout(stdout_buffer):
                raw_result = cascade_fn(run_identifier, ",".join(genes))
    finally:
        os.chdir(prev_cwd)

    stdout_text = stdout_buffer.getvalue()
    final_response_path = run_directory / _FINAL_RESPONSE_REL
    verification_path = run_directory / _VERIFICATION_REL
    gpt4_path = run_directory / _GPT4_REL

    final_response_text = _read_text_if_exists(final_response_path)
    verification_text = _read_text_if_exists(verification_path)
    gpt4_text = _read_text_if_exists(gpt4_path)

    artifact_paths = [
        str(path.resolve())
        for path in (final_response_path, verification_path, gpt4_path)
        if path.exists()
    ]

    result: dict = {
        "input_genes": genes,
        "request_id": run_identifier,
        "run_directory": str(run_directory.resolve()),
        "model_used": _PINNED_MODEL,
        "stdout": stdout_text,
        "final_summary": _last_block(final_response_text),
        "process_names": _extract_process_names(final_response_text),
        "verification_log": verification_text,
        "gpt4_initial_summary": _last_block(gpt4_text),
        "artifact_paths": artifact_paths,
    }
    if isinstance(raw_result, dict):
        result["raw_result"] = raw_result

    if not artifact_paths and not stdout_text.strip():
        raise RuntimeError(
            "GeneAgent cascade returned no visible outputs. Inspect "
            f"{run_directory} for partial artifacts."
        )

    return result
