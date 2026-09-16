"""Prepare and run the TissueAgent, Biomni and SpatialAgent tissue-niche study."""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from itertools import zip_longest
from pathlib import Path

import yaml

from .agent_baselines import preflight, run_method, safe_id
from .agent_inputs import PREPARED_ROOT, ROOT, load_prepared, prepare_dataset
from .protocol import LEGACY_PROMPT_VERSION, METHODS, PROMPT_VERSION, PROTOCOL, sha256, write_json

CONFIG = Path(__file__).with_name("configs") / "agent_comparison.yaml"
OUTPUT_ROOT = ROOT / "demo/outputs/tissue_niche/agent_comparisons"


def _run_job(dataset: str, method: str, seed: int, section: dict, config: dict, study_dir: Path):
    model = config.get(method, {}).get("model", config["model"])
    output = study_dir / dataset / method / f"seed-{seed}" / section["section_id"]
    print(f"Starting {dataset} {method} seed={seed} {section['section_id']}", flush=True)
    try:
        record = run_method(
            section, method=method, output_dir=output, config=config, model=model, seed=seed
        )
    except Exception as error:
        if (output / "run_record.json").exists():
            raise RuntimeError(
                f"Unindexed attempt exists at {output}; inspect it before resuming."
            ) from error
        output.mkdir(parents=True, exist_ok=True)
        record = {
            "protocol": PROTOCOL,
            "prompt_version": PROMPT_VERSION,
            "method": method,
            "model": model,
            "seed": seed,
            "section_id": section["section_id"],
            "query_sha256": section["query_sha256"],
            "status": "failed",
            "error": str(error),
        }
        write_json(output / "run_record.json", record)
    print(
        f"Finished {dataset} {method} seed={seed} {section['section_id']}: {record['status']}",
        flush=True,
    )
    return {
        "prompt_version": PROMPT_VERSION,
        "dataset": dataset,
        "method": method,
        "seed": seed,
        "section_id": section["section_id"],
        "status": record["status"],
        "model": model,
        "record": str((output / "run_record.json").relative_to(study_dir)),
        "record_sha256": sha256(output / "run_record.json"),
    }


def run_study(
    config: dict, study_dir: Path, *, prepared_root: Path = PREPARED_ROOT, resume: bool = False
) -> dict:
    """Run the declared section matrix, preserving all previously recorded attempts."""
    for key in ("datasets", "methods", "seeds"):
        if not config[key] or len(set(config[key])) != len(config[key]):
            raise ValueError(f"{key} must be a nonempty list without duplicates.")
    if set(config["methods"]) - set(METHODS):
        raise ValueError("Study contains unsupported methods.")
    for method in config["methods"]:
        seeds = config.get(method, {}).get("seeds", config["seeds"])
        if not seeds or len(set(seeds)) != len(seeds):
            raise ValueError(f"{method} seeds must be a nonempty list without duplicates.")
    for dataset in config["datasets"]:
        safe_id(dataset)
    manifest_path = study_dir / "study_manifest.json"
    if manifest_path.exists():
        if not resume:
            raise FileExistsError(f"Study exists: {study_dir}; use --resume for the same config.")
        manifest = json.loads(manifest_path.read_text())
        if manifest["config"] != config:
            raise ValueError("Resume configuration differs from the frozen study.")
        if manifest.get("prompt_version", LEGACY_PROMPT_VERSION) != PROMPT_VERSION:
            raise ValueError("Prompt version differs from the frozen study; use a new study ID.")
    else:
        study_dir.mkdir(parents=True, exist_ok=False)
        preparations = {
            dataset: load_prepared(dataset, output_root=prepared_root)
            for dataset in config["datasets"]
        }
        manifest = {
            "protocol": PROTOCOL,
            "prompt_version": PROMPT_VERSION,
            "config": config,
            "preparations": preparations,
            "runs": [],
        }
        write_json(manifest_path, manifest)
    previous = {
        (r["dataset"], r["method"], r["seed"], r["section_id"]): r for r in manifest["runs"]
    }
    jobs_by_method = {method: [] for method in config["methods"]}
    for dataset in config["datasets"]:
        for method in config["methods"]:
            for seed in config.get(method, {}).get("seeds", config["seeds"]):
                for section in manifest["preparations"][dataset]["sections"]:
                    key = (dataset, method, seed, section["section_id"])
                    if key in previous:
                        prior = previous[key]
                        if sha256(study_dir / prior["record"]) != prior["record_sha256"]:
                            raise ValueError("An archived run record was modified.")
                        continue
                    jobs_by_method[method].append((dataset, method, seed, section))
    jobs = [job for group in zip_longest(*jobs_by_method.values()) for job in group if job]
    with ThreadPoolExecutor(max_workers=config.get("max_workers", 1)) as pool:
        futures = [pool.submit(_run_job, *job, config, study_dir) for job in jobs]
        for future in as_completed(futures):
            manifest["runs"].append(future.result())
            write_json(manifest_path, manifest)
    return manifest


def main() -> int:
    """Expose preparation, dependency preflight and explicit paid execution separately."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["prepare", "preflight", "run"])
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--dataset", action="append")
    parser.add_argument("--method", choices=METHODS, action="append")
    parser.add_argument("--model")
    parser.add_argument("--seed", type=int, action="append")
    parser.add_argument("--study-id", default="tissue-niche-agents-gpt51-v3")
    parser.add_argument("--prepared-root", type=Path, default=PREPARED_ROOT)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--runtime-root", type=Path)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    config = yaml.safe_load(args.config.read_text())
    for key, value in (
        ("datasets", args.dataset),
        ("methods", args.method),
        ("model", args.model),
        ("seeds", args.seed),
    ):
        if value is not None:
            config[key] = value
    if args.runtime_root:
        config["runtime_root"] = str(args.runtime_root.resolve())
    for dataset in config["datasets"]:
        safe_id(dataset)
    if args.phase == "prepare":
        result = [
            prepare_dataset(dataset, output_root=args.prepared_root)
            for dataset in config["datasets"]
        ]
    elif args.phase == "preflight":
        result = {method: preflight(method, config) for method in config["methods"]}
    else:
        result = run_study(
            config,
            args.output_root / safe_id(args.study_id),
            prepared_root=args.prepared_root,
            resume=args.resume,
        )
    print(json.dumps(result, indent=2))
    if args.phase == "run" and any(run["status"] != "success" for run in result["runs"]):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
