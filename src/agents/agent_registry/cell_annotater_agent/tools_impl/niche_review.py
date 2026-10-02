"""Bounded spatial screening and evidence-constrained niche refinement."""

from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import scanpy as sc
from scipy.spatial import cKDTree
from scipy.spatial.distance import jensenshannon
from sklearn.cluster import MiniBatchKMeans
from langchain_core.messages import HumanMessage, SystemMessage

from agents.workspace_paths import (
    resolve_workspace_input,
    resolve_project_output,
    workspace_relative,
)
from .niche_artifacts import (
    RECEIPT_KEY,
    _file_hash,
    _validate_receipt,
    attach_niche_receipt,
    recover_niche_annotation_artifacts_tool,
)
from .niche_batch import checkpoint_json, model_identity
from agents.tissue_niche_context import get_tissue_niche_context

POLICY = "niche_targeted_review_v1"


def _decode(response):
    from .niche_annotation import _extract_json_object, _message_content_to_text

    return _extract_json_object(_message_content_to_text(response.content))


def _fractions(values):
    return {str(k): float(v) for k, v in pd.Series(values).value_counts(normalize=True).items()}


def _mean(x, indices):
    return np.asarray(x[indices].mean(axis=0)).ravel()


def _anchor_map(adata, metadata, model, path):
    if not metadata["parameters"]["celltype_key_resolved"]:
        return {}
    celltypes = sorted(
        adata.obs[metadata["parameters"]["celltype_key_resolved"]].astype(str).unique()
    )
    allowed = metadata["parameters"]["allowed_labels"]
    request = {
        "context": metadata["dataset_context"],
        "cell_types": celltypes,
        "allowed_regions": allowed,
    }
    digest = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
    if path.exists():
        saved = json.loads(path.read_text())
        if saved["request_sha256"] != digest:
            raise ValueError("Anchor checkpoint belongs to another input vocabulary.")
        mapping = saved["mapping"]
    else:
        response = model.invoke(
            [
                SystemMessage(
                    "Identify optional anatomical anchors only from explicitly regional supplied cell-type names. "
                    "Broad fibroblast, endothelial, immune or malignant identities are not regional anchors. "
                    "Do not invent regional associations for ambiguous names. Anchors will be supporting evidence "
                    "for spatial review, never direct final assignments. Return JSON "
                    '{"mapping":{"exact supplied cell type":"exact allowed anatomical region"}}; '
                    "an empty mapping is valid. Use no Unmatched anchors."
                ),
                HumanMessage(json.dumps(request)),
            ]
        )
        mapping = _decode(response).get("mapping")
        if not isinstance(mapping, dict):
            raise ValueError("Invalid optional anchor mapping.")
        checkpoint_json(path, {"request_sha256": digest, "mapping": mapping})
    if any(k not in celltypes or v not in allowed or v == "Unmatched" for k, v in mapping.items()):
        raise ValueError("Anchor mapping contains an unsupported cell type or region.")
    return mapping


def _screen(adata, metadata, anchor_mapping=None):
    """Partition in physical space, then flag measured local conflicts, not mixture alone."""
    params = metadata["parameters"]
    clusters = adata.obs[params["niche_key"]].astype(str).to_numpy()
    labels = adata.obs[params["annotation_col"]].astype(str).to_numpy()
    celltypes = (
        adata.obs[params["celltype_key_resolved"]].astype(str).to_numpy()
        if params["celltype_key_resolved"]
        else np.full(adata.n_obs, "unavailable")
    )
    xy = np.asarray(adata.obsm[params["spatial_key"]], dtype=float)[:, :2]
    slide_key = params.get("slide_key_resolved")
    slides = (
        adata.obs[slide_key].astype(str).to_numpy()
        if slide_key in adata.obs
        else np.full(adata.n_obs, "single")
    )
    groups, memberships = [], {}
    genes = np.asarray(adata.var_names.astype(str))
    for slide in np.unique(slides):
        section_idx = np.flatnonzero(slides == slide)
        all_mean = _mean(adata.X, section_idx)
        coords = xy[section_idx]
        _, nearest = cKDTree(coords).query(coords, k=min(17, len(coords)))
        if nearest.ndim == 1:
            nearest = nearest[:, None]
        local_labels = labels[section_idx][nearest[:, 1:]]
        anchor_votes = None
        if anchor_mapping:
            anchor_labels = pd.Series(celltypes[section_idx]).map(anchor_mapping)
            mask = anchor_labels.notna().to_numpy()
            if mask.any():
                distances, indices = cKDTree(coords[mask]).query(coords, k=min(15, mask.sum()))
                if indices.ndim == 1:
                    distances, indices = distances[:, None], indices[:, None]
                weights = 1 / (1 + distances / max(float(params["utag_max_dist"]), 1e-8))
                neighbors = anchor_labels.to_numpy()[mask][indices]
                anchor_votes = {
                    lab: ((neighbors == lab) * weights).sum(axis=1) / weights.sum(axis=1)
                    for lab in np.unique(neighbors)
                }
        for cluster in np.unique(clusters[section_idx]):
            local_idx = np.flatnonzero(clusters[section_idx] == cluster)
            parent_idx = section_idx[local_idx]
            parent_types = pd.Series(celltypes[parent_idx]).value_counts(normalize=True)
            parent_mean = _mean(adata.X, parent_idx)
            # No subdivision by cell-type labels; no merging or dropping rare clusters.
            k = min(4, max(2, math.ceil(len(parent_idx) / 2000))) if len(parent_idx) >= 80 else 1
            partition = (
                (
                    MiniBatchKMeans(
                        n_clusters=k, random_state=0, n_init=3, batch_size=1024
                    ).fit_predict(xy[parent_idx])
                )
                if k > 1
                else np.zeros(len(parent_idx), dtype=int)
            )
            for part in np.unique(partition):
                local_positions = local_idx[partition == part]
                indices = section_idx[local_positions]
                group_id = f"{slide}:{cluster}:spatial{part}"
                mean = _mean(adata.X, indices)
                contrast = mean - parent_mean
                informative = np.maximum(mean - all_mean, contrast)
                top = np.argsort(informative)[::-1][:12]
                top = [i for i in top if mean[i] > 0 and informative[i] > 0]
                composition = pd.Series(celltypes[indices]).value_counts(normalize=True)
                types = sorted(set(parent_types.index) | set(composition.index))
                js = float(
                    jensenshannon(
                        parent_types.reindex(types, fill_value=0),
                        composition.reindex(types, fill_value=0),
                        base=2,
                    )
                )
                expression_shift = float(np.mean(np.sort(np.maximum(contrast, 0))[-3:]))
                primary = labels[indices[0]]
                neighbor_fractions = _fractions(local_labels[local_positions].ravel())
                strongest_neighbor = max(
                    neighbor_fractions, key=neighbor_fractions.get, default=primary
                )
                neighbor_conflict = (
                    strongest_neighbor != primary
                    and neighbor_fractions.get(strongest_neighbor, 0) >= 0.6
                )
                anchors = (
                    {
                        lab: float(values[local_positions].mean())
                        for lab, values in anchor_votes.items()
                    }
                    if anchor_votes
                    else {}
                )
                strongest_anchor = max(anchors, key=anchors.get, default=primary)
                anchor_conflict = (
                    strongest_anchor != primary and anchors.get(strongest_anchor, 0) >= 0.7
                )
                reasons = []
                if primary == params["unmatched_label"]:
                    reasons.append("unresolved_primary")
                if js >= 0.25 and expression_shift >= 0.1 and k > 1:
                    reasons.append("spatially_segregated_composition_and_expression")
                if neighbor_conflict and expression_shift >= 0.1:
                    reasons.append("neighbor_label_and_expression_conflict")
                if anchor_conflict:
                    reasons.append("optional_anchor_disagreement")
                record = {
                    "group_id": group_id,
                    "parent_cluster": cluster,
                    "slide": str(slide),
                    "n_cells": len(indices),
                    "primary_label": primary,
                    "centroid": xy[indices].mean(axis=0).tolist(),
                    "coordinate_min": xy[indices].min(axis=0).tolist(),
                    "coordinate_max": xy[indices].max(axis=0).tolist(),
                    "celltype_fractions": _fractions(celltypes[indices]),
                    "composition_js_distance": js,
                    "mean_top3_expression_shift": expression_shift,
                    "neighbor_label_fractions": neighbor_fractions,
                    "soft_anchor_label_fractions": anchors,
                    "measured_gene_evidence": [
                        {
                            "gene": str(genes[i]),
                            "mean_expression": float(mean[i]),
                            "difference_from_parent": float(contrast[i]),
                            "difference_from_section": float(mean[i] - all_mean[i]),
                        }
                        for i in top
                    ],
                    "screening_reasons": reasons,
                    "priority": len(reasons) + js + min(expression_shift, 1.0),
                }
                groups.append(record)
                memberships[group_id] = indices
    return groups, memberships


def _decisions(groups, metadata, model, checkpoint_path, batch_size, run_id):
    allowed = metadata["parameters"]["allowed_labels"]
    binding = {
        "policy": POLICY,
        "groups": groups,
        "context": metadata["dataset_context"],
        "allowed_labels": allowed,
        "model": model_identity(model),
        "run_id": run_id,
    }
    digest = hashlib.sha256(json.dumps(binding, sort_keys=True).encode()).hexdigest()
    state = {"request_sha256": digest, "decisions": {}}
    if checkpoint_path.exists():
        state = json.loads(checkpoint_path.read_text())
        if state["request_sha256"] != digest:
            raise ValueError("Review checkpoint belongs to different evidence/settings.")
    missing = [g for g in groups if g["group_id"] not in state["decisions"]]
    for offset in range(0, len(missing), batch_size):
        batch = missing[offset : offset + batch_size]
        response = model.invoke(
            [
                SystemMessage(
                    "Review only the supplied spatial subregions of a primary niche annotation. "
                    "A mixed cell-type niche is normal; spatial subdivision alone is not evidence of distinct anatomy. "
                    "Retain the primary label unless measured expression AND local biological/spatial evidence "
                    "support a different allowed region. Anatomical orientation cannot be inferred from coordinate "
                    "signs. Optional anchors and neighboring predicted labels are fallible supporting evidence, "
                    "not ground truth or a command to copy labels. Generic stromal markers alone do not determine "
                    "a chamber. Never erase a rare population merely because it is small. "
                    'Return JSON {"decisions":[{"group_id":"...","action":"retain|assign|unresolved",'
                    '"label":"exact allowed label","supporting_genes":["measured gene", "measured gene"],'
                    '"spatial_reason":"local evidence and alternatives","justification":"reason"}]}. '
                    "Use retain for insufficient evidence to change the primary call. Assign requires at least "
                    "two genes from the supplied measured_gene_evidence plus a specific spatial reason. "
                    "Use unresolved only when evidence contradicts the primary label but no alternative is supported; "
                    "its final label must be Unmatched. Return exactly the requested groups."
                ),
                HumanMessage(
                    json.dumps(
                        {
                            "context": metadata["dataset_context"],
                            "allowed_labels": allowed,
                            "groups": batch,
                        },
                        ensure_ascii=False,
                    )
                ),
            ]
        )
        items = _decode(response).get("decisions")
        by_id = {g["group_id"]: g for g in batch}
        if not isinstance(items, list) or len(items) != len(batch):
            raise ValueError("Review response omitted or added groups; completed batches retained.")
        accepted = {}
        for item in items:
            gid = item.get("group_id")
            if gid not in by_id or gid in accepted:
                raise ValueError("Review returned unknown or duplicate group IDs.")
            group = by_id[gid]
            if (
                item.get("action") not in {"retain", "assign", "unresolved"}
                or item.get("label") not in allowed
            ):
                raise ValueError("Review returned invalid action or label.")
            if not item.get("justification"):
                raise ValueError("Review decision lacks justification.")
            measured = {g["gene"] for g in group["measured_gene_evidence"]}
            cites = set(item.get("supporting_genes") or [])
            if not cites.issubset(measured):
                raise ValueError("Review cited genes absent from the measured evidence.")
            if item["action"] == "retain":
                item["label"] = group["primary_label"]
            elif len(cites) < 2 or not str(item.get("spatial_reason", "")).strip():
                item.update(
                    action="retain",
                    label=group["primary_label"],
                    guard_reason="insufficient_measured_support_for_change",
                )
            elif item["action"] == "unresolved":
                item["label"] = metadata["parameters"]["unmatched_label"]
            accepted[gid] = item
        state["decisions"].update(accepted)
        checkpoint_json(checkpoint_path, state)
    return state["decisions"]


def review_tissue_niches_tool(
    annotated_h5ad: str,
    output_dir: str = "niche_review",
    output_path: str = "niche_reviewed.h5ad",
    use_anchor_evidence: bool = False,
    max_review_groups: int = 48,
    review_batch_size: int = 8,
    run_id: str = "default",
) -> dict:
    """Screen every niche; review selected spatial groups once and preserve other predictions."""
    try:
        if not 1 <= review_batch_size <= 16 or not 1 <= max_review_groups <= 128:
            raise ValueError("Review batch size must be 1–16 and group budget 1–128.")
        source = resolve_workspace_input(annotated_h5ad)
        output = resolve_project_output(output_path, suffix=".h5ad")
        if source == output:
            raise ValueError("Preserve the primary annotation; use a new reviewed output path.")
        directory = resolve_project_output(str(Path(output_dir) / "review_report.json")).parent
        directory.mkdir(parents=True, exist_ok=True)
        adata = sc.read_h5ad(source)
        receipt = json.loads(adata.uns[RECEIPT_KEY])
        metadata = copy.deepcopy(receipt["metadata"])
        if metadata.get("review"):
            raise ValueError("One spatial review is already recorded; do not repeat refinement.")
        original_path = (
            get_tissue_niche_context().get("input_path")
            or metadata["inputs"]["validation_input_path"]
        )
        original_input = sc.read_h5ad(resolve_workspace_input(original_path), backed="r")
        try:
            _validate_receipt(adata, receipt, original_input)
        finally:
            original_input.file.close()
        from config import DefaultModelCtor

        model = DefaultModelCtor()
        anchors = (
            _anchor_map(adata, metadata, model, directory / "anchor_map.json")
            if use_anchor_evidence
            else {}
        )
        groups, members = _screen(adata, metadata, anchors)
        covered = np.concatenate(list(members.values()))
        if not np.array_equal(np.sort(covered), np.arange(adata.n_obs)):
            raise ValueError("Spatial screening must cover every cell exactly once.")
        flagged = sorted(
            [g for g in groups if g["screening_reasons"]],
            key=lambda g: (-g["priority"], g["group_id"]),
        )
        selected = flagged[:max_review_groups]
        evidence = {
            "policy": POLICY,
            "primary_sha256": _file_hash(source),
            "anchor_mapping": anchors,
            "groups": groups,
            "selected_ids": [g["group_id"] for g in selected],
            "deferred_ids": [g["group_id"] for g in flagged[max_review_groups:]],
        }
        checkpoint_json(directory / "review_evidence.json", evidence)
        decisions = _decisions(
            selected,
            metadata,
            model,
            directory / "review_checkpoint.json",
            review_batch_size,
            run_id,
        )
        params = metadata["parameters"]
        column = params["annotation_col"]
        original = adata.obs[column].astype(str).to_numpy()
        predictions = original.copy()
        regions = adata.obs[params["niche_key"]].astype(str).to_numpy().astype(object)
        justifications = (
            adata.obs[params["justification_col"]].astype(str).to_numpy().astype(object)
        )
        final_results = copy.deepcopy(receipt["results"])
        for group in selected:
            decision = decisions[group["group_id"]]
            idx = members[group["group_id"]]
            if decision["label"] != group["primary_label"]:
                region = "review:" + group["group_id"]
                predictions[idx] = decision["label"]
                regions[idx] = region
                justifications[idx] = decision["justification"]
                final_results[region] = {
                    "niche_id": region,
                    "label": decision["label"],
                    "justification": decision["justification"],
                }
        adata.obs[f"{column}_before_refinement"] = adata.obs[column].copy()
        adata.obs[column] = pd.Categorical(predictions, categories=params["allowed_labels"])
        adata.obs[params["justification_col"]] = justifications
        adata.obs["tissueagent_review_region"] = pd.Categorical(regions)
        params["niche_key"] = "tissueagent_review_region"
        final_results = {k: v for k, v in final_results.items() if k in set(regions)}
        xy = np.asarray(adata.obsm[params["spatial_key"]])[:, :2]
        metadata["spatial_evidence"]["clusters"] = {
            region: {
                "n_cells": int((regions == region).sum()),
                "coordinate_min": xy[regions == region].min(axis=0).tolist(),
                "coordinate_max": xy[regions == region].max(axis=0).tolist(),
                "source": "retained_primary_or_reviewed_spatial_subregion",
            }
            for region in np.unique(regions)
        }
        report = {
            "policy": POLICY,
            "n_primary_clusters": int(len(receipt["results"])),
            "n_groups_screened": len(groups),
            "n_groups_flagged": len(flagged),
            "n_groups_reviewed": len(decisions),
            "n_groups_deferred": max(0, len(flagged) - max_review_groups),
            "review_status": "complete"
            if len(flagged) <= max_review_groups
            else "complete_with_deferrals",
            "n_cells_changed": int((original != predictions).sum()),
            "use_anchor_evidence": use_anchor_evidence,
            "decisions": decisions,
            "primary_sha256": evidence["primary_sha256"],
        }
        metadata["review"] = report
        metadata["summary"].update(
            n_niches=len(final_results),
            annotation_counts={k: int((predictions == k).sum()) for k in params["allowed_labels"]},
        )
        attach_niche_receipt(adata, metadata, receipt["queries"], final_results)
        output.parent.mkdir(parents=True, exist_ok=True)
        pending = output.with_suffix(".pending.h5ad")
        adata.write_h5ad(pending, compression="gzip")
        pending.replace(output)
        checkpoint_json(directory / "review_report.json", report)
        recovered = recover_niche_annotation_artifacts_tool(
            workspace_relative(output), workspace_relative(directory)
        )
        if recovered["status"] != "success":
            return recovered
        return {
            **recovered,
            **{k: v for k, v in report.items() if k != "decisions"},
            "review_report_json": workspace_relative(directory / "review_report.json"),
            "review_evidence_json": workspace_relative(directory / "review_evidence.json"),
        }
    except Exception as exc:
        return {
            "status": "error",
            "stage": "targeted_niche_review",
            "message": str(exc),
            "next_action": "Preserve primary predictions and completed checkpoints; correct the failed "
            "review without repeating clustering or primary labeling.",
        }
