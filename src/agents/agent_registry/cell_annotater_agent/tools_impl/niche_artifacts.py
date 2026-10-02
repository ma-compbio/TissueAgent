"""Validated niche audit export and recovery without clustering or model calls."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import shutil
from typing import Any, Optional

import numpy as np
import pandas as pd
import scanpy as sc

from agents.tissue_niche_context import get_tissue_niche_context
from agents.workspace_paths import (
    resolve_project_output,
    resolve_workspace_input,
    workspace_relative,
)

RECEIPT_KEY = "tissueagent_niche_annotation_receipt"


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(path.name + ".pending")
    pending.write_text(text)
    pending.replace(path)


def _json_text(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"


def attach_niche_receipt(adata, metadata, queries, results) -> None:
    """Keep the completed scientific record recoverable inside the annotated H5AD."""
    adata.uns[RECEIPT_KEY] = _json_text(
        {"version": 1, "metadata": metadata, "queries": queries, "results": results}
    )


def _validate_receipt(adata, receipt, original) -> list[dict]:
    if receipt.get("version") != 1:
        raise ValueError("Unsupported niche annotation receipt version.")
    metadata = receipt["metadata"]
    params = metadata["parameters"]
    context = get_tissue_niche_context()
    labels = params["allowed_labels"]
    annotation_col = params["annotation_col"]
    niche_key = params["niche_key"]
    celltype_key = params["celltype_key_resolved"]
    if context.get("annotation_col", annotation_col) != annotation_col:
        raise ValueError("Saved annotation column differs from the bound task.")
    if context.get("allowed_labels"):
        bound_labels = set(context["allowed_labels"]) | {
            context.get("unmatched_label", "Unmatched")
        }
        if set(labels) != bound_labels:
            raise ValueError("Saved vocabulary differs from the bound task.")
    if not adata.obs_names.is_unique or not adata.obs_names.equals(original.obs_names):
        raise ValueError("Saved annotation does not preserve the original cell IDs and order.")
    if not adata.var_names.equals(original.var_names):
        raise ValueError("Saved annotation does not preserve the original genes and order.")
    if celltype_key and not adata.obs[celltype_key].equals(original.obs[celltype_key]):
        raise ValueError("Saved annotation changed the supplied cell types.")
    spatial_key = params["spatial_key"]
    if not np.array_equal(adata.obsm[spatial_key], original.obsm[spatial_key]):
        raise ValueError("Saved annotation changed the spatial coordinates.")
    if not adata.obs[annotation_col].isin(labels).all():
        raise ValueError("Saved annotation has missing or out-of-vocabulary labels.")
    assignments = {str(k): v["label"] for k, v in receipt["results"].items()}
    expected = adata.obs[niche_key].astype(str).map(assignments)
    if expected.isna().any() or not np.array_equal(
        expected.to_numpy(), adata.obs[annotation_col].astype(str).to_numpy()
    ):
        raise ValueError("Saved cell labels disagree with their completed annotation receipt.")
    if metadata["summary"]["n_cells"] != adata.n_obs:
        raise ValueError("Saved cell count disagrees with the annotation receipt.")
    return [
        {"check": name, "status": "passed"}
        for name in (
            "cell_ids_and_order",
            "genes_and_order",
            "supplied_cell_types",
            "spatial_coordinates",
            "label_vocabulary",
            "annotation_receipt",
        )
    ] + [{"check": "separate_spatial_review", "status": "not_verified"}]


def recover_niche_annotation_artifacts_tool(
    annotated_h5ad: str,
    output_dir: str = "niche_annotation_results",
    output_path: Optional[str] = None,
    evidence_path: Optional[str] = None,
    parameters_path: Optional[str] = None,
    validation_path: Optional[str] = None,
    metadata_path: Optional[str] = None,
) -> dict[str, Any]:
    """Validate saved annotation, restore audits, and optionally copy to an exact output path.

    This operation never runs UTAG, labels clusters, or certifies a separate review.
    Exact audit paths can repair a plan's filename mismatch without changing predictions.
    """
    validated = False
    try:
        source = resolve_workspace_input(annotated_h5ad)
        destination = resolve_project_output(output_path) if output_path else source
        # Recovery must not turn an uploaded object into a writable output.
        resolve_project_output(workspace_relative(destination))
        if destination.suffix.lower() != ".h5ad":
            raise ValueError("Annotation output must have a .h5ad suffix.")
        directory = resolve_project_output(str(Path(output_dir) / "run_meta.json")).parent
        paths = {
            "niche_evidence_tsv": resolve_project_output(evidence_path)
            if evidence_path
            else directory / "niche_evidence.tsv",
            "annotation_parameters_json": resolve_project_output(parameters_path)
            if parameters_path
            else directory / "annotation_parameters.json",
            "validation_summary_tsv": resolve_project_output(validation_path)
            if validation_path
            else directory / "validation_summary.tsv",
            "run_meta_json": resolve_project_output(metadata_path)
            if metadata_path
            else directory / "run_meta.json",
            "niche_llm_queries_json": directory / "niche_llm_queries.json",
            "niche_llm_results_json": directory / "niche_llm_results.json",
            "spatial_evidence_json": directory / "spatial_evidence.json",
        }
        if len(set(paths.values())) != len(paths) or {source, destination} & set(paths.values()):
            raise ValueError("Audit paths must be distinct from one another and the H5AD files.")
        adata = sc.read_h5ad(source, backed="r")
        try:
            if RECEIPT_KEY not in adata.uns:
                raise ValueError(
                    "Saved annotation has no recoverable receipt; preserve it and inspect its "
                    "native metadata. Do not rerun annotation merely to repair audit files."
                )
            receipt = json.loads(adata.uns[RECEIPT_KEY])
            metadata = copy.deepcopy(receipt["metadata"])
            reference = (
                get_tissue_niche_context().get("input_path")
                or metadata["inputs"]["validation_input_path"]
            )
            original = sc.read_h5ad(resolve_workspace_input(reference), backed="r")
            try:
                checks = _validate_receipt(adata, receipt, original)
                validated = True
            finally:
                original.file.close()
            params = metadata["parameters"]
            clusters = metadata["spatial_evidence"]["clusters"]
            rows = [
                {
                    "niche_id": str(niche_id),
                    "n_cells": clusters[str(niche_id)]["n_cells"],
                    "label": result["label"],
                    "justification": result["justification"],
                    "spatial_evidence": json.dumps(clusters[str(niche_id)], sort_keys=True),
                }
                for niche_id, result in receipt["results"].items()
            ]
            # Validate everything before writing either the binary or any audit file.
            texts = {
                "niche_evidence_tsv": pd.DataFrame(rows).to_csv(sep="\t", index=False),
                "annotation_parameters_json": _json_text(
                    {
                        "parameters": params,
                        "parameter_selection": metadata["parameter_selection"],
                        "dataset_context": metadata["dataset_context"],
                    }
                ),
                "validation_summary_tsv": pd.DataFrame(checks).to_csv(sep="\t", index=False),
                "niche_llm_queries_json": _json_text(receipt["queries"]),
                "niche_llm_results_json": _json_text(receipt["results"]),
                "spatial_evidence_json": _json_text(metadata["spatial_evidence"]),
            }
            count = adata.n_obs
        finally:
            adata.file.close()
        source_hash = _file_hash(source)
        if destination != source:
            if destination.exists() and _file_hash(destination) != source_hash:
                raise ValueError(
                    "Copy destination already contains a different annotation; preserve it."
                )
            if not destination.exists():
                destination.parent.mkdir(parents=True, exist_ok=True)
                pending = destination.with_suffix(".pending.h5ad")
                shutil.copyfile(source, pending)
                pending.replace(destination)
        outputs = {key: workspace_relative(path) for key, path in paths.items()}
        metadata["outputs"].update(outputs)
        metadata["outputs"].update(
            annotated_object_h5ad=workspace_relative(destination),
            utag_object_h5ad=workspace_relative(destination),
        )
        metadata.update(annotation_status="complete", review_status="not_verified")
        metadata["annotated_h5ad_sha256"] = source_hash
        texts["run_meta_json"] = _json_text(metadata)
        for key, text in texts.items():
            _write_text(paths[key], text)
        return {
            "status": "success",
            "annotation_status": "complete",
            "review_status": "not_verified",
            "annotation_reused": True,
            "annotated_object_h5ad": workspace_relative(destination),
            "n_cells": count,
            **outputs,
            "next_action": "Audit artifacts are restored without changing predictions. Continue any "
            "planned spatial review; annotation availability does not prove review completion.",
        }
    except Exception as exc:
        return {
            "status": "error",
            "stage": "recover_niche_artifacts",
            "annotation_status": "complete" if validated else "not_validated",
            "validation_status": "passed" if validated else "failed",
            "review_status": "not_verified",
            "message": str(exc),
            "next_action": "Preserve the existing annotation and correct the recovery inputs; "
            "do not repeat clustering or labeling for an audit-file failure.",
        }
