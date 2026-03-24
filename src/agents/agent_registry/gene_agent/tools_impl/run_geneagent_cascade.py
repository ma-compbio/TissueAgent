"""Wrapper that runs the GeneAgent cascade pipeline and normalises its outputs."""

from __future__ import annotations

import contextlib
import io
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Sequence

from config import DATA_DIR

GENE_AGENT_SRC_DIR = Path(__file__).resolve().parent.parent / "original_repo" / "GeneAgent"

_GeneAgentCascade = None


def _get_gene_agent_cascade():
    """Lazily import GeneAgent cascade to avoid tkinter dependency at module load time."""
    global _GeneAgentCascade
    if _GeneAgentCascade is not None:
        return _GeneAgentCascade
    if str(GENE_AGENT_SRC_DIR) not in sys.path:
        sys.path.append(str(GENE_AGENT_SRC_DIR))
    try:
        from main_cascade import GeneAgent as _cls  # type: ignore
    except ModuleNotFoundError as exc:  # pragma: no cover - defensive
        raise RuntimeError(
            "Unable to import GeneAgent cascade. Ensure the original repository is present at "
            f"{GENE_AGENT_SRC_DIR}"
        ) from exc
    _GeneAgentCascade = _cls
    return _GeneAgentCascade


_FINAL_RESPONSE_REL = Path("Outputs/GeneAgent/Cascade/MsigDB_Final_Response_GeneAgent.txt")
_VERIFICATION_REL = Path("Verification Reports/Cascade/Claims_and_Verification_for_MsigDB.txt")
_GPT4_REL = Path("Outputs/GPT-4/MsigDB_Response_GPT4.txt")


def _read_text_if_exists(path: Path) -> str:
    """Return the text content of a file, or empty string if it does not exist."""
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _last_block(text: str, delimiter: str = "//") -> str:
    """Return the last non-empty segment after splitting on a delimiter."""
    parts = [part.strip() for part in text.split(delimiter) if part.strip()]
    return parts[-1] if parts else ""


def _extract_process_names(text: str) -> list[str]:
    """Parse unique ``Process: <name>`` lines from GeneAgent output text."""
    names = re.findall(r"^Process:\s*(.+)$", text, flags=re.MULTILINE)
    seen: set[str] = set()
    ordered: list[str] = []
    for name in names:
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
    """Run the GeneAgent cascade for a list of gene symbols.

    Args:
        gene_list: Iterable of gene symbols (case-sensitive). Empty/blank entries are ignored.
        request_id: Optional identifier stored alongside the run. Defaults to a timestamp.

    Returns:
        Dictionary containing normalized cascade outputs, including final summary text,
        process names, verification logs, artifact paths, and captured stdout.
    """
    genes = [gene.strip() for gene in gene_list if gene and gene.strip()]
    if not genes:
        raise ValueError("gene_list must contain at least one non-empty gene symbol.")

    run_identifier = request_id or datetime.utcnow().strftime("run_%Y%m%d_%H%M%S")
    run_directory = DATA_DIR / "gene_agent" / run_identifier
    run_directory.mkdir(parents=True, exist_ok=True)

    prev_cwd = Path.cwd()
    stdout_buffer = io.StringIO()
    try:
        os.chdir(run_directory)
        with contextlib.redirect_stdout(stdout_buffer):
            raw_result = _get_gene_agent_cascade()(run_identifier, ",".join(genes))
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

    normalized_result: dict = {
        "input_genes": genes,
        "request_id": run_identifier,
        "run_directory": str(run_directory.resolve()),
        "stdout": stdout_text,
        "final_summary": _last_block(final_response_text),
        "process_names": _extract_process_names(final_response_text),
        "verification_log": verification_text,
        "gpt4_initial_summary": _last_block(gpt4_text),
        "artifact_paths": artifact_paths,
    }

    if isinstance(raw_result, dict):
        normalized_result["raw_result"] = raw_result

    if not artifact_paths and not stdout_text.strip():
        raise RuntimeError(
            "GeneAgent cascade returned no visible outputs. "
            "Inspect the run directory for partial artifacts."
        )

    return normalized_result
