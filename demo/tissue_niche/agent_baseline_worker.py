"""Execute tissue-niche agents in their native Python environments."""

from __future__ import annotations

import argparse
import functools
import importlib
import importlib.metadata
import inspect
import json
import os
import errno
import random
import shutil
import socket
import sys
import traceback
from pathlib import Path
from queue import Empty, Queue
from typing import Any


def _link_artifact(source, destination):
    """Archive completed artifacts once per filesystem without duplicating matrices."""
    try:
        os.link(source, destination)
    except OSError as error:
        if error.errno != errno.EXDEV:
            raise
        shutil.copy2(source, destination)
    return str(destination)


def _text(value: Any) -> str:
    content = getattr(value, "content", value)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            item.get("text", "") if isinstance(item, dict) else str(item) for item in content
        )
    return str(content)


def _bind_factory(module: Any, name: str, model: str, audit: list, **settings: Any) -> Any:
    native = getattr(module, name)

    @functools.wraps(native)
    def configured(*args: Any, **kwargs: Any) -> Any:
        call = inspect.signature(native).bind_partial(*args, **kwargs)
        call.arguments["model"] = model
        call.arguments.update(settings)
        llm = native(*call.args, **call.kwargs)
        audit.append({"factory": f"{module.__name__}.{name}", "model": model, "settings": settings})
        return llm

    prefix = module.__name__.split(".")[0] + "."
    for loaded in list(sys.modules.values()):
        if loaded and getattr(loaded, "__name__", "").startswith(prefix):
            if getattr(loaded, name, None) is native:
                setattr(loaded, name, configured)
    setattr(module, name, configured)
    return configured


def _bind_openai_requests(
    model: str, audit: list, *, reasoning_effort: str | None = None, seed: int | None = None
) -> None:
    from openai.resources.chat.completions import AsyncCompletions, Completions
    from openai.resources.responses import AsyncResponses, Responses

    def wrap(native: Any, endpoint: str) -> Any:
        def record(kwargs: dict) -> dict:
            entry = {"endpoint": endpoint, "requested_model": kwargs.get("model"), "model": model}
            kwargs["model"] = model
            if reasoning_effort is not None:
                kwargs.pop("temperature", None)
                if "Responses" in endpoint:
                    kwargs["reasoning"] = {
                        **(kwargs.get("reasoning") or {}), "effort": reasoning_effort
                    }
                else:
                    kwargs["reasoning_effort"] = reasoning_effort
            if seed is not None and "Completions" in endpoint:
                kwargs["seed"] = seed
            for key in ("reasoning_effort", "reasoning", "seed", "temperature",
                        "max_tokens", "max_completion_tokens", "max_output_tokens"):
                entry[key] = kwargs.get(key)
            audit.append(entry)
            return entry

        def finish(entry: dict, response: Any) -> None:
            entry["response_model"] = getattr(response, "model", None)
            usage = getattr(response, "usage", None)
            entry["usage"] = usage.model_dump() if hasattr(usage, "model_dump") else None

        if inspect.iscoroutinefunction(inspect.unwrap(native)):

            @functools.wraps(native)
            async def invoke_async(*args: Any, **kwargs: Any) -> Any:
                entry = record(kwargs)
                response = await native(*args, **kwargs)
                finish(entry, response)
                return response

            return invoke_async

        @functools.wraps(native)
        def invoke(*args: Any, **kwargs: Any) -> Any:
            entry = record(kwargs)
            response = native(*args, **kwargs)
            finish(entry, response)
            return response

        return invoke

    for resource in (Completions, AsyncCompletions, Responses, AsyncResponses):
        resource.create = wrap(resource.create, resource.__name__)


def _run_biomni(request: dict) -> dict:
    version = importlib.metadata.version("biomni")
    if version != request["method_config"]["expected_version"]:
        raise RuntimeError(
            f"Expected Biomni {request['method_config']['expected_version']}, found {version}."
        )
    audit = []
    module = importlib.import_module("biomni.llm")
    source = request["method_config"]["source"]
    _bind_factory(module, "get_llm", request["model"], audit, source=source)
    from biomni.agent import A1
    from biomni.config import default_config

    default_config.llm = request["model"]
    default_config.source = source
    default_config.path = request["data_path"]
    default_config.timeout_seconds = request["execution_timeout_seconds"]
    agent = A1(
        path=request["data_path"],
        llm=request["model"],
        source=source,
        timeout_seconds=request["execution_timeout_seconds"],
        expected_data_lake_files=[],
    )
    native_stream = agent.app.stream

    def stream(*args: Any, **kwargs: Any) -> Any:
        kwargs["config"] = {
            **kwargs["config"],
            "recursion_limit": request["recursion_limit"],
            "configurable": {"thread_id": request["seed"]},
        }
        return native_stream(*args, **kwargs)

    agent.app.stream = stream
    workflow_error = None
    try:
        log, response = agent.go(request["prompt"])
    except Exception as error:
        traceback.print_exc()
        workflow_error = {"error_type": type(error).__name__, "error": str(error)}
        log, response = getattr(agent, "log", []), ""
    return {
        "version": version,
        "model_bindings": audit,
        "messages": [_text(item) for item in log],
        "final_response": _text(response),
        "workflow_error": workflow_error,
        "reference_data": "empty data lake; supplied cell types used as input",
    }


class _TextContentModel:
    def __init__(self, llm: Any):
        self.llm = llm

    def invoke(self, *args: Any, **kwargs: Any) -> Any:
        response = self.llm.invoke(*args, **kwargs)
        if not isinstance(response.content, str):
            response = response.model_copy(update={"content": _text(response)})
        return response


def _configure_niche_annotation(module: Any, contract: dict, audit: list) -> None:
    import matplotlib.cm as cm
    import matplotlib.pyplot as plt
    from pydantic import Field, create_model

    if not hasattr(cm, "get_cmap"):
        cm.get_cmap = plt.get_cmap
    tool = module.annotate_tissue_niches
    native = tool.func
    tool.args_schema = create_model(
        "BenchmarkNicheAnnotationInputs",
        __base__=tool.args_schema,
        anatomical_path=(
            str | None,
            Field(default=None, description="Optional anatomical image; None in this benchmark"),
        ),
    )

    @functools.wraps(native)
    def annotate(*args: Any, **kwargs: Any) -> Any:
        call = inspect.signature(native).bind_partial(*args, **kwargs)
        call.arguments["data_info"] = (
            json.dumps(contract["context"], sort_keys=True)
            + ". Annotation requirements: choose exactly one of "
            + json.dumps([*contract["labels"], contract["unmatched_label"]])
            + ". Multiple clusters may share the same high-level label. "
            + "Use Unmatched for uncertain assignments."
        )
        call.arguments["anatomical_path"] = None
        call.arguments["celltype_column"] = "cell_type"
        audit.append(dict(call.arguments))
        return native(*call.args, **call.kwargs)

    tool.func = annotate
    for name in ("_annotate_sample_batch", "_merge_niche_annotations_batch"):
        native_helper = getattr(module, name)

        def wrap(helper: Any) -> Any:
            @functools.wraps(helper)
            def invoke(*args: Any, **kwargs: Any) -> Any:
                call = inspect.signature(helper).bind(*args, **kwargs)
                call.arguments["llm"] = _TextContentModel(call.arguments["llm"])
                return helper(*call.args, **call.kwargs)

            return invoke

        setattr(module, name, wrap(native_helper))


def _configure_utag_clustering(module: Any) -> None:
    from pydantic import Field, create_model

    tool = module.run_utag_clustering
    tool.args_schema = create_model(
        "BenchmarkUtagInputs",
        __base__=tool.args_schema,
        slide_key=(str | None, Field(default=None, description="Optional sample/slide column")),
    )


def _run_spatialagent(request: dict) -> dict:
    sys.path.insert(0, request["source_path"])
    os.environ["USE_LOCAL_EMBEDDINGS"] = "true"
    module = importlib.import_module("spatialagent.agent")
    audit, annotation_calls = [], []
    make_llm = _bind_factory(
        module, "make_llm", request["model"], audit, use_azure=request["method_config"]["use_azure"]
    )
    interpretation = importlib.import_module("spatialagent.tool.interpretation")
    _configure_niche_annotation(interpretation, request["contract"], annotation_calls)
    analytics = importlib.import_module("spatialagent.tool.analytics")
    _configure_utag_clustering(analytics)
    utils = importlib.import_module("spatialagent.tool.utils")
    utils._EMBEDDING_CACHE_DIR = Path(request["data_path"]) / "embedding_cache"
    utils._EMBEDDING_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    llm = make_llm(request["model"])
    module.set_agent_model(request["model"], llm)
    agent = module.SpatialAgent(
        llm=llm,
        data_path=request["data_path"],
        save_path=request["output_dir"],
        tool_retrieval=True,
        tool_retrieval_method="llm",
        skill_retrieval=True,
        act_timeout=request["execution_timeout_seconds"],
        web_search_model=None,
    )
    if interpretation._get_subagent_model() != request["model"]:
        raise RuntimeError("SpatialAgent's annotation model differs from the requested model.")
    state, workflow_error = {}, None
    try:
        state = agent.run(
            request["prompt"],
            config={
                "recursion_limit": request["recursion_limit"],
                "thread_id": f"tissue-niche-{request['seed']}",
            },
        )
    except Exception as error:
        traceback.print_exc()
        workflow_error = {"error_type": type(error).__name__, "error": str(error)}
    messages = [_text(item) for item in (state or {}).get("messages", [])]
    return {
        "version": request["source_revision"],
        "model_bindings": audit,
        "annotation_calls": annotation_calls,
        "messages": messages,
        "final_response": messages[-1] if messages else "",
        "workflow_error": workflow_error,
        "auto_interpret_figures": agent.auto_interpret_figures,
        "annotation_prompt_binding": "public context and closed labels through data_info",
        "response_normalization": "text blocks only",
        "plotting_compatibility": "legacy cm.get_cmap uses pyplot.get_cmap when removed",
        "anatomical_reference": None,
        "tool_schema_binding": "anatomical_path and slide_key accept native None defaults",
    }


def _find_tissueagent_output(output_dir: Path) -> tuple[Path, list[str]]:
    import anndata as ad
    import h5py

    valid, non_hdf5 = [], []
    for path in sorted(output_dir.rglob("*annotated*.h5ad")):
        if path.name.endswith(".pending.h5ad"):
            continue
        if not h5py.is_hdf5(path):
            non_hdf5.append(str(path))
            continue
        data = ad.read_h5ad(path, backed="r")
        if "tissue_niche" in data.obs:
            valid.append(path)
        data.file.close()
    canonical = output_dir / "niche_annotated.h5ad"
    if canonical in valid:
        return canonical, non_hdf5
    if str(canonical) in non_hdf5:
        alias = canonical.read_text(errors="replace")
        targets = [path for path in valid if str(path.relative_to(output_dir)) in alias]
        if len(targets) == 1:
            return targets[0], non_hdf5
    if len(valid) == 1:
        return valid[0], non_hdf5
    raise RuntimeError(f"Expected one final annotated H5AD; found {valid}.")


def _run_tissueagent(request: dict) -> dict:
    runtime = Path(request["source_path"])
    sys.path[:0] = [str(runtime / "src"), str(runtime)]
    import config

    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        config.KERNEL_GATEWAY_PORT = listener.getsockname()[1]
    config.KERNEL_GATEWAY_URL = f"http://127.0.0.1:{config.KERNEL_GATEWAY_PORT}"
    from config import ACTIVE_PROJECT_DIR, DATA_DIR
    from models import model_seed_context, set_selection
    from agents.tissue_niche_context import bind_tissue_niche_context
    from agents.agent_registry.coding_agent.sandbox import KernelClient, LocalKernelGateway
    from graph.graph import create_tissueagent_graph
    from server.plan_store import plan_store

    uploads = ACTIVE_PROJECT_DIR / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    shutil.copy2(request["query_h5ad"], uploads / "query.h5ad")
    (ACTIVE_PROJECT_DIR / "outputs").mkdir(parents=True, exist_ok=True)
    set_selection(request["model"], request["model"])
    plan_store.reset()
    queue = Queue()
    kernel = KernelClient()
    kernel.set_workspace(DATA_DIR)
    gateway = LocalKernelGateway()
    prompt = request["prompt"].replace(request["query_h5ad"], "project/uploads/query.h5ad")
    prompt = prompt.replace(request["annotated_h5ad"], "project/outputs/niche_annotated.h5ad")
    task_context = {
        "input_path": "project/uploads/query.h5ad",
        "celltype_key": "cell_type",
        "spatial_key": "spatial",
        "annotation_col": request["contract"]["prediction_key"],
        "allowed_labels": request["contract"]["labels"],
        "unmatched_label": request["contract"]["unmatched_label"],
        "output_path": "project/outputs/niche_annotated.h5ad",
        "dataset_context": request["contract"]["context"],
    }
    result, workflow_error = {}, None
    try:
        gateway.ensure_running()
        with model_seed_context(request["seed"]), bind_tissue_niche_context(task_context):
            graph = create_tissueagent_graph(queue, lambda model: model, kernel_client=kernel)
            result = graph.compile().invoke(
                {"messages": [("user", prompt)]},
                config={"recursion_limit": request["recursion_limit"]},
            )
    except Exception as error:
        traceback.print_exc()
        workflow_error = {"error_type": type(error).__name__, "error": str(error)}
    finally:
        kernel.shutdown_kernels()
        gateway.stop()
    events = []
    while True:
        try:
            events.append(queue.get_nowait())
        except Empty:
            break
    output_dir = ACTIVE_PROJECT_DIR / "outputs"
    annotated, non_hdf5 = _find_tissueagent_output(output_dir)
    _link_artifact(annotated, request["annotated_h5ad"])
    shutil.copytree(
        output_dir, Path(request["output_dir"]) / "native", copy_function=_link_artifact
    )
    return {
        "version": request["source_revision"],
        "executed_prompt": prompt,
        "events": events,
        "messages": [_text(m) for m in result.get("messages", [])],
        "model_bindings": [{"model": request["model"], "roles": "orchestration and worker"}],
        "collected_native_h5ad": str(annotated),
        "ignored_non_hdf5_outputs": non_hdf5,
        "workflow_status": "failed_after_annotation" if workflow_error else "success",
        "workflow_error": workflow_error,
        "task_context": task_context,
    }


def _export_predictions(request: dict) -> dict:
    import anndata as ad
    import pandas as pd

    query = ad.read_h5ad(request["query_h5ad"], backed="r")
    annotated = ad.read_h5ad(request["annotated_h5ad"], backed="r")
    try:
        if not annotated.obs_names.is_unique:
            raise ValueError("Agent returned duplicate cell IDs.")
        if not set(annotated.obs_names).issubset(query.obs_names):
            raise ValueError("Agent returned foreign cell IDs.")
        expected_types = query.obs["cell_type"].reindex(annotated.obs_names).astype("string")
        if not expected_types.equals(annotated.obs["cell_type"].astype("string")):
            raise ValueError("Agent changed the supplied cell-type labels.")
        frame = pd.DataFrame({"raw_label": annotated.obs["tissue_niche"].astype("string")})
        frame.index.name = "cell_id"
        frame.to_csv(Path(request["output_dir"]) / "raw_predictions.tsv", sep="\t")
        return {"n_input_cells": query.n_obs, "n_returned_cells": annotated.n_obs}
    finally:
        query.file.close()
        annotated.file.close()


def main() -> int:
    """Execute one public request and persist native results or a failure record."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--result", required=True, type=Path)
    args = parser.parse_args()
    request = json.loads(args.request.read_text())
    model_calls = []
    result = {}
    try:
        import numpy as np

        random.seed(request["seed"])
        np.random.seed(request["seed"])
        _bind_openai_requests(
            request["model"], model_calls,
            reasoning_effort=request.get("reasoning_effort"), seed=request["seed"],
        )
        runners = {
            "biomni": _run_biomni,
            "spatialagent": _run_spatialagent,
            "tissueagent": _run_tissueagent,
        }
        result = runners[request["method"]](request)
        if request["method"] != "tissueagent":
            annotated, non_hdf5 = _find_tissueagent_output(Path(request["output_dir"]))
            destination = Path(request["annotated_h5ad"])
            if annotated != destination:
                if destination.exists():
                    destination.rename(destination.with_suffix(".alias.txt"))
                _link_artifact(annotated, destination)
            result.update(
                collected_native_h5ad=str(annotated), ignored_non_hdf5_outputs=non_hdf5
            )
        result.update(_export_predictions(request))
        result.update(status="success", model=request["model"], method=request["method"])
        result["seed_policy"] = "Python/NumPy seeded; upstream/API determinism is not guaranteed"
    except Exception as error:
        traceback.print_exc()
        result.update(status="failed", error_type=type(error).__name__, error=str(error))
    result["openai_model_calls"] = model_calls
    result["python_version"] = sys.version
    result["dependency_versions"] = {}
    for name in (
        "anndata",
        "scanpy",
        "numpy",
        "scipy",
        "pandas",
        "matplotlib",
        "langchain-core",
        "langgraph",
        "openai",
    ):
        try:
            result["dependency_versions"][name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            result["dependency_versions"][name] = None
    args.result.write_text(json.dumps(result, indent=2, default=str) + "\n")
    return 0 if result["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
