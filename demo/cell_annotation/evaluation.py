"""Leakage-safe, coverage-aware benchmark evaluation."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from langchain_core.messages import HumanMessage, SystemMessage
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
    precision_score,
)

from .benchmarks import REPO_ROOT, _label_contract_sha256, _sha256


UNASSIGNED = "Unassigned"

PREDICTION_MAPPING_SYSTEM_PROMPT = """\
Map free-text cell-annotation labels into a frozen evaluation label space.
Use only the semantic content of each raw prediction label and the supplied target definitions.
Do not infer disease, malignancy, tissue, or subtype from context that is not stated in the raw
label. Map ambiguous or unsupported labels to Unassigned. Return only one JSON object whose keys
exactly match the supplied unseen prediction labels and whose values are allowed target labels.
"""


def _path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path


def _verify_label_contract(prepared: dict[str, Any], mapping: dict[str, Any]) -> None:
    expected = prepared.get("label_contract_sha256")
    if expected is None:
        return
    observed = _label_contract_sha256(mapping)
    if observed != expected:
        raise ValueError(
            "Frozen label contract SHA-256 does not match the prepared benchmark; "
            "refusing to score predictions against a mutated label space."
        )


def _message_content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("type") in {"text", "output_text"}:
                parts.append(str(item.get("text", "")))
        return "\n".join(part for part in parts if part).strip()
    return str(content).strip()


def _strip_json_fence(response_text: str) -> str:
    stripped = response_text.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.DOTALL)
    return fenced.group(1).strip() if fenced else stripped


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Prediction-mapping response contains duplicate key {key!r}.")
        result[key] = value
    return result


def _prediction_mapping_method(predictions: pd.DataFrame, default: str) -> str:
    if "mapping_method" not in predictions:
        return default
    values = predictions["mapping_method"].dropna().astype(str).unique()
    if len(values) != 1:
        raise ValueError(
            f"{default} predictions must declare exactly one mapping_method; "
            f"found {sorted(values)}."
        )
    return str(values[0])


def _is_recognized_prediction_label(
    value: str,
    *,
    mapping: dict[str, Any],
    mapping_method: str,
) -> bool:
    if value in mapping.get("method_prediction_mapping", {}).get(mapping_method, {}):
        return True
    if value in mapping.get("common_prediction_mapping", {}):
        return True
    if value in mapping["target_labels"]:
        return True
    numeric_prefix = re.match(r"^(\d+)\s", value)
    if not numeric_prefix:
        return False
    numeric_value = int(numeric_prefix.group(1))
    return any(
        int(rule["numeric_prefix_min"]) <= numeric_value <= int(rule["numeric_prefix_max"])
        for rule in mapping.get("method_prediction_rules", {}).get(mapping_method, [])
    )


def _unseen_prediction_labels(
    predictions: pd.DataFrame,
    *,
    mapping: dict[str, Any],
    mapping_method: str,
) -> list[str]:
    labels = {str(value) for value in predictions["raw_prediction"].dropna().astype(str).unique()}
    return sorted(
        label
        for label in labels
        if not _is_recognized_prediction_label(
            label,
            mapping=mapping,
            mapping_method=mapping_method,
        )
    )


def _parse_prediction_mapping_response(
    response_text: str,
    *,
    unseen_labels: list[str],
    target_labels: list[str],
) -> dict[str, str]:
    if not response_text:
        raise ValueError("Prediction-mapping response was empty.")
    try:
        payload = json.loads(
            _strip_json_fence(response_text),
            object_pairs_hook=_reject_duplicate_json_keys,
        )
    except json.JSONDecodeError as exc:
        raise ValueError(f"Prediction-mapping response was not valid JSON: {exc.msg}.") from exc
    if not isinstance(payload, dict):
        raise ValueError("Prediction-mapping response must be one JSON object.")
    expected = set(unseen_labels)
    actual = set(payload)
    if actual != expected:
        raise ValueError(
            "Prediction-mapping response keys did not match unseen labels exactly; "
            f"missing={sorted(expected - actual)}, extra={sorted(actual - expected)}."
        )
    invalid_targets = sorted(
        {
            str(target)
            for target in payload.values()
            if not isinstance(target, str) or target not in target_labels
        }
    )
    if invalid_targets:
        raise ValueError(
            "Prediction-mapping response used targets outside the frozen label space: "
            + ", ".join(invalid_targets)
        )
    return {label: str(payload[label]) for label in unseen_labels}


def materialize_prediction_mapping(
    label_mapping_path: str | Path,
    prediction_path: str | Path,
    output_path: str | Path,
    *,
    prediction_method: str,
    model: Any,
    model_metadata: dict[str, Any],
) -> dict[str, Any]:
    """Create a truth-blind, run-local mapping for unseen prediction labels."""
    resolved_mapping_path = _path(label_mapping_path)
    resolved_prediction_path = _path(prediction_path)
    resolved_output_path = _path(output_path)
    mapping = json.loads(resolved_mapping_path.read_text(encoding="utf-8"))
    predictions = pd.read_csv(
        resolved_prediction_path,
        sep="\t",
        index_col=0,
        low_memory=False,
    )
    if "raw_prediction" not in predictions:
        raise ValueError("Predictions are missing the raw_prediction column.")
    mapping_method = _prediction_mapping_method(predictions, prediction_method)
    unseen_labels = _unseen_prediction_labels(
        predictions,
        mapping=mapping,
        mapping_method=mapping_method,
    )
    target_labels = list(mapping["target_labels"])
    human_prompt = json.dumps(
        {
            "target_labels": target_labels,
            "target_label_definitions": mapping.get("target_label_definitions", {}),
            "unseen_prediction_labels": unseen_labels,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    raw_response = ""
    extension: dict[str, str] = {}
    if unseen_labels:
        response = model.invoke(
            [
                SystemMessage(PREDICTION_MAPPING_SYSTEM_PROMPT),
                HumanMessage(human_prompt),
            ]
        )
        raw_response = _message_content_to_text(response.content)
        extension = _parse_prediction_mapping_response(
            raw_response,
            unseen_labels=unseen_labels,
            target_labels=target_labels,
        )
    artifact = {
        "schema_version": "1.0",
        "status": "complete",
        "prediction_method": prediction_method,
        "mapping_method": mapping_method,
        "prediction_path": str(resolved_prediction_path),
        "prediction_sha256": _sha256(resolved_prediction_path),
        "base_mapping_path": str(resolved_mapping_path),
        "base_mapping_sha256": _sha256(resolved_mapping_path),
        "label_contract_sha256": _label_contract_sha256(mapping),
        "target_labels": target_labels,
        "unseen_prediction_labels": unseen_labels,
        "mapping": extension,
        "model": model_metadata if unseen_labels else None,
        "system_prompt": PREDICTION_MAPPING_SYSTEM_PROMPT if unseen_labels else None,
        "human_prompt": human_prompt if unseen_labels else None,
        "raw_response": raw_response if unseen_labels else None,
    }
    resolved_output_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_output_path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    return artifact


def _load_prediction_mapping(
    prediction_mapping_path: str | Path,
    *,
    mapping: dict[str, Any],
    mapping_path: Path,
    prediction_method: str,
    prediction_path: Path,
    predictions: pd.DataFrame,
    mapping_method: str,
) -> dict[str, str]:
    artifact = json.loads(_path(prediction_mapping_path).read_text(encoding="utf-8"))
    if artifact.get("status") != "complete":
        raise ValueError("Run-local prediction mapping is not complete.")
    expected_fields = {
        "prediction_method": prediction_method,
        "mapping_method": mapping_method,
        "prediction_sha256": _sha256(prediction_path),
        "base_mapping_sha256": _sha256(mapping_path),
        "label_contract_sha256": _label_contract_sha256(mapping),
        "target_labels": list(mapping["target_labels"]),
    }
    mismatches = [
        field for field, expected in expected_fields.items() if artifact.get(field) != expected
    ]
    if mismatches:
        raise ValueError(
            "Run-local prediction mapping does not match its frozen inputs: "
            + ", ".join(mismatches)
        )
    unseen_labels = _unseen_prediction_labels(
        predictions,
        mapping=mapping,
        mapping_method=mapping_method,
    )
    if artifact.get("unseen_prediction_labels") != unseen_labels:
        raise ValueError("Run-local prediction mapping does not cover the current unseen labels.")
    extension = artifact.get("mapping")
    if not isinstance(extension, dict):
        raise ValueError("Run-local prediction mapping must contain one mapping object.")
    return _parse_prediction_mapping_response(
        json.dumps(extension),
        unseen_labels=unseen_labels,
        target_labels=list(mapping["target_labels"]),
    )


def _evaluation_sources(
    prepared: dict[str, Any],
    prediction_paths: dict[str, str | Path],
    prediction_mapping_path: str | Path | None = None,
) -> dict[str, Any]:
    truth_path = _path(prepared["ground_truth_tsv"])
    mapping_path = _path(prepared["label_mapping_json"])
    sources = {
        "ground_truth": {
            "path": str(truth_path),
            "sha256": _sha256(truth_path),
        },
        "label_mapping": {
            "path": str(mapping_path),
            "sha256": _sha256(mapping_path),
        },
        "predictions": {
            method: {
                "path": str(_path(prediction_path)),
                "sha256": _sha256(_path(prediction_path)),
            }
            for method, prediction_path in sorted(prediction_paths.items())
        },
    }
    if prediction_mapping_path is not None:
        resolved_prediction_mapping_path = _path(prediction_mapping_path)
        sources["prediction_mapping"] = {
            "path": str(resolved_prediction_mapping_path),
            "sha256": _sha256(resolved_prediction_mapping_path),
        }
    return sources


def _resolve_label_space(
    mapping: dict[str, Any],
    label_space: str,
) -> tuple[list[str], list[str], dict[str, str]]:
    primary_labels = list(mapping["target_labels"])
    if label_space == "primary":
        return primary_labels, primary_labels, {label: label for label in primary_labels}

    secondary_spaces = mapping.get("secondary_label_spaces", {})
    if label_space not in secondary_spaces:
        available = ", ".join(sorted(secondary_spaces)) or "none"
        raise ValueError(
            f"Unknown secondary label space {label_space!r}; available spaces: {available}."
        )
    definition = secondary_spaces[label_space]
    target_labels = list(definition["target_labels"])
    mapping_from_primary = {
        str(source): str(target) for source, target in definition["mapping_from_primary"].items()
    }
    missing_primary = sorted(set(primary_labels).difference(mapping_from_primary))
    if missing_primary:
        raise ValueError(
            f"Secondary label space {label_space!r} mapping_from_primary is incomplete: "
            + ", ".join(missing_primary)
        )
    extra_primary = sorted(set(mapping_from_primary).difference(primary_labels))
    if extra_primary:
        raise ValueError(
            f"Secondary label space {label_space!r} maps unknown primary labels: "
            + ", ".join(extra_primary)
        )
    unknown_targets = sorted(set(mapping_from_primary.values()).difference(target_labels))
    if unknown_targets:
        raise ValueError(
            f"Secondary label space {label_space!r} maps outside its target label set: "
            + ", ".join(unknown_targets)
        )
    if len(target_labels) != len(set(target_labels)):
        raise ValueError(f"Secondary label space {label_space!r} has duplicate target labels.")
    if UNASSIGNED in primary_labels and (
        UNASSIGNED not in target_labels or mapping_from_primary[UNASSIGNED] != UNASSIGNED
    ):
        raise ValueError(f"Secondary label space {label_space!r} must preserve {UNASSIGNED!r}.")
    return primary_labels, target_labels, mapping_from_primary


def evaluate_predictions(
    prepared: dict[str, Any] | str | Path,
    prediction_paths: dict[str, str | Path] | None = None,
    *,
    label_space: str = "primary",
    exclude_ground_truth_raw_labels: list[str] | None = None,
    prediction_mapping_path: str | Path | None = None,
    output_stem: str = "metrics",
) -> pd.DataFrame:
    """Score every truth cell, explicitly counting missing/unmapped predictions."""
    if not isinstance(prepared, dict):
        prepared = json.loads(_path(prepared).read_text(encoding="utf-8"))
    run_dir = _path(prepared["run_dir"])
    truth = pd.read_csv(
        _path(prepared["ground_truth_tsv"]), sep="\t", index_col=0, low_memory=False
    )
    truth.index = truth.index.astype(str)
    if not truth.index.is_unique:
        raise ValueError("Ground-truth cell identifiers are not unique.")
    all_truth_index = truth.index.copy()
    mapping = json.loads(_path(prepared["label_mapping_json"]).read_text(encoding="utf-8"))
    _verify_label_contract(prepared, mapping)
    truth_column = prepared["ground_truth_column"]
    ground_truth_mapping = mapping["ground_truth_mapping"]
    raw_truth = truth[truth_column].astype(str)
    excluded_labels = set(exclude_ground_truth_raw_labels or [])
    if excluded_labels:
        missing_exclusions = sorted(excluded_labels.difference(raw_truth.unique()))
        if missing_exclusions:
            raise ValueError(
                "Requested ground-truth exclusions were not found: " + ", ".join(missing_exclusions)
            )
        keep = ~raw_truth.isin(excluded_labels)
        truth = truth.loc[keep].copy()
        raw_truth = raw_truth.loc[keep]
    unmapped_truth = sorted(set(raw_truth).difference(ground_truth_mapping))
    if unmapped_truth:
        raise ValueError("Ground-truth mapping is incomplete: " + ", ".join(unmapped_truth))
    primary_target_labels, target_labels, mapping_from_primary = _resolve_label_space(
        mapping,
        label_space,
    )
    primary_truth = raw_truth.map(ground_truth_mapping)
    unknown_targets = sorted(set(primary_truth).difference(primary_target_labels))
    if unknown_targets:
        raise ValueError(
            "Ground truth maps outside target label set: " + ", ".join(unknown_targets)
        )
    harmonized_truth = primary_truth.map(mapping_from_primary)

    if prediction_paths is None:
        prediction_paths = {
            method: run_dir / f"{method}_predictions.tsv"
            for method in ("tissueagent", "celltypist", "gptcelltype")
            if (run_dir / f"{method}_predictions.tsv").exists()
        }
    if not prediction_paths:
        raise FileNotFoundError(f"No prediction files were supplied or found in {run_dir}.")
    if prediction_mapping_path is not None and len(prediction_paths) != 1:
        raise ValueError("One run-local prediction mapping can score exactly one prediction file.")

    score_labels = [label for label in target_labels if label != UNASSIGNED]
    rows: list[dict[str, Any]] = []
    for method, prediction_path in prediction_paths.items():
        resolved_prediction_path = _path(prediction_path)
        predictions = pd.read_csv(
            resolved_prediction_path,
            sep="\t",
            index_col=0,
            low_memory=False,
        )
        predictions.index = predictions.index.astype(str)
        if not predictions.index.is_unique:
            raise ValueError(f"{method} predictions contain duplicate cell identifiers.")
        extra = predictions.index.difference(all_truth_index)
        if len(extra):
            raise ValueError(
                f"{method} predictions contain {len(extra)} cells absent from ground truth."
            )
        aligned = predictions.reindex(truth.index)
        raw_prediction = aligned["raw_prediction"].astype("string")
        mapping_method = _prediction_mapping_method(predictions, method)
        method_mapping = dict(mapping.get("method_prediction_mapping", {}).get(mapping_method, {}))
        if prediction_mapping_path is not None:
            method_mapping.update(
                _load_prediction_mapping(
                    prediction_mapping_path,
                    mapping=mapping,
                    mapping_path=_path(prepared["label_mapping_json"]),
                    prediction_method=method,
                    prediction_path=resolved_prediction_path,
                    predictions=predictions,
                    mapping_method=mapping_method,
                )
            )
        method_rules = mapping.get("method_prediction_rules", {}).get(mapping_method, [])
        common_mapping = mapping.get("common_prediction_mapping", {})

        def harmonize(value: Any) -> str:
            if pd.isna(value):
                return UNASSIGNED
            text = str(value)
            if text in method_mapping:
                return method_mapping[text]
            if text in common_mapping:
                return common_mapping[text]
            if text in primary_target_labels:
                return text
            numeric_prefix = re.match(r"^(\d+)\s", text)
            if numeric_prefix:
                numeric_value = int(numeric_prefix.group(1))
                for rule in method_rules:
                    if (
                        int(rule["numeric_prefix_min"])
                        <= numeric_value
                        <= int(rule["numeric_prefix_max"])
                    ):
                        return str(rule["target"])
            return UNASSIGNED

        def is_recognized(value: Any) -> bool:
            if pd.isna(value):
                return True
            text = str(value)
            if text in method_mapping or text in common_mapping or text in primary_target_labels:
                return True
            numeric_prefix = re.match(r"^(\d+)\s", text)
            if not numeric_prefix:
                return False
            numeric_value = int(numeric_prefix.group(1))
            return any(
                int(rule["numeric_prefix_min"]) <= numeric_value <= int(rule["numeric_prefix_max"])
                for rule in method_rules
            )

        primary_prediction = raw_prediction.map(harmonize)
        unknown_prediction_targets = sorted(
            set(primary_prediction).difference(primary_target_labels)
        )
        if unknown_prediction_targets:
            raise ValueError(
                f"{method} predictions map outside primary target label set: "
                + ", ".join(unknown_prediction_targets)
            )
        harmonized_prediction = primary_prediction.map(mapping_from_primary)
        unmapped_mask = raw_prediction.notna() & ~raw_prediction.map(is_recognized)
        unmapped_counts = raw_prediction[unmapped_mask].value_counts().to_dict()
        if prediction_mapping_path is not None and unmapped_counts:
            raise ValueError(
                f"Run-local prediction mapping is incomplete for {method}: "
                + ", ".join(sorted(unmapped_counts))
            )
        ontology_mapped_coverage = float((harmonized_prediction != UNASSIGNED).mean())
        prediction_row_coverage = float(
            len(predictions.index.intersection(all_truth_index)) / len(all_truth_index)
        )
        nonmissing_prediction_coverage = float(raw_prediction.notna().mean())
        metrics = {
            "method": method,
            "n_truth_cells": len(truth),
            "n_excluded_truth_cells": int(len(all_truth_index) - len(truth)),
            "n_prediction_rows": len(predictions),
            "n_assigned": int((harmonized_prediction != UNASSIGNED).sum()),
            "n_unassigned": int((harmonized_prediction == UNASSIGNED).sum()),
            "backend_prediction_row_coverage": prediction_row_coverage,
            "scored_raw_prediction_nonmissing_coverage": nonmissing_prediction_coverage,
            "ontology_mapped_prediction_coverage": ontology_mapped_coverage,
            "prediction_coverage": ontology_mapped_coverage,
            "accuracy": float(accuracy_score(harmonized_truth, harmonized_prediction)),
            "balanced_accuracy": float(
                balanced_accuracy_score(harmonized_truth, harmonized_prediction)
            ),
            "macro_precision": float(
                precision_score(
                    harmonized_truth,
                    harmonized_prediction,
                    labels=score_labels,
                    average="macro",
                    zero_division=0,
                )
            ),
            "macro_f1": float(
                f1_score(
                    harmonized_truth,
                    harmonized_prediction,
                    labels=score_labels,
                    average="macro",
                    zero_division=0,
                )
            ),
            "n_unmapped_raw_labels": len(unmapped_counts),
        }
        rows.append(metrics)
        artifact_tag = (
            "" if output_stem == "metrics" else f"_{output_stem.removeprefix('metrics_')}"
        )
        normalized = pd.DataFrame(
            {
                "ground_truth_raw": raw_truth,
                "ground_truth": harmonized_truth,
                "prediction_raw": raw_prediction,
                "prediction": harmonized_prediction,
            },
            index=truth.index,
        )
        normalized.index.name = "cell_id"
        normalized.to_csv(
            run_dir / f"{method}{artifact_tag}_evaluated_predictions.tsv",
            sep="\t",
        )
        matrix = confusion_matrix(
            harmonized_truth,
            harmonized_prediction,
            labels=target_labels,
        )
        pd.DataFrame(matrix, index=target_labels, columns=target_labels).to_csv(
            run_dir / f"{method}{artifact_tag}_confusion_matrix.tsv",
            sep="\t",
        )
        precision, recall, per_class_f1, support = precision_recall_fscore_support(
            harmonized_truth,
            harmonized_prediction,
            labels=score_labels,
            zero_division=0,
        )
        pd.DataFrame(
            {
                "precision": precision,
                "recall": recall,
                "f1": per_class_f1,
                "support": support,
            },
            index=score_labels,
        ).to_csv(run_dir / f"{method}{artifact_tag}_per_class_metrics.tsv", sep="\t")
        (run_dir / f"{method}{artifact_tag}_unmapped_labels.json").write_text(
            json.dumps(unmapped_counts, indent=2),
            encoding="utf-8",
        )

    metrics_frame = pd.DataFrame(rows).set_index("method").sort_index()
    metrics_frame.to_csv(run_dir / f"{output_stem}.tsv", sep="\t")
    metrics_payload = {
        "schema_version": "1.0",
        "label_space": label_space,
        "target_labels": target_labels,
        "excluded_ground_truth_raw_labels": sorted(excluded_labels),
        "label_contract_sha256": _label_contract_sha256(mapping),
        "metric_definitions": {
            "backend_prediction_row_coverage": (
                "Fraction of all query/truth rows present in the backend prediction table."
            ),
            "scored_raw_prediction_nonmissing_coverage": (
                "Fraction of scored truth rows with a nonmissing raw backend prediction."
            ),
            "ontology_mapped_prediction_coverage": (
                "Fraction of scored truth rows mapped to a target other than Unassigned."
            ),
            "prediction_coverage": (
                "Backward-compatible alias for ontology_mapped_prediction_coverage."
            ),
        },
        "sources": _evaluation_sources(
            prepared,
            prediction_paths,
            prediction_mapping_path,
        ),
        "methods": metrics_frame.reset_index().to_dict(orient="records"),
    }
    (run_dir / f"{output_stem}.json").write_text(
        json.dumps(metrics_payload, indent=2),
        encoding="utf-8",
    )
    return metrics_frame


def bootstrap_grouped_metrics(
    prepared: dict[str, Any] | str | Path,
    group_column: str,
    prediction_paths: dict[str, str | Path] | None = None,
    *,
    label_space: str = "primary",
    group_transform: dict[str, str] | None = None,
    exclude_ground_truth_raw_labels: list[str] | None = None,
    n_resamples: int = 1_000,
    random_seed: int = 0,
    output_stem: str = "metrics_grouped_bootstrap",
) -> pd.DataFrame:
    """Estimate metric uncertainty by resampling held-out truth groups."""
    if n_resamples < 1:
        raise ValueError("n_resamples must be at least 1.")
    if not isinstance(prepared, dict):
        prepared = json.loads(_path(prepared).read_text(encoding="utf-8"))
    run_dir = _path(prepared["run_dir"])
    truth = pd.read_csv(
        _path(prepared["ground_truth_tsv"]), sep="\t", index_col=0, low_memory=False
    )
    truth.index = truth.index.astype(str)
    if not truth.index.is_unique:
        raise ValueError("Ground-truth cell identifiers are not unique.")
    if group_column not in truth:
        raise ValueError(f"Ground-truth grouping column is absent: {group_column}")
    if truth[group_column].isna().any():
        raise ValueError(f"Ground-truth grouping column contains missing values: {group_column}")
    all_truth_index = truth.index.copy()
    mapping = json.loads(_path(prepared["label_mapping_json"]).read_text(encoding="utf-8"))
    _verify_label_contract(prepared, mapping)
    truth_column = prepared["ground_truth_column"]
    ground_truth_mapping = mapping["ground_truth_mapping"]
    raw_truth = truth[truth_column].astype(str)
    excluded_labels = set(exclude_ground_truth_raw_labels or [])
    if excluded_labels:
        missing_exclusions = sorted(excluded_labels.difference(raw_truth.unique()))
        if missing_exclusions:
            raise ValueError(
                "Requested ground-truth exclusions were not found: " + ", ".join(missing_exclusions)
            )
        keep = ~raw_truth.isin(excluded_labels)
        truth = truth.loc[keep].copy()
        raw_truth = raw_truth.loc[keep]
    unmapped_truth = sorted(set(raw_truth).difference(ground_truth_mapping))
    if unmapped_truth:
        raise ValueError("Ground-truth mapping is incomplete: " + ", ".join(unmapped_truth))
    primary_target_labels, target_labels, mapping_from_primary = _resolve_label_space(
        mapping,
        label_space,
    )
    primary_truth = raw_truth.map(ground_truth_mapping)
    unknown_targets = sorted(set(primary_truth).difference(primary_target_labels))
    if unknown_targets:
        raise ValueError(
            "Ground truth maps outside target label set: " + ", ".join(unknown_targets)
        )
    harmonized_truth = primary_truth.map(mapping_from_primary)

    groups = truth[group_column].astype(str)
    normalized_group_transform = {
        str(source): str(target) for source, target in (group_transform or {}).items()
    }
    if normalized_group_transform:
        groups = groups.replace(normalized_group_transform)
    unique_groups = groups.unique()
    if len(unique_groups) < 2:
        raise ValueError("Grouped bootstrap requires at least two distinct groups.")
    group_positions = {group: np.flatnonzero(groups.to_numpy() == group) for group in unique_groups}

    if prediction_paths is None:
        prediction_paths = {
            method: run_dir / f"{method}_predictions.tsv"
            for method in ("tissueagent", "celltypist", "gptcelltype")
            if (run_dir / f"{method}_predictions.tsv").exists()
        }
    if not prediction_paths:
        raise FileNotFoundError(f"No prediction files were supplied or found in {run_dir}.")

    score_labels = [label for label in target_labels if label != UNASSIGNED]
    truth_values = harmonized_truth.to_numpy()
    rng = np.random.default_rng(random_seed)
    resampled_group_indices = rng.integers(
        len(unique_groups),
        size=(n_resamples, len(unique_groups)),
    )
    rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    for method, prediction_path in prediction_paths.items():
        predictions = pd.read_csv(_path(prediction_path), sep="\t", index_col=0, low_memory=False)
        predictions.index = predictions.index.astype(str)
        if not predictions.index.is_unique:
            raise ValueError(f"{method} predictions contain duplicate cell identifiers.")
        extra = predictions.index.difference(all_truth_index)
        if len(extra):
            raise ValueError(
                f"{method} predictions contain {len(extra)} cells absent from ground truth."
            )
        aligned = predictions.reindex(truth.index)
        raw_prediction = aligned["raw_prediction"].astype("string")
        mapping_method = method
        if "mapping_method" in aligned:
            mapping_values = aligned["mapping_method"].dropna().astype(str).unique()
            if len(mapping_values) != 1:
                raise ValueError(
                    f"{method} predictions must declare exactly one mapping_method; "
                    f"found {sorted(mapping_values)}."
                )
            mapping_method = str(mapping_values[0])
        method_mapping = mapping.get("method_prediction_mapping", {}).get(mapping_method, {})
        method_rules = mapping.get("method_prediction_rules", {}).get(mapping_method, [])
        common_mapping = mapping.get("common_prediction_mapping", {})

        def harmonize(value: Any) -> str:
            if pd.isna(value):
                return UNASSIGNED
            text = str(value)
            if text in method_mapping:
                return method_mapping[text]
            if text in common_mapping:
                return common_mapping[text]
            if text in primary_target_labels:
                return text
            numeric_prefix = re.match(r"^(\d+)\s", text)
            if numeric_prefix:
                numeric_value = int(numeric_prefix.group(1))
                for rule in method_rules:
                    if (
                        int(rule["numeric_prefix_min"])
                        <= numeric_value
                        <= int(rule["numeric_prefix_max"])
                    ):
                        return str(rule["target"])
            return UNASSIGNED

        primary_prediction = raw_prediction.map(harmonize)
        unknown_prediction_targets = sorted(
            set(primary_prediction).difference(primary_target_labels)
        )
        if unknown_prediction_targets:
            raise ValueError(
                f"{method} predictions map outside primary target label set: "
                + ", ".join(unknown_prediction_targets)
            )
        prediction_values = primary_prediction.map(mapping_from_primary).to_numpy()
        point_metrics = {
            "accuracy": float(accuracy_score(truth_values, prediction_values)),
            "balanced_accuracy": float(balanced_accuracy_score(truth_values, prediction_values)),
            "macro_precision": float(
                precision_score(
                    truth_values,
                    prediction_values,
                    labels=score_labels,
                    average="macro",
                    zero_division=0,
                )
            ),
            "macro_f1": float(
                f1_score(
                    truth_values,
                    prediction_values,
                    labels=score_labels,
                    average="macro",
                    zero_division=0,
                )
            ),
        }
        grouped_confusions = np.stack(
            [
                confusion_matrix(
                    truth_values[positions],
                    prediction_values[positions],
                    labels=target_labels,
                )
                for positions in group_positions.values()
            ]
        )
        sampled_confusions = grouped_confusions[resampled_group_indices].sum(axis=1)
        totals = sampled_confusions.sum(axis=(1, 2))
        diagonal = np.diagonal(sampled_confusions, axis1=1, axis2=2)
        truth_support = sampled_confusions.sum(axis=2)
        prediction_support = sampled_confusions.sum(axis=1)
        accuracy = diagonal.sum(axis=1) / totals
        present_truth = truth_support > 0
        recall = np.divide(
            diagonal,
            truth_support,
            out=np.zeros_like(diagonal, dtype=float),
            where=present_truth,
        )
        balanced_accuracy = recall.sum(axis=1) / present_truth.sum(axis=1)
        score_indices = np.asarray(
            [target_labels.index(label) for label in score_labels],
            dtype=int,
        )
        score_prediction_support = prediction_support[:, score_indices]
        per_class_precision = np.divide(
            diagonal[:, score_indices],
            score_prediction_support,
            out=np.zeros_like(score_prediction_support, dtype=float),
            where=score_prediction_support > 0,
        )
        macro_precision = per_class_precision.mean(axis=1)
        f1_denominator = truth_support[:, score_indices] + prediction_support[:, score_indices]
        per_class_f1 = np.divide(
            2 * diagonal[:, score_indices],
            f1_denominator,
            out=np.zeros_like(f1_denominator, dtype=float),
            where=f1_denominator > 0,
        )
        macro_f1 = per_class_f1.mean(axis=1)
        method_rows = pd.DataFrame(
            {
                "method": method,
                "resample": np.arange(n_resamples),
                "accuracy": accuracy,
                "balanced_accuracy": balanced_accuracy,
                "macro_precision": macro_precision,
                "macro_f1": macro_f1,
            }
        ).to_dict(orient="records")
        rows.extend(method_rows)
        method_distribution = pd.DataFrame(method_rows)
        summary: dict[str, Any] = {
            "method": method,
            "n_truth_cells": len(truth),
            "n_excluded_truth_cells": int(len(all_truth_index) - len(truth)),
            "n_groups": len(unique_groups),
            "n_resamples": n_resamples,
            "random_seed": random_seed,
        }
        for metric, value in point_metrics.items():
            summary[metric] = value
            summary[f"{metric}_ci_lower"] = float(method_distribution[metric].quantile(0.025))
            summary[f"{metric}_ci_upper"] = float(method_distribution[metric].quantile(0.975))
        summary_rows.append(summary)

    distribution_frame = pd.DataFrame(rows)
    distribution_frame.to_csv(run_dir / f"{output_stem}_distribution.tsv", sep="\t", index=False)
    summary_frame = pd.DataFrame(summary_rows).set_index("method").sort_index()
    summary_frame.to_csv(run_dir / f"{output_stem}.tsv", sep="\t")
    payload = {
        "schema_version": "1.0",
        "label_space": label_space,
        "target_labels": target_labels,
        "excluded_ground_truth_raw_labels": sorted(excluded_labels),
        "label_contract_sha256": _label_contract_sha256(mapping),
        "sources": _evaluation_sources(prepared, prediction_paths),
        "group_column": group_column,
        "group_transform": normalized_group_transform,
        "confidence_level": 0.95,
        "n_resamples": n_resamples,
        "random_seed": random_seed,
        "methods": summary_frame.reset_index().to_dict(orient="records"),
    }
    (run_dir / f"{output_stem}.json").write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )
    return summary_frame
