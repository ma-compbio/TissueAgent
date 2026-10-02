"""Run matched baseline repetitions and combine them with frozen TissueAgent results."""

from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
from pathlib import Path

import pandas as pd
import yaml

from .agent_inputs import load_prepared
from .agent_collection import collect_study
from .evaluation import evaluate_study, load_predictions, load_study, load_truth
from .plot_agent_comparison import DATASET_NAMES, METHOD_NAMES, plot_performance
from .protocol import PROMPT_VERSION, scientific_prompt, sha256, validate_query, write_json
from .run_agents import run_study


def audit_reference(reference: Path, config: dict) -> dict:
    """Verify every reference run and the exact public task before new inference."""
    study = load_study(reference)
    if study["prompt_version"] != PROMPT_VERSION:
        raise ValueError("The reference must use the current shared prompt.")
    if study["config"]["methods"] != ["tissueagent"]:
        raise ValueError("Supply the frozen TissueAgent-only study.")
    for key in (
        "model",
        "seeds",
        "recursion_limit",
        "execution_timeout_seconds",
        "process_timeout_seconds",
    ):
        if config[key] != study["config"][key]:
            raise ValueError(f"Baseline configuration differs from TissueAgent: {key}.")
    if set(config["datasets"]) != set(study["config"]["datasets"]):
        raise ValueError("Dataset cohorts differ.")
    if config["methods"] != ["biomni", "spatialagent"]:
        raise ValueError("The new cohort must contain both native baselines.")
    if config["model"] != "gpt-5.1" or config["reasoning_effort"] != "high":
        raise ValueError("The latest TissueAgent source uses GPT-5.1 with high reasoning.")
    inputs, truths = [], {}
    for dataset, prepared in study["preparations"].items():
        if load_prepared(dataset) != prepared:
            raise ValueError(f"Prepared inputs differ from the reference: {dataset}.")
        truths[dataset] = load_truth(prepared)
        for section in prepared["sections"]:
            inputs.append(
                {
                    "dataset": dataset,
                    "section_id": section["section_id"],
                    **validate_query(Path(section["query_h5ad"])),
                }
            )
    expected = {
        (dataset, seed, section["section_id"])
        for dataset, prepared in study["preparations"].items()
        for seed in config["seeds"]
        for section in prepared["sections"]
    }
    actual = {(e["dataset"], e["seed"], e["section_id"]) for e in study["runs"]}
    if actual != expected or len(actual) != len(study["runs"]):
        raise ValueError("The frozen TissueAgent cohort is incomplete or duplicated.")
    runs = []
    for entry in study["runs"]:
        section = next(
            s
            for s in study["preparations"][entry["dataset"]]["sections"]
            if s["section_id"] == entry["section_id"]
        )
        truth = truths[entry["dataset"]]
        ids = truth.index[truth["section_id"] == entry["section_id"]]
        load_predictions(reference, entry, section, ids)
        record_path = reference / entry["record"]
        record = json.loads(record_path.read_text())
        request = json.loads((record_path.parent / "worker_request.json").read_text())
        prompt = scientific_prompt(
            section["contract"], request["query_h5ad"], request["annotated_h5ad"]
        )
        if request["prompt"] != prompt or request["execution_prompt"]:
            raise ValueError("An executed reference request differs from the shared task.")
        models_source = Path(request["source_path"]) / "src/models.py"
        if sha256(models_source) != sha256(Path(__file__).parents[2] / "src/models.py"):
            raise ValueError("Inspect changed reference model settings before inference.")
        runs.append(
            {
                **entry,
                "models_source_sha256": sha256(models_source),
                "source_snapshot_sha256": record["runtime"]["source_snapshot_sha256"],
            }
        )
    return {
        "reference_study": str(reference.resolve()),
        "reference_manifest_sha256": sha256(reference / "study_manifest.json"),
        "prompt_version": PROMPT_VERSION,
        "inputs": inputs,
        "reference_runs": runs,
        "home_free_bytes_before": shutil.disk_usage(Path(__file__).parents[2]).free,
        "reasoning_evidence": "Preserved models.py selects high; old payload logs omit it",
        "matching": [
            "task text except paths",
            "query bytes",
            "context and allowed labels",
            "model and reasoning effort",
            "wall-clock and graph limits",
            "scoring cohort",
        ],
        "repairs": [
            "match GPT-5.1 high reasoning at the SDK boundary",
            "apply shared graph limit through native Biomni go/stream",
            "collect unambiguous annotations after baseline workflow errors",
            "preserve native diagnostics if output export fails",
            "accept SpatialAgent native slide_key=None default",
            "restore SpatialAgent default automatic figure interpretation",
            "supply missing Biomni leidenalg 0.10.2 through a dependency overlay",
        ],
        "remaining_differences": [
            "Native prompts, tools, skills, graph semantics and scientific parameter choices",
            "Biomni uses Responses, which has no seed argument; Chat calls receive run seed",
            "SDK model bindings do not cover arbitrary subprocesses or direct HTTP",
            "Separate processes and stripped files do not enforce OS-level truth isolation",
            "TissueAgent high reasoning is verified from frozen source, not historical payloads",
            "These datasets have been used during development; "
            "this benchmark is not an untouched validation cohort",
        ],
    }


def compose_studies(reference: Path, baselines: Path, output: Path) -> dict:
    """Reference original immutable records without copying matrices or selecting attempts."""
    original, fresh = load_study(reference), load_study(baselines)
    if original["prompt_version"] != fresh["prompt_version"]:
        raise ValueError("Cannot combine different prompt versions.")
    if original["preparations"] != fresh["preparations"]:
        raise ValueError("Cannot combine different prepared inputs or truth.")
    for key in (
        "model",
        "seeds",
        "recursion_limit",
        "execution_timeout_seconds",
        "process_timeout_seconds",
    ):
        if original["config"][key] != fresh["config"][key]:
            raise ValueError(f"Cannot combine different {key} conditions.")
    combined = copy.deepcopy(fresh)
    combined["config"]["methods"] = ["tissueagent", "biomni", "spatialagent"]
    combined["config"]["tissueagent"] = original["config"].get("tissueagent", {})
    combined["runs"], combined["source_studies"] = [], []
    for directory, study in ((reference, original), (baselines, fresh)):
        combined["source_studies"].append(
            {
                "path": str(directory.resolve()),
                "manifest_sha256": sha256(directory / "study_manifest.json"),
            }
        )
        for entry in study["runs"]:
            if entry["status"] not in {"success", "partial", "failed"}:
                raise ValueError("An attempt is not finalized.")
            combined["runs"].append(
                {**entry, "record": os.path.relpath(directory / entry["record"], output)}
            )
    expected = {
        (dataset, method, seed, section["section_id"])
        for dataset, prepared in combined["preparations"].items()
        for method in combined["config"]["methods"]
        for seed in combined["config"]["seeds"]
        for section in prepared["sections"]
    }
    actual = {(e["dataset"], e["method"], e["seed"], e["section_id"]) for e in combined["runs"]}
    if expected != actual or len(actual) != len(combined["runs"]):
        raise ValueError("Every declared repeat and section must have exactly one attempt.")
    output.mkdir(exist_ok=True)
    write_json(output / "study_manifest.json", combined)
    return combined


def main() -> None:
    """Audit, run the native baselines once each, and generate the final comparison."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tissueagent-study", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--collection-decision", type=Path)
    args = parser.parse_args()
    config = yaml.safe_load(args.config.read_text())
    args.output_dir.mkdir(parents=True, exist_ok=True)
    audit = audit_reference(args.tissueagent_study, config)
    audit_path = args.output_dir / "audit.json"
    if audit_path.exists():
        previous = json.loads(audit_path.read_text())
        if previous["reference_manifest_sha256"] != audit["reference_manifest_sha256"]:
            raise ValueError("The reference differs from the original audit.")
        audit["home_free_bytes_before"] = previous["home_free_bytes_before"]
    if args.collection_decision:
        audit["collection_decision"] = {
            "path": str(args.collection_decision.resolve()),
            "sha256": sha256(args.collection_decision),
        }
    write_json(audit_path, audit)
    print(
        "Reference/input/prompt audit passed; executing unrecorded baseline attempts.",
        flush=True,
    )
    baselines = args.output_dir / "baselines"
    run_study(config, baselines, resume=args.resume)
    comparison = args.output_dir / "comparison"
    reference = args.tissueagent_study
    if args.collection_decision:
        reference = collect_study(
            reference, args.output_dir / "collected/tissueagent", args.collection_decision
        )
        baselines = collect_study(
            baselines, args.output_dir / "collected/baselines", args.collection_decision
        )
    combined = compose_studies(reference, baselines, comparison)
    metrics = evaluate_study(comparison)
    plot_performance(comparison, comparison / "figures")
    summary = pd.read_csv(comparison / "evaluation/summary.tsv", sep="\t")
    lines = [
        "Final tissue-niche agent comparison",
        "",
        "GPT-5.1, high reasoning; seeds 42, 43, 44 on each dataset. "
        "TissueAgent uses the frozen September 13 skill/plan study. "
        "All newly declared baseline attempts are retained.",
        "",
        "| Dataset | Method | Macro F1, mean ± SD | Balanced accuracy, mean ± SD | "
        "Complete | Scored |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in summary.itertuples():

        def value(mean, sd):
            if pd.isna(mean):
                return "No result"
            return f"{mean:.3f}" if pd.isna(sd) else f"{mean:.3f} ± {sd:.3f}"

        lines.append(
            f"| {DATASET_NAMES[row.dataset]} | {METHOD_NAMES[row.method]} | "
            f"{value(row.macro_f1_mean, row.macro_f1_std)} | "
            f"{value(row.balanced_accuracy_mean, row.balanced_accuracy_std)} | "
            f"{row.n_successful_runs}/{row.n_planned_runs} | {row.n_scored_runs} |"
        )
    lines += [
        "",
        "Heart: 228,635 scored cells pooled across three physical sections. "
        "Ovarian cancer: 338,695 input cells, 246,544 scored; the 92,151 unscored "
        "cells remain in every input for context.",
        "",
        "Dots show individual repetitions; error bars are sample SD. Missing labels "
        "and unavailable sections count as Unmatched on the full scored cohort. "
        "An entirely failed repetition has no accuracy score; completion is shown separately. "
        "There is no truth-based cluster matching or semantic label remapping.",
        "",
        "![Performance](comparison/figures/performance.png)",
        "",
        "[PDF](comparison/figures/performance.pdf) · "
        "[Per-run metrics](comparison/evaluation/metrics.tsv) · "
        "[Audit](audit.json) · [Study provenance](comparison/study_manifest.json)",
        "",
        "Remaining comparison limits:",
        "",
    ]
    lines.extend(f"- {item}." for item in audit["remaining_differences"])
    if args.collection_decision:
        recovered = sum(
            row["collection_corrected"]
            for directory in (reference, baselines)
            for row in json.loads((directory / "collection_audit.json").read_text())
        )
        lines += [
            "",
            f"Collection recovered {recovered} completed section outputs rejected by the former "
            "working-copy hash rule. All retained outputs were checked against immutable original "
            "inputs; raw labels and original attempts were preserved. This decision preceded "
            "inspection of new accuracy scores. [Collection decision](collection_decision.json).",
        ]
    failed = [entry for entry in combined["runs"] if entry["status"] == "failed"]
    if failed:
        lines += ["", "Sections without usable annotations:", ""]
        for entry in failed:
            record = json.loads((comparison / entry["record"]).read_text())
            lines.append(
                f"- {DATASET_NAMES[entry['dataset']]} / {METHOD_NAMES[entry['method']]} / "
                f"seed {entry['seed']} / {entry['section_id']}: {record.get('error', 'failed')}."
            )
    (args.output_dir / "report.md").write_text("\n".join(lines) + "\n")
    print(metrics.to_string(index=False), flush=True)


if __name__ == "__main__":
    main()
