"""Run an upstream agent baseline inside its own Python environment."""

from __future__ import annotations

import argparse
import functools
import importlib
import importlib.metadata
import inspect
import json
import os
import sys
import traceback
from pathlib import Path
from typing import Any


def _package_version(distribution: str) -> str | None:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return None


def _message_content(message: Any) -> Any:
    content = getattr(message, "content", message)
    if isinstance(content, (str, int, float, bool)) or content is None:
        return content
    if isinstance(content, list):
        return [_message_content(item) for item in content]
    if isinstance(content, dict):
        return {str(key): _message_content(value) for key, value in content.items()}
    return str(content)


def _normalize_h5ad_for_parent(path: str | Path) -> dict[str, Any] | None:
    annotated_path = Path(path)
    if not annotated_path.exists():
        return None

    import anndata as ad

    annotated = ad.read_h5ad(annotated_path)
    removed: list[str] = []

    def remove_nulls(mapping: dict[str, Any], prefix: str) -> None:
        for key, value in list(mapping.items()):
            location = f"{prefix}.{key}"
            if value is None:
                del mapping[key]
                removed.append(location)
            elif isinstance(value, dict):
                remove_nulls(value, location)

    remove_nulls(annotated.uns, "uns")
    compatible_path = annotated_path.with_name(f".{annotated_path.name}.compatible")
    annotated.write_h5ad(compatible_path, compression="gzip")
    compatible_path.replace(annotated_path)
    return {"removed_null_metadata": removed}


def _run_biomni(request: dict[str, Any]) -> dict[str, Any]:
    model = request["model"]
    source = request.get("source")
    version = _package_version("biomni")
    expected_version = request.get("expected_version")
    if expected_version is not None and version != expected_version:
        raise RuntimeError(f"biomni=={expected_version} is required; found {version}.")

    biomni_llm = importlib.import_module("biomni.llm")
    native_get_llm = biomni_llm.get_llm

    @functools.wraps(native_get_llm)
    def configured_get_llm(*args: Any, **kwargs: Any) -> Any:
        call = inspect.signature(native_get_llm).bind_partial(*args, **kwargs)
        call.arguments["model"] = model
        call.arguments["source"] = source
        return native_get_llm(*call.args, **call.kwargs)

    biomni_llm.get_llm = configured_get_llm

    from biomni.agent import A1
    from biomni.config import default_config

    expected_data_lake_files = request["expected_data_lake_files"]
    if expected_data_lake_files is not None:
        biomni_utils = importlib.import_module("biomni.utils")
        download_results = biomni_utils.check_and_download_s3_files(
            s3_bucket_url="https://biomni-release.s3.amazonaws.com",
            local_data_lake_path=str(Path(request["data_path"]) / "biomni_data" / "data_lake"),
            expected_files=expected_data_lake_files,
            folder="data_lake",
        )
        failed_downloads = [name for name, success in download_results.items() if not success]
        if failed_downloads:
            raise RuntimeError("Biomni data-lake download failed: " + ", ".join(failed_downloads))

    genomics = importlib.import_module("biomni.tool.genomics")
    native_annotation = genomics.annotate_celltype_scRNA

    from langchain_core.runnables import RunnableLambda

    @functools.wraps(native_get_llm)
    def text_response_llm(*args: Any, **kwargs: Any) -> Any:
        llm = configured_get_llm(*args, **kwargs)
        return llm | RunnableLambda(
            lambda response: (
                response.text() if callable(getattr(response, "text", None)) else str(response)
            )
        )

    @functools.wraps(native_annotation)
    def configured_annotation(*args: Any, **kwargs: Any) -> Any:
        call = inspect.signature(native_annotation).bind_partial(*args, **kwargs)
        call.arguments["llm"] = model
        return native_annotation(*call.args, **call.kwargs)

    genomics.annotate_celltype_scRNA = configured_annotation
    genomics.get_llm = text_response_llm
    a1_module = importlib.import_module("biomni.agent.a1")
    native_bash = a1_module.run_bash_script

    @functools.wraps(native_bash)
    def configured_bash(script: str, *args: Any, **kwargs: Any) -> Any:
        if "annotate_celltype_scRNA" in script:
            return (
                "ERROR: Execute annotate_celltype_scRNA as plain Python in the existing "
                "execution block, without a shell or subprocess. Its required LLM "
                "compatibility bindings are installed only in this Python process."
            )
        return native_bash(script, *args, **kwargs)

    a1_module.run_bash_script = configured_bash
    default_config.llm = model
    default_config.source = source
    default_config.path = request["data_path"]
    default_config.timeout_seconds = request["agent_timeout_seconds"]
    default_config.use_tool_retriever = request["use_tool_retriever"]
    default_config.commercial_mode = request["commercial_mode"]
    agent = A1(
        path=request["data_path"],
        llm=model,
        source=source,
        use_tool_retriever=request["use_tool_retriever"],
        timeout_seconds=request["agent_timeout_seconds"],
        commercial_mode=request["commercial_mode"],
        expected_data_lake_files=expected_data_lake_files,
    )
    log, response = agent.go(request["prompt"])
    return {
        "status": "success",
        "method": "biomni",
        "version": version,
        "model": model,
        "source": source,
        "llm_output_normalization": "AIMessage.text",
        "runtime_dependencies": {
            name: _package_version(name) for name in ("scanpy", "igraph", "leidenalg")
        },
        "pythonpath": os.environ.get("PYTHONPATH", ""),
        "query_preprocessing": {
            "adapter_transform": "none",
            "responsibility": "Biomni agent; see execution transcript for decisions",
            "agent_input_h5ad": request["query_h5ad"],
        },
        "log": [_message_content(item) for item in log],
        "final_response": _message_content(response),
    }


def _configure_harmony_compatibility() -> dict[str, Any]:
    import harmonypy
    import numpy as np
    import scanpy.external as sce

    def harmony_integrate(
        adata: Any,
        key: str | list[str],
        *,
        basis: str = "X_pca",
        adjusted_basis: str = "X_pca_harmony",
        **kwargs: Any,
    ) -> None:
        values = adata.obsm[basis].astype(np.float64)
        harmony_output = harmonypy.run_harmony(values, adata.obs, key, **kwargs)
        corrected = np.asarray(harmony_output.Z_corr)
        if corrected.shape[0] != adata.n_obs:
            corrected = corrected.T
        adata.obsm[adjusted_basis] = corrected

    sce.pp.harmony_integrate = harmony_integrate
    return {
        "harmonypy_version": _package_version("harmonypy"),
        "scanpy_version": _package_version("scanpy"),
        "corrected_orientation": "cells_by_components",
    }


def _run_spatialagent(request: dict[str, Any]) -> dict[str, Any]:
    source_path = Path(request["source_path"])
    sys.path.insert(0, str(source_path))
    os.chdir(source_path)
    os.environ["USE_LOCAL_EMBEDDINGS"] = str(request["use_local_embeddings"]).lower()

    from spatialagent.agent import SpatialAgent

    spatialagent_agent = importlib.import_module("spatialagent.agent")
    native_make_llm = spatialagent_agent.make_llm

    @functools.wraps(native_make_llm)
    def configured_make_llm(*args: Any, **kwargs: Any) -> Any:
        kwargs.setdefault("use_azure", request["use_azure"])
        return native_make_llm(*args, **kwargs)

    spatialagent_agent.make_llm = configured_make_llm

    spatialagent_utils = importlib.import_module("spatialagent.tool.utils")
    embedding_cache_path = Path(request["embedding_cache_path"])
    embedding_cache_path.mkdir(parents=True, exist_ok=True)
    spatialagent_utils._EMBEDDING_CACHE_DIR = embedding_cache_path
    harmony_compatibility = _configure_harmony_compatibility()

    model = request["model"]
    llm = configured_make_llm(model)
    agent = SpatialAgent(
        llm=llm,
        data_path=request["data_path"],
        save_path=request["save_path"],
        tool_retrieval=request["tool_retrieval"],
        tool_retrieval_method=request["tool_retrieval_method"],
        skill_retrieval=request["skill_retrieval"],
        auto_interpret_figures=False,
        act_timeout=request["act_timeout_seconds"],
        web_search_model=None,
    )
    state = agent.run(
        request["prompt"],
        config={
            "recursion_limit": request["recursion_limit"],
            "thread_id": "tissueagent-cell-annotation-baseline",
        },
    )
    messages = state.get("messages", []) if state else []
    return {
        "status": "success",
        "method": "spatialagent",
        "version": request.get("source_revision"),
        "model": model,
        "use_azure": request["use_azure"],
        "harmony_compatibility": harmony_compatibility,
        "messages": [_message_content(message) for message in messages],
        "final_response": _message_content(messages[-1]) if messages else None,
    }


def main() -> int:
    """Run one requested upstream baseline and persist a JSON result."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--method", choices=("biomni", "spatialagent"), required=True)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()
    request = json.loads(args.request.read_text(encoding="utf-8"))
    try:
        import scanpy as sc

        sc.settings.verbosity = 2
        result = _run_biomni(request) if args.method == "biomni" else _run_spatialagent(request)
        compatibility = _normalize_h5ad_for_parent(request["annotated_h5ad"])
        if compatibility is not None:
            result["h5ad_compatibility"] = compatibility
    except Exception as error:
        result = {
            "status": "error",
            "method": args.method,
            "error_type": type(error).__name__,
            "message": str(error),
        }
        args.result.write_text(json.dumps(result, indent=2), encoding="utf-8")
        traceback.print_exc()
        return 1
    args.result.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
