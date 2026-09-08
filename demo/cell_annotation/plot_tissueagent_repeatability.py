"""Aggregate and plot explicit TissueAgent repeatability-study artifacts.

The study manifest has this schema::

    {
      "schema_version": "1.0",
      "study_id": "tissueagent-repeatability-20260804-v1",
      "datasets": [
        {
          "dataset_id": "developing_human_heart",
          "display_name": "Developing human heart",
          "expected_label_space": "primary",
          "expected_exclusions": [],
          "runs": [
            {
              "replicate": 1,
              "run_id": "repeatability-heart-r1",
              "prepared_run_json": "path/to/prepared_run.json",
              "tissueagent_run_json": "path/to/tissueagent_run.json",
              "metrics_tsv": "path/to/metrics_repeatability.tsv",
              "metrics_json": "path/to/metrics_repeatability.json"
            }
          ]
        }
      ]
    }

Relative artifact paths are resolved from the manifest directory. Every dataset
must contain exactly replicates 1, 2, and 3.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import textwrap
import time
from pathlib import Path
from typing import Any

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


EXPECTED_REPLICATES = (1, 2, 3)
METRICS = (("accuracy", "Accuracy"), ("macro_precision", "Macro precision"))
SCORE_COLUMNS = ("prediction_coverage", "accuracy", "macro_precision")
COUNT_COLUMNS = (
    "n_truth_cells",
    "n_excluded_truth_cells",
    "n_prediction_rows",
    "n_assigned",
    "n_unassigned",
    "n_unmapped_raw_labels",
)
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
TISSUEAGENT_COLOR = "#4C78A8"
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


def _require_text(value: Any, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context} must be a non-empty string.")
    return value


def _require_sha256(value: Any, context: str) -> str:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise ValueError(f"{context} must be a 64-character hexadecimal digest.")
    return value.lower()


def _resolve_artifact(manifest_dir: Path, value: Any, context: str) -> Path:
    raw_path = _require_text(value, context)
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = manifest_dir / path
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(f"{context} does not exist: {path}")
    return path


def _require_source_record(record: Any, context: str) -> dict[str, str]:
    if not isinstance(record, dict):
        raise ValueError(f"{context} must be an object.")
    return {
        "path": _require_text(record.get("path"), f"{context}.path"),
        "sha256": _require_sha256(record.get("sha256"), f"{context}.sha256"),
    }


def _coerce_score(value: Any, context: str) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{context} must be numeric.") from exc
    if not math.isfinite(numeric) or not 0 <= numeric <= 1:
        raise ValueError(f"{context} must be finite and between 0 and 1.")
    return numeric


def _coerce_count(value: Any, context: str) -> int:
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{context} must be numeric.") from exc
    if not math.isfinite(numeric) or numeric < 0 or not numeric.is_integer():
        raise ValueError(f"{context} must be a nonnegative integer.")
    return int(numeric)


def _extract_tissueagent_metrics(
    metrics_path: Path,
    metadata_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    frame = pd.read_csv(metrics_path, sep="\t", index_col=0)
    frame.index = frame.index.astype(str)
    if not frame.index.is_unique:
        raise ValueError(f"Metrics TSV has duplicate method rows: {metrics_path}")
    if list(frame.index).count("tissueagent") != 1:
        raise ValueError(f"Metrics TSV must contain exactly one tissueagent row: {metrics_path}")
    missing_columns = sorted(set(SCORE_COLUMNS + COUNT_COLUMNS).difference(frame.columns))
    if missing_columns:
        raise ValueError(f"Metrics TSV {metrics_path} is missing columns: {missing_columns}")

    tsv_record: dict[str, Any] = {}
    for column in SCORE_COLUMNS:
        tsv_record[column] = _coerce_score(
            frame.loc["tissueagent", column],
            f"{metrics_path}: tissueagent.{column}",
        )
    for column in COUNT_COLUMNS:
        tsv_record[column] = _coerce_count(
            frame.loc["tissueagent", column],
            f"{metrics_path}: tissueagent.{column}",
        )
    if tsv_record["n_truth_cells"] < 1:
        raise ValueError(f"Metrics TSV has no scored truth observations: {metrics_path}")
    if (
        tsv_record["n_truth_cells"] + tsv_record["n_excluded_truth_cells"]
        != tsv_record["n_prediction_rows"]
    ):
        raise ValueError(f"Metrics TSV scored and excluded counts are inconsistent: {metrics_path}")
    if tsv_record["n_assigned"] + tsv_record["n_unassigned"] != tsv_record["n_truth_cells"]:
        raise ValueError(f"Metrics TSV assigned counts are inconsistent: {metrics_path}")
    expected_coverage = tsv_record["n_assigned"] / tsv_record["n_truth_cells"]
    if not math.isclose(
        tsv_record["prediction_coverage"],
        expected_coverage,
        rel_tol=0,
        abs_tol=1e-12,
    ):
        raise ValueError(f"Metrics TSV prediction coverage is inconsistent: {metrics_path}")

    metadata = _read_json(metadata_path, "Metrics JSON")
    for field in (
        "schema_version",
        "label_space",
        "target_labels",
        "excluded_ground_truth_raw_labels",
        "label_contract_sha256",
        "sources",
        "methods",
    ):
        if field not in metadata:
            raise ValueError(f"Metrics JSON {metadata_path} is missing {field!r}.")
    _require_text(metadata["schema_version"], f"{metadata_path}: schema_version")
    _require_text(metadata["label_space"], f"{metadata_path}: label_space")
    target_labels = metadata["target_labels"]
    if (
        not isinstance(target_labels, list)
        or not target_labels
        or not all(isinstance(label, str) and label for label in target_labels)
        or len(target_labels) != len(set(target_labels))
    ):
        raise ValueError(f"Metrics JSON {metadata_path} has invalid target_labels.")
    exclusions = metadata["excluded_ground_truth_raw_labels"]
    if (
        not isinstance(exclusions, list)
        or not all(isinstance(label, str) and label for label in exclusions)
        or len(exclusions) != len(set(exclusions))
    ):
        raise ValueError(
            f"Metrics JSON {metadata_path} has invalid excluded_ground_truth_raw_labels."
        )
    contract_sha = _require_sha256(
        metadata["label_contract_sha256"],
        f"{metadata_path}: label_contract_sha256",
    )
    sources = metadata["sources"]
    if not isinstance(sources, dict):
        raise ValueError(f"Metrics JSON {metadata_path} has invalid sources.")
    normalized_sources = {
        "ground_truth": _require_source_record(
            sources.get("ground_truth"),
            f"{metadata_path}: sources.ground_truth",
        ),
        "label_mapping": _require_source_record(
            sources.get("label_mapping"),
            f"{metadata_path}: sources.label_mapping",
        ),
    }
    predictions = sources.get("predictions")
    if not isinstance(predictions, dict):
        raise ValueError(f"Metrics JSON {metadata_path} has invalid sources.predictions.")
    normalized_sources["prediction"] = _require_source_record(
        predictions.get("tissueagent"),
        f"{metadata_path}: sources.predictions.tissueagent",
    )

    methods = metadata["methods"]
    if not isinstance(methods, list):
        raise ValueError(f"Metrics JSON {metadata_path} has invalid methods.")
    matches = [
        record
        for record in methods
        if isinstance(record, dict) and record.get("method") == "tissueagent"
    ]
    if len(matches) != 1:
        raise ValueError(
            f"Metrics JSON must contain exactly one tissueagent method record: {metadata_path}"
        )
    json_record = matches[0]
    for column in SCORE_COLUMNS:
        observed = _coerce_score(json_record.get(column), f"{metadata_path}: {column}")
        if not math.isclose(observed, tsv_record[column], rel_tol=0, abs_tol=1e-12):
            raise ValueError(
                f"Metrics TSV/JSON mismatch for tissueagent.{column}: "
                f"{metrics_path} versus {metadata_path}."
            )
    for column in COUNT_COLUMNS:
        observed = _coerce_count(json_record.get(column), f"{metadata_path}: {column}")
        if observed != tsv_record[column]:
            raise ValueError(
                f"Metrics TSV/JSON mismatch for tissueagent.{column}: "
                f"{metrics_path} versus {metadata_path}."
            )

    evaluation = {
        "schema_version": metadata["schema_version"],
        "label_space": metadata["label_space"],
        "target_labels": target_labels,
        "excluded_ground_truth_raw_labels": exclusions,
        "label_contract_sha256": contract_sha,
        "sources": normalized_sources,
    }
    return tsv_record, evaluation


def _validate_prepared_run(
    payload: dict[str, Any],
    *,
    dataset_id: str,
    run_id: str,
    path: Path,
) -> dict[str, Any]:
    if payload.get("dataset_id") != dataset_id:
        raise ValueError(f"Prepared run dataset_id does not match manifest: {path}")
    if payload.get("run_id") != run_id:
        raise ValueError(f"Prepared run run_id does not match manifest: {path}")
    if payload.get("run_mode") != "full":
        raise ValueError(f"Repeatability studies require full prepared runs: {path}")
    if payload.get("selection_blind_query_audit", {}).get("status") != "passed":
        raise ValueError(f"Prepared run selection-blind query audit did not pass: {path}")
    if payload.get("validation", {}).get("status") != "success":
        raise ValueError(f"Prepared run validation did not succeed: {path}")
    return {
        "selection_blind_id": _require_text(
            payload.get("selection_blind_id"),
            f"{path}: selection_blind_id",
        ),
        "label_contract_sha256": _require_sha256(
            payload.get("label_contract_sha256"),
            f"{path}: label_contract_sha256",
        ),
        "n_obs": _coerce_count(payload.get("n_obs"), f"{path}: n_obs"),
        "n_vars": _coerce_count(payload.get("n_vars"), f"{path}: n_vars"),
        "random_seed": _coerce_count(payload.get("random_seed"), f"{path}: random_seed"),
        "manifest": _require_text(payload.get("manifest"), f"{path}: manifest"),
    }


def _validate_tissueagent_run(payload: dict[str, Any], path: Path) -> dict[str, Any]:
    if payload.get("status") != "success":
        raise ValueError(f"TissueAgent run did not succeed: {path}")
    if payload.get("method") != "tissueagent":
        raise ValueError(f"TissueAgent run has an unexpected method: {path}")
    if payload.get("outer_graph_status") != "completed":
        raise ValueError(f"TissueAgent outer graph did not complete: {path}")
    if payload.get("routing_audit", {}).get("status") != "passed":
        raise ValueError(f"TissueAgent routing audit did not pass: {path}")
    reference = payload.get("reference_audit")
    if (
        not isinstance(reference, dict)
        or reference.get("status") != "passed"
        or reference.get("agent_generated_under_project_outputs") is not True
    ):
        raise ValueError(f"TissueAgent reference acquisition audit did not pass: {path}")
    available_agents = payload.get("available_domain_agents")
    available_ids = {
        agent.get("id")
        for agent in available_agents or []
        if isinstance(agent, dict)
    }
    registry_audit = payload.get("domain_agent_registry_audit")
    if (
        not {"single_cell", "cell_annotator"}.issubset(available_ids)
        or len(available_ids) < 3
        or not isinstance(registry_audit, dict)
        or registry_audit.get("status") != "passed"
        or registry_audit.get("graph_domain_agents_override") is not False
    ):
        raise ValueError(f"TissueAgent did not expose the full domain-agent registry: {path}")
    invocations = payload.get("agent_invocations")
    invoked_names = {
        invocation.get("agent_name")
        for invocation in invocations or []
        if isinstance(invocation, dict)
    }
    if not {"Single Cell Agent", "Cell Annotator Agent"}.issubset(invoked_names):
        raise ValueError(f"TissueAgent did not recruit the expected agents autonomously: {path}")
    project = payload.get("evaluation_project")
    if (
        not isinstance(project, dict)
        or project.get("status") != "parked"
        or project.get("isolated_from_other_replicates") is not True
    ):
        raise ValueError(f"TissueAgent evaluation project isolation audit failed: {path}")
    model_configuration = payload.get("model_configuration")
    if not isinstance(model_configuration, dict):
        raise ValueError(f"TissueAgent model configuration is absent: {path}")
    return {
        "annotation_method": _require_text(
            payload.get("annotation_method"),
            f"{path}: annotation_method",
        ),
        "label_source": _require_text(payload.get("label_source"), f"{path}: label_source"),
        "mapping_method": _require_text(
            payload.get("mapping_method"),
            f"{path}: mapping_method",
        ),
        "n_predictions": _coerce_count(
            payload.get("n_predictions"),
            f"{path}: n_predictions",
        ),
        "outer_graph_status": payload["outer_graph_status"],
        "routing_audit_status": payload["routing_audit"]["status"],
        "reference_sha256": _require_sha256(
            reference.get("sha256"),
            f"{path}: reference_audit.sha256",
        ),
        "reference_dataset_ids_json": json.dumps(
            sorted(str(value) for value in reference.get("observed_dataset_ids", []))
        ),
        "evaluation_project_id": _require_text(
            project.get("project_id"),
            f"{path}: evaluation_project.project_id",
        ),
        "model_seed": _coerce_count(
            model_configuration.get("request_seed"),
            f"{path}: model_configuration.request_seed",
        ),
    }


def _dataset_invariant(record: dict[str, Any]) -> dict[str, Any]:
    return {
        key: record[key]
        for key in (
            "label_space",
            "target_labels_json",
            "excluded_ground_truth_raw_labels_json",
            "label_contract_sha256",
            "ground_truth_sha256",
            "label_mapping_sha256",
            "n_truth_cells",
            "n_excluded_truth_cells",
            "n_prediction_rows",
            "n_obs",
            "n_vars",
            "random_seed",
            "benchmark_manifest",
        )
    }


def load_repeatability_study(
    manifest_path: str | Path,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Load and validate a manifest-bound TissueAgent repeatability study."""
    manifest_path = Path(manifest_path).expanduser().resolve()
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Study manifest does not exist: {manifest_path}")
    manifest = _read_json(manifest_path, "Study manifest")
    _require_text(manifest.get("schema_version"), "Study manifest schema_version")
    study_id = _require_text(manifest.get("study_id"), "Study manifest study_id")
    datasets = manifest.get("datasets")
    if not isinstance(datasets, list) or not datasets:
        raise ValueError("Study manifest datasets must be a non-empty list.")

    manifest_dir = manifest_path.parent
    seen_dataset_ids: set[str] = set()
    seen_display_names: set[str] = set()
    rows: list[dict[str, Any]] = []
    input_records: list[dict[str, Any]] = []
    dataset_order: list[dict[str, str]] = []
    for position, dataset in enumerate(datasets):
        if not isinstance(dataset, dict):
            raise ValueError("Each study manifest dataset must be an object.")
        dataset_id = _require_text(dataset.get("dataset_id"), "Dataset dataset_id")
        display_name = _require_text(dataset.get("display_name"), "Dataset display_name")
        if dataset_id in seen_dataset_ids:
            raise ValueError(f"Duplicate dataset_id in study manifest: {dataset_id}")
        if display_name in seen_display_names:
            raise ValueError(f"Duplicate display_name in study manifest: {display_name}")
        seen_dataset_ids.add(dataset_id)
        seen_display_names.add(display_name)
        expected_label_space = _require_text(
            dataset.get("expected_label_space"),
            f"{dataset_id}: expected_label_space",
        )
        expected_exclusions = dataset.get("expected_exclusions")
        if (
            not isinstance(expected_exclusions, list)
            or not all(isinstance(label, str) and label for label in expected_exclusions)
            or len(expected_exclusions) != len(set(expected_exclusions))
        ):
            raise ValueError(f"{dataset_id}: expected_exclusions must be a unique string list.")
        runs = dataset.get("runs")
        if not isinstance(runs, list):
            raise ValueError(f"{dataset_id}: runs must be a list.")
        replicates = [run.get("replicate") for run in runs if isinstance(run, dict)]
        if len(runs) != 3 or sorted(replicates) != list(EXPECTED_REPLICATES):
            raise ValueError(
                f"{dataset_id}: runs must contain exactly replicates {EXPECTED_REPLICATES}."
            )

        dataset_order.append({"dataset_id": dataset_id, "display_name": display_name})
        invariant: dict[str, Any] | None = None
        seen_run_ids: set[str] = set()
        for run in sorted(runs, key=lambda value: value["replicate"]):
            replicate = int(run["replicate"])
            manifest_model_seed = _coerce_count(
                run.get("model_seed"),
                f"{dataset_id} replicate {replicate}: model_seed",
            )
            run_id = _require_text(run.get("run_id"), f"{dataset_id} replicate {replicate}: run_id")
            if run_id in seen_run_ids:
                raise ValueError(f"{dataset_id}: duplicate run_id {run_id!r}.")
            seen_run_ids.add(run_id)
            paths = {
                field: _resolve_artifact(
                    manifest_dir,
                    run.get(field),
                    f"{dataset_id} replicate {replicate}: {field}",
                )
                for field in (
                    "prepared_run_json",
                    "tissueagent_run_json",
                    "metrics_tsv",
                    "metrics_json",
                )
            }
            if len(set(paths.values())) != len(paths):
                raise ValueError(f"{dataset_id} replicate {replicate} artifact paths collide.")

            prepared = _validate_prepared_run(
                _read_json(paths["prepared_run_json"], "Prepared run JSON"),
                dataset_id=dataset_id,
                run_id=run_id,
                path=paths["prepared_run_json"],
            )
            tissueagent = _validate_tissueagent_run(
                _read_json(paths["tissueagent_run_json"], "TissueAgent run JSON"),
                paths["tissueagent_run_json"],
            )
            metrics, evaluation = _extract_tissueagent_metrics(
                paths["metrics_tsv"],
                paths["metrics_json"],
            )
            if evaluation["label_space"] != expected_label_space:
                raise ValueError(
                    f"{dataset_id} replicate {replicate} label_space does not match manifest."
                )
            if sorted(evaluation["excluded_ground_truth_raw_labels"]) != sorted(
                expected_exclusions
            ):
                raise ValueError(
                    f"{dataset_id} replicate {replicate} exclusions do not match manifest."
                )
            if evaluation["label_contract_sha256"] != prepared["label_contract_sha256"]:
                raise ValueError(
                    f"{dataset_id} replicate {replicate} label contract differs from prepared run."
                )
            if metrics["n_prediction_rows"] != prepared["n_obs"]:
                raise ValueError(
                    f"{dataset_id} replicate {replicate} prediction rows differ from n_obs."
                )
            if tissueagent["n_predictions"] != metrics["n_prediction_rows"]:
                raise ValueError(
                    f"{dataset_id} replicate {replicate} run prediction count differs from metrics."
                )
            if tissueagent["model_seed"] != manifest_model_seed:
                raise ValueError(
                    f"{dataset_id} replicate {replicate} model seed differs from manifest."
                )

            row = {
                "dataset_id": dataset_id,
                "display_name": display_name,
                "dataset_order": position,
                "replicate": replicate,
                "run_id": run_id,
                **metrics,
                **tissueagent,
                "label_space": evaluation["label_space"],
                "target_labels_json": json.dumps(evaluation["target_labels"]),
                "excluded_ground_truth_raw_labels_json": json.dumps(
                    evaluation["excluded_ground_truth_raw_labels"]
                ),
                "label_contract_sha256": evaluation["label_contract_sha256"],
                "ground_truth_sha256": evaluation["sources"]["ground_truth"]["sha256"],
                "label_mapping_sha256": evaluation["sources"]["label_mapping"]["sha256"],
                "prediction_sha256": evaluation["sources"]["prediction"]["sha256"],
                "selection_blind_id": prepared["selection_blind_id"],
                "n_obs": prepared["n_obs"],
                "n_vars": prepared["n_vars"],
                "random_seed": prepared["random_seed"],
                "benchmark_manifest": prepared["manifest"],
            }
            observed_invariant = _dataset_invariant(row)
            if invariant is None:
                invariant = observed_invariant
            elif observed_invariant != invariant:
                changed = sorted(
                    key for key in invariant if invariant[key] != observed_invariant[key]
                )
                raise ValueError(
                    f"{dataset_id} replicate {replicate} changes frozen dataset inputs: {changed}."
                )
            rows.append(row)
            input_records.append(
                {
                    "dataset_id": dataset_id,
                    "display_name": display_name,
                    "replicate": replicate,
                    "run_id": run_id,
                    "annotation_method": tissueagent["annotation_method"],
                    "selection_blind_id": prepared["selection_blind_id"],
                    "reference_sha256": tissueagent["reference_sha256"],
                    "reference_dataset_ids_json": tissueagent[
                        "reference_dataset_ids_json"
                    ],
                    "evaluation_project_id": tissueagent["evaluation_project_id"],
                    "artifacts": {
                        name: {"path": str(path), "sha256": _sha256(path)}
                        for name, path in paths.items()
                    },
                    "evaluation": evaluation,
                }
            )

    frame = pd.DataFrame(rows).sort_values(["dataset_order", "replicate"]).reset_index(drop=True)
    provenance = {
        "schema_version": "1.0",
        "study_id": study_id,
        "study_manifest": {
            "path": str(manifest_path),
            "sha256": _sha256(manifest_path),
        },
        "dataset_order": dataset_order,
        "inputs": input_records,
    }
    return frame, provenance


def _summarize(metrics: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (dataset_order, dataset_id, display_name), group in metrics.groupby(
        ["dataset_order", "dataset_id", "display_name"],
        sort=True,
    ):
        for metric, _ in METRICS:
            values = group[metric].astype(float)
            rows.append(
                {
                    "dataset_id": dataset_id,
                    "display_name": display_name,
                    "dataset_order": dataset_order,
                    "metric": metric,
                    "n_runs": len(values),
                    "mean": float(values.mean()),
                    "sample_sd": float(values.std(ddof=1)),
                    "minimum": float(values.min()),
                    "maximum": float(values.max()),
                }
            )
    return pd.DataFrame(rows)


def _plot(
    metrics: pd.DataFrame,
    summary: pd.DataFrame,
    *,
    title: str,
    note: str,
    png_path: Path,
    pdf_path: Path,
) -> str:
    datasets = (
        metrics[["dataset_id", "display_name", "dataset_order"]]
        .drop_duplicates()
        .sort_values("dataset_order")
    )
    display_names = datasets["display_name"].tolist()
    x_positions = list(range(len(datasets)))
    rendered_note = (
        f"{note.rstrip()} Bars are means; error bars are ±1 sample SD across n=3 "
        "independent fresh TissueAgent executions; points are individual runs."
    )
    note_lines = textwrap.wrap(rendered_note, width=145) or [""]
    figure, axes = plt.subplots(
        1,
        len(METRICS),
        figsize=(15, 7.2 + 0.25 * max(0, len(note_lines) - 1)),
        sharey=True,
    )
    upper_values: list[float] = []
    for metric, _ in METRICS:
        metric_summary = summary.loc[summary["metric"] == metric].sort_values("dataset_order")
        upper_values.extend((metric_summary["mean"] + metric_summary["sample_sd"]).tolist())
    y_upper = max(1.02, max(upper_values) + 0.06)

    point_offsets = (-0.10, 0.0, 0.10)
    for axis, (metric, panel_title) in zip(axes, METRICS, strict=True):
        metric_summary = summary.loc[summary["metric"] == metric].sort_values("dataset_order")
        means = metric_summary["mean"].to_numpy(dtype=float)
        standard_deviations = metric_summary["sample_sd"].to_numpy(dtype=float)
        bars = axis.bar(
            x_positions,
            means,
            0.54,
            yerr=standard_deviations,
            capsize=6,
            color=TISSUEAGENT_COLOR,
            error_kw={"elinewidth": 1.6, "capthick": 1.6},
        )
        for dataset_position, dataset_id in enumerate(datasets["dataset_id"]):
            values = (
                metrics.loc[metrics["dataset_id"] == dataset_id]
                .sort_values("replicate")[metric]
                .to_numpy(dtype=float)
            )
            axis.scatter(
                [dataset_position + offset for offset in point_offsets],
                values,
                color=POINT_COLOR,
                edgecolor="white",
                linewidth=0.8,
                s=38,
                zorder=4,
            )
        for bar, mean, standard_deviation in zip(
            bars,
            means,
            standard_deviations,
            strict=True,
        ):
            axis.text(
                bar.get_x() + bar.get_width() / 2,
                mean + standard_deviation + 0.015,
                f"{mean:.2f}",
                ha="center",
                va="bottom",
                fontsize=10,
            )
        axis.set_title(panel_title, loc="left", fontsize=17, fontweight="bold")
        axis.set_xticks(x_positions, display_names)
        axis.tick_params(axis="x", labelsize=12)
        axis.tick_params(axis="y", labelsize=11)
        axis.set_ylim(0, y_upper)
        axis.grid(axis="y", color="#D9D9D9", linewidth=0.8)
        axis.set_axisbelow(True)
        axis.spines["top"].set_visible(False)
        axis.spines["right"].set_visible(False)
        axis.set_ylabel("Score", fontsize=13)

    figure.suptitle(title, fontsize=20, fontweight="bold", y=0.98)
    figure.text(
        0.5,
        0.02,
        "\n".join(note_lines),
        ha="center",
        va="bottom",
        fontsize=10.5,
        color="#555555",
    )
    note_margin = 0.07 + 0.025 * max(0, len(note_lines) - 1)
    figure.tight_layout(rect=(0.02, note_margin, 1, 0.93), w_pad=3.5)
    figure.savefig(png_path, dpi=220, bbox_inches="tight")
    figure.savefig(pdf_path, bbox_inches="tight")
    plt.close(figure)
    return rendered_note


def plot_tissueagent_repeatability(
    manifest_path: str | Path,
    output_dir: str | Path,
    *,
    output_prefix: str = "tissueagent_repeatability",
    title: str = "End-to-end TissueAgent repeatability on full benchmark datasets",
    note: str = (
        "Frozen query and label contracts; TissueAgent independently acquires a reference and "
        "configures one backend per run; missing predictions count as Unassigned."
    ),
) -> dict[str, Any]:
    """Validate, aggregate, plot, and provenance-bind a repeatability study."""
    if not output_prefix or Path(output_prefix).name != output_prefix:
        raise ValueError("output_prefix must be a non-empty file-name prefix.")
    manifest_path = Path(manifest_path).expanduser().resolve()
    output_dir = Path(output_dir).expanduser().resolve()
    planned_outputs = {
        "runs_tsv": output_dir / f"{output_prefix}_runs.tsv",
        "summary_tsv": output_dir / f"{output_prefix}_summary.tsv",
        "png": output_dir / f"{output_prefix}_accuracy_macro_precision.png",
        "pdf": output_dir / f"{output_prefix}_accuracy_macro_precision.pdf",
        "provenance_json": output_dir / f"{output_prefix}_provenance.json",
    }
    if manifest_path in planned_outputs.values():
        raise ValueError("Output paths collide with the study manifest.")
    existing = sorted(path for path in planned_outputs.values() if path.exists())
    if existing:
        raise FileExistsError(
            "Refusing to overwrite existing repeatability artifacts: "
            + ", ".join(str(path) for path in existing)
        )

    metrics, provenance = load_repeatability_study(manifest_path)
    input_paths = {
        Path(artifact["path"])
        for record in provenance["inputs"]
        for artifact in record["artifacts"].values()
    }
    collisions = sorted(set(planned_outputs.values()).intersection(input_paths))
    if collisions:
        raise ValueError(
            "Output paths collide with repeatability inputs: "
            + ", ".join(str(path) for path in collisions)
        )

    summary = _summarize(metrics)
    output_dir.mkdir(parents=True, exist_ok=True)
    metrics.to_csv(planned_outputs["runs_tsv"], sep="\t", index=False)
    summary.to_csv(planned_outputs["summary_tsv"], sep="\t", index=False)
    rendered_note = _plot(
        metrics,
        summary,
        title=title,
        note=note,
        png_path=planned_outputs["png"],
        pdf_path=planned_outputs["pdf"],
    )

    provenance.update(
        {
            "error_bars": {
                "central_value": "arithmetic_mean",
                "dispersion": "sample_standard_deviation",
                "ddof": 1,
                "n_replicates_per_dataset": 3,
                "raw_points_overlaid": True,
            },
            "metrics": [metric for metric, _ in METRICS],
            "title": title,
            "note_prefix": note,
            "rendered_note": rendered_note,
            "outputs": {
                name: {"path": str(path), "sha256": _sha256(path)}
                for name, path in planned_outputs.items()
                if name != "provenance_json"
            },
            "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
    )
    planned_outputs["provenance_json"].write_text(
        json.dumps(provenance, indent=2),
        encoding="utf-8",
    )
    provenance["provenance_json"] = str(planned_outputs["provenance_json"])
    return provenance


def main() -> None:
    """Parse a study manifest and write repeatability artifacts."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--output-prefix", default="tissueagent_repeatability")
    parser.add_argument(
        "--title",
        default="End-to-end TissueAgent repeatability on full benchmark datasets",
    )
    parser.add_argument(
        "--note",
        default=(
            "Frozen query and label contracts; TissueAgent independently acquires a reference "
            "and configures one backend per run; missing predictions count as Unassigned."
        ),
    )
    args = parser.parse_args()
    result = plot_tissueagent_repeatability(
        args.manifest,
        args.output_dir,
        output_prefix=args.output_prefix,
        title=args.title,
        note=args.note,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
