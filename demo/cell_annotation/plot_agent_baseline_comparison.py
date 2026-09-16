"""Plot the full-cohort agent baselines beside the latest validated existing results."""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

import numpy as np
import pandas as pd

from .run_agent_baseline_comparison import ROOT, RUN_ID, configure_runtime


STUDY = ROOT / (
    "demo/outputs/cell_annotation/"
    "tissueagent-repeatability-heart-bcl-scope-v11-han-20260825-v1/"
    "study_manifest_posthoc_mapping_v1.json"
)
BASELINES = ROOT / (
    "demo/outputs/cell_annotation/final-heart-bcl-han-stereoseq-20260801-v1/"
    "cell_annotation_final_heart_bcl_han_stereoseq_provenance.json"
)
METHODS = ("tissueagent", "gptcelltype", "celltypist", "biomni", "spatialagent")
LABELS = ("TissueAgent", "GPTCellType", "CellTypist", "Biomni", "SpatialAgent")
COLORS = ("#4C78A8", "#F58518", "#54A24B", "#B279A2", "#E45756")
METRICS = (
    ("accuracy", "Accuracy"),
    ("macro_precision", "Macro precision"),
    ("balanced_accuracy", "Balanced accuracy"),
    ("macro_f1", "Macro F1"),
)


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


def _observation_ids(path: Path) -> set[str]:
    import h5py

    with h5py.File(path) as handle:
        obs = handle["obs"]
        return set(obs[obs.attrs["_index"]].asstr()[:])


def collect_results(run_id: str, overrides: dict) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Load existing and new scores after checking matching evaluation provenance."""
    from .benchmarks import _sha256, load_manifest
    from .plot_repeatability_with_baselines import (
        _evaluation_signature,
        _load_baselines,
        _repeatability_signatures,
    )
    from .plot_tissueagent_repeatability import load_repeatability_study

    _, tissue_provenance = load_repeatability_study(STUDY)
    signatures = _repeatability_signatures(tissue_provenance)
    baselines, baseline_provenance, _ = _load_baselines(BASELINES, signatures)
    study = json.loads(STUDY.read_text())
    czi_metadata_path = (
        ROOT / "data/cache/biomni/biomni_data/data_lake/czi_census_datasets_v4.parquet"
    )
    czi_metadata = pd.read_parquet(czi_metadata_path).set_index("dataset_id")
    rows, sources = [], []
    for order, spec in enumerate(study["datasets"]):
        shared = {
            "dataset_id": spec["dataset_id"],
            "display_name": spec["display_name"],
            "dataset_order": order,
            "label_space": spec["expected_label_space"],
            "label_contract_sha256": spec["expected_label_contract_sha256"],
        }
        for run in spec["runs"]:
            tissue_run = json.loads(Path(run["tissueagent_run_json"]).read_text())
            assert tissue_run["model_configuration"]["selection"] == {
                "orchestration": "gpt-5.1", "worker": "gpt-5.1"
            }
            path = Path(run["metrics_tsv"])
            row = pd.read_csv(path, sep="\t").set_index("method").loc["tissueagent"].to_dict()
            rows.append({**shared, **row, "method": "tissueagent", "replicate": run["replicate"]})
        selected = baselines.loc[
            baselines.label_contract_sha256.eq(spec["expected_label_contract_sha256"])
        ]
        for _, row in selected.iterrows():
            rows.append({**row.to_dict(), **shared, "replicate": 1})
        for method in ("biomni", "spatialagent"):
            selected_run = overrides.get(f"{spec['dataset_id']}:{method}", f"{run_id}-{method}")
            directory = ROOT / "demo/outputs/cell_annotation" / spec["dataset_id"] / selected_run
            metrics_path = directory / f"metrics_{method}.tsv"
            metadata_path = directory / f"metrics_{method}.json"
            metadata = json.loads(metadata_path.read_text())
            signature = _evaluation_signature(metadata, str(metadata_path))
            if signature != signatures[spec["expected_label_contract_sha256"]]:
                raise ValueError(f"New baseline evaluation lineage differs: {metadata_path}")
            for record in (
                metadata["sources"]["ground_truth"],
                metadata["sources"]["label_mapping"],
                metadata["sources"]["predictions"][method],
                metadata["sources"]["prediction_mapping"],
            ):
                assert _sha256(Path(record["path"])) == record["sha256"]
            run = json.loads((directory / f"{method}_predictions.run.json").read_text())
            assert run["status"] == "success" and run["model"] == "gpt-5.1"
            assert run["query_sha256"] == spec["expected_prepared_query_sha256"]
            request = json.loads((directory / method / "worker_request.json").read_text())
            assert _sha256(Path(request["query_h5ad"])) == run["query_sha256"]
            alignment_path = directory / "task_prompt_alignment.json"
            alignment = json.loads(alignment_path.read_text())
            template, prompt_sources = matched_task_prompt(spec)
            assert alignment["task_prompt_template"] == template
            if "comparison_config" in alignment:
                from .run_agent_baseline_comparison import load_config

                config_path = directory / alignment["comparison_config"]
                assert _sha256(config_path) == alignment["comparison_config_sha256"]
                configured = next(
                    item for item in load_config(config_path)["datasets"]
                    if item["dataset_id"] == spec["dataset_id"]
                )
                assert configured["task_prompt_template"] == template
            else:
                assert alignment["tissueagent_prompt_sources"] == prompt_sources
            assert request["task_prompt_template"] == template
            assert request["task_prompt"] == template.replace(
                "<QUERY_H5AD>", request["query_h5ad"]
            ).replace("<ANNOTATED_H5AD>", request["annotated_h5ad"])
            assert request["prompt"].startswith(request["task_prompt"] + "\n\n")
            if method == "biomni":
                assert "working_h5ad" not in request
                assert run["query_preprocessing"]["adapter_transform"] == "none"
            row = pd.read_csv(metrics_path, sep="\t").set_index("method").loc[method].to_dict()
            json_row = next(item for item in metadata["methods"] if item["method"] == method)
            for metric, _ in METRICS:
                assert np.isclose(row[metric], json_row[metric], atol=1e-12, rtol=0)
            assert int(row["n_truth_cells"]) == spec["expected_n_truth_cells"]
            outcome_path = directory / "annotation_outcome.json"
            outcome = (
                json.loads(outcome_path.read_text())
                if outcome_path.exists()
                else {"status": "not_flagged"}
            )
            if outcome_path.exists():
                assert outcome["query_sha256"] == run["query_sha256"]
                assert outcome["n_prediction_rows"] == run["n_predictions"]
                prediction_path = Path(metadata["sources"]["predictions"][method]["path"])
                labels = pd.read_csv(prediction_path, sep="\t").raw_prediction.unique()
                assert set(labels) == set(outcome["raw_prediction_labels"])
                outcome["audit_artifact"] = {
                    "path": str(outcome_path), "sha256": _sha256(outcome_path)
                }
            row["annotation_outcome"] = outcome["status"]
            rows.append({**shared, **row, "method": method, "replicate": 1})
            references = []
            reference_paths = sorted((directory / method / "czi_reference").glob("*.h5ad"))
            if reference_paths:
                query_ids = _observation_ids(Path(request["query_h5ad"]))
                excluded_dois = load_manifest(spec["dataset_id"])["reference_audit"].get(
                    "forbidden_collection_dois", []
                )
                for path in reference_paths:
                    dataset_id = path.stem.removeprefix("sc_reference_")
                    reference = czi_metadata.loc[dataset_id]
                    doi = str(reference.collection_doi)
                    overlap = len(query_ids & _observation_ids(path))
                    assert doi not in excluded_dois, f"Excluded source-study reference: {path}"
                    assert overlap == 0, f"Reference/query observation overlap: {path}"
                    references.append(
                        {
                            "path": str(path),
                            "sha256": _sha256(path),
                            "dataset_id": dataset_id,
                            "collection_doi": doi,
                            "dataset_title": str(reference.dataset_title),
                            "observation_id_overlap": overlap,
                            "forbidden_source_check": "passed",
                        }
                    )
            sources.append(
                {
                    "dataset_id": spec["dataset_id"],
                    "method": method,
                    "metrics_path": str(metrics_path),
                    "metrics_sha256": _sha256(metrics_path),
                    "metadata_path": str(metadata_path),
                    "metadata_sha256": _sha256(metadata_path),
                    "run": run,
                    "task_prompt_alignment": {
                        "path": str(alignment_path),
                        "sha256": _sha256(alignment_path),
                        **alignment,
                    },
                    "reference_files": references,
                    "annotation_outcome": outcome,
                }
            )
    raw = pd.DataFrame(rows)
    summary = []
    for (dataset, method), group in raw.groupby(["dataset_id", "method"], sort=False):
        row = {
            key: group.iloc[0][key]
            for key in (
                "dataset_id",
                "display_name",
                "dataset_order",
                "label_space",
                "label_contract_sha256",
            )
        }
        row.update(method=method, n_runs=len(group), n_truth_cells=int(group.n_truth_cells.iloc[0]))
        row["annotation_outcome"] = group.annotation_outcome.fillna("not_flagged").iloc[0]
        for metric, _ in METRICS:
            row[metric] = float(group[metric].mean())
            row[f"{metric}_sd"] = float(group[metric].std(ddof=1)) if len(group) > 1 else None
        row["prediction_coverage"] = float(group.prediction_coverage.mean())
        summary.append(row)
    provenance = {
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tissueagent_study": {"path": str(STUDY), "sha256": _sha256(STUDY)},
        "existing_baselines": {"path": str(BASELINES), "sha256": _sha256(BASELINES)},
        "comparison_checks": (
            "matching original query bytes, saved TissueAgent scientific task prompts, "
            "truth, label contracts, mappings and exclusions; no adapter preprocessing"
        ),
        "new_baselines": sources,
        "existing_inputs": baseline_provenance["inputs"],
        "tissueagent_inputs": tissue_provenance["inputs"],
        "reference_metadata_snapshot": {
            "path": str(czi_metadata_path),
            "sha256": _sha256(czi_metadata_path),
        },
        "attempt_selection": (
            "First completed evaluation per dataset/method; no score-based selection."
        ),
    }
    failed_attempts = []
    family = run_id.rsplit("-v", 1)[0]
    for spec in study["datasets"]:
        parent = ROOT / "demo/outputs/cell_annotation" / spec["dataset_id"]
        for directory in sorted(parent.glob(f"{family}-v*")):
            paths = list(directory.glob("*_predictions.run.json"))
            paths.extend(directory.glob("interruption.json"))
            for path in paths:
                record = json.loads(path.read_text())
                if record["status"] != "success":
                    failed_attempts.append({"path": str(path), "sha256": _sha256(path), **record})
    provenance["failed_or_interrupted_attempts"] = failed_attempts
    return pd.DataFrame(summary), raw, provenance


def plot_results(summary: pd.DataFrame, raw: pd.DataFrame, output: Path) -> None:
    """Render four evaluation metrics with TissueAgent replicate error bars."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter

    plt.rcParams.update(
        {"font.size": 11, "pdf.fonttype": 42, "axes.spines.top": False, "axes.spines.right": False}
    )
    figure, axes = plt.subplots(2, 2, figsize=(16, 10))
    datasets = (
        summary[["dataset_id", "display_name", "dataset_order"]]
        .drop_duplicates()
        .sort_values("dataset_order")
    )
    centers = np.arange(len(datasets))
    width = 0.155
    for axis, (metric, title) in zip(axes.flat, METRICS, strict=True):
        for index, (method, label, color) in enumerate(zip(METHODS, LABELS, COLORS, strict=True)):
            group = (
                summary.loc[summary.method.eq(method)]
                .set_index("dataset_id")
                .loc[datasets.dataset_id]
            )
            positions = centers + (index - 2) * width
            bars = axis.bar(positions, group[metric], width * 0.92, color=color, label=label)
            if method == "tissueagent":
                axis.errorbar(
                    positions,
                    group[metric],
                    yerr=group[f"{metric}_sd"],
                    fmt="none",
                    color="#222222",
                    capsize=3,
                    lw=1,
                )
                for x, dataset in zip(positions, datasets.dataset_id, strict=True):
                    values = raw.loc[
                        raw.dataset_id.eq(dataset) & raw.method.eq(method), metric
                    ].to_numpy()
                    axis.scatter(
                        x + np.linspace(-0.025, 0.025, len(values)),
                        values,
                        s=12,
                        color="#222222",
                        zorder=4,
                    )
            for bar, score, sd, outcome in zip(
                bars,
                group[metric],
                group[f"{metric}_sd"].fillna(0),
                group.annotation_outcome,
                strict=True,
            ):
                flagged = outcome != "not_flagged"
                if flagged and score == 0:
                    axis.plot(
                        bar.get_x() + bar.get_width() / 2,
                        0,
                        marker="x",
                        color=color,
                        clip_on=False,
                    )
                axis.text(
                    bar.get_x() + bar.get_width() / 2,
                    score + sd + 0.014,
                    f"{score * 100:.1f}" + ("†" if flagged else ""),
                    ha="center",
                    va="bottom",
                    fontsize=8,
                )
        axis.set_title(title, loc="left", fontweight="bold")
        axis.set_ylim(0, 1.05)
        axis.yaxis.set_major_formatter(PercentFormatter(1))
        axis.set_xticks(
            centers,
            [
                "Developing human heart\n228,635 cells",
                "BCL\n49,566 scored cells",
                "Mouse brain Stereo-seq\n478,740 cells",
            ],
        )
        axis.grid(axis="y", alpha=0.18)
        axis.set_axisbelow(True)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    figure.legend(
        handles, labels, loc="upper center", bbox_to_anchor=(0.5, 0.94), ncol=5, frameon=False
    )
    figure.suptitle("Cell annotation: matched-task agent reruns", fontsize=19, y=0.98)
    footnote = (
        "Biomni / SpatialAgent: original queries and matched TissueAgent scientific tasks.\n"
        "TissueAgent: mean ± sample SD across 3 runs (dots). Other methods: one run each.\n"
        "All LLM-based methods use GPT-5.1. BCL excludes 344 B14 cells.\n"
        "Stereo-seq truth: publisher-provided Spatial-ID annotations, compared in shared "
        "Cell Ontology space."
    )
    if summary.annotation_outcome.ne("not_flagged").any():
        footnote += (
            "\n† Annotation failure: only generic labels returned; counted as Unassigned."
        )
    figure.text(
        0.5,
        0.055,
        footnote,
        ha="center",
        va="center",
        fontsize=10,
    )
    figure.tight_layout(rect=(0.02, 0.12, 0.99, 0.91), h_pad=3)
    for extension in ("png", "pdf"):
        figure.savefig(output / f"evaluation_comparison.{extension}", dpi=200, facecolor="white")
    plt.close(figure)


def main() -> None:
    """Audit source runs or redraw the committed comparison tables."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--results-dir",
        type=Path,
        help="Redraw saved metric tables without loading or re-auditing source runs.",
    )
    parser.add_argument("--run-id", default=RUN_ID)
    parser.add_argument(
        "--run-override", action="append", default=[], metavar="DATASET:METHOD=RUN_ID"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "demo/outputs/cell_annotation" / f"{RUN_ID}-comparison",
    )
    args = parser.parse_args()
    if args.results_dir is not None:
        summary = pd.read_csv(args.results_dir / "comparison_metrics.tsv", sep="\t")
        raw = pd.read_csv(args.results_dir / "individual_run_metrics.tsv", sep="\t")
        args.output_dir.mkdir(parents=True, exist_ok=False)
        plot_results(summary, raw, args.output_dir)
        print(args.output_dir)
        return
    configure_runtime()
    overrides = dict(item.split("=", 1) for item in args.run_override)
    summary, raw, provenance = collect_results(args.run_id, overrides)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    summary.to_csv(args.output_dir / "comparison_metrics.tsv", sep="\t", index=False)
    raw.to_csv(args.output_dir / "individual_run_metrics.tsv", sep="\t", index=False)
    (args.output_dir / "provenance.json").write_text(json.dumps(provenance, indent=2))
    plot_results(summary, raw, args.output_dir)
    print(
        summary[["display_name", "method", "accuracy", "balanced_accuracy", "macro_f1"]].to_string(
            index=False
        )
    )
    print(args.output_dir)


if __name__ == "__main__":
    main()
