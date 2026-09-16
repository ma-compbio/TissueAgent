"""Validate annotations against immutable inputs and correct working-copy collection errors."""

from __future__ import annotations

import copy
import json
import os
import shutil
from pathlib import Path

import h5py
import numpy as np
from anndata.io import read_elem

from .evaluation import load_study
from .protocol import sha256, write_json


def validate_annotation(section: dict, annotated: Path) -> dict:
    """Check returned identities and supplied evidence against the original public query."""
    if sha256(section["query_h5ad"]) != section["query_sha256"]:
        raise ValueError("Agent modified the canonical prepared input.")
    with h5py.File(section["query_h5ad"], "r") as query, h5py.File(annotated, "r") as output:
        original_obs, returned_obs = read_elem(query["obs"]), read_elem(output["obs"])
        if not returned_obs.index.is_unique or not set(returned_obs.index).issubset(
            original_obs.index
        ):
            raise ValueError("Annotation contains duplicate or foreign cell IDs.")
        expected = original_obs["cell_type"].reindex(returned_obs.index).astype("string")
        if not expected.equals(returned_obs["cell_type"].astype("string")):
            raise ValueError("Annotation changed the original supplied cell types.")
        indices = original_obs.index.get_indexer(returned_obs.index)
        if not np.array_equal(
            read_elem(query["obsm/spatial"])[indices], read_elem(output["obsm/spatial"])
        ):
            raise ValueError("Annotation changed the original spatial coordinates.")
        if "tissue_niche" not in returned_obs:
            raise ValueError("Annotation has no tissue_niche column.")
        return {"n_original_cells": len(original_obs), "n_returned_cells": len(returned_obs)}


def collect_study(source: Path, destination: Path, decision: Path) -> Path:
    """Retain raw attempts and collect valid outputs rejected only for working-copy edits."""
    from .agent_baselines import _collect_predictions, _link_artifact

    original = load_study(source)
    study = copy.deepcopy(original)
    destination.mkdir(parents=True, exist_ok=True)
    study["runs"] = []
    study["collection_source"] = {
        "study": str(source.resolve()),
        "manifest_sha256": sha256(source / "study_manifest.json"),
        "decision_sha256": sha256(decision),
    }
    validations = []
    for entry in original["runs"]:
        path = source / entry["record"]
        if sha256(path) != entry["record_sha256"]:
            raise ValueError("An original attempt record changed.")
        record = json.loads(path.read_text())
        section = next(
            s
            for s in original["preparations"][entry["dataset"]]["sections"]
            if s["section_id"] == entry["section_id"]
        )
        recover = entry["status"] == "failed" and record.get("error") == (
            "Agent modified the staged input."
        )
        if entry["status"] in {"success", "partial"} or recover:
            annotated = path.parent / "artifacts/niche_annotated.h5ad"
            evidence = validate_annotation(section, annotated)
            validations.append({**entry, **evidence, "collection_corrected": recover})
        else:
            validations.append({**entry, "collection_corrected": False})
        if recover:
            worker = json.loads((path.parent / "worker_result.json").read_text())
            if worker["status"] != "success":
                raise ValueError("Working-copy recovery requires a completed native export.")
            output = (
                destination
                / entry["dataset"]
                / entry["method"]
                / (f"seed-{entry['seed']}")
                / entry["section_id"]
            )
            if not output.exists():
                output.mkdir(parents=True)
                for name in (
                    "worker_request.json",
                    "worker_result.json",
                    "stdout.log",
                    "stderr.log",
                ):
                    _link_artifact(path.parent / name, output / name)
                shutil.copytree(
                    path.parent / "artifacts", output / "artifacts", copy_function=_link_artifact
                )
            corrected = copy.deepcopy(record)
            corrected["collection_correction"] = {
                "original_record": str(path.resolve()),
                "original_record_sha256": entry["record_sha256"],
                "original_status": record["status"],
                "original_error": record["error"],
                "decision_sha256": sha256(decision),
                "collector_sha256": sha256(__file__),
                "canonical_input_and_annotation_validation": evidence,
            }
            corrected.pop("error")
            corrected.pop("error_type")
            corrected.update(_collect_predictions(section, Path(record["runtime_dir"]), output))
            if worker.get("workflow_error"):
                corrected["status"] = "partial"
            corrected["annotated_h5ad_sha256"] = sha256(annotated)
            corrected["staged_input_modified"] = True
            write_json(output / "run_record.json", corrected)
            entry = {
                **entry,
                "status": corrected["status"],
                "record": str((output / "run_record.json").relative_to(destination)),
                "record_sha256": sha256(output / "run_record.json"),
            }
        else:
            entry = {**entry, "record": os.path.relpath(path, destination)}
        study["runs"].append(entry)
    write_json(destination / "study_manifest.json", study)
    write_json(destination / "collection_audit.json", validations)
    return destination
