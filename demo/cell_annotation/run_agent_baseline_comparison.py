"""Prepare, run, and score agent comparisons from versioned benchmark settings."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import traceback
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
CONFIG = Path(__file__).with_name("configs") / "agent_comparison.yaml"
RUN_ID = "agent-baselines-matched-gpt51-full-20260906-v1"


def load_config(path: Path = CONFIG) -> dict:
    """Load the comparison's model, task, cohort, and scoring settings."""
    config = yaml.safe_load(path.read_text())
    datasets = [spec["dataset_id"] for spec in config["datasets"]]
    if not datasets or len(datasets) != len(set(datasets)):
        raise ValueError("Comparison datasets must be nonempty and unique.")
    return config


def configure_runtime() -> None:
    """Configure writable runtime caches without machine-specific interpreter paths."""
    cache = ROOT / "workspace/cache/runtime"
    cache.mkdir(parents=True, exist_ok=True)
    for variable, suffix in {
        "TMPDIR": "",
        "XDG_CACHE_HOME": "xdg",
        "HF_HOME": "huggingface",
        "UV_CACHE_DIR": "uv",
        "NUMBA_CACHE_DIR": "numba",
        "MPLCONFIGDIR": "matplotlib",
        "TORCH_HOME": "torch",
    }.items():
        path = cache / suffix
        path.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault(variable, str(path))
    for variable in (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMBA_NUM_THREADS",
    ):
        os.environ.setdefault(variable, "8")
    os.environ["PYTHONUNBUFFERED"] = "1"


def prepare_run(spec: dict, run_id: str, config: dict, *, existing_only: bool = False) -> dict:
    """Prepare from dataset sources and verify the original comparison's input identity."""
    import pandas as pd

    from .baselines import _agent_task_prompt
    from .benchmarks import (
        _label_contract_sha256,
        _sha256,
        load_manifest,
        prepare_benchmark,
        validate_selection_blind_query,
    )

    if Path(run_id).name != run_id or run_id in {"", ".", ".."}:
        raise ValueError("Run ID must be a single nonempty path component.")
    manifest = load_manifest(spec["dataset_id"])
    template = _agent_task_prompt(Path("<QUERY_H5AD>"), Path("<ANNOTATED_H5AD>"), manifest)
    if template != spec["task_prompt_template"]:
        raise ValueError("Dataset manifest no longer matches the configured scientific task.")
    mapping_source = ROOT / spec["evaluation_mapping"]
    if _sha256(mapping_source) != spec["expected_evaluation_mapping_sha256"]:
        raise ValueError("Configured evaluation mapping differs from the frozen comparison.")
    run_dir = ROOT / "demo/outputs/cell_annotation" / spec["dataset_id"] / run_id
    prepared_path = run_dir / "prepared_run.json"
    if prepared_path.exists():
        prepared = json.loads(prepared_path.read_text())
    else:
        if existing_only:
            raise FileNotFoundError(
                f"Evaluation requires an existing prepared run: {prepared_path}"
            )
        prepared = prepare_benchmark(
            spec["dataset_id"], run_mode="full", run_id=run_id, random_seed=config["random_seed"]
        )
        mapping = json.loads(mapping_source.read_text())
        if _label_contract_sha256(mapping) != prepared["label_contract_sha256"]:
            raise ValueError("Evaluation mapping changed the prepared biological label contract.")
        shutil.copy2(mapping_source, ROOT / prepared["label_mapping_json"])

    snapshot = run_dir / "comparison_config.yaml"
    if snapshot.exists() and yaml.safe_load(snapshot.read_text()) != config:
        raise ValueError("Comparison settings changed; use a new run ID.")
    if prepared["dataset_id"] != spec["dataset_id"] or prepared["run_mode"] != "full":
        raise ValueError("Prepared run is not the requested full dataset.")
    for key, expected in (
        ("query_h5ad", "expected_prepared_query_sha256"),
        ("ground_truth_tsv", "expected_ground_truth_sha256"),
        ("label_mapping_json", "expected_evaluation_mapping_sha256"),
    ):
        if _sha256(ROOT / prepared[key]) != spec[expected]:
            raise ValueError(f"Prepared {key} differs from the frozen comparison.")
    mapping = json.loads((ROOT / prepared["label_mapping_json"]).read_text())
    if _label_contract_sha256(mapping) != spec["expected_label_contract_sha256"]:
        raise ValueError("Prepared label contract differs from the frozen comparison.")
    validate_selection_blind_query(ROOT / prepared["query_h5ad"], manifest["query"])
    truth = pd.read_csv(ROOT / prepared["ground_truth_tsv"], sep="\t", index_col=0)
    excluded = truth[prepared["ground_truth_column"]].isin(spec["expected_exclusions"])
    observed = (prepared["n_obs"], len(truth), int((~excluded).sum()), int(excluded.sum()))
    expected = (
        spec["expected_n_obs"],
        spec["expected_n_obs"],
        spec["expected_n_truth_cells"],
        spec["expected_n_excluded_truth_cells"],
    )
    if observed != expected:
        raise ValueError(f"Comparison cohort changed: expected {expected}, observed {observed}.")
    if not snapshot.exists():
        snapshot.write_text(yaml.safe_dump(config, sort_keys=False))
    return prepared


def run_one(
    spec: dict,
    method: str,
    run_id: str,
    evaluate_only: bool,
    resume_from: Path | None = None,
    *,
    config: dict,
) -> None:
    """Execute and score one agent with the comparison's frozen task and label contract."""
    from .baselines import run_biomni, run_spatialagent
    from .benchmarks import _sha256
    from .evaluation import evaluate_predictions, materialize_prediction_mapping
    from models import build_chat_model, get_model_spec, model_seed_context

    prepared = prepare_run(spec, run_id, config, existing_only=evaluate_only)
    run_dir = ROOT / prepared["run_dir"]
    prediction = run_dir / f"{method}_predictions.tsv"
    if prediction.exists():
        alignment = json.loads((run_dir / "task_prompt_alignment.json").read_text())
        if alignment["task_prompt_template"] != spec["task_prompt_template"]:
            raise ValueError("Existing predictions used a different scientific task.")
        if method != "tissueagent":
            record = json.loads((run_dir / f"{method}_predictions.run.json").read_text())
            if record["model"] != config["model"]:
                raise ValueError("Existing predictions used a different model.")
            for setting in ("execution_timeout_seconds", "process_timeout_seconds"):
                if alignment[setting] != config[setting]:
                    raise ValueError(f"Existing predictions used a different {setting}.")
    if not prediction.exists() and not evaluate_only:
        template = spec["task_prompt_template"]
        (run_dir / "task_prompt_alignment.json").write_text(
            json.dumps(
                {
                    "protocol": "matched_task_original_query_v1",
                    "task_prompt_template": template,
                    "template_sha256": hashlib.sha256(template.encode()).hexdigest(),
                    "comparison_config": "comparison_config.yaml",
                    "comparison_config_sha256": _sha256(run_dir / "comparison_config.yaml"),
                    "changes_to_scientific_task": "input and output paths only",
                    "adapter_preprocessing": "none",
                    "execution_timeout_seconds": config["execution_timeout_seconds"],
                    "process_timeout_seconds": config["process_timeout_seconds"],
                    "runtime_environment": {
                        key: os.environ.get(key)
                        for key in ("PYTHONPATH", "TMPDIR", "XDG_CACHE_HOME", "HF_HOME")
                    },
                },
                indent=2,
            )
        )
        if method == "tissueagent":
            from models import get_selection, set_selection

            from .benchmarks import load_manifest
            from .tissueagent_runner import _evaluation_prompt, run_tissueagent

            native_prompt = _evaluation_prompt(
                load_manifest(spec["dataset_id"]), Path("<QUERY_H5AD>"), Path("<ANNOTATED_H5AD>")
            )
            if native_prompt != template:
                raise ValueError("TissueAgent's scientific task differs from the comparison.")
            previous = get_selection()
            try:
                set_selection(config["model"], config["model"])
                with model_seed_context(config["tissueagent_seed"]):
                    run_tissueagent(prepared)
            finally:
                set_selection(**previous)
        else:
            runner = run_biomni if method == "biomni" else run_spatialagent
            options = {"resume_from": resume_from} if resume_from is not None else {}
            runner(
                prepared,
                model=config["model"],
                task_prompt_template=template,
                execution_timeout_seconds=config["execution_timeout_seconds"],
                process_timeout_seconds=config["process_timeout_seconds"],
                **options,
            )
    if not prediction.exists():
        raise FileNotFoundError(f"No {method} predictions to evaluate: {prediction}")
    mapping = run_dir / f"{method}_prediction_mapping.json"
    if mapping.exists():
        mapper = json.loads(mapping.read_text()).get("model")
        if mapper and (
            mapper["model_id"] != config["prediction_mapping_model"]
            or mapper["request_seed"] != config["prediction_mapping_seed"]
        ):
            raise ValueError("Existing prediction mapping used different evaluator settings.")
    if not mapping.exists():
        with model_seed_context(config["prediction_mapping_seed"]):
            materialize_prediction_mapping(
                prepared["label_mapping_json"],
                prediction,
                mapping,
                prediction_method=method,
                model=build_chat_model(config["prediction_mapping_model"]),
                model_metadata={
                    "model_id": config["prediction_mapping_model"],
                    "provider": get_model_spec(config["prediction_mapping_model"]).provider,
                    "request_seed": config["prediction_mapping_seed"],
                },
            )
    metrics = evaluate_predictions(
        prepared,
        prediction_paths={method: prediction},
        label_space=spec["expected_label_space"],
        exclude_ground_truth_raw_labels=spec["expected_exclusions"],
        prediction_mapping_path=mapping,
        output_stem=f"metrics_{method}",
    )
    print(metrics.to_string(), flush=True)


def main() -> int:
    """Run the selected method on each requested full cohort."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--method",
        choices=("tissueagent", "biomni", "spatialagent"),
        action="append",
        required=True,
    )
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--dataset", action="append")
    parser.add_argument("--run-id", default=RUN_ID)
    phases = parser.add_mutually_exclusive_group()
    phases.add_argument("--evaluate-only", action="store_true")
    phases.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--resume-from", type=Path)
    args = parser.parse_args()
    if args.resume_from is not None and args.method != ["spatialagent"]:
        parser.error("--resume-from is supported only with --method spatialagent.")
    config = load_config(args.config)
    known = {spec["dataset_id"] for spec in config["datasets"]}
    if unknown := set(args.dataset or []) - known:
        parser.error(f"Unknown comparison datasets: {', '.join(sorted(unknown))}")
    configure_runtime()
    failed = []
    for spec in config["datasets"]:
        dataset = spec["dataset_id"]
        if args.dataset and dataset not in args.dataset:
            continue
        for method in dict.fromkeys(args.method):
            print(f"START {dataset} {method}", flush=True)
            try:
                run_id = f"{args.run_id}-{method}"
                if args.prepare_only:
                    prepare_run(spec, run_id, config)
                else:
                    run_one(
                        spec, method, run_id, args.evaluate_only, args.resume_from, config=config
                    )
            except Exception:
                traceback.print_exc()
                failed.append({"dataset": dataset, "method": method})
            else:
                print(f"DONE {dataset} {method}", flush=True)
    print(json.dumps({"methods": args.method, "failed": failed}), flush=True)
    return int(bool(failed))


if __name__ == "__main__":
    raise SystemExit(main())
