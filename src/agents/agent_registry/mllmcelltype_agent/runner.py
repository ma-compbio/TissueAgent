"""Adapter that runs mLLMCelltype from inside TissueAgent.

mLLMCelltype is a clean pip package (``pip install mllmcelltype``) whose only
notable dependency is ``openai>=1.0`` (uncapped) plus optional provider SDKs.
TissueAgent pins ``langchain-openai``/``openai<2.0``, so to stay conflict-free
we run the upstream call in an **isolated ``mllmcelltype`` conda env** through
``_driver.py`` — the same isolation strategy the CellVoyager adapter uses.

If that env is not present we fall back to importing the package **in-process**
(from the pinned submodule's ``python/`` source tree). The in-process path is
convenient for smoke tests but may hit the ``openai`` version pin on some
installs; the isolated env is the supported production path.

Create the env once:

    conda create -n mllmcelltype -y python=3.11
    conda run -n mllmcelltype pip install "mllmcelltype[openai,anthropic]"

Either ``OPENAI_API_KEY`` or ``ANTHROPIC_API_KEY`` must be resolvable through
TissueAgent's key registry (UI-pasted value or environment variable).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from config import active_project_outputs
from logger import logger

_HERE = Path(__file__).resolve().parent
_UPSTREAM_DIR = _HERE / "upstream"
# The upstream Python package lives under upstream/python/mllmcelltype/.
_UPSTREAM_PKG_PARENT = _UPSTREAM_DIR / "python"
_DRIVER = _HERE / "_driver.py"

# Isolated conda env name (see module docstring for how to create it).
_ISOLATED_ENV = "mllmcelltype"

# Hard cap: annotation is a handful of LLM calls per cluster, but a large
# marker table in consensus mode with multi-round discussion can be slow.
_TIMEOUT_S = 3600


def _resolve_keys_into_env(env: dict[str, str]) -> tuple[str, str]:
    """Populate provider API keys from TissueAgent's registry.

    Returns ``(preferred_provider, note)``. Raises ``RuntimeError`` if neither
    an OpenAI nor an Anthropic key is available.
    """
    try:
        from models import get_api_key  # local import to avoid import cycles
    except Exception:  # noqa: BLE001 — during unit tests `models` may be absent
        get_api_key = None  # type: ignore[assignment]

    def _key(provider: str, env_var: str) -> Optional[str]:
        if get_api_key is not None:
            try:
                val = get_api_key(provider)  # type: ignore[arg-type]
                if val:
                    return val
            except Exception:  # noqa: BLE001
                pass
        return env.get(env_var) or os.environ.get(env_var)

    openai_key = _key("openai", "OPENAI_API_KEY")
    anthropic_key = _key("anthropic", "ANTHROPIC_API_KEY")

    if openai_key:
        env["OPENAI_API_KEY"] = openai_key
    if anthropic_key:
        env["ANTHROPIC_API_KEY"] = anthropic_key

    if openai_key:
        return "openai", "using OpenAI key"
    if anthropic_key:
        return "anthropic", "using Anthropic key (OpenAI key absent)"
    raise RuntimeError(
        "mLLMCelltype requires an OpenAI or Anthropic API key; neither "
        "OPENAI_API_KEY nor ANTHROPIC_API_KEY is set (checked TissueAgent's "
        "key registry and the environment)."
    )


def _isolated_env_available() -> bool:
    if shutil.which("conda") is None:
        return False
    probe = subprocess.run(
        ["conda", "run", "-n", _ISOLATED_ENV, "python", "-c", "import mllmcelltype"],
        capture_output=True,
        text=True,
        check=False,
    )
    return probe.returncode == 0


def _normalise_marker_genes(marker_genes: dict[str, list[str]]) -> dict[str, list[str]]:
    """Coerce keys to str and values to clean, deduped gene-symbol lists."""
    cleaned: dict[str, list[str]] = {}
    for cluster, genes in marker_genes.items():
        seen: set[str] = set()
        ordered: list[str] = []
        for g in genes:
            g = str(g).strip()
            if g and g not in seen:
                seen.add(g)
                ordered.append(g)
        if ordered:
            cleaned[str(cluster)] = ordered
    return cleaned


def _run_in_process(request: dict, env_keys: tuple[str, str]) -> dict:
    """Fallback: import the pinned submodule package in-process and run it.

    Used only when the isolated conda env is absent. May be subject to the
    host's ``openai`` version; on conflict, create the isolated env instead.
    """
    pkg_parent = str(_UPSTREAM_PKG_PARENT)
    added = False
    if _UPSTREAM_PKG_PARENT.is_dir() and pkg_parent not in sys.path:
        sys.path.insert(0, pkg_parent)
        added = True
    try:
        # Reuse the driver's logic to keep a single source of truth.
        sys.path.insert(0, str(_HERE))
        import importlib

        driver = importlib.import_module("_driver")
        return driver._run(request)  # type: ignore[attr-defined]
    finally:
        if added:
            try:
                sys.path.remove(pkg_parent)
            except ValueError:
                pass


def run_mllmcelltype_annotation(
    marker_genes: dict[str, list[str]],
    species: str,
    tissue: Optional[str] = None,
    mode: str = "single",
    provider: str = "openai",
    model: Optional[str] = None,
    models: Optional[list[str]] = None,
    additional_context: Optional[str] = None,
    request_id: Optional[str] = None,
) -> dict:
    """Annotate scRNA-seq clusters with mLLMCelltype.

    Args:
        marker_genes: Mapping of cluster id -> ordered marker-gene symbols
            (most significant first), e.g. ``{"0": ["CD3D", "CD3E", ...]}``.
        species: Organism, e.g. ``"human"`` or ``"mouse"`` (required).
        tissue: Optional tissue context (e.g. ``"blood"``) — improves labels.
        mode: ``"single"`` (one model, flat labels) or ``"consensus"``
            (multiple models with confidence + per-model votes).
        provider: Provider for single mode (default ``"openai"``). Ignored in
            consensus mode.
        model: Explicit model string. Recommended — the upstream config's
            default model names may be newer than your key can serve. If
            omitted, the runner picks a sensible default for the resolved key.
        models: List of model strings for consensus mode (e.g.
            ``["gpt-4o", "claude-3-5-sonnet-latest"]``).
        additional_context: Extra free-text biological context.
        request_id: Optional id for the run artifact directory.

    Returns:
        A JSON-serialisable dict:
          - status: "ok" | "error"
          - mode, annotations (cluster -> label)
          - consensus_proportion, entropy, model_annotations (consensus mode)
          - run_directory, artifact_path
          - execution ("isolated_env" | "in_process")
        On error, ``status == "error"`` with ``error`` / ``error_type``.

    Raises:
        ValueError: if ``marker_genes`` is empty or ``species`` is blank.
        RuntimeError: if the upstream submodule is missing or no API key is
            resolvable.
    """
    if not _UPSTREAM_DIR.is_dir():
        raise RuntimeError(
            f"mLLMCelltype upstream not found at {_UPSTREAM_DIR}. "
            "Run `git submodule update --init --recursive` from the repo root."
        )
    marker_genes = _normalise_marker_genes(marker_genes or {})
    if not marker_genes:
        raise ValueError("marker_genes must map at least one cluster to genes.")
    if not (species or "").strip():
        raise ValueError("species is required (e.g. 'human' or 'mouse').")

    child_env = {**os.environ}
    preferred_provider, key_note = _resolve_keys_into_env(child_env)

    # Default provider/model selection follows whichever key is present.
    if mode != "consensus":
        if provider == "openai" and preferred_provider == "anthropic":
            provider = "anthropic"
        if model is None:
            model = "gpt-4o" if provider == "openai" else "claude-3-5-sonnet-latest"

    run_identifier = request_id or datetime.now(timezone.utc).strftime(
        "run_%Y%m%d_%H%M%S"
    )
    run_dir = active_project_outputs() / "mllmcelltype" / run_identifier
    run_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = run_dir / "cache"

    request = {
        "marker_genes": marker_genes,
        "species": species,
        "tissue": tissue,
        "mode": mode,
        "provider": provider,
        "model": model,
        "models": models,
        "additional_context": additional_context,
        "cache_dir": str(cache_dir),
    }
    request_path = run_dir / "request.json"
    result_path = run_dir / "result.json"
    request_path.write_text(json.dumps(request, indent=2), encoding="utf-8")

    logger.info(
        "mLLMCelltype[%s]: annotating %d clusters (species=%s, mode=%s, %s).",
        run_identifier,
        len(marker_genes),
        species,
        mode,
        key_note,
    )

    used_isolated = _isolated_env_available()
    if used_isolated:
        proc = subprocess.run(
            [
                "conda", "run", "-n", _ISOLATED_ENV, "--live-stream",
                "python", str(_DRIVER), str(request_path), str(result_path),
            ],
            cwd=str(_HERE),
            env=child_env,
            capture_output=True,
            text=True,
            check=False,
            timeout=_TIMEOUT_S,
        )
        if result_path.is_file():
            result = json.loads(result_path.read_text(encoding="utf-8"))
        else:
            result = {
                "status": "error",
                "error_type": "NoResult",
                "error": "driver produced no result.json",
                "stderr_tail": "\n".join(proc.stderr.splitlines()[-20:]),
            }
        result["execution"] = "isolated_env"
        result["returncode"] = proc.returncode
    else:
        logger.warning(
            "mLLMCelltype[%s]: isolated env `%s` not found; running in-process "
            "from the pinned submodule (create the env for the supported path).",
            run_identifier,
            _ISOLATED_ENV,
        )
        try:
            result = _run_in_process(request, (preferred_provider, key_note))
        except Exception as exc:  # noqa: BLE001 — report, don't crash the graph
            result = {
                "status": "error",
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
        result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        result["execution"] = "in_process"

    result.setdefault("request_id", run_identifier)
    result["run_directory"] = str(run_dir.resolve())
    result["artifact_path"] = str(result_path.resolve())
    result["input_clusters"] = list(marker_genes.keys())

    if result.get("status") == "ok":
        logger.info(
            "mLLMCelltype[%s]: done — %d clusters labelled.",
            run_identifier,
            len(result.get("annotations", {})),
        )
    else:
        logger.error(
            "mLLMCelltype[%s]: failed (%s): %s",
            run_identifier,
            result.get("error_type"),
            result.get("error"),
        )
    return result
