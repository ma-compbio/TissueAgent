"""Run upstream agent baselines on the frozen cohorts of a comparison study."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import time
import traceback
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
STUDY = ROOT / (
    "demo/outputs/cell_annotation/"
    "tissueagent-repeatability-heart-bcl-scope-v11-han-20260825-v1/"
    "study_manifest_posthoc_mapping_v1.json"
)
RUN_ID = "agent-baselines-matched-gpt51-full-20260906-v1"


def matched_task_prompt(spec: dict) -> tuple[str, list[dict]]:
    """Recover the saved TissueAgent task, replacing only the two IO paths."""
    from .benchmarks import _sha256

    templates, sources = [], []
    for run in spec["runs"]:
        path = Path(run["tissueagent_run_json"])
        prompt = json.loads(path.read_text())["prompt"]
        template, query_count = re.subn(
            r"^(Annotate cell types in (?:spatial )?AnnData )'[^']+'",
            r"\1'<QUERY_H5AD>'",
            prompt,
        )
        template, output_count = re.subn(
            r"Save the annotated H5AD to '[^']+'\.$",
            "Save the annotated H5AD to '<ANNOTATED_H5AD>'.",
            template,
        )
        if query_count != 1 or output_count != 1:
            raise ValueError(f"Cannot identify TissueAgent task IO paths: {path}")
        templates.append(template)
        sources.append({"path": str(path), "sha256": _sha256(path), "prompt": prompt})
    if len(set(templates)) != 1:
        raise ValueError("TissueAgent replicates have different scientific task prompts.")
    return templates[0], sources


def configure_runtime() -> None:
    """Configure writable runtime caches and the installed isolated environments."""
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
    env_root = Path("/data/magroup/etrop/tissueagent-conda/envs")
    os.environ.setdefault("BIOMNI_PYTHON", str(env_root / "tissueagent_biomni_008/bin/python"))
    os.environ.setdefault(
        "SPATIALAGENT_PYTHON", str(env_root / "tissueagent_spatialagent_e51ec0f/bin/python")
    )
    os.environ.setdefault("SPATIALAGENT_REPO", "/home/etrop/tissueagent-baselines/SpatialAgent")
    os.environ["PYTHONUNBUFFERED"] = "1"


def prepare_frozen_run(spec: dict, run_id: str) -> dict:
    """Copy the exact previously evaluated inputs into a fresh blinded run."""
    from .benchmarks import _sha256, load_manifest, validate_selection_blind_query

    source_manifest = Path(spec["runs"][0]["prepared_run_json"])
    prepared = json.loads(source_manifest.read_text())
    run_dir = ROOT / "demo/outputs/cell_annotation" / spec["dataset_id"] / run_id
    prepared_path = run_dir / "prepared_run.json"
    if prepared_path.exists():
        return json.loads(prepared_path.read_text())
    blind_id = hashlib.sha256(f"{spec['dataset_id']}:{run_id}".encode()).hexdigest()[:30]
    query_dir = run_dir / "benchmark_input" / blind_id
    query_dir.mkdir(parents=True, exist_ok=False)
    for key, destination in {
        "query_h5ad": query_dir / "query.h5ad",
        "ground_truth_tsv": run_dir / "ground_truth.tsv",
        "label_mapping_json": run_dir / "label_mapping.json",
    }.items():
        source = ROOT / prepared[key]
        shutil.copy2(source, destination)
        assert _sha256(source) == _sha256(destination)
        prepared[key] = str(destination.relative_to(ROOT))
    assert _sha256(ROOT / prepared["query_h5ad"]) == spec["expected_prepared_query_sha256"]
    assert (
        _sha256(ROOT / prepared["label_mapping_json"]) == spec["expected_evaluation_mapping_sha256"]
    )
    prepared.update(
        run_id=run_id,
        run_dir=str(run_dir.relative_to(ROOT)),
        selection_blind_id=blind_id,
        prepared_run_json=str(prepared_path.relative_to(ROOT)),
        timestamp_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        frozen_input_source={"path": str(source_manifest), "sha256": _sha256(source_manifest)},
    )
    prepared["validation"]["h5ad_path"] = str(ROOT / prepared["query_h5ad"])
    prepared["selection_blind_query_audit"] = validate_selection_blind_query(
        ROOT / prepared["query_h5ad"], load_manifest(spec["dataset_id"])["query"]
    )
    prepared_path.write_text(json.dumps(prepared, indent=2))
    return prepared


def run_one(
    spec: dict, method: str, run_id: str, evaluate_only: bool, resume_from: Path | None = None
) -> None:
    """Execute and score one baseline with the study's existing label contract."""
    from .baselines import run_biomni, run_spatialagent
    from .evaluation import evaluate_predictions, materialize_prediction_mapping
    from src.models import build_chat_model, model_seed_context

    prepared = prepare_frozen_run(spec, run_id)
    run_dir = ROOT / prepared["run_dir"]
    prediction = run_dir / f"{method}_predictions.tsv"
    if not prediction.exists() and not evaluate_only:
        runner = run_biomni if method == "biomni" else run_spatialagent
        template, sources = matched_task_prompt(spec)
        (run_dir / "task_prompt_alignment.json").write_text(
            json.dumps(
                {
                    "protocol": "matched_task_original_query_v1",
                    "task_prompt_template": template,
                    "template_sha256": hashlib.sha256(template.encode()).hexdigest(),
                    "tissueagent_prompt_sources": sources,
                    "changes_to_scientific_task": "input and output paths only",
                    "adapter_preprocessing": "none",
                    "execution_timeout_seconds": 21600,
                    "process_timeout_seconds": 43200,
                    "runtime_environment": {
                        key: os.environ.get(key)
                        for key in ("PYTHONPATH", "TMPDIR", "XDG_CACHE_HOME", "HF_HOME")
                    },
                },
                indent=2,
            )
        )
        options = {"resume_from": resume_from} if resume_from is not None else {}
        runner(
            prepared,
            model="gpt-5.1",
            task_prompt_template=template,
            execution_timeout_seconds=21600,
            process_timeout_seconds=43200,
            **options,
        )
    mapping = run_dir / f"{method}_prediction_mapping.json"
    if not mapping.exists():
        with model_seed_context(42):
            materialize_prediction_mapping(
                prepared["label_mapping_json"],
                prediction,
                mapping,
                prediction_method=method,
                model=build_chat_model("gpt-5.1"),
                model_metadata={"model_id": "gpt-5.1", "provider": "openai", "request_seed": 42},
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
    parser.add_argument("--method", choices=("biomni", "spatialagent"), required=True)
    parser.add_argument("--dataset", action="append")
    parser.add_argument("--run-id", default=RUN_ID)
    parser.add_argument("--evaluate-only", action="store_true")
    parser.add_argument("--resume-from", type=Path)
    args = parser.parse_args()
    if args.method == "biomni" and args.resume_from is not None:
        parser.error("Autonomous Biomni runs must start from the original query, without resume.")
    configure_runtime()
    study = json.loads(STUDY.read_text())
    failed = []
    for spec in study["datasets"]:
        dataset = spec["dataset_id"]
        if args.dataset and dataset not in args.dataset:
            continue
        print(f"START {dataset} {args.method}", flush=True)
        try:
            run_one(
                spec,
                args.method,
                f"{args.run_id}-{args.method}",
                args.evaluate_only,
                args.resume_from,
            )
        except Exception:
            traceback.print_exc()
            failed.append(dataset)
        else:
            print(f"DONE {dataset} {args.method}", flush=True)
    print(json.dumps({"method": args.method, "failed": failed}), flush=True)
    return int(bool(failed))


if __name__ == "__main__":
    raise SystemExit(main())
