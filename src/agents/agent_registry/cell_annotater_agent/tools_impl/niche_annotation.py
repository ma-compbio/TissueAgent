from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import scanpy as sc
from scipy import sparse

from config import DATA_DIR, DATASET_DIR, UPLOADS_DIR

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
    "cell_type_label",
    "predicted_cell_type",
    "annotation",
    "bulk_labels",
    "label",
)


def _relative_to_data_dir(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(DATA_DIR.resolve()))
    except ValueError:
        return str(resolved)


def _resolve_path(path_like: str, *, must_exist: bool) -> Path:
    """
    Resolve a user-provided path into DATA_DIR while allowing references to common
    app-managed subdirectories. Always enforces that the final target stays inside
    DATA_DIR.
    """
    raw_path = Path(path_like).expanduser()
    data_root = DATA_DIR.resolve()

    candidate_roots = [
        None if raw_path.is_absolute() else DATA_DIR,
        None if raw_path.is_absolute() else DATASET_DIR,
        None if raw_path.is_absolute() else UPLOADS_DIR,
    ]

    candidates = []
    if raw_path.is_absolute():
        candidates.append(raw_path)
    else:
        for root in candidate_roots:
            if root is None:
                continue
            candidates.append(root / raw_path)

    seen: set[Path] = set()
    for candidate in candidates:
        resolved_candidate = candidate.resolve()
        if resolved_candidate in seen:
            continue
        seen.add(resolved_candidate)
        try:
            resolved_candidate.relative_to(data_root)
        except ValueError:
            continue
        if must_exist and not resolved_candidate.exists():
            continue
        return resolved_candidate

    if must_exist:
        searched_locations = [str((root / raw_path).resolve()) for root in {DATA_DIR, DATASET_DIR, UPLOADS_DIR}]
        raise FileNotFoundError(
            f"Path '{path_like}' not found inside DATA_DIR '{DATA_DIR}'. "
            f"Searched: {', '.join(sorted(searched_locations))}"
        )

    target = (raw_path if raw_path.is_absolute() else DATA_DIR / raw_path).resolve()
    try:
        target.relative_to(data_root)
    except ValueError as exc:
        raise ValueError(
            f"Output path '{path_like}' must be inside DATA_DIR '{DATA_DIR}'."
        ) from exc
    return target


def niche_annotation_tool(
    spatial_anndata_path: str,
    output_dir: str = "niche_annotation_results",
    slide_key: Optional[str] = "auto",
    celltype_key: Optional[str] = "auto",
    spatial_key: str = "spatial",
    niche_key: str = "UTAG Label_leiden_0.3",
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
) -> Dict[str, Any]:
    """
    Run UTAG niche discovery, label each niche via an internal LLM call, and
    apply the resulting annotations back to the AnnData object.
    """

    try:
        spatial_path = _resolve_path(spatial_anndata_path, must_exist=True)
    except FileNotFoundError as exc:
        return {"status": "error", "message": str(exc)}
    except ValueError as exc:
        return {"status": "error", "message": str(exc)}

    try:
        output_dir_path = _resolve_path(output_dir, must_exist=False)
    except ValueError as exc:
        return {"status": "error", "message": str(exc)}

    output_dir_path.mkdir(parents=True, exist_ok=True)

    try:
        adata = sc.read_h5ad(spatial_path)
    except Exception as exc:
        return {
            "status": "error",
            "message": f"Failed to read AnnData file '{spatial_anndata_path}': {exc}",
        }

    try:
        resolved_slide_key = _resolve_or_create_slide_key(adata, slide_key)
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
    utag_resolutions = utag_resolutions or [0.05, 0.1, 0.3]

    try:
        utag_results = _run_utag(
            adata=adata,
            slide_key=resolved_slide_key,
            max_dist=utag_max_dist,
            normalization_mode=utag_normalization_mode,
            apply_clustering=utag_apply_clustering,
            clustering_method=utag_clustering_method,
            resolutions=utag_resolutions,
        )
    except Exception as exc:
        return {
            "status": "error",
            "message": f"UTAG niche discovery failed: {exc}",
        }

    if niche_key not in utag_results.obs:
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
        llm_queries = build_niche_llm_queries(
            utag_results,
            niche_key=niche_key,
            celltype_key=resolved_celltype_key,
            spatial_key=spatial_key,
            top_n_celltypes=top_n_celltypes,
            top_n_marker_genes=top_n_marker_genes,
            allowed_labels=label_space,
            unmatched_label=unmatched_label,
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

    utag_output_path = output_dir_path / "utag_adata.h5ad"
    annotated_output_path = output_dir_path / "tissue_niche_annotated_object.h5ad"
    llm_queries_path = output_dir_path / "niche_llm_queries.json"
    llm_results_path = output_dir_path / "niche_llm_results.json"

    try:
        utag_results.write(utag_output_path, compression="gzip")
        _write_json(llm_queries_path, llm_queries)
        _write_json(llm_results_path, llm_results)
    except Exception as exc:
        return {
            "status": "error",
            "message": f"Failed while writing niche annotation artifacts: {exc}",
        }

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
        utag_results.write(annotated_output_path, compression="gzip")
    except Exception as exc:
        return {
            "status": "error",
            "message": f"Failed while writing the final annotated AnnData artifact: {exc}",
        }

    counts = utag_results.obs[annotation_col].value_counts(dropna=False)
    counts = counts.reindex(label_space, fill_value=0)
    annotation_counts = {str(label): int(count) for label, count in counts.items()}
    niche_id_to_label = {
        niche_id: result["label"]
        for niche_id, result in llm_results.items()
    }

    logs_dir = DATA_DIR / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    meta_path = logs_dir / "niche_annotation_run_meta.json"

    metadata = {
        "status": "success",
        "method": "UTAG + internal LLM niche labeling",
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
) -> Dict[str, str]:
    """
    Build one LLM prompt per UTAG niche using cell-type composition and spatial
    centroid summaries.

    Returns
    -------
    dict
        Mapping of niche_id to LLM query string.
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
            f"Expected adata.obsm['{spatial_key}'] to have at least two columns, got shape {coords.shape}."
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
        niche_size = int(mask.sum())

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

        query = f"""
You are an expert spatial biologist.
Your task is to provide a concise, biologically meaningful anatomical label for a spatial tissue niche.
Each niche is a spatially coherent cluster identified using UTAG.

Niche ID: {niche}
Number of cells: {niche_size}

Spatial Location:
- Centroid X: {centroid_x:.2f}
- Centroid Y: {centroid_y:.2f}

Cell Type Composition:
{celltype_lines}

Marker Gene Summary:
{marker_gene_lines}

Rules:
- Output a SINGLE short anatomical label from this allowed set: {allowed_labels_json}
- If the niche is ambiguous or does not match the allowed set, output "{unmatched_label}".
- Do NOT mention genes or cell-type names inside the label.
- After the label, provide a short 1-2 sentence justification.
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

    columns_by_folded_name = {
        str(column).casefold(): str(column)
        for column in adata.obs.columns
    }

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

    columns_by_folded_name = {
        str(column).casefold(): str(column)
        for column in adata.obs.columns
    }

    if requested_key_folded in AUTO_CELLTYPE_KEY_VALUES:
        for candidate in CELLTYPE_KEY_CANDIDATES:
            resolved = columns_by_folded_name.get(candidate.casefold())
            if resolved is not None:
                return resolved
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

    lines = [
        f"- {celltype}: {fraction:.1f}%"
        for celltype, fraction in celltype_counts.items()
    ]
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
    """
    Apply per-niche LLM labels and justifications back to each observation in an
    AnnData object.
    """

    if niche_key not in adata.obs:
        raise KeyError(f"niche_key '{niche_key}' was not found in adata.obs")

    label_space = _prepare_allowed_labels(allowed_labels, unmatched_label)
    lookup = {
        str(niche_id): {
            "label": _normalize_label(result.get("label", unmatched_label), label_space, unmatched_label),
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
    for niche_id, query in llm_queries.items():
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
