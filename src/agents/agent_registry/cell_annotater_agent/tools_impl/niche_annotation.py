"""UTAG tissue-niche inspection, annotation, and artifact generation."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import scanpy as sc
from scipy import sparse
from scipy.spatial import cKDTree

from agents.tissue_niche_context import get_tissue_niche_context
from .niche_spatial import (
    RadiusGraphLimitError,
    graph_diagnostics,
    radius_graph,
    spatial_niche_evidence,
)
from agents.workspace_paths import (
    resolve_project_output,
    resolve_workspace_input,
    workspace_relative,
)
from config import active_project_outputs

DEFAULT_UNMATCHED_LABEL = "Unmatched"
AUTO_KEY_VALUES = {"auto", "infer", "detect"}
NO_KEY_VALUES = {"", "none", "null", "false", "no"}
SYNTHETIC_SLIDE_KEY = "_tissueagent_slide_id"
SLIDE_KEY_CANDIDATES = (
    "sample_id",
    "sample",
    "slide_id",
    "slide",
    "library_id",
    "section",
    "tissue_section",
    "batch",
)
AUTO_CELLTYPE_KEY_VALUES = {"auto", "infer", "detect"}
NO_CELLTYPE_KEY_VALUES = {"", "none", "null", "false", "no"}
CELLTYPE_KEY_CANDIDATES = (
    "harmony_predicted_cell_type",
    "cell_type",
    "celltype",
    "populations",
    "cell_type_label",
    "predicted_cell_type",
    "annotation",
    "bulk_labels",
    "label",
)
NICHE_KEY_PATTERN = re.compile(
    r"^UTAG Label_(?P<clustering_method>[A-Za-z0-9_-]+)_(?P<resolution>[0-9]*\.?[0-9]+)$"
)
PREFLIGHT_MAX_EXPRESSION_ROWS = 2048
PREFLIGHT_MAX_EXPRESSION_COLUMNS = 2048
PREFLIGHT_MAX_DISTANCE_QUERIES_PER_SLIDE = 10_000


def _relative_to_data_dir(path: Path) -> str:
    return workspace_relative(path)


def _resolve_path(path_like: str, *, must_exist: bool) -> Path:
    """Resolve workspace inputs and project-scoped outputs."""
    return resolve_workspace_input(path_like) if must_exist else resolve_project_output(path_like)


def _evenly_spaced_indices(length: int, maximum: int) -> np.ndarray:
    if length <= maximum:
        return np.arange(length, dtype=np.int64)
    return np.unique(np.linspace(0, length - 1, num=maximum, dtype=np.int64))


def _expression_preflight(adata: sc.AnnData) -> Dict[str, Any]:
    row_indices = _evenly_spaced_indices(adata.n_obs, PREFLIGHT_MAX_EXPRESSION_ROWS)
    column_slice = slice(0, min(adata.n_vars, PREFLIGHT_MAX_EXPRESSION_COLUMNS))
    matrix = adata[row_indices, column_slice].to_memory().X
    if sparse.issparse(matrix):
        values = matrix.data.astype(np.float64, copy=False)
        sampled_entries = int(matrix.shape[0] * matrix.shape[1])
    else:
        dense = np.asarray(matrix, dtype=np.float64)
        values = dense.ravel()
        sampled_entries = int(dense.size)

    finite_values = values[np.isfinite(values)]
    nonzero_values = finite_values[finite_values != 0]
    integer_like_fraction = (
        float(np.mean(np.isclose(nonzero_values, np.rint(nonzero_values), atol=1e-6, rtol=0)))
        if nonzero_values.size
        else None
    )
    negative_fraction = float(np.mean(nonzero_values < 0)) if nonzero_values.size else 0.0
    if values.size != finite_values.size:
        expression_state = "invalid"
    elif nonzero_values.size == 0:
        expression_state = "ambiguous"
    elif negative_fraction > 0:
        expression_state = "signed_processed"
    elif "log1p" in adata.uns:
        expression_state = "log1p_normalized"
    elif integer_like_fraction is not None and integer_like_fraction >= 0.99:
        expression_state = "raw_count_like"
    else:
        expression_state = "nonnegative_continuous"

    return {
        "matrix_dtype": str(adata.X.dtype),
        "sampled_rows": int(len(row_indices)),
        "sampled_columns": int(matrix.shape[1]),
        "sampled_entries": sampled_entries,
        "sampled_stored_values": int(values.size),
        "sampled_nonzero_values": int(nonzero_values.size),
        "sampled_nonfinite_stored_values": int(values.size - finite_values.size),
        "sampled_negative_fraction": negative_fraction,
        "sampled_integer_like_fraction": integer_like_fraction,
        "log1p_metadata_present": "log1p" in adata.uns,
        "raw_attribute_present": adata.raw is not None,
        "layers": sorted(str(key) for key in adata.layers),
        "expression_state": expression_state,
    }


def _slide_candidates(adata: sc.AnnData) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    columns_by_folded_name = {str(column).casefold(): str(column) for column in adata.obs.columns}
    for candidate in SLIDE_KEY_CANDIDATES:
        resolved = columns_by_folded_name.get(candidate.casefold())
        if resolved is None or any(item["key"] == resolved for item in candidates):
            continue
        values = adata.obs[resolved]
        counts = values.astype("string").fillna("<missing>").value_counts()
        candidates.append(
            {
                "key": resolved,
                "n_groups": int(len(counts)),
                "missing": int(values.isna().sum()),
                "group_sizes": {str(key): int(value) for key, value in counts.items()},
            }
        )
    return candidates


def _distance_preflight(
    adata: sc.AnnData,
    *,
    spatial_key: str,
    slide_candidates: List[Dict[str, Any]],
) -> Dict[str, Any]:
    coordinates = np.asarray(adata.obsm[spatial_key], dtype=np.float64)
    if coordinates.ndim != 2 or coordinates.shape[1] < 2:
        raise ValueError(
            f"obsm['{spatial_key}'] must have at least two columns; got {coordinates.shape}."
        )
    xy = coordinates[:, :2]
    if not np.isfinite(xy).all():
        raise ValueError(f"obsm['{spatial_key}'] contains non-finite coordinates.")

    slide_key = slide_candidates[0]["key"] if slide_candidates else None
    slide_values = (
        adata.obs[slide_key].astype("string").fillna("<missing>")
        if slide_key is not None
        else pd.Series("sample_0", index=adata.obs_names, dtype="string")
    )
    per_slide: Dict[str, Any] = {}
    all_distances: List[np.ndarray] = []
    for slide in slide_values.unique():
        positions = np.flatnonzero((slide_values == slide).to_numpy())
        slide_xy = xy[positions]
        if len(slide_xy) < 2:
            per_slide[str(slide)] = {
                "n_observations": int(len(slide_xy)),
                "sampled_queries": 0,
                "nearest_neighbor_distance_quantiles": None,
            }
            continue
        query_indices = _evenly_spaced_indices(
            len(slide_xy), PREFLIGHT_MAX_DISTANCE_QUERIES_PER_SLIDE
        )
        neighbor_ranks = [rank for rank in (1, 5, 10, 20) if rank < len(slide_xy)]
        distances, _ = cKDTree(slide_xy).query(
            slide_xy[query_indices], k=[rank + 1 for rank in neighbor_ranks]
        )
        nearest = np.asarray(distances[:, 0], dtype=np.float64)
        all_distances.append(nearest)
        quantiles = np.quantile(nearest, [0.05, 0.25, 0.5, 0.75, 0.95])
        per_slide[str(slide)] = {
            "n_observations": int(len(slide_xy)),
            "sampled_queries": int(len(nearest)),
            "nonself_neighbor_distance_quantiles": {
                str(rank): dict(
                    zip(
                        ["p25", "median", "p75", "p95"],
                        np.quantile(distances[:, index], [0.25, 0.5, 0.75, 0.95]).tolist(),
                        strict=True,
                    )
                )
                for index, rank in enumerate(neighbor_ranks)
            },
            "nearest_neighbor_distance_quantiles": {
                "p05": float(quantiles[0]),
                "p25": float(quantiles[1]),
                "median": float(quantiles[2]),
                "p75": float(quantiles[3]),
                "p95": float(quantiles[4]),
            },
        }
    if not all_distances:
        raise ValueError(
            "At least one spatial group must contain two observations to estimate distances."
        )
    combined = np.concatenate(all_distances)
    combined_quantiles = np.quantile(combined, [0.05, 0.25, 0.5, 0.75, 0.95])
    units = get_tissue_niche_context().get("dataset_context", {}).get("coordinate_units")
    if not units or units == "source spatial coordinate units":
        units = "Unspecified: distances use input coordinate units, not established micrometers."
    return {
        "key": spatial_key,
        "coordinate_units": units,
        "shape": [int(value) for value in coordinates.shape],
        "coordinate_min": [float(value) for value in xy.min(axis=0)],
        "coordinate_max": [float(value) for value in xy.max(axis=0)],
        "distance_grouping_key": slide_key,
        "sampled_nearest_neighbor_distances": int(len(combined)),
        "nearest_neighbor_distance_quantiles": {
            "p05": float(combined_quantiles[0]),
            "p25": float(combined_quantiles[1]),
            "median": float(combined_quantiles[2]),
            "p75": float(combined_quantiles[3]),
            "p95": float(combined_quantiles[4]),
        },
        "per_slide": per_slide,
    }


def _inspect_tissue_niche_input_path(
    path: Path,
    *,
    celltype_key: str = "auto",
    spatial_key: str = "auto",
    niche_key: Optional[str] = None,
    neighborhood_radii: Optional[List[float]] = None,
    slide_key: Optional[str] = "auto",
) -> Dict[str, Any]:
    adata = sc.read_h5ad(path, backed="r")
    try:
        celltype_key = _resolve_celltype_key(adata, celltype_key)
        if celltype_key is None:
            raise KeyError(f"Specify the cell-type column from obs: {list(adata.obs.columns)}")
        spatial_key = _resolve_spatial_key(adata, spatial_key)
        niche_match = NICHE_KEY_PATTERN.fullmatch(niche_key or "")

        celltypes = adata.obs[celltype_key]
        counts = celltypes.astype("string").fillna("<missing>").value_counts()
        slide_candidates = _slide_candidates(adata)
        report: Dict[str, Any] = {
            "status": "success",
            "input": {
                "path": str(path),
                "n_observations": int(adata.n_obs),
                "n_variables": int(adata.n_vars),
            },
            "manifest_contract": {
                "celltype_key": celltype_key,
                "spatial_key": spatial_key,
                "niche_key": niche_key,
                "required_clustering_method": (
                    niche_match.group("clustering_method") if niche_match else None
                ),
                "required_resolution": float(niche_match.group("resolution"))
                if niche_match
                else None,
            },
            "available_fields": {
                "obs_columns": list(map(str, adata.obs.columns)),
                "obsm_shapes": {str(key): list(value.shape) for key, value in adata.obsm.items()},
            },
            "celltypes": {
                "key": celltype_key,
                "n_labels": int(celltypes.nunique(dropna=True)),
                "missing": int(celltypes.isna().sum()),
                "top_label_counts": {
                    str(key): int(value) for key, value in counts.head(20).items()
                },
            },
            "slide_key_candidates": slide_candidates,
            "spatial": _distance_preflight(
                adata,
                spatial_key=spatial_key,
                slide_candidates=slide_candidates,
            ),
            "expression": _expression_preflight(adata),
        }
        if neighborhood_radii:
            grouping = _resolve_or_create_slide_key(adata, slide_key)
            candidates = []
            for radius in neighborhood_radii:
                try:
                    diagnostics = graph_diagnostics(
                        radius_graph(adata, spatial_key, grouping, radius)
                    )
                except RadiusGraphLimitError as exc:
                    candidates.append(
                        {
                            "radius": exc.radius,
                            "status": "resource_limit",
                            "estimated_edges": exc.estimated_edges,
                            "edge_limit": exc.edge_limit,
                            "message": str(exc),
                        }
                    )
                else:
                    candidates.append({"radius": radius, "status": "success", **diagnostics})
            report["candidate_neighborhoods"] = candidates
            report["n_usable_neighborhoods"] = sum(
                item["status"] == "success" for item in candidates
            )
            if not report["n_usable_neighborhoods"]:
                report["next_action"] = (
                    "No requested radius has usable graph diagnostics. Inspect another feasible "
                    "candidate before choosing spatial scale; the input inventory remains valid."
                )
    finally:
        adata.file.close()

    encoded = json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
    report["inspection_sha256"] = hashlib.sha256(encoded).hexdigest()
    return report


def inspect_tissue_niche_input_tool(
    spatial_anndata_path: str,
    celltype_key: str = "auto",
    spatial_key: str = "auto",
    niche_key: Optional[str] = None,
    neighborhood_radii: Optional[List[float]] = None,
    slide_key: Optional[str] = "auto",
) -> Dict[str, Any]:
    """Inspect a truth-blinded spatial AnnData before choosing niche parameters."""
    try:
        context = get_tissue_niche_context()
        celltype_key = context.get("celltype_key", celltype_key)
        spatial_key = context.get("spatial_key", spatial_key)
        path = _resolve_path(spatial_anndata_path, must_exist=True)
        report = _inspect_tissue_niche_input_path(
            path,
            celltype_key=celltype_key,
            spatial_key=spatial_key,
            niche_key=niche_key,
            neighborhood_radii=neighborhood_radii,
            slide_key=slide_key,
        )
    except Exception as exc:
        return {
            "status": "error",
            "stage": "inspect_tissue_niche_input",
            "error_type": type(exc).__name__,
            "message": str(exc),
            "recoverable": isinstance(exc, (KeyError, ValueError, FileNotFoundError)),
            "next_action": "Correct the argument using available fields or paths; inspect again.",
        }
    report["input"]["path"] = _relative_to_data_dir(path)
    report.pop("inspection_sha256")
    encoded = json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
    report["inspection_sha256"] = hashlib.sha256(encoded).hexdigest()
    return report


def niche_annotation_tool(
    spatial_anndata_path: str,
    output_dir: str = "niche_annotation_results",
    slide_key: Optional[str] = "auto",
    celltype_key: Optional[str] = "auto",
    spatial_key: str = "spatial",
    niche_key: Optional[str] = None,
    annotation_col: str = "tissue_niche",
    justification_col: str = "tissue_niche_justification",
    allowed_labels: Optional[List[str]] = None,
    unmatched_label: str = DEFAULT_UNMATCHED_LABEL,
    top_n_celltypes: Optional[int] = 15,
    top_n_marker_genes: Optional[int] = 15,
    utag_max_dist: float = 20.0,
    utag_normalization_mode: str = "l1_norm",
    utag_apply_clustering: bool = True,
    utag_clustering_method: str = "leiden",
    utag_resolutions: Optional[List[float]] = None,
    parameter_rationale: str = "",
    preflight_sha256: Optional[str] = None,
    output_path: Optional[str] = None,
    dataset_context: Optional[Dict[str, Any]] = None,
    preview_only: bool = False,
) -> Dict[str, Any]:
    """Discover or reuse spatial niches, then label and save a validated H5AD."""
    context = get_tissue_niche_context()
    celltype_key = context.get("celltype_key", celltype_key)
    spatial_key = context.get("spatial_key", spatial_key)
    annotation_col = context.get("annotation_col", annotation_col)
    allowed_labels = context.get("allowed_labels", allowed_labels)
    unmatched_label = context.get("unmatched_label", unmatched_label)
    output_path = context.get("output_path", output_path)
    dataset_context = context.get("dataset_context", dataset_context) or {}
    if not preview_only and (
        not allowed_labels or not any(label != unmatched_label for label in allowed_labels)
    ):
        return {
            "status": "error",
            "stage": "validate_task",
            "recoverable": True,
            "message": "Pass the original allowed anatomical labels before annotation.",
        }
    try:
        spatial_path = _resolve_path(spatial_anndata_path, must_exist=True)
    except FileNotFoundError as exc:
        return {"status": "error", "message": str(exc)}
    except ValueError as exc:
        return {"status": "error", "message": str(exc)}

    try:
        output_dir_path = _resolve_path(
            str(Path(output_dir) / "niche_llm_queries.json"), must_exist=False
        ).parent
        annotated_output_path = (
            _resolve_path(output_path, must_exist=False)
            if output_path
            else output_dir_path / "tissue_niche_annotated_object.h5ad"
        )
    except ValueError as exc:
        return {"status": "error", "message": str(exc)}

    output_dir_path.mkdir(parents=True, exist_ok=True)
    annotated_output_path.parent.mkdir(parents=True, exist_ok=True)
    if annotated_output_path == spatial_path and (
        not context or spatial_path == _resolve_path(context["input_path"], must_exist=True)
    ):
        return {"status": "error", "message": "Use a new output path; input must remain unchanged."}

    try:
        adata = sc.read_h5ad(spatial_path)
    except Exception as exc:
        return {
            "status": "error",
            "message": f"Failed to read AnnData file '{spatial_anndata_path}': {exc}",
        }

    try:
        resolved_slide_key = _resolve_or_create_slide_key(adata, slide_key)
        spatial_key = _resolve_spatial_key(adata, spatial_key)
        resolved_celltype_key = _resolve_celltype_key(adata, celltype_key)
    except KeyError as exc:
        return {"status": "error", "message": str(exc)}

    if spatial_key not in adata.obsm:
        return {
            "status": "error",
            "message": (
                f"Input AnnData is missing spatial_key '{spatial_key}' in .obsm. "
                f"Available embeddings: {sorted(map(str, adata.obsm.keys()))}"
            ),
        }

    label_space = _prepare_allowed_labels(allowed_labels, unmatched_label)
    candidate_parameters = adata.uns.get("tissueagent_niche_candidate", {})
    if not utag_apply_clustering and candidate_parameters.get("niche_key") == niche_key:
        utag_max_dist = float(candidate_parameters["radius"])
    utag_resolutions = utag_resolutions or [0.3]
    if niche_key is None and utag_apply_clustering and len(utag_resolutions) == 1:
        niche_key = f"UTAG Label_{utag_clustering_method}_{utag_resolutions[0]}"
    if niche_key is None:
        return {"status": "error", "message": "Specify the existing or selected clustering key."}
    expected_keys = [f"UTAG Label_{utag_clustering_method}_{value}" for value in utag_resolutions]
    if utag_apply_clustering and niche_key not in expected_keys:
        return {
            "status": "error",
            "recoverable": True,
            "message": f"Selected configuration will create {expected_keys}; correct niche_key.",
        }

    try:
        utag_results = (
            _run_utag(
                adata=adata,
                slide_key=resolved_slide_key,
                max_dist=utag_max_dist,
                normalization_mode=utag_normalization_mode,
                apply_clustering=utag_apply_clustering,
                clustering_method=utag_clustering_method,
                resolutions=utag_resolutions,
            )
            if utag_apply_clustering
            else adata.copy()
        )
    except Exception as exc:
        return {
            "status": "error",
            "message": f"UTAG niche discovery failed: {exc}",
        }

    if niche_key not in utag_results.obs:
        if not utag_apply_clustering:
            return {
                "status": "error",
                "recoverable": True,
                "message": f"Input '{spatial_anndata_path}' has no cluster column '{niche_key}'. "
                "For labeling a preview, set spatial_anndata_path to its returned candidate_h5ad, "
                "not the unclustered query. Copy the selected preview's labeling_arguments; "
                "no new UTAG computation is needed.",
            }
        available_niche_keys = sorted(
            key for key in map(str, utag_results.obs.columns) if key.startswith("UTAG Label")
        )
        return {
            "status": "error",
            "message": (
                f"UTAG completed but niche_key '{niche_key}' was not created. "
                f"Available UTAG columns: {available_niche_keys}"
            ),
        }

    try:
        resolved_celltype_key = _resolve_celltype_key(utag_results, celltype_key)
    except KeyError as exc:
        return {"status": "error", "message": str(exc)}

    try:
        if annotation_col in utag_results.obs:
            if f"{annotation_col}_before_refinement" in utag_results.obs:
                return {"status": "error", "message": "One refinement is already saved; report it."}
        evidence = spatial_niche_evidence(
            utag_results,
            niche_key,
            resolved_celltype_key,
            spatial_key,
            resolved_slide_key,
            utag_max_dist,
        )
        if preview_only:
            candidate = output_dir_path / f"niche_candidate_{uuid.uuid4().hex[:8]}.h5ad"
            utag_results.uns["tissueagent_niche_candidate"] = {
                "radius": float(utag_max_dist),
                "niche_key": niche_key,
            }
            utag_results.write(candidate, compression="gzip")
            _write_json(
                candidate.with_suffix(".json"),
                {
                    "spatial_evidence": evidence,
                    "niche_key": niche_key,
                    "parameter_rationale": parameter_rationale,
                    "utag_resolutions": utag_resolutions,
                    "normalization_mode": utag_normalization_mode,
                },
            )
            sizes = [item["n_cells"] for item in evidence["clusters"].values()]
            return {
                "status": "ready_for_labeling",
                "candidate_h5ad": _relative_to_data_dir(candidate),
                "niche_key": niche_key,
                "radius_used": utag_max_dist,
                "n_niches": len(sizes),
                "cluster_size_quantiles": dict(
                    zip(
                        ["min", "p25", "median", "p75", "max"],
                        np.quantile(sizes, [0, 0.25, 0.5, 0.75, 1]).tolist(),
                        strict=True,
                    )
                ),
                "spatial_evidence": evidence,
                "labeling_arguments": {
                    "spatial_anndata_path": _relative_to_data_dir(candidate),
                    "niche_key": niche_key,
                    "utag_max_dist": utag_max_dist,
                    "utag_apply_clustering": False,
                    "preview_only": False,
                },
                "next_action": "Review granularity and local coherence for the requested anatomy. "
                "Reuse this candidate with utag_apply_clustering=False, its niche_key and radius, "
                "and preview_only=False to label it; or inspect one justified alternative.",
            }
        llm_queries = build_niche_llm_queries(
            utag_results,
            niche_key=niche_key,
            celltype_key=resolved_celltype_key,
            spatial_key=spatial_key,
            top_n_celltypes=top_n_celltypes,
            top_n_marker_genes=top_n_marker_genes,
            allowed_labels=label_space,
            unmatched_label=unmatched_label,
            dataset_context=dataset_context,
            spatial_evidence=evidence,
        )
        llm_results = _label_niches_with_llm(
            llm_queries,
            allowed_labels=label_space,
            unmatched_label=unmatched_label,
        )
    except Exception as exc:
        return {
            "status": "error",
            "message": f"LLM niche labeling failed: {exc}",
        }

    utag_output_path = annotated_output_path
    llm_queries_path = output_dir_path / "niche_llm_queries.json"
    llm_results_path = output_dir_path / "niche_llm_results.json"

    try:
        _write_json(output_dir_path / "spatial_evidence.json", evidence)
        if annotation_col in utag_results.obs:
            for artifact in (llm_queries_path, llm_results_path):
                if artifact.exists():
                    artifact.rename(artifact.with_stem(artifact.stem + "_before_refinement"))
        _write_json(llm_queries_path, llm_queries)
        _write_json(llm_results_path, llm_results)
    except Exception as exc:
        return {
            "status": "error",
            "message": f"Failed while writing niche annotation artifacts: {exc}",
        }

    if annotation_col in utag_results.obs:
        utag_results.obs[f"{annotation_col}_before_refinement"] = utag_results.obs[annotation_col]
    apply_niche_annotations_to_adata(
        utag_results,
        niche_key=niche_key,
        llm_results=llm_results,
        annotation_col=annotation_col,
        justification_col=justification_col,
        allowed_labels=label_space,
        unmatched_label=unmatched_label,
    )

    try:
        if not utag_results.obs_names.equals(adata.obs_names):
            utag_results = utag_results[adata.obs_names].copy()
        if resolved_celltype_key and not utag_results.obs[resolved_celltype_key].equals(
            adata.obs[resolved_celltype_key]
        ):
            raise ValueError("Annotation changed supplied cell-type labels.")
        pending_path = annotated_output_path.with_suffix(".pending.h5ad")
        utag_results.write(pending_path, compression="gzip")
        check = sc.read_h5ad(pending_path, backed="r")
        try:
            if (
                not check.obs_names.equals(adata.obs_names)
                or not check.obs[annotation_col].isin(label_space).all()
            ):
                raise ValueError("Saved annotation failed cell-ID or vocabulary validation.")
        finally:
            check.file.close()
        pending_path.replace(annotated_output_path)
    except Exception as exc:
        return {
            "status": "error",
            "message": f"Failed while writing the final annotated AnnData artifact: {exc}",
        }

    counts = utag_results.obs[annotation_col].value_counts(dropna=False)
    counts = counts.reindex(label_space, fill_value=0)
    annotation_counts = {str(label): int(count) for label, count in counts.items()}
    niche_id_to_label = {niche_id: result["label"] for niche_id, result in llm_results.items()}

    logs_dir = active_project_outputs() / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    meta_path = logs_dir / "niche_annotation_run_meta.json"

    metadata = {
        "status": "success",
        "method": "UTAG + internal LLM niche labeling",
        "dataset_context": dataset_context,
        "spatial_evidence": evidence,
        "clustering_source": "native_utag" if utag_apply_clustering else "existing_clusters",
        "parameters": {
            "slide_key_requested": slide_key,
            "slide_key_resolved": resolved_slide_key,
            "celltype_key_requested": celltype_key,
            "celltype_key_resolved": resolved_celltype_key,
            "spatial_key": spatial_key,
            "niche_key": niche_key,
            "annotation_col": annotation_col,
            "justification_col": justification_col,
            "allowed_labels": label_space,
            "unmatched_label": unmatched_label,
            "top_n_celltypes": top_n_celltypes,
            "top_n_marker_genes": top_n_marker_genes,
            "utag_max_dist": utag_max_dist,
            "utag_normalization_mode": utag_normalization_mode,
            "utag_apply_clustering": utag_apply_clustering,
            "utag_clustering_method": utag_clustering_method,
            "utag_resolutions": utag_resolutions,
        },
        "parameter_selection": {
            "rationale": parameter_rationale.strip(),
            "preflight_sha256": preflight_sha256,
        },
        "runtime": {
            "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
        "inputs": {
            "spatial_anndata_path": _relative_to_data_dir(spatial_path),
        },
        "outputs": {
            "utag_object_h5ad": _relative_to_data_dir(utag_output_path),
            "annotated_object_h5ad": _relative_to_data_dir(annotated_output_path),
            "niche_llm_queries_json": _relative_to_data_dir(llm_queries_path),
            "niche_llm_results_json": _relative_to_data_dir(llm_results_path),
        },
        "summary": {
            "n_cells": int(utag_results.n_obs),
            "n_niches": int(len(llm_results)),
            "annotation_counts": annotation_counts,
        },
    }
    _write_json(meta_path, metadata)

    return {
        "status": "success",
        "output_dir": _relative_to_data_dir(output_dir_path),
        "utag_object_h5ad": _relative_to_data_dir(utag_output_path),
        "annotated_object_h5ad": _relative_to_data_dir(annotated_output_path),
        "niche_llm_queries_json": _relative_to_data_dir(llm_queries_path),
        "niche_llm_results_json": _relative_to_data_dir(llm_results_path),
        "run_meta_json": _relative_to_data_dir(meta_path),
        "niche_key": niche_key,
        "celltype_key": resolved_celltype_key,
        "annotation_col": annotation_col,
        "justification_col": justification_col,
        "n_cells": int(utag_results.n_obs),
        "n_niches": int(len(llm_results)),
        "annotation_counts": annotation_counts,
        "niche_id_to_label": niche_id_to_label,
        "radius_used": utag_max_dist,
        "niche_annotations": llm_results,
        "spatial_diagnostics": evidence["graph"],
        "spatial_evidence_json": _relative_to_data_dir(output_dir_path / "spatial_evidence.json"),
        "parameter_rationale": parameter_rationale.strip(),
        "preflight_sha256": preflight_sha256,
    }


def build_niche_llm_queries(
    adata: sc.AnnData,
    niche_key: str = "UTAG Label_leiden_0.3",
    celltype_key: Optional[str] = "auto",
    spatial_key: str = "spatial",
    top_n_celltypes: Optional[int] = 15,
    top_n_marker_genes: Optional[int] = 15,
    allowed_labels: Optional[List[str]] = None,
    unmatched_label: str = DEFAULT_UNMATCHED_LABEL,
    dataset_context: Optional[Dict[str, Any]] = None,
    spatial_evidence: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    """Build one LLM prompt per UTAG niche.

    Returns:
        A mapping of niche ID to LLM query string.
    """
    if niche_key not in adata.obs:
        raise KeyError(f"niche_key '{niche_key}' was not found in adata.obs")
    if spatial_key not in adata.obsm:
        raise KeyError(f"spatial_key '{spatial_key}' was not found in adata.obsm")
    resolved_celltype_key = _resolve_celltype_key(adata, celltype_key)

    labels = adata.obs[niche_key].astype("category").cat.remove_unused_categories()
    niches = [str(niche) for niche in labels.cat.categories]
    coords = np.asarray(adata.obsm[spatial_key])
    if coords.ndim != 2 or coords.shape[1] < 2:
        raise ValueError(
            f"Expected adata.obsm['{spatial_key}'] to have at least two columns, "
            f"got shape {coords.shape}."
        )

    label_space = _prepare_allowed_labels(allowed_labels, unmatched_label)
    allowed_labels_json = json.dumps(label_space, ensure_ascii=False)

    queries: Dict[str, str] = {}
    label_strings = labels.astype(str)

    for niche in niches:
        mask = (label_strings == niche).to_numpy()
        if not np.any(mask):
            continue

        centroid_x = float(coords[mask, 0].mean())
        centroid_y = float(coords[mask, 1].mean())

        celltype_lines = _format_celltype_composition(
            adata=adata,
            mask=mask,
            celltype_key=resolved_celltype_key,
            top_n_celltypes=top_n_celltypes,
        )
        marker_gene_lines = _format_marker_gene_summary(
            adata=adata,
            mask=mask,
            top_n_marker_genes=top_n_marker_genes,
        )
        marker_gene_section = (
            f"\n\nMarker Gene Summary:\n{marker_gene_lines}"
            if top_n_marker_genes is not None and top_n_marker_genes > 0
            else ""
        )

        evidence = spatial_evidence or {}
        query = f"""
You are an expert spatial biologist.
Assign the anatomical tissue region supported by the measured evidence.
Computational clusters can pool cells from different anatomical regions.
Spatial coherence is not guaranteed.

Public dataset context:
{json.dumps(dataset_context or {}, ensure_ascii=False, sort_keys=True)}

Niche ID: {niche}
Number of cells: {int(mask.sum())}

Spatial Location:
- Centroid X: {centroid_x:.2f}
- Centroid Y: {centroid_y:.2f}

Cell Type Composition:
{celltype_lines}{marker_gene_section}

Spatial evidence from supplied coordinates and cell types:
{json.dumps(evidence.get("clusters", {}).get(niche, {}), ensure_ascii=False)}

Other clusters in this section (IDs are computational, not known anatomical regions):
{json.dumps(evidence.get("cluster_overview", []), ensure_ascii=False)}

Rules:
- Output a SINGLE short anatomical label from this allowed set: {allowed_labels_json}
- If ambiguous, output "{unmatched_label}".
- Use the requested anatomical scale. Compare plausible labels against the measured evidence.
- Common stromal, vascular, or immune cell types alone do not identify a unique anatomical region.
- Coordinate signs do not establish anatomical orientation.
- Do not present unmeasured physiology as observed evidence.
- Multiple clusters may share a label. Not every allowed label must occur in this section.
- If the cluster combines incompatible regional contexts, explain the ambiguity
  and whether spatial subdivision would help.
- Do NOT mention genes or cell-type names in the label.
- After the label, output 1-2 sentence justification.
- Return ONLY valid JSON with no markdown fences and no extra text.

Return this JSON object:
{{
  "label": "<label>",
  "niche_id": "{niche}",
  "justification": "<short explanation>"
}}
""".strip()
        queries[niche] = query

    return queries


def _resolve_or_create_slide_key(
    adata: sc.AnnData,
    slide_key: Optional[str],
) -> str:
    """Resolve a slide/sample column, or create a single-slide grouping."""
    if slide_key is None:
        adata.obs[SYNTHETIC_SLIDE_KEY] = "sample_0"
        return SYNTHETIC_SLIDE_KEY

    requested_key = str(slide_key).strip()
    requested_key_folded = requested_key.casefold()
    if requested_key_folded in NO_KEY_VALUES:
        adata.obs[SYNTHETIC_SLIDE_KEY] = "sample_0"
        return SYNTHETIC_SLIDE_KEY

    columns_by_folded_name = {str(column).casefold(): str(column) for column in adata.obs.columns}

    if requested_key_folded in AUTO_KEY_VALUES:
        for candidate in SLIDE_KEY_CANDIDATES:
            resolved = columns_by_folded_name.get(candidate.casefold())
            if resolved is not None:
                return resolved
        adata.obs[SYNTHETIC_SLIDE_KEY] = "sample_0"
        return SYNTHETIC_SLIDE_KEY

    resolved = columns_by_folded_name.get(requested_key_folded)
    if resolved is not None:
        return resolved

    available = sorted(map(str, adata.obs.columns))
    raise KeyError(
        f"Input AnnData is missing slide_key '{slide_key}' in .obs. "
        f"Available columns: {available}. Use slide_key='auto' to infer a common "
        "slide/sample column or create a single-slide grouping."
    )


def _resolve_spatial_key(adata: sc.AnnData, spatial_key: str) -> str:
    requested = str(spatial_key).casefold()
    names = {str(key).casefold(): str(key) for key in adata.obsm}
    if requested in AUTO_KEY_VALUES:
        candidates = [
            names[key] for key in ("spatial", "spatial_coordinates", "coordinates") if key in names
        ]
        if len(candidates) == 1:
            return candidates[0]
    elif requested in names:
        return names[requested]
    raise KeyError(
        f"Cannot resolve spatial_key '{spatial_key}'. Available obsm: {list(adata.obsm)}. "
        "Specify the array containing physical coordinates; an embedding is not sufficient."
    )


def _resolve_celltype_key(
    adata: sc.AnnData,
    celltype_key: Optional[str],
) -> Optional[str]:
    """Resolve an optional cell-type obs column, with explicit auto detection."""
    if celltype_key is None:
        return None

    requested_key = str(celltype_key).strip()
    requested_key_folded = requested_key.casefold()
    if requested_key_folded in NO_CELLTYPE_KEY_VALUES:
        return None

    columns_by_folded_name = {str(column).casefold(): str(column) for column in adata.obs.columns}

    if requested_key_folded in AUTO_CELLTYPE_KEY_VALUES:
        candidates = [
            columns_by_folded_name[candidate.casefold()]
            for candidate in CELLTYPE_KEY_CANDIDATES
            if candidate.casefold() in columns_by_folded_name
        ]
        if len(candidates) == 1:
            return candidates[0]
        if len(candidates) > 1:
            raise KeyError(f"Ambiguous cell-type columns: {candidates}. Specify celltype_key.")
        return None

    resolved = columns_by_folded_name.get(requested_key_folded)
    if resolved is not None:
        return resolved

    available = sorted(map(str, adata.obs.columns))
    raise KeyError(
        f"Input AnnData is missing celltype_key '{celltype_key}' in .obs. "
        f"Available columns: {available}. Use celltype_key='auto' to infer a common "
        "cell-type column, or celltype_key=None to run niche labeling from marker "
        "gene summaries only."
    )


def _format_celltype_composition(
    *,
    adata: sc.AnnData,
    mask: np.ndarray,
    celltype_key: Optional[str],
    top_n_celltypes: Optional[int],
) -> str:
    if celltype_key is None:
        return "- Not available in this AnnData object."

    celltypes = adata.obs.loc[mask, celltype_key].astype(str)
    celltype_counts = celltypes.value_counts(normalize=True).mul(100)
    if top_n_celltypes is not None and top_n_celltypes > 0:
        celltype_counts = celltype_counts.head(top_n_celltypes)

    lines = [f"- {celltype}: {fraction:.1f}%" for celltype, fraction in celltype_counts.items()]
    return "\n".join(lines) if lines else "- No cell-type labels available for this niche."


def _format_marker_gene_summary(
    *,
    adata: sc.AnnData,
    mask: np.ndarray,
    top_n_marker_genes: Optional[int],
) -> str:
    if top_n_marker_genes is None or top_n_marker_genes <= 0:
        return "- Marker gene summary disabled."
    if adata.n_vars == 0:
        return "- No genes available in this AnnData object."

    background_mask = ~mask
    in_mean = _column_mean(adata.X[mask])
    if np.any(background_mask):
        background_mean = _column_mean(adata.X[background_mask])
    else:
        background_mean = np.zeros_like(in_mean)

    enrichment_delta = in_mean - background_mean
    finite = np.isfinite(in_mean) & np.isfinite(enrichment_delta)
    if not np.any(finite):
        return "- No finite gene expression summary could be computed."

    candidate_indices = np.flatnonzero(finite)
    positive_indices = candidate_indices[enrichment_delta[candidate_indices] > 0]
    if len(positive_indices) > 0:
        candidate_indices = positive_indices
        ranking_values = enrichment_delta[candidate_indices]
    else:
        ranking_values = in_mean[candidate_indices]

    ranked_indices = candidate_indices[np.argsort(ranking_values)[::-1]]
    ranked_indices = ranked_indices[:top_n_marker_genes]
    if len(ranked_indices) == 0:
        return "- No marker-like genes found for this niche."

    lines = []
    for gene_index in ranked_indices:
        gene = str(adata.var_names[gene_index])
        lines.append(
            f"- {gene}: mean={in_mean[gene_index]:.3g}, "
            f"delta_vs_other_niches={enrichment_delta[gene_index]:.3g}"
        )
    return "\n".join(lines)


def _column_mean(matrix: Any) -> np.ndarray:
    if sparse.issparse(matrix):
        return np.asarray(matrix.mean(axis=0)).ravel()
    return np.asarray(matrix).mean(axis=0)


def apply_niche_annotations_to_adata(
    adata: sc.AnnData,
    niche_key: str,
    llm_results: Dict[str, Dict[str, str]],
    annotation_col: str = "tissue_niche",
    justification_col: str = "tissue_niche_justification",
    allowed_labels: Optional[List[str]] = None,
    unmatched_label: str = DEFAULT_UNMATCHED_LABEL,
) -> sc.AnnData:
    """Apply per-niche LLM labels and justifications to each observation."""
    if niche_key not in adata.obs:
        raise KeyError(f"niche_key '{niche_key}' was not found in adata.obs")

    label_space = _prepare_allowed_labels(allowed_labels, unmatched_label)
    lookup = {
        str(niche_id): {
            "label": _normalize_label(
                result.get("label", unmatched_label), label_space, unmatched_label
            ),
            "justification": str(result.get("justification", "")).strip(),
        }
        for niche_id, result in llm_results.items()
    }

    niche_assignments = adata.obs[niche_key].astype(str)
    new_labels: List[str] = []
    new_justifications: List[str] = []

    for niche_id in niche_assignments:
        entry = lookup.get(
            str(niche_id),
            {"label": unmatched_label, "justification": ""},
        )
        new_labels.append(entry["label"])
        new_justifications.append(entry["justification"])

    adata.obs[annotation_col] = pd.Categorical(new_labels, categories=label_space)
    adata.obs[justification_col] = new_justifications
    return adata


def _run_utag(
    adata: sc.AnnData,
    slide_key: str,
    max_dist: float,
    normalization_mode: str,
    apply_clustering: bool,
    clustering_method: str,
    resolutions: List[float],
) -> sc.AnnData:
    try:
        import utag
    except ImportError as exc:
        raise RuntimeError(
            "The 'utag' package is not installed in the active environment."
        ) from exc

    return utag.utag(
        adata,
        slide_key=slide_key,
        max_dist=max_dist,
        normalization_mode=normalization_mode,
        apply_clustering=apply_clustering,
        clustering_method=clustering_method,
        resolutions=resolutions,
    )


def _label_niches_with_llm(
    llm_queries: Dict[str, str],
    allowed_labels: Optional[List[str]],
    unmatched_label: str,
) -> Dict[str, Dict[str, str]]:
    from langchain_core.messages import HumanMessage, SystemMessage

    from config import DefaultModelCtor

    model = DefaultModelCtor()
    system_prompt = SystemMessage(
        "You label UTAG-derived tissue niches. Respond with only a single valid JSON object."
    )

    results: Dict[str, Dict[str, str]] = {}
    for index, (niche_id, query) in enumerate(llm_queries.items(), 1):
        logging.info("Tissue-niche labeling %d/%d (cluster %s)", index, len(llm_queries), niche_id)
        response = model.invoke([system_prompt, HumanMessage(query)])
        parsed = _parse_llm_annotation_response(
            _message_content_to_text(response.content),
            niche_id=niche_id,
            allowed_labels=allowed_labels,
            unmatched_label=unmatched_label,
        )
        results[str(niche_id)] = parsed

    return results


def _message_content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
                continue
            if isinstance(item, dict) and item.get("type") in {"text", "output_text"}:
                parts.append(str(item.get("text", "")))
        return "\n".join(part for part in parts if part).strip()
    return str(content).strip()


def _parse_llm_annotation_response(
    response_text: str,
    niche_id: str,
    allowed_labels: Optional[List[str]],
    unmatched_label: str,
) -> Dict[str, str]:
    payload = _extract_json_object(response_text)
    if not isinstance(payload, dict):
        raise ValueError(
            f"Expected JSON object for niche '{niche_id}', got: {type(payload).__name__}"
        )

    label = _normalize_label(payload.get("label", unmatched_label), allowed_labels, unmatched_label)
    justification = str(payload.get("justification", "")).strip()
    return {
        "niche_id": str(niche_id),
        "label": label,
        "justification": justification,
    }


def _extract_json_object(response_text: str) -> Any:
    cleaned = response_text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    json_start = cleaned.find("{")
    if json_start == -1:
        raise ValueError(f"No JSON object found in model response: {response_text}")

    decoder = json.JSONDecoder()
    try:
        payload, _ = decoder.raw_decode(cleaned[json_start:])
    except json.JSONDecodeError as exc:
        raise ValueError(f"Failed to parse model response as JSON: {response_text}") from exc
    return payload


def _prepare_allowed_labels(
    allowed_labels: Optional[List[str]],
    unmatched_label: str,
) -> List[str]:
    labels = list(allowed_labels or [])
    labels.append(unmatched_label)

    deduped: List[str] = []
    seen = set()
    for label in labels:
        normalized = str(label).strip()
        if not normalized:
            continue
        key = normalized.casefold()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(normalized)
    return deduped


def _normalize_label(
    label: Any,
    allowed_labels: Optional[List[str]],
    unmatched_label: str,
) -> str:
    normalized = str(label).strip()
    if not normalized:
        return unmatched_label

    if not allowed_labels:
        return normalized

    canonical = {candidate.casefold(): candidate for candidate in allowed_labels}
    return canonical.get(normalized.casefold(), unmatched_label)


def _write_json(path: Path, payload: Any) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
