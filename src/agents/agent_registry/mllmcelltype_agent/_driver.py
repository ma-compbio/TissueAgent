"""In-env driver for mLLMCelltype.

This script is executed *inside the isolated ``mllmcelltype`` conda env* by
``runner.py`` (via ``conda run``), so it may import the upstream package
freely without touching TissueAgent's pinned dependency set. It reads a JSON
request from a file, calls mLLMCelltype, and writes a JSON result to a file.

Keeping the actual upstream call in a separate, env-isolated process is the
same pattern the CellVoyager adapter uses: the upstream's ``openai>=1`` /
``google-genai`` stack coexists with TissueAgent's pinned ``openai<2.0``
without a resolver conflict.

Contract (all paths are absolute):
    python _driver.py <request_json> <result_json>

Request JSON keys:
    marker_genes:   dict[str, list[str]]   (required)
    species:        str                    (required)
    tissue:         str | None
    mode:           "single" | "consensus" (default "single")
    provider:       str                    (single mode; default "openai")
    model:          str | None
    models:         list[str] | None        (consensus mode)
    additional_context: str | None
    cache_dir:      str | None

The result JSON always has a top-level ``status`` of "ok" or "error".
"""

from __future__ import annotations

import json
import sys
import traceback
from typing import Any


def _run(request: dict[str, Any]) -> dict[str, Any]:
    # Imported here (not at module top) so an import failure is reported as a
    # structured error rather than a bare traceback on the caller's stderr.
    from mllmcelltype import annotate_clusters, interactive_consensus_annotation

    marker_genes = request["marker_genes"]
    species = request["species"]
    tissue = request.get("tissue")
    additional_context = request.get("additional_context")
    cache_dir = request.get("cache_dir")
    mode = request.get("mode", "single")

    if mode == "consensus":
        models = request.get("models") or None
        result = interactive_consensus_annotation(
            marker_genes=marker_genes,
            species=species,
            models=models,
            tissue=tissue,
            additional_context=additional_context,
            use_cache=True,
            cache_dir=cache_dir,
            verbose=False,
        )
        # interactive_consensus_annotation returns a 10-key dict; surface the
        # fields a downstream agent actually consumes and keep them JSON-safe.
        return {
            "status": "ok",
            "mode": "consensus",
            "annotations": result.get("consensus", {}),
            "consensus_proportion": result.get("consensus_proportion", {}),
            "entropy": result.get("entropy", {}),
            "controversial_clusters": result.get("controversial_clusters", []),
            "model_annotations": result.get("model_annotations", {}),
            "models_used": [
                m if isinstance(m, str) else m.get("model")
                for m in (request.get("models") or [])
            ],
        }

    # Single-model mode → flat dict[str, str].
    provider = request.get("provider", "openai")
    model = request.get("model")
    annotations = annotate_clusters(
        marker_genes=marker_genes,
        species=species,
        provider=provider,
        model=model,
        tissue=tissue,
        additional_context=additional_context,
        use_cache=True,
        cache_dir=cache_dir,
    )
    return {
        "status": "ok",
        "mode": "single",
        "annotations": annotations,
        "provider": provider,
        "model": model,
    }


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: python _driver.py <request_json> <result_json>", file=sys.stderr)
        return 2
    request_path, result_path = sys.argv[1], sys.argv[2]
    try:
        with open(request_path, "r", encoding="utf-8") as fh:
            request = json.load(fh)
        result = _run(request)
    except Exception as exc:  # noqa: BLE001 — deliberately catch-all: the parent
        # process only sees this file, so every failure must be captured here.
        result = {
            "status": "error",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }
    with open(result_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)
    return 0 if result.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
