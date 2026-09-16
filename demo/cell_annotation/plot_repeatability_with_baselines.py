"""Compare seeded TissueAgent runs with certified single-run annotation baselines."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import textwrap
import time
from pathlib import Path
from typing import Any

import matplotlib
import pandas as pd

from demo.cell_annotation.plot_tissueagent_repeatability import load_repeatability_study

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


METHODS = ("tissueagent", "gptcelltype", "celltypist")
BASELINE_METHODS = ("gptcelltype", "celltypist")
METRICS = (("accuracy", "Accuracy"), ("macro_precision", "Macro precision"))
METHOD_LABELS = {
    "tissueagent": "TissueAgent (mean ± SD, n=3)",
    "gptcelltype": "GPTCellType (single run)",
    "celltypist": "CellTypist (single run)",
}
METHOD_COLORS = {
    "tissueagent": "#4C78A8",
    "gptcelltype": "#F58518",
    "celltypist": "#54A24B",
}
POINT_COLOR = "#17324D"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024**2), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path, context: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{context} is not valid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{context} must contain an object: {path}")
    return payload


def _resolve_record_path(record: Any, *, relative_to: Path, context: str) -> Path:
    if not isinstance(record, dict):
        raise ValueError(f"{context} must be an object.")
    raw_path = record.get("path")
    expected_sha256 = record.get("sha256")
    if not isinstance(raw_path, str) or not raw_path:
        raise ValueError(f"{context}.path must be a non-empty string.")
    if not isinstance(expected_sha256, str) or len(expected_sha256) != 64:
        raise ValueError(f"{context}.sha256 must be a SHA-256 digest.")
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = relative_to / path
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(f"{context} does not exist: {path}")
    if _sha256(path) != expected_sha256.lower():
        raise ValueError(f"{context} hash does not match: {path}")
    return path


def _evaluation_signature(evaluation: Any, context: str) -> dict[str, Any]:
    if not isinstance(evaluation, dict):
        raise ValueError(f"{context} must be an object.")
    sources = evaluation.get("sources")
    if not isinstance(sources, dict):
        raise ValueError(f"{context}.sources must be an object.")
    ground_truth = sources.get("ground_truth")
    label_mapping = sources.get("label_mapping")
    for name, record in (("ground_truth", ground_truth), ("label_mapping", label_mapping)):
        if not isinstance(record, dict) or not isinstance(record.get("sha256"), str):
            raise ValueError(f"{context}.sources.{name}.sha256 is required.")
    signature = {
        "label_space": evaluation.get("label_space"),
        "target_labels": evaluation.get("target_labels"),
        "excluded_ground_truth_raw_labels": evaluation.get(
            "excluded_ground_truth_raw_labels"
        ),
        "label_contract_sha256": evaluation.get("label_contract_sha256"),
        "ground_truth_sha256": ground_truth["sha256"],
        "label_mapping_sha256": label_mapping["sha256"],
    }
    if not isinstance(signature["label_space"], str) or not signature["label_space"]:
        raise ValueError(f"{context}.label_space is invalid.")
    if not isinstance(signature["target_labels"], list) or not signature["target_labels"]:
        raise ValueError(f"{context}.target_labels is invalid.")
    if not isinstance(signature["excluded_ground_truth_raw_labels"], list):
        raise ValueError(f"{context}.excluded_ground_truth_raw_labels is invalid.")
    contract = signature["label_contract_sha256"]
    if not isinstance(contract, str) or len(contract) != 64:
        raise ValueError(f"{context}.label_contract_sha256 is invalid.")
    return signature


def _repeatability_signatures(provenance: dict[str, Any]) -> dict[str, dict[str, Any]]:
    signatures: dict[str, dict[str, Any]] = {}
    for index, record in enumerate(provenance.get("inputs", [])):
        if not isinstance(record, dict):
            raise ValueError(f"Repeatability provenance input {index} is invalid.")
        signature = _evaluation_signature(
            record.get("evaluation"),
            f"repeatability input {index}.evaluation",
        )
        contract = signature["label_contract_sha256"]
        if contract in signatures and signatures[contract] != signature:
            raise ValueError(f"Repeatability runs disagree for label contract {contract}.")
        signatures[contract] = signature
    if not signatures:
        raise ValueError("Repeatability provenance contains no evaluation signatures.")
    return signatures


def _load_baselines(
    provenance_path: Path,
    repeatability_signatures: dict[str, dict[str, Any]],
) -> tuple[pd.DataFrame, dict[str, Any], Path]:
    provenance = _read_json(provenance_path, "Baseline provenance")
    metrics_path = _resolve_record_path(
        provenance.get("combined_metrics"),
        relative_to=provenance_path.parent,
        context="baseline provenance combined_metrics",
    )
    frame = pd.read_csv(metrics_path, sep="\t")
    required_columns = {
        "dataset",
        "method",
        "label_space",
        "label_contract_sha256",
        "target_labels_json",
        "excluded_ground_truth_raw_labels_json",
        "n_truth_cells",
        "n_excluded_truth_cells",
        "n_prediction_rows",
        "accuracy",
        "macro_precision",
    }
    missing = sorted(required_columns.difference(frame.columns))
    if missing:
        raise ValueError(f"Baseline metrics are missing columns: {missing}")

    provenance_signatures: dict[str, dict[str, Any]] = {}
    for index, record in enumerate(provenance.get("inputs", [])):
        if not isinstance(record, dict):
            raise ValueError(f"Baseline provenance input {index} is invalid.")
        signature = _evaluation_signature(record.get("evaluation"), f"baseline input {index}")
        contract = signature["label_contract_sha256"]
        if contract in provenance_signatures:
            raise ValueError(f"Duplicate baseline label contract: {contract}")
        provenance_signatures[contract] = signature
    if set(provenance_signatures) != set(repeatability_signatures):
        raise ValueError("Baseline and repeatability label-contract sets differ.")
    for contract, signature in provenance_signatures.items():
        if signature != repeatability_signatures[contract]:
            raise ValueError(f"Baseline lineage differs for label contract {contract}.")

    selected = frame.loc[frame["method"].isin(BASELINE_METHODS)].copy()
    expected_rows = len(repeatability_signatures) * len(BASELINE_METHODS)
    if len(selected) != expected_rows:
        raise ValueError(f"Expected {expected_rows} baseline rows, found {len(selected)}.")
    if selected.duplicated(["label_contract_sha256", "method"]).any():
        raise ValueError("Baseline metrics contain duplicate contract/method rows.")

    for row_index, row in selected.iterrows():
        contract = str(row["label_contract_sha256"])
        if contract not in repeatability_signatures:
            raise ValueError(f"Unknown baseline label contract: {contract}")
        signature = repeatability_signatures[contract]
        if row["label_space"] != signature["label_space"]:
            raise ValueError(f"Baseline row {row_index} label_space differs from repeatability.")
        if json.loads(row["target_labels_json"]) != signature["target_labels"]:
            raise ValueError(f"Baseline row {row_index} target labels differ from repeatability.")
        if (
            json.loads(row["excluded_ground_truth_raw_labels_json"])
            != signature["excluded_ground_truth_raw_labels"]
        ):
            raise ValueError(f"Baseline row {row_index} exclusions differ from repeatability.")
        for metric, _ in METRICS:
            score = float(row[metric])
            if not math.isfinite(score) or not 0 <= score <= 1:
                raise ValueError(f"Baseline row {row_index} has invalid {metric}.")
    return selected, provenance, metrics_path


def _build_comparison(
    repeatability_runs: pd.DataFrame,
    baselines: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    datasets = (
        repeatability_runs[
            ["dataset_id", "display_name", "dataset_order", "label_contract_sha256"]
        ]
        .drop_duplicates()
        .sort_values("dataset_order")
    )
    if datasets["label_contract_sha256"].duplicated().any():
        raise ValueError("Repeatability datasets must have unique label contracts.")
    for dataset in datasets.itertuples(index=False):
        run_rows = repeatability_runs.loc[
            repeatability_runs["dataset_id"] == dataset.dataset_id
        ].sort_values("replicate")
        if list(run_rows["replicate"]) != [1, 2, 3]:
            raise ValueError(f"{dataset.dataset_id} does not contain replicates 1, 2, and 3.")
        row: dict[str, Any] = {
            "dataset_id": dataset.dataset_id,
            "display_name": dataset.display_name,
            "dataset_order": int(dataset.dataset_order),
            "method": "tissueagent",
            "n_runs": 3,
            "estimate_type": "mean_of_three_independent_seeded_runs",
            "label_contract_sha256": dataset.label_contract_sha256,
            "model_seeds_json": json.dumps(run_rows["model_seed"].astype(int).tolist()),
        }
        for metric, _ in METRICS:
            values = run_rows[metric].astype(float)
            row[metric] = float(values.mean())
            row[f"{metric}_sample_sd"] = float(values.std(ddof=1))
            row[f"{metric}_runs_json"] = json.dumps(values.tolist())
        rows.append(row)

        baseline_rows = baselines.loc[
            baselines["label_contract_sha256"] == dataset.label_contract_sha256
        ].set_index("method")
        for method in BASELINE_METHODS:
            baseline = baseline_rows.loc[method]
            rows.append(
                {
                    "dataset_id": dataset.dataset_id,
                    "display_name": dataset.display_name,
                    "dataset_order": int(dataset.dataset_order),
                    "method": method,
                    "n_runs": 1,
                    "estimate_type": "single_certified_benchmark_run",
                    "label_contract_sha256": dataset.label_contract_sha256,
                    "model_seeds_json": "",
                    "accuracy": float(baseline["accuracy"]),
                    "accuracy_sample_sd": None,
                    "accuracy_runs_json": json.dumps([float(baseline["accuracy"])]),
                    "macro_precision": float(baseline["macro_precision"]),
                    "macro_precision_sample_sd": None,
                    "macro_precision_runs_json": json.dumps(
                        [float(baseline["macro_precision"])]
                    ),
                }
            )
    return pd.DataFrame(rows)


def _plot(
    comparison: pd.DataFrame,
    repeatability_runs: pd.DataFrame,
    *,
    title: str,
    note: str,
    png_path: Path,
    pdf_path: Path,
) -> str:
    datasets = (
        comparison[["dataset_id", "display_name", "dataset_order"]]
        .drop_duplicates()
        .sort_values("dataset_order")
    )
    dataset_ids = datasets["dataset_id"].tolist()
    display_names = datasets["display_name"].tolist()
    x_positions = list(range(len(datasets)))
    width = 0.24
    rendered_note = (
        f"{note.rstrip()} TissueAgent bars are means with ±1 sample SD across three fresh "
        "executions (seeds 42, 43, and 44); points are individual runs. GPTCellType and "
        "CellTypist are single certified benchmark estimates and therefore have no error bars."
    )
    note_lines = textwrap.wrap(rendered_note, width=150) or [""]
    figure, axes = plt.subplots(
        1,
        len(METRICS),
        figsize=(16, 7.5 + 0.25 * max(0, len(note_lines) - 1)),
        sharey=True,
    )
    for axis, (metric, panel_title) in zip(axes, METRICS, strict=True):
        for method_index, method in enumerate(METHODS):
            method_frame = comparison.loc[comparison["method"] == method].set_index(
                "dataset_id"
            )
            values = [float(method_frame.loc[dataset_id, metric]) for dataset_id in dataset_ids]
            offsets = [
                position + (method_index - (len(METHODS) - 1) / 2) * width
                for position in x_positions
            ]
            bar_options: dict[str, Any] = {}
            if method == "tissueagent":
                bar_options.update(
                    {
                        "yerr": [
                            float(method_frame.loc[dataset_id, f"{metric}_sample_sd"])
                            for dataset_id in dataset_ids
                        ],
                        "capsize": 5,
                        "error_kw": {"elinewidth": 1.5, "capthick": 1.5},
                    }
                )
            bars = axis.bar(
                offsets,
                values,
                width,
                label=METHOD_LABELS[method],
                color=METHOD_COLORS[method],
                **bar_options,
            )
            for dataset_index, (bar, value) in enumerate(zip(bars, values, strict=True)):
                label_top = value
                if method == "tissueagent":
                    dataset_id = dataset_ids[dataset_index]
                    sample_sd = float(
                        method_frame.loc[dataset_id, f"{metric}_sample_sd"]
                    )
                    maximum_run = float(
                        repeatability_runs.loc[
                            repeatability_runs["dataset_id"] == dataset_id,
                            metric,
                        ].max()
                    )
                    label_top = max(value + sample_sd, maximum_run)
                axis.text(
                    bar.get_x() + bar.get_width() / 2,
                    label_top + 0.018,
                    f"{value:.2f}",
                    ha="center",
                    va="bottom",
                    fontsize=9.5,
                )
            if method == "tissueagent":
                for dataset_index, dataset_id in enumerate(dataset_ids):
                    values_for_runs = (
                        repeatability_runs.loc[
                            repeatability_runs["dataset_id"] == dataset_id
                        ]
                        .sort_values("replicate")[metric]
                        .astype(float)
                        .tolist()
                    )
                    axis.scatter(
                        [
                            offsets[dataset_index] - 0.045,
                            offsets[dataset_index],
                            offsets[dataset_index] + 0.045,
                        ],
                        values_for_runs,
                        color=POINT_COLOR,
                        edgecolor="white",
                        linewidth=0.7,
                        s=30,
                        zorder=4,
                    )
        axis.set_title(panel_title, loc="left", fontsize=17, fontweight="bold")
        axis.set_xticks(x_positions, display_names)
        axis.tick_params(axis="x", labelsize=11.5)
        axis.tick_params(axis="y", labelsize=11)
        axis.set_ylim(0, 1.03)
        axis.grid(axis="y", color="#D9D9D9", linewidth=0.8)
        axis.set_axisbelow(True)
        axis.spines["top"].set_visible(False)
        axis.spines["right"].set_visible(False)
        axis.set_ylabel("Score", fontsize=13)

    handles, labels = axes[0].get_legend_handles_labels()
    figure.legend(
        handles,
        labels,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.89),
        ncol=len(METHODS),
        frameon=False,
        fontsize=12,
    )
    figure.suptitle(title, fontsize=20, fontweight="bold", y=0.98)
    figure.text(
        0.5,
        0.02,
        "\n".join(note_lines),
        ha="center",
        va="bottom",
        fontsize=10,
        color="#555555",
    )
    note_margin = 0.07 + 0.025 * max(0, len(note_lines) - 1)
    figure.tight_layout(rect=(0.02, note_margin, 1, 0.85), w_pad=3.5)
    figure.savefig(png_path, dpi=220, bbox_inches="tight")
    figure.savefig(pdf_path, bbox_inches="tight")
    plt.close(figure)
    return rendered_note


def plot_repeatability_with_baselines(
    repeatability_manifest: Path,
    baseline_provenance: Path,
    output_dir: Path,
    *,
    output_prefix: str,
    title: str,
    note: str,
) -> dict[str, Any]:
    """Validate compatible lineages and plot repeated TissueAgent against baselines."""
    repeatability_manifest = repeatability_manifest.expanduser().resolve()
    baseline_provenance = baseline_provenance.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    if not output_prefix or Path(output_prefix).name != output_prefix:
        raise ValueError("output_prefix must be a non-empty file-name prefix.")
    outputs = {
        "metrics_tsv": output_dir / f"{output_prefix}_metrics.tsv",
        "png": output_dir / f"{output_prefix}_accuracy_macro_precision.png",
        "pdf": output_dir / f"{output_prefix}_accuracy_macro_precision.pdf",
        "provenance_json": output_dir / f"{output_prefix}_provenance.json",
    }
    existing = sorted(path for path in outputs.values() if path.exists())
    if existing:
        raise FileExistsError(
            "Refusing to overwrite existing comparison artifacts: "
            + ", ".join(str(path) for path in existing)
        )

    repeatability_runs, repeatability_provenance = load_repeatability_study(
        repeatability_manifest
    )
    signatures = _repeatability_signatures(repeatability_provenance)
    baselines, baseline_payload, baseline_metrics_path = _load_baselines(
        baseline_provenance,
        signatures,
    )
    comparison = _build_comparison(repeatability_runs, baselines)
    output_dir.mkdir(parents=True, exist_ok=True)
    comparison.to_csv(outputs["metrics_tsv"], sep="\t", index=False, na_rep="")
    rendered_note = _plot(
        comparison,
        repeatability_runs,
        title=title,
        note=note,
        png_path=outputs["png"],
        pdf_path=outputs["pdf"],
    )
    provenance = {
        "schema_version": "1.0",
        "repeatability_study": {
            "path": str(repeatability_manifest),
            "sha256": _sha256(repeatability_manifest),
            "study_id": repeatability_provenance["study_id"],
        },
        "certified_baselines": {
            "provenance_path": str(baseline_provenance),
            "provenance_sha256": _sha256(baseline_provenance),
            "metrics_path": str(baseline_metrics_path),
            "metrics_sha256": _sha256(baseline_metrics_path),
            "source_timestamp_utc": baseline_payload.get("timestamp_utc"),
        },
        "compatibility": {
            "status": "passed",
            "validated_fields": [
                "label_space",
                "target_labels",
                "excluded_ground_truth_raw_labels",
                "label_contract_sha256",
                "ground_truth_sha256",
                "label_mapping_sha256",
            ],
            "label_contract_sha256s": sorted(signatures),
        },
        "method_estimates": {
            "tissueagent": {
                "n_runs": 3,
                "central_value": "arithmetic_mean",
                "error_bar": "sample_standard_deviation",
                "ddof": 1,
                "raw_points_overlaid": True,
                "model_seeds": [42, 43, 44],
            },
            "gptcelltype": {"n_runs": 1, "error_bar": None},
            "celltypist": {"n_runs": 1, "error_bar": None},
        },
        "title": title,
        "note_prefix": note,
        "rendered_note": rendered_note,
        "outputs": {
            name: {"path": str(path), "sha256": _sha256(path)}
            for name, path in outputs.items()
            if name != "provenance_json"
        },
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    outputs["provenance_json"].write_text(
        json.dumps(provenance, indent=2),
        encoding="utf-8",
    )
    provenance["provenance_json"] = str(outputs["provenance_json"])
    return provenance


def main() -> None:
    """Parse inputs and write comparison artifacts."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeatability-manifest", required=True, type=Path)
    parser.add_argument("--baseline-provenance", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument(
        "--output-prefix",
        default="tissueagent_repeatability_with_baselines",
    )
    parser.add_argument(
        "--title",
        default="Cell-annotation performance across TissueAgent runs and baselines",
    )
    parser.add_argument(
        "--note",
        default=(
            "Frozen per-dataset label contracts; missing or unsupported predictions count as "
            "Unassigned; BCL excludes 344 B14 truth cells."
        ),
    )
    args = parser.parse_args()
    result = plot_repeatability_with_baselines(
        args.repeatability_manifest,
        args.baseline_provenance,
        args.output_dir,
        output_prefix=args.output_prefix,
        title=args.title,
        note=args.note,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
