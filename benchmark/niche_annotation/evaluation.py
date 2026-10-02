"""Direct-label evaluation of named tissue niches without semantic remapping."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix, precision_recall_fscore_support

from .protocol import (
    LEGACY_PROMPT_VERSION,
    PROTOCOL,
    SUPPORTED_PROMPT_VERSIONS,
    UNMATCHED,
    normalize_predictions,
    scientific_prompt,
    sha256,
    write_json,
)


def score_predictions(truth: pd.Series, predictions: pd.Series, labels: list[str]) -> tuple:
    """Score all supplied truth cells, counting missing predictions as abstentions."""
    if not truth.index.is_unique or not predictions.index.is_unique:
        raise ValueError("Scoring requires unique cell IDs.")
    if truth.isna().any() or not set(truth).issubset(labels):
        raise ValueError("Scored truth must contain only the declared biological classes.")
    predicted = normalize_predictions(predictions.reindex(truth.index), labels)
    precision, recall, f1, support = precision_recall_fscore_support(
        truth.to_numpy(dtype=str), predicted.to_numpy(dtype=str), labels=labels, zero_division=0
    )
    by_class = pd.DataFrame(
        {"label": labels, "precision": precision, "recall": recall, "f1": f1, "support": support}
    )
    metrics = {
        "macro_f1": float(f1.mean()) if len(truth) else np.nan,
        "balanced_accuracy": float(recall[support > 0].mean()) if len(truth) else np.nan,
        "n_scored": len(truth),
        "prediction_coverage": float((predicted != UNMATCHED).mean()) if len(truth) else np.nan,
    }
    classes = [*labels, UNMATCHED]
    matrix = pd.DataFrame(
        confusion_matrix(truth.to_numpy(dtype=str), predicted.to_numpy(dtype=str), labels=classes),
        index=classes,
        columns=classes,
    )
    matrix.index.name = "ground_truth"
    return metrics, by_class, matrix


def load_study(study_dir: Path) -> dict:
    """Load one frozen agent study with the expected protocol."""
    study = json.loads((study_dir / "study_manifest.json").read_text())
    if study["protocol"] != PROTOCOL:
        raise ValueError("Study uses a different annotation protocol.")
    version = study.get("prompt_version", LEGACY_PROMPT_VERSION)
    if version not in SUPPORTED_PROMPT_VERSIONS:
        raise ValueError("Study uses an unknown prompt version.")
    if any(
        entry.get("prompt_version", LEGACY_PROMPT_VERSION) != version for entry in study["runs"]
    ):
        raise ValueError("Study mixes different prompt versions.")
    return study


def load_truth(preparation: dict) -> pd.DataFrame:
    """Read and verify evaluator-only truth and cell identity metadata."""
    if sha256(preparation["truth_tsv"]) != preparation["truth_sha256"]:
        raise ValueError("Evaluation truth was modified.")
    truth = pd.read_csv(
        preparation["truth_tsv"], sep="\t", dtype={"cell_id": str}, keep_default_na=False
    ).set_index("cell_id")
    if not truth.index.is_unique or len(truth) != preparation["n_cells"]:
        raise ValueError("Truth IDs differ from the prepared cohort.")
    if truth["scored"].dtype != bool:
        raise ValueError("The private scored mask must be boolean.")
    return truth


def load_predictions(
    study_dir: Path, entry: dict, section: dict, expected_ids: pd.Index
) -> pd.Series | None:
    """Verify one run and return its final labels, or None for a failed run."""
    record_path = study_dir / entry["record"]
    if sha256(record_path) != entry["record_sha256"]:
        raise ValueError("Run record was modified.")
    record = json.loads(record_path.read_text())
    for key in ("method", "model", "seed", "section_id", "status"):
        if record[key] != entry[key]:
            raise ValueError(f"Run record disagrees with study field {key}.")
    version = entry.get("prompt_version", LEGACY_PROMPT_VERSION)
    if record.get("prompt_version", LEGACY_PROMPT_VERSION) != version:
        raise ValueError("Run record disagrees with the study prompt version.")
    if record["query_sha256"] != section["query_sha256"]:
        raise ValueError("Methods used different section inputs.")
    if record["status"] == "failed":
        return None
    if record["status"] not in {"success", "partial"}:
        raise ValueError("Run is not finalized.")
    if record["contract"] != section["contract"]:
        raise ValueError("Run used a different public annotation contract.")
    expected_prompt = scientific_prompt(
        section["contract"], "<QUERY_H5AD>", "<ANNOTATED_H5AD>", version=version
    )
    if record["task_prompt_template"] != expected_prompt:
        raise ValueError("Run used a different scientific task prompt.")
    path = record_path.parent / "predictions.tsv"
    if sha256(path) != record["predictions_sha256"]:
        raise ValueError("Prediction artifact was modified.")
    predictions = pd.read_csv(path, sep="\t", dtype="string", keep_default_na=False)
    predictions = predictions.set_index("cell_id")
    if not predictions.index.is_unique or set(predictions.index) != set(expected_ids):
        raise ValueError("Predictions do not preserve the full expected cohort.")
    normalized = normalize_predictions(predictions["raw_label"], section["contract"]["labels"])
    if not (normalized == predictions["tissue_niche"]).all():
        raise ValueError("Final labels differ from the direct-label normalization contract.")
    return predictions["tissue_niche"].reindex(expected_ids)


def evaluate_study(study_dir: Path) -> pd.DataFrame:
    """Score the complete planned matrix, retaining partial, failed and pending runs."""
    study = load_study(study_dir)
    entries = {(e["dataset"], e["method"], e["seed"], e["section_id"]): e for e in study["runs"]}
    if len(entries) != len(study["runs"]):
        raise ValueError("Study contains duplicate jobs.")
    output = study_dir / "evaluation"
    output.mkdir(exist_ok=True)
    rows, section_rows, class_rows = [], [], []
    for dataset, prepared in study["preparations"].items():
        truth = load_truth(prepared)
        labels = prepared["sections"][0]["contract"]["labels"]
        scored = truth.loc[truth["scored"], "ground_truth"]
        if set(scored) != set(labels):
            raise ValueError("Every declared class must be represented in dataset-level truth.")
        for method in study["config"]["methods"]:
            model = study["config"].get(method, {}).get("model", study["config"]["model"])
            for seed in study["config"].get(method, {}).get("seeds", study["config"]["seeds"]):
                info = {"dataset": dataset, "method": method, "model": model, "seed": seed}
                predictions = pd.Series(UNMATCHED, index=truth.index, dtype="string")
                statuses = []
                for section in prepared["sections"]:
                    ids = truth.index[truth["section_id"] == section["section_id"]]
                    entry = entries.get((dataset, method, seed, section["section_id"]))
                    if entry and entry["model"] != model:
                        raise ValueError(
                            "Run model differs from the configured comparison condition."
                        )
                    result = load_predictions(study_dir, entry, section, ids) if entry else None
                    status = entry["status"] if entry else "pending"
                    statuses.append(status)
                    if result is not None:
                        predictions.loc[ids] = result
                    section_truth = scored.loc[scored.index.intersection(ids)]
                    metrics, _, _ = score_predictions(section_truth, predictions, labels)
                    if result is None:
                        metrics.update(macro_f1=np.nan, balanced_accuracy=np.nan)
                    section_rows.append(
                        {**info, "section_id": section["section_id"], "status": status, **metrics}
                    )
                usable = sum(status in {"success", "partial"} for status in statuses)
                status = (
                    "success"
                    if all(s == "success" for s in statuses)
                    else ("partial" if usable else "failed" if "failed" in statuses else "pending")
                )
                metrics, classes, matrix = score_predictions(scored, predictions, labels)
                if not usable:
                    metrics.update(macro_f1=np.nan, balanced_accuracy=np.nan)
                else:
                    class_rows.append(classes.assign(**info))
                    matrix.to_csv(
                        output / f"{dataset}-{method}-seed-{seed}-confusion.tsv", sep="\t"
                    )
                rows.append(
                    {
                        **info,
                        "status": status,
                        "n_cells": len(truth),
                        "n_unscored_truth": len(truth) - len(scored),
                        "n_sections_with_output": usable,
                        "n_sections": len(statuses),
                        **metrics,
                    }
                )
    metrics = pd.DataFrame(rows)
    metrics.to_csv(output / "metrics.tsv", sep="\t", index=False)
    pd.DataFrame(section_rows).to_csv(output / "per_section_metrics.tsv", sep="\t", index=False)
    if class_rows:
        pd.concat(class_rows).to_csv(output / "per_class_metrics.tsv", sep="\t", index=False)
    summary = metrics.groupby(["dataset", "method", "model"], sort=False).agg(
        macro_f1_mean=("macro_f1", "mean"),
        macro_f1_std=("macro_f1", "std"),
        balanced_accuracy_mean=("balanced_accuracy", "mean"),
        balanced_accuracy_std=("balanced_accuracy", "std"),
        n_scored_runs=("macro_f1", "count"),
        n_planned_runs=("seed", "size"),
        n_successful_runs=("status", lambda values: int((values == "success").sum())),
    )
    summary.to_csv(output / "summary.tsv", sep="\t")
    write_json(
        output / "evaluation.json",
        {
            "protocol": PROTOCOL,
            "prompt_version": study.get("prompt_version", LEGACY_PROMPT_VERSION),
            "study_manifest_sha256": sha256(study_dir / "study_manifest.json"),
            "metrics_sha256": sha256(output / "metrics.tsv"),
            "summary_sha256": sha256(output / "summary.tsv"),
            "macro_classes": "fixed biological labels; Unmatched excluded from macro averaging",
            "balanced_accuracy": "unadjusted mean recall of truth-supported biological classes",
            "missing_prediction_policy": "Unmatched; no intersection-only scoring or LLM remapping",
            "partial_run_policy": "missing sections count as Unmatched in pooled dataset scores",
        },
    )
    return metrics
