from __future__ import annotations

import contextlib
import io
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Sequence

from config import DATA_DIR

GENE_AGENT_SRC_DIR = Path(__file__).resolve().parent.parent / "original_repo" / "GeneAgent"
if str(GENE_AGENT_SRC_DIR) not in sys.path:
    sys.path.append(str(GENE_AGENT_SRC_DIR))

try:
    from main_cascade import GeneAgent as _GeneAgentCascade  # type: ignore
except ModuleNotFoundError as exc:  # pragma: no cover - defensive
    raise RuntimeError(
        "Unable to import GeneAgent cascade. Ensure the original repository is present at "
        f"{GENE_AGENT_SRC_DIR}"
    ) from exc


def run_geneagent_cascade(
    gene_list: Sequence[str],
    request_id: str | None = None,
) -> dict:
    """
    Run the GeneAgent cascade for a list of gene symbols.

    Args:
        gene_list: Iterable of gene symbols (case-sensitive). Empty/blank entries are ignored.
        request_id: Optional identifier stored alongside the run. Defaults to a timestamp.

    Returns:
        Dictionary containing the cascade outputs, including final summary text, process names,
        artifact paths, and captured stdout.
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
            result = _GeneAgentCascade(run_identifier, ",".join(genes))
    finally:
        os.chdir(prev_cwd)

    stdout_text = stdout_buffer.getvalue()

    if not isinstance(result, dict):
        raise RuntimeError(
            "GeneAgent cascade completed without returning a result dictionary. "
            "Inspect the captured stdout output for details."
        )

    result = {**result}
    result["input_genes"] = genes
    result["request_id"] = run_identifier
    result["run_directory"] = str(run_directory.resolve())
    result["stdout"] = stdout_text
    return result

