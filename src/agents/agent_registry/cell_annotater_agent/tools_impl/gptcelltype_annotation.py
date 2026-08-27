"""Native GPTCellType-style cluster annotation for spatial AnnData objects."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4
import json
import math
import os
import re

import anndata as ad
from langchain_core.messages import HumanMessage, SystemMessage
import numpy as np
import pandas as pd
import scanpy as sc
from scipy import sparse

from agents.agent_registry.cell_annotater_agent.tools_impl.harmony_transfer import (
    ENSEMBL_GENE_RE,
    GENE_SYMBOL_COLUMNS,
    _inspect_expression_matrix,
)
from agents.agent_registry.cell_annotater_agent.tools_impl.gptcelltype_readiness import (
    EXECUTION_GENE_FILTER_MIN_CELLS,
    EXECUTION_MAX_PCS,
    EXECUTION_MAX_VARIABLE_FEATURES,
    EXECUTION_N_NEIGHBORS,
    LEIDEN_DIRECTED,
    LEIDEN_FLAVOR,
    LEIDEN_N_ITERATIONS,
    LEIDEN_USE_WEIGHTS,
    PCA_SVD_SOLVER,
    RANDOM_STATE,
    gptcelltype_execution_clustering_profile,
    gptcelltype_readiness_execution_binding,
)
from agents.workspace_paths import (
    resolve_project_output,
    resolve_workspace_input,
    workspace_relative,
)
from models import get_model_id, get_model_seed, get_model_spec, model_ctor_for_role


ANNOTATION_METHOD = "gptcelltype"
LABEL_SOURCE = "gptcelltype_free_text"
CLUSTER_KEY = "__gptcelltype_cluster__"
MAX_TOP_MARKER_GENES = 10
MAX_API_BATCH_SIZE = 25
MAX_API_ATTEMPTS = 10
MAX_API_TIMEOUT_SECONDS = 600
FORBIDDEN_CLUSTER_COLUMN_TERMS = (
    "annotation",
    "class",
    "cell_type",
    "celltype",
    "ground_truth",
    "identity",
    "label",
    "manual",
    "population",
    "prediction",
    "reference",
    "subclass",
    "truth",
)
SAFE_CLUSTER_COLUMN_RE = re.compile(
    r"^(?:leiden(?:[_.-].*)?|louvain(?:[_.-].*)?|seurat_clusters?|"
    r"transcriptomic_clusters?)$"
)
SYSTEM_PROMPT = (
    "You are performing GPTCellType-style cell-cluster annotation from positive marker "
    "genes. Return only one valid JSON object. Its keys must exactly match the supplied "
    "cluster IDs, and each value must be one concise free-text cell-type name. Do not return "
    "explanations, markdown, confidence values, or additional keys."
)
OUTPUT_COLUMNS = (
    "gptcelltype_cluster",
    "gptcelltype_predicted_cell_type",
    "gptcelltype_status",
    "gptcelltype_exclusion_reason",
    "cell_annotation_predicted_cell_type",
    "cell_annotation_prediction_confidence",
    "cell_annotation_status",
    "cell_annotation_exclusion_reason",
    "cell_annotation_method",
    "label",
)


class BatchAnnotationError(RuntimeError):
    """Report a batch that exhausted its bounded model attempts."""

    def __init__(
        self,
        batch_index: int,
        attempts: int,
        prompt_records: list[dict[str, Any]] | None = None,
        response_records: list[dict[str, Any]] | None = None,
    ) -> None:
        """Record the failed one-indexed batch and its attempt count."""
        self.batch_index = batch_index
        self.attempts = attempts
        self.prompt_records = prompt_records or []
        self.response_records = response_records or []
        super().__init__(
            f"GPTCellType batch {batch_index} did not produce valid exact-key JSON "
            f"after {attempts} attempts."
        )


def _utc_timestamp() -> str:
    """Return an RFC 3339 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _validate_context(value: str, *, field: str, maximum_length: int) -> str:
    """Validate concise audit or provider context."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string.")
    cleaned = value.strip()
    if len(cleaned) > maximum_length:
        raise ValueError(f"{field} must contain at most {maximum_length} characters.")
    if field in {"species", "tissue"} and any(character in cleaned for character in "\r\n"):
        raise ValueError(f"{field} must be a single-line broad descriptor.")
    return cleaned


def _validate_parameters(
    *,
    species: str,
    tissue: str,
    selection_rationale: str,
    cluster_column: str | None,
    resolution: float,
    top_marker_genes: int,
    api_batch_size: int,
    max_api_attempts_per_batch: int,
    api_timeout_seconds: int,
) -> tuple[str, str, str, str | None]:
    """Validate the public tool parameters and return normalized strings."""
    clean_species = _validate_context(species, field="species", maximum_length=100)
    clean_tissue = _validate_context(tissue, field="tissue", maximum_length=200)
    clean_rationale = _validate_context(
        selection_rationale,
        field="selection_rationale",
        maximum_length=4000,
    )

    clean_cluster_column: str | None = None
    if cluster_column is not None:
        if not isinstance(cluster_column, str) or not cluster_column.strip():
            raise ValueError("cluster_column must be None or a non-empty column name.")
        clean_cluster_column = cluster_column.strip()
        normalized_column = clean_cluster_column.casefold().replace(" ", "_")
        if any(term in normalized_column for term in FORBIDDEN_CLUSTER_COLUMN_TERMS):
            raise ValueError(
                "cluster_column appears to contain annotation or evaluation labels. "
                "Provide a genuine transcriptomic cluster column or omit it to create "
                "deterministic Leiden clusters."
            )
        if SAFE_CLUSTER_COLUMN_RE.fullmatch(normalized_column) is None:
            raise ValueError(
                "cluster_column must use a recognized transcriptomic clustering name "
                "(Leiden, Louvain, Seurat clusters, or transcriptomic_cluster). Omit it "
                "to create deterministic Leiden clusters."
            )

    if isinstance(resolution, bool) or not isinstance(resolution, (int, float)):
        raise ValueError("resolution must be a finite positive number.")
    if not math.isfinite(float(resolution)) or float(resolution) <= 0:
        raise ValueError("resolution must be a finite positive number.")

    integer_parameters = {
        "top_marker_genes": top_marker_genes,
        "api_batch_size": api_batch_size,
        "max_api_attempts_per_batch": max_api_attempts_per_batch,
        "api_timeout_seconds": api_timeout_seconds,
    }
    for name, value in integer_parameters.items():
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{name} must be an integer.")

    if not 1 <= top_marker_genes <= MAX_TOP_MARKER_GENES:
        raise ValueError(
            f"top_marker_genes must be between 1 and {MAX_TOP_MARKER_GENES}; "
            "the published GPTCellType contract uses at most 10 markers."
        )
    if not 1 <= api_batch_size <= MAX_API_BATCH_SIZE:
        raise ValueError(f"api_batch_size must be between 1 and {MAX_API_BATCH_SIZE}.")
    if not 1 <= max_api_attempts_per_batch <= MAX_API_ATTEMPTS:
        raise ValueError(f"max_api_attempts_per_batch must be between 1 and {MAX_API_ATTEMPTS}.")
    if not 1 <= api_timeout_seconds <= MAX_API_TIMEOUT_SECONDS:
        raise ValueError(f"api_timeout_seconds must be between 1 and {MAX_API_TIMEOUT_SECONDS}.")

    return clean_species, clean_tissue, clean_rationale, clean_cluster_column


def _artifact_paths(output_path: Path) -> dict[str, Path]:
    """Derive adjacent audit-artifact paths from the output H5AD path."""
    base = output_path.with_suffix("")
    return {
        "annotated_object_h5ad": output_path,
        "run_meta_json": output_path.with_suffix(".run_meta.json"),
        "markers_json": base.with_name(f"{base.name}.gptcelltype_markers.json"),
        "prompts_json": base.with_name(f"{base.name}.gptcelltype_prompts.json"),
        "responses_json": base.with_name(f"{base.name}.gptcelltype_responses.json"),
    }


def _ensure_outputs_available(paths: dict[str, Path]) -> None:
    """Fail before computation if any requested artifact already exists."""
    collisions = [path for path in paths.values() if path.exists()]
    if collisions:
        rendered = ", ".join(str(path) for path in collisions)
        raise FileExistsError(f"Refusing to overwrite existing artifact(s): {rendered}")


def _publish_temp_exclusively(temporary_path: Path, output_path: Path) -> None:
    """Publish a completed temporary file without replacing an existing path."""
    try:
        os.link(temporary_path, output_path)
    except FileExistsError as exc:
        raise FileExistsError(f"Refusing to overwrite existing artifact: {output_path}") from exc
    finally:
        temporary_path.unlink(missing_ok=True)


def _write_json_exclusively(payload: Any, output_path: Path) -> None:
    """Write JSON through a same-directory temporary file and exclusive publish."""
    temporary_path = output_path.with_name(f".{output_path.name}.{uuid4().hex}.tmp.json")
    try:
        with temporary_path.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        _publish_temp_exclusively(temporary_path, output_path)
    finally:
        temporary_path.unlink(missing_ok=True)


def _write_h5ad_exclusively(dataset: ad.AnnData, output_path: Path) -> None:
    """Write an H5AD through a same-directory temporary file and exclusive publish."""
    temporary_path = output_path.with_name(
        f".{output_path.stem}.{uuid4().hex}.tmp{output_path.suffix}"
    )
    previous_allow_nullable_strings = ad.settings.allow_write_nullable_strings
    try:
        ad.settings.allow_write_nullable_strings = True
        dataset.write_h5ad(temporary_path, compression="gzip")
        _publish_temp_exclusively(temporary_path, output_path)
    finally:
        ad.settings.allow_write_nullable_strings = previous_allow_nullable_strings
        temporary_path.unlink(missing_ok=True)


def _matrix_values(matrix: Any) -> np.ndarray:
    """Return the stored values used for finite and sign validation."""
    if sparse.issparse(matrix):
        return np.asarray(matrix.data)
    return np.asarray(matrix).ravel()


def _validate_expression_values(dataset: ad.AnnData) -> None:
    """Require finite, nonnegative expression suitable for log-scale marker tests."""
    values = _matrix_values(dataset.X)
    if values.size and not np.isfinite(values).all():
        raise ValueError("The expression matrix contains non-finite values.")
    if values.size and np.any(values < 0):
        raise ValueError(
            "The expression matrix contains negative values and cannot be used for "
            "GPTCellType positive-marker ranking."
        )


def _prepare_expression(
    dataset: ad.AnnData,
    inspection: dict[str, Any],
) -> tuple[ad.AnnData, str]:
    """Return a log-normalized working copy using the inspected matrix state."""
    state = inspection["expression_state"]
    if state == "raw_count_like":
        working = dataset.copy()
        _validate_expression_values(working)
        sc.pp.normalize_total(working, target_sum=10_000)
        sc.pp.log1p(working)
        return working, "normalized_raw_counts_to_10000_then_log1p"

    if state == "processed_continuous":
        has_log1p = bool(inspection.get("log1p_metadata_present"))
        negative_fraction = float(inspection.get("sampled_negative_fraction", 0.0))
        if not has_log1p or negative_fraction != 0.0:
            raise ValueError(
                "Processed expression is accepted only with explicit AnnData log1p "
                "metadata and nonnegative expression evidence."
            )
        working = dataset.copy()
        _validate_expression_values(working)
        return working, "used_existing_nonnegative_log1p_expression"

    raise ValueError(
        "GPTCellType requires a high-confidence raw-count-like matrix or explicit "
        "nonnegative log1p expression; inspection classified this matrix as "
        f"'{state}'."
    )


def _prepare_gene_symbols(dataset: ad.AnnData) -> tuple[ad.AnnData, dict[str, Any]]:
    """Use a complete symbol column when var names are not already gene symbols."""
    working = dataset
    original_names = pd.Index(working.var_names.astype(str))
    candidates: list[tuple[str, pd.Index]] = [("var_names", original_names)]
    for column in GENE_SYMBOL_COLUMNS:
        if column not in working.var:
            continue
        candidate = working.var[column].astype("string").fillna("").astype(str).str.strip()
        valid = ~candidate.str.casefold().isin({"", "nan", "none", "na"})
        if bool(valid.all()):
            candidates.append((f"var['{column}']", pd.Index(candidate)))

    selection: tuple[str, pd.Index, float, float, float] | None = None
    for source, symbols in candidates:
        if len(symbols) != working.n_vars or not symbols.is_unique:
            continue
        ensembl_fraction = float(np.mean([bool(ENSEMBL_GENE_RE.match(value)) for value in symbols]))
        numeric_fraction = float(np.mean([value.isdigit() for value in symbols]))
        symbol_like_fraction = float(
            np.mean(
                [
                    bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", value))
                    and not ENSEMBL_GENE_RE.match(value)
                    and not value.isdigit()
                    for value in symbols
                ]
            )
        )
        if ensembl_fraction < 0.5 and numeric_fraction < 0.5 and symbol_like_fraction >= 0.8:
            selection = (
                source,
                symbols,
                ensembl_fraction,
                numeric_fraction,
                symbol_like_fraction,
            )
            break

    if selection is None:
        raise ValueError(
            "GPTCellType requires gene-symbol-like marker identifiers. Query features are "
            "predominantly Ensembl, numeric, duplicated, or otherwise unsuitable and no complete "
            "unique symbol column was available."
        )
    source, symbols, ensembl_fraction, numeric_fraction, symbol_like_fraction = selection

    if source != "var_names":
        working = working.copy()
        working.var["gptcelltype_original_gene_identifier"] = original_names
        working.var_names = symbols
    return working, {
        "source": source,
        "n_features": int(working.n_vars),
        "n_identifiers_changed": int(np.count_nonzero(original_names != symbols)),
        "ensembl_like_fraction": ensembl_fraction,
        "numeric_like_fraction": numeric_fraction,
        "gene_symbol_like_fraction": symbol_like_fraction,
    }


def _nonzero_observation_mask(dataset: ad.AnnData) -> np.ndarray:
    """Return observations with at least one nonzero transcriptomic feature."""
    if sparse.issparse(dataset.X):
        detected = np.asarray((dataset.X != 0).sum(axis=1)).ravel()
    else:
        detected = np.count_nonzero(np.asarray(dataset.X), axis=1)
    return detected > 0


def _canonical_cluster_ids(series: pd.Series) -> tuple[np.ndarray, np.ndarray]:
    """Convert nonmissing cluster values to unambiguous string identifiers."""
    missing = series.isna().to_numpy()
    cluster_ids = np.empty(len(series), dtype=object)
    cluster_ids[:] = None
    identities_by_id: dict[str, tuple[str, str]] = {}

    for position, value in enumerate(series.to_numpy(dtype=object)):
        if missing[position]:
            continue
        cluster_id = str(value).strip()
        if not cluster_id:
            missing[position] = True
            continue
        identity = (type(value).__qualname__, repr(value))
        previous_identity = identities_by_id.setdefault(cluster_id, identity)
        if previous_identity != identity:
            raise ValueError(
                "cluster_column contains distinct values that collapse to the same "
                f"string cluster ID '{cluster_id}'."
            )
        cluster_ids[position] = cluster_id

    return cluster_ids, missing


def _cluster_transcriptomic_working_copy(
    working: ad.AnnData,
    *,
    resolution: float,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """Create deterministic Leiden clusters without using spatial coordinates."""
    transcriptomic_mask = _nonzero_observation_mask(working)
    n_transcriptomic = int(np.count_nonzero(transcriptomic_mask))
    if n_transcriptomic < 3:
        raise ValueError(
            "At least three observations with nonzero expression are required to create "
            "Leiden clusters. Supply a valid cluster_column for smaller datasets."
        )

    clustering = working[transcriptomic_mask, :].copy()
    sc.pp.filter_genes(clustering, min_cells=EXECUTION_GENE_FILTER_MIN_CELLS)
    if clustering.n_vars < 3:
        raise ValueError(
            "At least three detected genes are required to create transcriptomic clusters."
        )

    n_top_genes = min(EXECUTION_MAX_VARIABLE_FEATURES, clustering.n_vars)
    if n_top_genes < clustering.n_vars:
        sc.pp.highly_variable_genes(
            clustering,
            n_top_genes=n_top_genes,
            flavor="seurat",
            inplace=True,
        )
        if int(clustering.var["highly_variable"].sum()) < 3:
            raise ValueError("Highly-variable-gene selection retained fewer than three genes.")
        clustering = clustering[:, clustering.var["highly_variable"]].copy()

    n_pcs = min(EXECUTION_MAX_PCS, clustering.n_obs - 1, clustering.n_vars - 1)
    if n_pcs < 2:
        raise ValueError("At least two principal components are required for Leiden clustering.")
    n_neighbors = min(EXECUTION_N_NEIGHBORS, clustering.n_obs - 1)
    sc.pp.pca(
        clustering,
        n_comps=n_pcs,
        random_state=RANDOM_STATE,
        svd_solver=PCA_SVD_SOLVER,
    )
    sc.pp.neighbors(
        clustering,
        n_neighbors=n_neighbors,
        n_pcs=n_pcs,
        random_state=RANDOM_STATE,
    )
    sc.tl.leiden(
        clustering,
        resolution=float(resolution),
        random_state=RANDOM_STATE,
        key_added=CLUSTER_KEY,
        flavor=LEIDEN_FLAVOR,
        n_iterations=LEIDEN_N_ITERATIONS,
        directed=LEIDEN_DIRECTED,
        use_weights=LEIDEN_USE_WEIGHTS,
    )

    generated = clustering.obs[CLUSTER_KEY].astype(str).to_numpy(dtype=object)
    cluster_ids = np.empty(working.n_obs, dtype=object)
    cluster_ids[:] = None
    cluster_ids[transcriptomic_mask] = generated
    missing = ~transcriptomic_mask
    unique_clusters = sorted(set(generated))
    if len(unique_clusters) < 2:
        raise ValueError(
            "Leiden clustering produced only one cluster, so one-vs-rest marker ranking "
            "is undefined. Increase resolution or supply a cluster_column."
        )

    details = {
        "source": "generated_leiden",
        "cluster_column": None,
        "resolution": float(resolution),
        "random_state": RANDOM_STATE,
        "n_neighbors": int(n_neighbors),
        "n_pcs": int(n_pcs),
        "pca_svd_solver": PCA_SVD_SOLVER,
        "leiden_flavor": LEIDEN_FLAVOR,
        "leiden_n_iterations": LEIDEN_N_ITERATIONS,
        "leiden_directed": LEIDEN_DIRECTED,
        "leiden_use_weights": LEIDEN_USE_WEIGHTS,
        "n_transcriptomic_observations": n_transcriptomic,
        "n_zero_expression_observations": int(np.count_nonzero(missing)),
        "execution_clustering_profile": gptcelltype_execution_clustering_profile(
            cluster_column=None,
            resolution=resolution,
        ),
    }
    return cluster_ids, missing, details


def _resolve_clusters(
    original: ad.AnnData,
    working: ad.AnnData,
    *,
    cluster_column: str | None,
    resolution: float,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """Use an explicit cluster column or generate transcriptomic Leiden clusters."""
    if cluster_column is None:
        return _cluster_transcriptomic_working_copy(working, resolution=resolution)

    if cluster_column not in original.obs.columns:
        raise KeyError(f"cluster_column '{cluster_column}' was not found in query .obs.")
    cluster_ids, missing = _canonical_cluster_ids(original.obs[cluster_column])
    nonzero_expression = _nonzero_observation_mask(working)
    missing = missing | ~nonzero_expression
    assigned_clusters = sorted(
        {
            str(cluster_ids[position])
            for position in np.flatnonzero(~missing)
            if cluster_ids[position] is not None
        }
    )
    if len(assigned_clusters) < 2:
        raise ValueError(
            "cluster_column must contain at least two nonmissing clusters with nonzero "
            "expression for one-vs-rest marker ranking."
        )
    details = {
        "source": "query_obs",
        "cluster_column": cluster_column,
        "resolution": None,
        "random_state": None,
        "n_neighbors": None,
        "n_pcs": None,
        "n_transcriptomic_observations": int(np.count_nonzero(~missing)),
        "n_zero_expression_observations": int(np.count_nonzero(~nonzero_expression)),
        "execution_clustering_profile": gptcelltype_execution_clustering_profile(
            cluster_column=cluster_column,
            resolution=resolution,
        ),
    }
    return cluster_ids, missing, details


def _positive_marker_genes(
    working: ad.AnnData,
    cluster_ids: np.ndarray,
    missing_cluster_mask: np.ndarray,
    *,
    top_marker_genes: int,
) -> tuple[dict[str, list[str]], list[dict[str, Any]]]:
    """Compute one-vs-rest Wilcoxon positive markers across all expression genes."""
    assigned_mask = ~missing_cluster_mask
    marker_data = working[assigned_mask, :].copy()
    marker_clusters = np.asarray(cluster_ids[assigned_mask], dtype=str)
    ordered_clusters = sorted(set(marker_clusters))
    marker_data.obs[CLUSTER_KEY] = pd.Categorical(
        marker_clusters,
        categories=ordered_clusters,
    )
    n_ranked_gene_candidates = min(
        marker_data.n_vars,
        max(1_000, top_marker_genes * 100),
    )
    sc.tl.rank_genes_groups(
        marker_data,
        groupby=CLUSTER_KEY,
        groups=ordered_clusters,
        reference="rest",
        method="wilcoxon",
        n_genes=n_ranked_gene_candidates,
        use_raw=False,
        rankby_abs=False,
        tie_correct=False,
    )

    markers_by_cluster: dict[str, list[str]] = {}
    cluster_records: list[dict[str, Any]] = []
    for cluster_id in ordered_clusters:
        results = sc.get.rank_genes_groups_df(marker_data, group=cluster_id)
        positive = results.loc[
            np.isfinite(results["scores"].to_numpy(dtype=float))
            & np.isfinite(results["logfoldchanges"].to_numpy(dtype=float))
            & (results["scores"].to_numpy(dtype=float) > 0)
            & (results["logfoldchanges"].to_numpy(dtype=float) > 0)
        ]
        marker_names: list[str] = []
        seen: set[str] = set()
        for value in positive["names"]:
            gene = str(value).strip()
            if not gene or gene.casefold() == "nan" or gene in seen:
                continue
            seen.add(gene)
            marker_names.append(gene)
            if len(marker_names) == top_marker_genes:
                break

        markers_by_cluster[cluster_id] = marker_names
        cluster_records.append(
            {
                "cluster_id": cluster_id,
                "n_observations": int(np.count_nonzero(marker_clusters == cluster_id)),
                "marker_genes": marker_names,
                "n_marker_genes": len(marker_names),
                "n_ranked_gene_candidates": int(n_ranked_gene_candidates),
                "eligible_for_annotation": bool(marker_names),
                "exclusion_reason": None if marker_names else "no_positive_markers",
            }
        )

    return markers_by_cluster, cluster_records


def _batched(values: list[str], size: int) -> Iterable[list[str]]:
    """Yield deterministic bounded batches."""
    for start in range(0, len(values), size):
        yield values[start : start + size]


def _build_human_prompt(
    *,
    species: str,
    tissue: str,
    cluster_ids: list[str],
    markers_by_cluster: dict[str, list[str]],
) -> str:
    """Build a provider payload containing only allowed biological context."""
    payload = {
        "species": species,
        "tissue": tissue,
        "clusters": [
            {
                "cluster_id": cluster_id,
                "marker_genes": markers_by_cluster[cluster_id],
            }
            for cluster_id in cluster_ids
        ],
    }
    return (
        "Assign one cell-type name to every cluster in this JSON payload. Return a JSON "
        "object keyed by cluster_id.\n"
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    )


def _message_content_to_text(content: Any) -> str:
    """Normalize provider message content without changing its textual response."""
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
    """Remove one optional JSON markdown fence while retaining the raw audit text."""
    stripped = response_text.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.DOTALL)
    return fenced.group(1).strip() if fenced else stripped


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Build a JSON object while rejecting duplicate keys."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Model response contains duplicate JSON key '{key}'.")
        result[key] = value
    return result


def _parse_batch_response(response_text: str, expected_cluster_ids: list[str]) -> dict[str, str]:
    """Parse a strict JSON mapping whose keys exactly match the requested clusters."""
    if not response_text.strip():
        raise ValueError("Model response was empty.")
    try:
        payload = json.loads(
            _strip_json_fence(response_text),
            object_pairs_hook=_reject_duplicate_json_keys,
        )
    except json.JSONDecodeError as exc:
        raise ValueError(f"Model response was not valid JSON: {exc.msg}.") from exc
    if not isinstance(payload, dict):
        raise ValueError("Model response must be one JSON object.")

    expected = set(expected_cluster_ids)
    actual = set(payload)
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing or extra:
        raise ValueError(
            f"Model response cluster keys did not match exactly; missing={missing}, extra={extra}."
        )

    labels: dict[str, str] = {}
    for cluster_id in expected_cluster_ids:
        value = payload[cluster_id]
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"Model response label for cluster '{cluster_id}' must be a non-empty string."
            )
        label = value.strip()
        if "\n" in label or "\r" in label:
            raise ValueError(f"Model response label for cluster '{cluster_id}' must be one line.")
        if len(label) > 200:
            raise ValueError(
                f"Model response label for cluster '{cluster_id}' exceeds 200 characters."
            )
        labels[cluster_id] = label
    return labels


def _annotate_batches(
    model: Any,
    *,
    species: str,
    tissue: str,
    markers_by_cluster: dict[str, list[str]],
    api_batch_size: int,
    max_api_attempts_per_batch: int,
) -> tuple[
    dict[str, str],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    """Invoke the configured worker model in bounded, fully audited batches."""
    eligible_clusters = sorted(
        cluster_id for cluster_id, markers in markers_by_cluster.items() if markers
    )
    labels_by_cluster: dict[str, str] = {}
    prompt_records: list[dict[str, Any]] = []
    response_records: list[dict[str, Any]] = []
    system_message = SystemMessage(SYSTEM_PROMPT)

    for batch_index, cluster_ids in enumerate(
        _batched(eligible_clusters, api_batch_size),
        start=1,
    ):
        human_prompt = _build_human_prompt(
            species=species,
            tissue=tissue,
            cluster_ids=cluster_ids,
            markers_by_cluster=markers_by_cluster,
        )
        prompt_records.append(
            {
                "batch_index": batch_index,
                "cluster_ids": cluster_ids,
                "system_prompt": SYSTEM_PROMPT,
                "human_prompt": human_prompt,
            }
        )
        attempts: list[dict[str, Any]] = []
        parsed_labels: dict[str, str] | None = None

        for attempt_number in range(1, max_api_attempts_per_batch + 1):
            try:
                response = model.invoke([system_message, HumanMessage(human_prompt)])
            except Exception as exc:
                attempts.append(
                    {
                        "attempt": attempt_number,
                        "raw_response": "",
                        "parse_error": None,
                        "invocation_error": f"{type(exc).__name__}: {exc}",
                    }
                )
                continue

            raw_response = _message_content_to_text(response.content)
            try:
                parsed_labels = _parse_batch_response(raw_response, cluster_ids)
            except Exception as exc:
                attempts.append(
                    {
                        "attempt": attempt_number,
                        "raw_response": raw_response,
                        "parse_error": f"{type(exc).__name__}: {exc}",
                        "invocation_error": None,
                    }
                )
                continue

            attempts.append(
                {
                    "attempt": attempt_number,
                    "raw_response": raw_response,
                    "parse_error": None,
                    "invocation_error": None,
                }
            )
            break

        successful_attempt = len(attempts) if parsed_labels is not None else None
        response_records.append(
            {
                "batch_index": batch_index,
                "cluster_ids": cluster_ids,
                "attempt_count": len(attempts),
                "retry_count": max(0, len(attempts) - 1),
                "successful_attempt": successful_attempt,
                "attempts": attempts,
            }
        )
        if parsed_labels is None:
            raise BatchAnnotationError(
                batch_index,
                len(attempts),
                prompt_records=prompt_records,
                response_records=response_records,
            )
        labels_by_cluster.update(parsed_labels)

    return labels_by_cluster, prompt_records, response_records


def _attach_annotations(
    output: ad.AnnData,
    *,
    cluster_ids: np.ndarray,
    missing_cluster_mask: np.ndarray,
    zero_expression_mask: np.ndarray,
    clustering_source: str,
    markers_by_cluster: dict[str, list[str]],
    labels_by_cluster: dict[str, str],
) -> dict[str, Any]:
    """Attach cluster labels and explicit exclusions without changing observation order."""
    prediction_values = np.empty(output.n_obs, dtype=object)
    prediction_values[:] = None
    status_values = np.full(output.n_obs, "excluded_from_annotation", dtype=object)
    reason_values = np.empty(output.n_obs, dtype=object)

    missing_reason = (
        "zero_expression"
        if clustering_source == "generated_leiden"
        else "missing_cluster_assignment"
    )
    reason_values[missing_cluster_mask] = missing_reason
    reason_values[zero_expression_mask] = "zero_expression"

    for position, cluster_id in enumerate(cluster_ids):
        if missing_cluster_mask[position]:
            continue
        normalized_cluster_id = str(cluster_id)
        if not markers_by_cluster[normalized_cluster_id]:
            reason_values[position] = "no_positive_markers"
            continue
        prediction_values[position] = labels_by_cluster[normalized_cluster_id]
        status_values[position] = "annotated"
        reason_values[position] = "not_excluded"

    label_categories = sorted({str(value) for value in prediction_values if value is not None})
    cluster_categories = sorted({str(value) for value in cluster_ids if value is not None})
    output.obs["gptcelltype_cluster"] = pd.Categorical(
        cluster_ids,
        categories=cluster_categories,
    )
    predicted = pd.Series(
        pd.Categorical(prediction_values, categories=label_categories),
        index=output.obs_names,
    )
    statuses = pd.Categorical(
        status_values,
        categories=["annotated", "excluded_from_annotation"],
    )
    reasons = pd.Categorical(reason_values)

    output.obs["gptcelltype_predicted_cell_type"] = predicted
    output.obs["gptcelltype_status"] = statuses
    output.obs["gptcelltype_exclusion_reason"] = reasons
    output.obs["cell_annotation_predicted_cell_type"] = predicted.copy()
    output.obs["cell_annotation_prediction_confidence"] = np.full(output.n_obs, np.nan)
    output.obs["cell_annotation_status"] = statuses
    output.obs["cell_annotation_exclusion_reason"] = reasons
    output.obs["cell_annotation_method"] = pd.Categorical([ANNOTATION_METHOD] * output.n_obs)
    output.obs["label"] = predicted.copy()

    annotated_mask = status_values == "annotated"
    label_counts = (
        pd.Series(prediction_values[annotated_mask], dtype="object").value_counts().sort_index()
    )
    reason_counts = pd.Series(reason_values, dtype="object").value_counts().sort_index()
    return {
        "n_cells_annotated": int(np.count_nonzero(annotated_mask)),
        "n_cells_excluded": int(np.count_nonzero(~annotated_mask)),
        "n_unique_cell_types": int(len(label_counts)),
        "cell_type_counts": {str(key): int(value) for key, value in label_counts.items()},
        "exclusion_reason_counts": {str(key): int(value) for key, value in reason_counts.items()},
    }


def _output_columns_are_available(dataset: ad.AnnData) -> None:
    """Prevent silent replacement of prior annotation columns or provenance."""
    collisions = sorted(set(OUTPUT_COLUMNS).intersection(dataset.obs.columns))
    if collisions:
        raise ValueError(
            "Query .obs already contains GPTCellType output-contract columns: "
            + ", ".join(collisions)
        )
    if "tissueagent_cell_annotation" in dataset.uns:
        raise ValueError(
            "Query .uns already contains 'tissueagent_cell_annotation'; refusing to "
            "replace prior annotation provenance."
        )


def _artifact_references(paths: dict[str, Path]) -> dict[str, str]:
    """Return agent-visible workspace-relative artifact paths."""
    return {name: workspace_relative(path) for name, path in paths.items()}


def _write_success_bundle(
    output: ad.AnnData,
    *,
    paths: dict[str, Path],
    markers_payload: dict[str, Any],
    prompts_payload: dict[str, Any],
    responses_payload: dict[str, Any],
    run_metadata: dict[str, Any],
) -> None:
    """Publish all success artifacts and remove this run's files on partial failure."""
    created: list[Path] = []
    try:
        _write_json_exclusively(markers_payload, paths["markers_json"])
        created.append(paths["markers_json"])
        _write_json_exclusively(prompts_payload, paths["prompts_json"])
        created.append(paths["prompts_json"])
        _write_json_exclusively(responses_payload, paths["responses_json"])
        created.append(paths["responses_json"])
        _write_h5ad_exclusively(output, paths["annotated_object_h5ad"])
        created.append(paths["annotated_object_h5ad"])
        _write_json_exclusively(run_metadata, paths["run_meta_json"])
        created.append(paths["run_meta_json"])
    except Exception:
        for created_path in reversed(created):
            created_path.unlink(missing_ok=True)
        raise


def _error_result(stage: str, exc: Exception, **details: Any) -> dict[str, Any]:
    """Return a structured user-visible failure without hiding its cause."""
    result: dict[str, Any] = {
        "status": "error",
        "operation": "gptcelltype_annotation",
        "annotation_method": ANNOTATION_METHOD,
        "label_source": LABEL_SOURCE,
        "stage": stage,
        "error_type": type(exc).__name__,
        "message": f"GPTCellType annotation failed during {stage}: {exc}",
    }
    if isinstance(exc, BatchAnnotationError):
        result["failed_batch_index"] = exc.batch_index
        result["failed_batch_attempts"] = exc.attempts
    result.update(details)
    return result


def gptcelltype_annotation_tool(
    spatial_anndata_path: str,
    output_path: str,
    species: str,
    tissue: str,
    selection_rationale: str,
    cluster_column: str | None = None,
    resolution: float = 1.0,
    top_marker_genes: int = 10,
    api_batch_size: int = 25,
    max_api_attempts_per_batch: int = 3,
    api_timeout_seconds: int = 120,
    execution_contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Annotate spatial clusters with the published GPTCellType marker-list strategy."""
    stage = "validate_parameters"
    inspection: dict[str, Any] | None = None
    preprocessing_decision: str | None = None
    gene_identifier_decision: dict[str, Any] | None = None
    clustering: dict[str, Any] | None = None
    readiness_execution_binding: dict[str, Any] | None = None
    markers_by_cluster: dict[str, list[str]] | None = None
    cluster_records: list[dict[str, Any]] | None = None
    response_records: list[dict[str, Any]] = []
    try:
        (
            clean_species,
            clean_tissue,
            clean_rationale,
            clean_cluster_column,
        ) = _validate_parameters(
            species=species,
            tissue=tissue,
            selection_rationale=selection_rationale,
            cluster_column=cluster_column,
            resolution=resolution,
            top_marker_genes=top_marker_genes,
            api_batch_size=api_batch_size,
            max_api_attempts_per_batch=max_api_attempts_per_batch,
            api_timeout_seconds=api_timeout_seconds,
        )
        readiness_execution_binding = gptcelltype_readiness_execution_binding(
            cluster_column=clean_cluster_column,
            resolution=float(resolution),
            top_marker_genes=top_marker_genes,
        )

        stage = "resolve_paths"
        spatial_path = resolve_workspace_input(spatial_anndata_path)
        annotated_output_path = resolve_project_output(output_path, suffix=".h5ad")
        paths = _artifact_paths(annotated_output_path)
        annotated_output_path.parent.mkdir(parents=True, exist_ok=True)
        _ensure_outputs_available(paths)
        artifact_references = _artifact_references(paths)

        stage = "inspect_expression"
        inspection = _inspect_expression_matrix(spatial_path, role="spatial")

        stage = "load_query"
        original = ad.read_h5ad(spatial_path)
        if original.n_obs == 0 or original.n_vars == 0:
            raise ValueError(f"Query AnnData is empty: shape={original.shape}.")
        if not original.obs_names.is_unique:
            raise ValueError("Query observation identifiers must be unique.")
        if not original.var_names.is_unique:
            raise ValueError("Query gene identifiers must be unique.")
        original_obs_names = np.asarray(original.obs_names, dtype=object).copy()
        _output_columns_are_available(original)

        stage = "prepare_expression"
        working, preprocessing_decision = _prepare_expression(original, inspection)

        stage = "prepare_gene_symbols"
        working, gene_identifier_decision = _prepare_gene_symbols(working)

        stage = "resolve_clusters"
        cluster_ids, missing_cluster_mask, clustering = _resolve_clusters(
            original,
            working,
            cluster_column=clean_cluster_column,
            resolution=float(resolution),
        )

        stage = "rank_positive_markers"
        markers_by_cluster, cluster_records = _positive_marker_genes(
            working,
            cluster_ids,
            missing_cluster_mask,
            top_marker_genes=top_marker_genes,
        )
        eligible_clusters = sorted(
            cluster_id for cluster_id, markers in markers_by_cluster.items() if markers
        )
        if not eligible_clusters:
            raise ValueError(
                "No cluster had a positive Wilcoxon marker gene, so GPTCellType "
                "annotation cannot be requested."
            )

        stage = "initialize_worker_model"
        worker_model_id = get_model_id("worker")
        worker_model_seed = get_model_seed()
        worker_model_spec = get_model_spec(worker_model_id)
        model = model_ctor_for_role(
            "worker",
            timeout=api_timeout_seconds,
            max_retries=0,
        )()
        if get_model_id("worker") != worker_model_id:
            raise RuntimeError(
                "The configured worker model changed while GPTCellType was initializing; "
                "rerun to preserve an unambiguous audit record."
            )

        stage = "annotate_marker_batches"
        labels_by_cluster, prompt_records, response_records = _annotate_batches(
            model,
            species=clean_species,
            tissue=clean_tissue,
            markers_by_cluster=markers_by_cluster,
            api_batch_size=api_batch_size,
            max_api_attempts_per_batch=max_api_attempts_per_batch,
        )

        stage = "attach_predictions"
        output = original.copy()
        summary = _attach_annotations(
            output,
            cluster_ids=cluster_ids,
            missing_cluster_mask=missing_cluster_mask,
            zero_expression_mask=~_nonzero_observation_mask(working),
            clustering_source=clustering["source"],
            markers_by_cluster=markers_by_cluster,
            labels_by_cluster=labels_by_cluster,
        )
        if output.n_obs != original.n_obs or not np.array_equal(
            np.asarray(output.obs_names, dtype=object),
            original_obs_names,
        ):
            raise RuntimeError(
                "Internal observation-integrity check failed before writing the output."
            )

        warning_messages = [
            "GPTCellType assigns one free-text label per cluster, not independently per cell.",
            "GPTCellType does not provide calibrated prediction confidence; confidence is NaN.",
        ]
        clusters_with_short_marker_lists = [
            record["cluster_id"]
            for record in cluster_records
            if 0 < record["n_marker_genes"] < top_marker_genes
        ]
        clusters_without_markers = [
            record["cluster_id"]
            for record in cluster_records
            if not record["eligible_for_annotation"]
        ]
        if clusters_with_short_marker_lists:
            warning_messages.append(
                "Some clusters had fewer positive markers than requested: "
                + ", ".join(clusters_with_short_marker_lists)
            )
        if clusters_without_markers:
            warning_messages.append(
                "Clusters without positive markers were explicitly excluded: "
                + ", ".join(clusters_without_markers)
            )
        if clustering["source"] == "generated_leiden":
            warning_messages.append(
                "Clusters were generated deterministically from transcriptomic expression "
                "without spatial coordinates."
            )

        total_api_attempts = sum(int(record["attempt_count"]) for record in response_records)
        total_retries = sum(int(record["retry_count"]) for record in response_records)
        timestamp = _utc_timestamp()
        output.uns["tissueagent_cell_annotation"] = {
            "annotation_method": ANNOTATION_METHOD,
            "label_source": LABEL_SOURCE,
            "selection_rationale": clean_rationale,
            "species": clean_species,
            "tissue": clean_tissue,
            "cluster_source": clustering["source"],
            "cluster_column": clean_cluster_column or "",
            "top_marker_genes": int(top_marker_genes),
            "gene_identifier_source": gene_identifier_decision["source"],
            "readiness_execution_binding_status": readiness_execution_binding["status"],
            "readiness_profile_id": readiness_execution_binding["readiness_profile_id"],
            "execution_clustering_profile_id": readiness_execution_binding[
                "execution_clustering_profile_id"
            ],
            "selection_contract_id": (
                execution_contract.get("selection_contract_id", "")
                if execution_contract is not None
                else ""
            ),
            "parameter_policy_version": (
                execution_contract.get("parameter_policy_version", "")
                if execution_contract is not None
                else ""
            ),
            "configuration_sha256": (
                execution_contract.get("configuration_sha256", "")
                if execution_contract is not None
                else ""
            ),
            "execution_contract_json": (
                json.dumps(execution_contract, sort_keys=True, separators=(",", ":"))
                if execution_contract is not None
                else ""
            ),
            "worker_model_id": worker_model_id,
            "worker_model_provider": worker_model_spec.provider,
            "worker_model_seed": worker_model_seed,
            "confidence_available": False,
            "markers_json": artifact_references["markers_json"],
            "prompts_json": artifact_references["prompts_json"],
            "responses_json": artifact_references["responses_json"],
            "run_meta_json": artifact_references["run_meta_json"],
        }

        markers_payload = {
            "status": "success",
            "annotation_method": ANNOTATION_METHOD,
            "marker_test": {
                "method": "wilcoxon",
                "comparison": "one_vs_rest",
                "positive_markers_only": True,
                "gene_space": "all_query_expression_genes",
                "requested_top_marker_genes": int(top_marker_genes),
                "maximum_allowed_marker_genes": MAX_TOP_MARKER_GENES,
            },
            "clustering": clustering,
            "clusters": cluster_records,
        }
        prompts_payload = {
            "status": "success",
            "annotation_method": ANNOTATION_METHOD,
            "worker_model": {
                "id": worker_model_id,
                "provider": worker_model_spec.provider,
                "api_model": worker_model_spec.api_model,
            },
            "batches": prompt_records,
        }
        responses_payload = {
            "status": "success",
            "annotation_method": ANNOTATION_METHOD,
            "worker_model": {
                "id": worker_model_id,
                "provider": worker_model_spec.provider,
                "api_model": worker_model_spec.api_model,
            },
            "total_api_attempts": total_api_attempts,
            "total_retry_count": total_retries,
            "retry_counts_by_batch": {
                str(record["batch_index"]): int(record["retry_count"])
                for record in response_records
            },
            "batches": response_records,
        }
        run_metadata = {
            "status": "success",
            "annotation_method": ANNOTATION_METHOD,
            "label_source": LABEL_SOURCE,
            "selection_rationale": clean_rationale,
            "execution_contract": execution_contract,
            "runtime": {
                "timestamp_utc": timestamp,
                "worker_model_id": worker_model_id,
                "worker_model_provider": worker_model_spec.provider,
                "worker_api_model": worker_model_spec.api_model,
                "worker_model_seed": worker_model_seed,
                "api_timeout_seconds": int(api_timeout_seconds),
                "api_max_retries_in_model_client": 0,
                "total_api_attempts": total_api_attempts,
                "total_retry_count": total_retries,
            },
            "parameters": {
                "species": clean_species,
                "tissue": clean_tissue,
                "cluster_column": clean_cluster_column,
                "resolution": float(resolution),
                "top_marker_genes": int(top_marker_genes),
                "api_batch_size": int(api_batch_size),
                "max_api_attempts_per_batch": int(max_api_attempts_per_batch),
            },
            "expression": {
                "inspection": inspection,
                "preprocessing_decision": preprocessing_decision,
                "gene_identifiers": gene_identifier_decision,
            },
            "clustering": clustering,
            "readiness_execution_binding": readiness_execution_binding,
            "inputs": {
                "spatial_anndata_path": workspace_relative(spatial_path),
            },
            "outputs": artifact_references,
            "summary": {
                "n_input_cells": int(original.n_obs),
                "n_output_cells": int(output.n_obs),
                "n_clusters": int(len(markers_by_cluster)),
                "n_clusters_annotated": int(len(eligible_clusters)),
                **summary,
                "confidence_available": False,
                "warnings": warning_messages,
            },
        }

        stage = "write_outputs"
        _write_success_bundle(
            output,
            paths=paths,
            markers_payload=markers_payload,
            prompts_payload=prompts_payload,
            responses_payload=responses_payload,
            run_metadata=run_metadata,
        )

        return {
            "status": "success",
            "operation": "gptcelltype_annotation",
            "annotation_method": ANNOTATION_METHOD,
            "label_source": LABEL_SOURCE,
            "selection_rationale": clean_rationale,
            "execution_contract": execution_contract,
            **artifact_references,
            "n_input_cells": int(original.n_obs),
            "n_output_cells": int(output.n_obs),
            "n_clusters": int(len(markers_by_cluster)),
            "n_clusters_annotated": int(len(eligible_clusters)),
            **summary,
            "confidence_available": False,
            "worker_model_id": worker_model_id,
            "worker_model_provider": worker_model_spec.provider,
            "worker_model_seed": worker_model_seed,
            "readiness_execution_binding_status": readiness_execution_binding["status"],
            "readiness_profile_id": readiness_execution_binding["readiness_profile_id"],
            "execution_clustering_profile_id": readiness_execution_binding[
                "execution_clustering_profile_id"
            ],
            "total_api_attempts": total_api_attempts,
            "total_retry_count": total_retries,
            "warnings": warning_messages,
        }
    except Exception as exc:
        error_details: dict[str, Any] = {}
        if inspection is not None:
            error_details["expression_inspection"] = inspection
        if preprocessing_decision is not None:
            error_details["preprocessing_decision"] = preprocessing_decision
        if gene_identifier_decision is not None:
            error_details["gene_identifier_decision"] = gene_identifier_decision
        if clustering is not None:
            error_details["clustering"] = clustering
        if readiness_execution_binding is not None:
            error_details["readiness_execution_binding"] = readiness_execution_binding
        if markers_by_cluster is not None:
            error_details["markers_by_cluster"] = markers_by_cluster
        if cluster_records is not None:
            error_details["cluster_records"] = cluster_records
        if isinstance(exc, BatchAnnotationError):
            response_records = exc.response_records
            error_details["prompt_records"] = exc.prompt_records
            error_details["response_records"] = exc.response_records
        if response_records:
            error_details["api_attempts_completed"] = sum(
                int(record["attempt_count"]) for record in response_records
            )
            error_details["batch_retry_counts"] = {
                str(record["batch_index"]): int(record["retry_count"])
                for record in response_records
            }
        return _error_result(stage, exc, **error_details)
