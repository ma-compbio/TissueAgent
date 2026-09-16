"""Bounded query-only evidence for GPTCellType cluster and marker readiness."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import hashlib
import json
import math
import re

import anndata as ad
import h5py
import numpy as np
import pandas as pd
import scanpy as sc
from scipy import sparse
from scipy.stats import mannwhitneyu
from sklearn.metrics import adjusted_mutual_info_score

from agents.agent_registry.cell_annotater_agent.tools_impl.harmony_transfer import (
    ENSEMBL_GENE_RE,
    GENE_SYMBOL_COLUMNS,
)


RANDOM_STATE = 42
MAX_SAMPLED_CELLS = 2048
MAX_CANDIDATE_FEATURES = 4096
MAX_VARIABLE_FEATURES = 2000
FEATURE_BLOCK_COUNT = 16
MIN_NONZERO_CELLS = 40
MIN_VARIABLE_FEATURES = 20
MIN_CLUSTER_SIDE = 20
LEIDEN_RESOLUTION = 1.0
N_NEIGHBORS = 15
MAX_PCS = 30
N_PERMUTATIONS = 100
N_AMI_BOOTSTRAPS = 200
MARKER_Q_THRESHOLD = 0.05
MARKER_AUROC_THRESHOLD = 0.70
MIN_QUALIFIED_MARKERS = 3
STRONG_COHERENCE_EFFECT = 0.50
MODERATE_COHERENCE_EFFECT = 0.25
STRONG_AMI_LOWER_BOUND = 0.50
STRONG_MARKER_COVERAGE = 0.80
MODERATE_MARKER_COVERAGE = 0.50
PCA_SVD_SOLVER = "arpack"
LEIDEN_FLAVOR = "leidenalg"
LEIDEN_N_ITERATIONS = -1
LEIDEN_DIRECTED = True
LEIDEN_USE_WEIGHTS = True
EXECUTION_MAX_VARIABLE_FEATURES = 2000
EXECUTION_MAX_PCS = 50
EXECUTION_N_NEIGHBORS = 15
EXECUTION_GENE_FILTER_MIN_CELLS = 1
EXECUTION_TOP_MARKER_GENES = 10
GPTCELLTYPE_READINESS_PROFILE_VERSION = "gptcelltype_readiness_profile_v1"
GPTCELLTYPE_EXECUTION_CLUSTERING_PROFILE_VERSION = "gptcelltype_execution_clustering_profile_v1"
GPTCELLTYPE_READINESS_EXECUTION_BINDING_VERSION = "gptcelltype_readiness_execution_binding_v1"


def _profile_id(payload: dict[str, Any]) -> str:
    """Return a stable identifier for one JSON-safe profile."""
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _identified_profile(payload: dict[str, Any]) -> dict[str, Any]:
    """Attach a stable identifier without hashing the identifier itself."""
    return {**payload, "profile_id": _profile_id(payload)}


def gptcelltype_readiness_profile() -> dict[str, Any]:
    """Return the canonical bounded readiness configuration and supported execution args."""
    supported_execution_arguments = {
        "cluster_column": None,
        "resolution": LEIDEN_RESOLUTION,
        "top_marker_genes": EXECUTION_TOP_MARKER_GENES,
    }
    supported_execution_clustering_profile = gptcelltype_execution_clustering_profile(
        cluster_column=None,
        resolution=LEIDEN_RESOLUTION,
    )
    return _identified_profile(
        {
            "version": GPTCELLTYPE_READINESS_PROFILE_VERSION,
            "sampling": {
                "random_state": RANDOM_STATE,
                "maximum_cells": MAX_SAMPLED_CELLS,
                "maximum_candidate_features": MAX_CANDIDATE_FEATURES,
                "feature_block_count": FEATURE_BLOCK_COUNT,
                "method": "seeded_uniform_rows_and_spread_contiguous_feature_blocks",
            },
            "feature_selection": {
                "maximum_variable_features": MAX_VARIABLE_FEATURES,
                "minimum_variable_features": MIN_VARIABLE_FEATURES,
                "minimum_cells_detecting_feature": "max(3, ceil(n_sampled_cells * 0.01))",
                "split_method": "alternating_descending_variance_rank",
            },
            "clustering": {
                "source": "generated_leiden",
                "algorithm": "leiden",
                "resolution": LEIDEN_RESOLUTION,
                "maximum_neighbors": N_NEIGHBORS,
                "maximum_pcs": MAX_PCS,
                "pca_svd_solver": PCA_SVD_SOLVER,
                "random_state": RANDOM_STATE,
                "leiden_flavor": LEIDEN_FLAVOR,
                "leiden_n_iterations": LEIDEN_N_ITERATIONS,
                "leiden_directed": LEIDEN_DIRECTED,
                "leiden_use_weights": LEIDEN_USE_WEIGHTS,
            },
            "evidence": {
                "minimum_nonzero_cells": MIN_NONZERO_CELLS,
                "minimum_cluster_and_rest_size": MIN_CLUSTER_SIDE,
                "n_permutations": N_PERMUTATIONS,
                "n_ami_bootstraps": N_AMI_BOOTSTRAPS,
                "marker_q_threshold": MARKER_Q_THRESHOLD,
                "marker_auroc_threshold": MARKER_AUROC_THRESHOLD,
                "minimum_qualified_markers": MIN_QUALIFIED_MARKERS,
                "strong_coherence_effect": STRONG_COHERENCE_EFFECT,
                "moderate_coherence_effect": MODERATE_COHERENCE_EFFECT,
                "strong_ami_lower_bound": STRONG_AMI_LOWER_BOUND,
                "strong_marker_coverage": STRONG_MARKER_COVERAGE,
                "moderate_marker_coverage": MODERATE_MARKER_COVERAGE,
            },
            "supported_execution_arguments": supported_execution_arguments,
            "supported_execution_clustering_profile": (supported_execution_clustering_profile),
            "explicit_cluster_policy": {
                "status": "separate_readiness_profile_required",
                "reason": (
                    "The bounded readiness diagnostic does not access query observation metadata "
                    "and therefore cannot support a supplied cluster column."
                ),
            },
        }
    )


def gptcelltype_execution_clustering_profile(
    *,
    cluster_column: str | None,
    resolution: float,
) -> dict[str, Any]:
    """Characterize the exact generated or query-provided execution clustering source."""
    if isinstance(resolution, bool) or not isinstance(resolution, (int, float)):
        raise ValueError("resolution must be a finite positive number.")
    normalized_resolution = float(resolution)
    if not math.isfinite(normalized_resolution) or normalized_resolution <= 0:
        raise ValueError("resolution must be a finite positive number.")
    if cluster_column is not None and (
        not isinstance(cluster_column, str) or not cluster_column.strip()
    ):
        raise ValueError("cluster_column must be None or a non-empty string.")
    clean_cluster_column = cluster_column.strip() if cluster_column is not None else None

    if clean_cluster_column is None:
        payload = {
            "version": GPTCELLTYPE_EXECUTION_CLUSTERING_PROFILE_VERSION,
            "source": "generated_leiden",
            "cluster_column": None,
            "resolution": normalized_resolution,
            "generated_clustering": {
                "gene_filter_min_cells": EXECUTION_GENE_FILTER_MIN_CELLS,
                "maximum_variable_features": EXECUTION_MAX_VARIABLE_FEATURES,
                "variable_feature_flavor": "seurat",
                "maximum_neighbors": EXECUTION_N_NEIGHBORS,
                "maximum_pcs": EXECUTION_MAX_PCS,
                "pca_svd_solver": PCA_SVD_SOLVER,
                "random_state": RANDOM_STATE,
                "leiden_flavor": LEIDEN_FLAVOR,
                "leiden_n_iterations": LEIDEN_N_ITERATIONS,
                "leiden_directed": LEIDEN_DIRECTED,
                "leiden_use_weights": LEIDEN_USE_WEIGHTS,
            },
            "explicit_cluster_validation": None,
        }
    else:
        payload = {
            "version": GPTCELLTYPE_EXECUTION_CLUSTERING_PROFILE_VERSION,
            "source": "query_obs",
            "cluster_column": clean_cluster_column,
            "resolution": None,
            "generated_clustering": None,
            "explicit_cluster_validation": {
                "minimum_nonmissing_nonzero_clusters": 2,
                "current_readiness_profile_supports_column": False,
                "separate_readiness_profile_required": True,
            },
        }
    return _identified_profile(payload)


def gptcelltype_readiness_execution_binding(
    *,
    cluster_column: str | None,
    resolution: float,
    top_marker_genes: int,
) -> dict[str, Any]:
    """Compare executable scientific arguments with the canonical readiness scope."""
    if (
        isinstance(top_marker_genes, bool)
        or not isinstance(top_marker_genes, int)
        or not 1 <= top_marker_genes <= EXECUTION_TOP_MARKER_GENES
    ):
        raise ValueError(f"top_marker_genes must be between 1 and {EXECUTION_TOP_MARKER_GENES}.")
    readiness_profile = gptcelltype_readiness_profile()
    execution_profile = gptcelltype_execution_clustering_profile(
        cluster_column=cluster_column,
        resolution=resolution,
    )
    expected = readiness_profile["supported_execution_arguments"]
    expected_clustering_profile = readiness_profile["supported_execution_clustering_profile"]
    mismatch_codes: list[str] = []
    if execution_profile["source"] == "query_obs":
        mismatch_codes.append("explicit_cluster_requires_separate_readiness_profile")
    elif execution_profile["resolution"] != expected["resolution"]:
        mismatch_codes.append("generated_resolution_not_readiness_profiled")
    elif execution_profile["profile_id"] != expected_clustering_profile["profile_id"]:
        mismatch_codes.append("generated_clustering_configuration_not_readiness_profiled")
    if top_marker_genes != expected["top_marker_genes"]:
        mismatch_codes.append("top_marker_count_not_readiness_profiled")

    payload = {
        "version": GPTCELLTYPE_READINESS_EXECUTION_BINDING_VERSION,
        "status": ("matched" if not mismatch_codes else "separate_readiness_profile_required"),
        "mismatch_codes": mismatch_codes,
        "readiness_profile_id": readiness_profile["profile_id"],
        "execution_clustering_profile_id": execution_profile["profile_id"],
        "expected_execution_arguments": expected,
        "provided_execution_arguments": {
            "cluster_column": execution_profile["cluster_column"],
            "resolution": execution_profile["resolution"],
            "top_marker_genes": top_marker_genes,
        },
        "execution_clustering_profile": execution_profile,
    }
    return _identified_profile(payload)


def _sampled_row_indices(n_rows: int, maximum: int) -> np.ndarray:
    """Return a deterministic uniform sample of row positions."""
    if n_rows <= maximum:
        return np.arange(n_rows, dtype=np.int64)
    rng = np.random.default_rng(RANDOM_STATE)
    return np.sort(rng.choice(n_rows, size=maximum, replace=False))


def _feature_block_slices(
    n_features: int,
    maximum: int,
    maximum_blocks: int,
) -> list[slice]:
    """Return bounded contiguous feature blocks spread across the feature axis."""
    if n_features <= maximum:
        return [slice(0, n_features)]

    n_blocks = min(maximum_blocks, maximum)
    widths = np.full(n_blocks, maximum // n_blocks, dtype=int)
    widths[: maximum % n_blocks] += 1
    segment_edges = np.linspace(0, n_features, num=n_blocks + 1, dtype=int)
    blocks: list[slice] = []
    for block_index, width in enumerate(widths):
        segment_start = int(segment_edges[block_index])
        segment_stop = int(segment_edges[block_index + 1])
        start = segment_start + max(0, (segment_stop - segment_start - int(width)) // 2)
        blocks.append(slice(start, start + int(width)))
    return blocks


def _h5ad_shape(x_element: h5py.Dataset | h5py.Group) -> tuple[int, int]:
    """Read an H5AD expression shape without loading observation metadata."""
    if isinstance(x_element, h5py.Dataset):
        return int(x_element.shape[0]), int(x_element.shape[1])
    shape = x_element.attrs.get("shape")
    if shape is None:
        raise ValueError("The H5AD X element does not declare a two-dimensional shape.")
    return int(shape[0]), int(shape[1])


def _read_bounded_expression(
    path: Path,
    *,
    max_cells: int = MAX_SAMPLED_CELLS,
    max_features: int = MAX_CANDIDATE_FEATURES,
) -> tuple[Any, pd.DataFrame, dict[str, Any]]:
    """Read only bounded X blocks and feature metadata from an H5AD file."""
    with h5py.File(path, "r") as handle:
        if "X" not in handle or "var" not in handle:
            raise ValueError("The query H5AD must contain X and var elements.")
        x_element = handle["X"]
        n_cells, n_features = _h5ad_shape(x_element)
        if n_cells == 0 or n_features == 0:
            raise ValueError(f"Query AnnData is empty: shape=({n_cells}, {n_features}).")

        row_indices = _sampled_row_indices(n_cells, max_cells)
        feature_slices = _feature_block_slices(
            n_features,
            max_features,
            FEATURE_BLOCK_COUNT,
        )
        feature_indices = np.concatenate(
            [np.arange(block.start, block.stop, dtype=np.int64) for block in feature_slices]
        )
        matrix_source = (
            x_element if isinstance(x_element, h5py.Dataset) else ad.io.sparse_dataset(x_element)
        )
        matrix_blocks = [
            matrix_source[row_indices, feature_slice] for feature_slice in feature_slices
        ]
        if any(sparse.issparse(block) for block in matrix_blocks):
            matrix = sparse.hstack(
                [
                    block if sparse.issparse(block) else sparse.csr_matrix(block)
                    for block in matrix_blocks
                ],
                format="csr",
            )
        else:
            matrix = np.concatenate(
                [np.asarray(block) for block in matrix_blocks],
                axis=1,
            )

        var = ad.io.read_elem(handle["var"])
        if not isinstance(var, pd.DataFrame) or len(var) != n_features:
            raise ValueError("The query H5AD var element is not a valid feature table.")
        selected_columns = [column for column in GENE_SYMBOL_COLUMNS if column in var.columns]
        bounded_var = var.iloc[feature_indices][selected_columns].copy()
        bounded_var.index = pd.Index(var.index[feature_indices].astype(str))

    return (
        matrix,
        bounded_var,
        {
            "sampling_method": "seeded_uniform_row_positions_and_spread_contiguous_feature_blocks",
            "random_state": RANDOM_STATE,
            "n_total_cells": n_cells,
            "n_sampled_cells": int(len(row_indices)),
            "max_sampled_cells": int(max_cells),
            "n_total_features": n_features,
            "n_candidate_features": int(len(feature_indices)),
            "max_candidate_features": int(max_features),
            "n_feature_blocks": int(len(feature_slices)),
            "query_obs_accessed": False,
            "query_obs_names_accessed": False,
        },
    )


def _matrix_values(matrix: Any) -> np.ndarray:
    """Return stored matrix values for finite and sign validation."""
    if sparse.issparse(matrix):
        return np.asarray(matrix.data, dtype=np.float64)
    return np.asarray(matrix, dtype=np.float64).ravel()


def _prepare_sample_expression(
    matrix: Any,
    inspection: dict[str, Any],
) -> tuple[Any, np.ndarray, str]:
    """Prepare a bounded nonzero-cell matrix from inspected expression state."""
    values = _matrix_values(matrix)
    if values.size and not np.isfinite(values).all():
        raise ValueError("The bounded expression sample contains non-finite values.")
    if values.size and np.any(values < 0):
        raise ValueError("The bounded expression sample contains negative values.")

    if sparse.issparse(matrix):
        row_sums = np.asarray(matrix.sum(axis=1)).ravel()
    else:
        row_sums = np.asarray(matrix, dtype=np.float64).sum(axis=1)
    nonzero_mask = row_sums > 0
    working = matrix[nonzero_mask, :]
    state = inspection.get("expression_state")

    if state == "raw_count_like":
        if sparse.issparse(working):
            working = working.astype(np.float64).tocsr(copy=True)
            sampled_totals = np.asarray(working.sum(axis=1)).ravel()
            working = sparse.diags(10_000 / sampled_totals) @ working
            working.data = np.log1p(working.data)
        else:
            working = np.asarray(working, dtype=np.float64).copy()
            working *= (10_000 / working.sum(axis=1))[:, None]
            np.log1p(working, out=working)
        decision = "normalized_bounded_raw_sample_to_10000_then_log1p"
    elif (
        state == "processed_continuous"
        and inspection.get("processed_expression_state") == "log1p_normalized"
        and float(inspection.get("sampled_negative_fraction", 0.0)) == 0.0
    ):
        working = (
            working.astype(np.float64).tocsr(copy=True)
            if sparse.issparse(working)
            else np.asarray(working, dtype=np.float64).copy()
        )
        decision = "used_bounded_explicit_nonnegative_log1p_sample"
    else:
        raise ValueError(
            "GPTCellType readiness requires raw-count-like expression or explicit "
            "nonnegative log1p expression."
        )

    return working, nonzero_mask, decision


def _identifier_readiness(var: pd.DataFrame) -> dict[str, Any]:
    """Select a complete unique gene-symbol-like representation without returning names."""
    candidates: list[tuple[str, pd.Index]] = [("var_names", pd.Index(var.index.astype(str)))]
    for column in GENE_SYMBOL_COLUMNS:
        if column not in var:
            continue
        values = var[column].astype("string").fillna("").astype(str).str.strip()
        valid = ~values.str.casefold().isin({"", "nan", "none", "na"})
        if bool(valid.all()):
            candidates.append((f"var['{column}']", pd.Index(values)))

    summaries: list[dict[str, Any]] = []
    for source, identifiers in candidates:
        ensembl_fraction = float(
            np.mean([bool(ENSEMBL_GENE_RE.match(value)) for value in identifiers])
        )
        numeric_fraction = float(np.mean([value.isdigit() for value in identifiers]))
        symbol_fraction = float(
            np.mean(
                [
                    bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", value))
                    and not ENSEMBL_GENE_RE.match(value)
                    and not value.isdigit()
                    for value in identifiers
                ]
            )
        )
        suitable = bool(
            identifiers.is_unique
            and ensembl_fraction < 0.5
            and numeric_fraction < 0.5
            and symbol_fraction >= 0.8
        )
        summaries.append(
            {
                "source": source,
                "unique": bool(identifiers.is_unique),
                "ensembl_like_fraction": ensembl_fraction,
                "numeric_like_fraction": numeric_fraction,
                "gene_symbol_like_fraction": symbol_fraction,
                "suitable": suitable,
            }
        )

    selected = next((summary for summary in summaries if summary["suitable"]), None)
    return {
        "suitable": selected is not None,
        "selected_source": selected["source"] if selected else None,
        "representations_checked": summaries,
        "gene_names_returned": False,
    }


def _feature_variances(matrix: Any) -> np.ndarray:
    """Return per-feature population variance for a sparse or dense matrix."""
    if sparse.issparse(matrix):
        means = np.asarray(matrix.mean(axis=0)).ravel()
        second_moments = np.asarray(matrix.multiply(matrix).mean(axis=0)).ravel()
        return np.maximum(0.0, second_moments - means**2)
    dense = np.asarray(matrix, dtype=np.float64)
    return np.var(dense, axis=0)


def _detected_feature_counts(matrix: Any) -> np.ndarray:
    """Return the number of sampled cells detecting each feature."""
    if sparse.issparse(matrix):
        return np.asarray((matrix != 0).sum(axis=0)).ravel()
    return np.count_nonzero(np.asarray(matrix), axis=0)


def _select_and_split_features(matrix: Any) -> tuple[Any, Any, dict[str, Any]]:
    """Select variable features and divide them into balanced disjoint views."""
    variances = _feature_variances(matrix)
    detected = _detected_feature_counts(matrix)
    minimum_detected = max(3, int(np.ceil(matrix.shape[0] * 0.01)))
    eligible = np.flatnonzero(
        (detected >= minimum_detected) & np.isfinite(variances) & (variances > 1e-12)
    )
    ranked = eligible[np.lexsort((eligible, -variances[eligible]))][:MAX_VARIABLE_FEATURES]
    if len(ranked) % 2:
        ranked = ranked[:-1]
    view_a_indices = ranked[0::2]
    view_b_indices = ranked[1::2]
    return (
        matrix[:, view_a_indices],
        matrix[:, view_b_indices],
        {
            "minimum_cells_detecting_feature": minimum_detected,
            "n_variable_candidate_features": int(len(eligible)),
            "n_selected_variable_features": int(len(ranked)),
            "max_selected_variable_features": MAX_VARIABLE_FEATURES,
            "split_method": "alternating_descending_variance_rank",
            "n_features_view_a": int(len(view_a_indices)),
            "n_features_view_b": int(len(view_b_indices)),
            "feature_names_returned": False,
        },
    )


def _cluster_view(matrix: Any) -> tuple[np.ndarray, Any, dict[str, Any]]:
    """Run the GPTCellType default transcriptomic clustering on one feature view."""
    n_pcs = min(MAX_PCS, matrix.shape[0] - 1, matrix.shape[1] - 1)
    if n_pcs < 2:
        raise ValueError("Each feature view must support at least two principal components.")
    n_neighbors = min(N_NEIGHBORS, matrix.shape[0] - 1)
    dataset = ad.AnnData(
        matrix.copy(),
        obs=pd.DataFrame(index=[f"sampled_{index}" for index in range(matrix.shape[0])]),
    )
    sc.pp.pca(
        dataset,
        n_comps=n_pcs,
        random_state=RANDOM_STATE,
        svd_solver=PCA_SVD_SOLVER,
    )
    sc.pp.neighbors(
        dataset,
        n_neighbors=n_neighbors,
        use_rep="X_pca",
        random_state=RANDOM_STATE,
    )
    sc.tl.leiden(
        dataset,
        resolution=LEIDEN_RESOLUTION,
        random_state=RANDOM_STATE,
        key_added="cluster",
        flavor=LEIDEN_FLAVOR,
        n_iterations=LEIDEN_N_ITERATIONS,
        directed=LEIDEN_DIRECTED,
        use_weights=LEIDEN_USE_WEIGHTS,
    )
    labels = dataset.obs["cluster"].astype(str).to_numpy()
    counts = np.unique(labels, return_counts=True)[1]
    quantiles = np.quantile(counts, [0.0, 0.25, 0.5, 0.75, 1.0])
    return (
        labels,
        dataset.obsp["connectivities"].copy(),
        {
            "algorithm": "leiden",
            "resolution": LEIDEN_RESOLUTION,
            "random_state": RANDOM_STATE,
            "n_neighbors": int(n_neighbors),
            "n_pcs": int(n_pcs),
            "pca_svd_solver": PCA_SVD_SOLVER,
            "leiden_flavor": LEIDEN_FLAVOR,
            "leiden_n_iterations": LEIDEN_N_ITERATIONS,
            "leiden_directed": LEIDEN_DIRECTED,
            "leiden_use_weights": LEIDEN_USE_WEIGHTS,
            "n_clusters": int(len(counts)),
            "cluster_size_quantiles": {
                "minimum": float(quantiles[0]),
                "p25": float(quantiles[1]),
                "median": float(quantiles[2]),
                "p75": float(quantiles[3]),
                "maximum": float(quantiles[4]),
            },
            "cluster_ids_returned": False,
            "cluster_assignments_returned": False,
        },
    )


def _cross_view_localization(
    labels: np.ndarray,
    other_view_graph: Any,
    rng: np.random.Generator,
) -> dict[str, Any]:
    """Measure whether clusters remain local in a disjoint gene-view graph."""
    edges = sparse.triu(other_view_graph, k=1).tocoo()
    if edges.nnz == 0 or float(edges.data.sum()) <= 0:
        raise ValueError("The disjoint gene-view neighbor graph contains no weighted edges.")
    total_weight = float(edges.data.sum())
    observed = float(edges.data[labels[edges.row] == labels[edges.col]].sum() / total_weight)
    cluster_sizes = np.unique(labels, return_counts=True)[1].astype(np.float64)
    n_cells = float(len(labels))
    chance = float(np.sum(cluster_sizes * (cluster_sizes - 1)) / (n_cells * (n_cells - 1)))
    adjusted = float((observed - chance) / max(np.finfo(float).eps, 1.0 - chance))

    null_values = np.empty(N_PERMUTATIONS, dtype=np.float64)
    for permutation_index in range(N_PERMUTATIONS):
        permuted = rng.permutation(labels)
        null_values[permutation_index] = float(
            edges.data[permuted[edges.row] == permuted[edges.col]].sum() / total_weight
        )
    p_value = float((1 + np.count_nonzero(null_values >= observed)) / (N_PERMUTATIONS + 1))
    return {
        "observed_same_cluster_edge_fraction": observed,
        "finite_population_chance_fraction": chance,
        "chance_adjusted_enrichment": adjusted,
        "permutation_p_value": p_value,
        "n_permutations": N_PERMUTATIONS,
    }


def _ami_summary(
    labels_a: np.ndarray,
    labels_b: np.ndarray,
    rng: np.random.Generator,
) -> dict[str, Any]:
    """Return chance-adjusted cross-view agreement with a paired bootstrap interval."""
    observed = float(adjusted_mutual_info_score(labels_a, labels_b))
    bootstrap_values: list[float] = []
    for _ in range(N_AMI_BOOTSTRAPS):
        indices = rng.integers(0, len(labels_a), size=len(labels_a))
        if len(np.unique(labels_a[indices])) < 2 or len(np.unique(labels_b[indices])) < 2:
            continue
        bootstrap_values.append(
            float(adjusted_mutual_info_score(labels_a[indices], labels_b[indices]))
        )
    if not bootstrap_values:
        lower, upper = observed, observed
    else:
        lower, upper = np.quantile(bootstrap_values, [0.025, 0.975])
    return {
        "adjusted_mutual_information": observed,
        "bootstrap_95_percent_interval": [float(lower), float(upper)],
        "n_bootstrap_replicates": int(len(bootstrap_values)),
    }


def _benjamini_hochberg(p_values: np.ndarray) -> np.ndarray:
    """Apply the Benjamini-Hochberg false-discovery-rate adjustment."""
    p_values = np.asarray(p_values, dtype=np.float64)
    adjusted = np.ones_like(p_values)
    finite = np.isfinite(p_values)
    finite_indices = np.flatnonzero(finite)
    if not len(finite_indices):
        return adjusted
    ordered = finite_indices[np.argsort(p_values[finite_indices], kind="mergesort")]
    ranks = np.arange(1, len(ordered) + 1, dtype=np.float64)
    ordered_adjusted = p_values[ordered] * len(ordered) / ranks
    ordered_adjusted = np.minimum.accumulate(ordered_adjusted[::-1])[::-1]
    adjusted[ordered] = np.clip(ordered_adjusted, 0.0, 1.0)
    return adjusted


def _held_out_marker_support(labels: np.ndarray, held_out_matrix: Any) -> dict[str, Any]:
    """Test positive markers only in genes not used to create the supplied clusters."""
    dense = (
        held_out_matrix.toarray()
        if sparse.issparse(held_out_matrix)
        else np.asarray(held_out_matrix, dtype=np.float64)
    )
    cluster_values, cluster_sizes = np.unique(labels, return_counts=True)
    qualified_counts: list[int] = []
    supported_cells = 0
    evaluable_clusters = 0
    supported_clusters = 0

    for cluster, cluster_size in zip(cluster_values, cluster_sizes, strict=True):
        in_cluster = labels == cluster
        n_in = int(cluster_size)
        n_out = int(len(labels) - n_in)
        if min(n_in, n_out) < MIN_CLUSTER_SIDE:
            qualified_counts.append(0)
            continue
        evaluable_clusters += 1
        test = mannwhitneyu(
            dense[in_cluster, :],
            dense[~in_cluster, :],
            axis=0,
            alternative="greater",
            method="asymptotic",
        )
        p_values = np.asarray(test.pvalue, dtype=np.float64)
        auroc = np.asarray(test.statistic, dtype=np.float64) / (n_in * n_out)
        adjusted = _benjamini_hochberg(p_values)
        positive_mean = np.mean(dense[in_cluster, :], axis=0) > np.mean(
            dense[~in_cluster, :], axis=0
        )
        qualified = (
            (adjusted <= MARKER_Q_THRESHOLD) & (auroc >= MARKER_AUROC_THRESHOLD) & positive_mean
        )
        n_qualified = int(np.count_nonzero(qualified))
        qualified_counts.append(n_qualified)
        if n_qualified >= MIN_QUALIFIED_MARKERS:
            supported_clusters += 1
            supported_cells += n_in

    quantiles = np.quantile(qualified_counts, [0.0, 0.25, 0.5, 0.75, 1.0])
    return {
        "n_clusters": int(len(cluster_values)),
        "n_evaluable_clusters": int(evaluable_clusters),
        "minimum_cluster_and_rest_size": MIN_CLUSTER_SIDE,
        "n_supported_clusters": int(supported_clusters),
        "supported_cluster_fraction": float(supported_clusters / max(1, len(cluster_values))),
        "supported_cell_fraction": float(supported_cells / len(labels)),
        "qualified_marker_count_quantiles": {
            "minimum": float(quantiles[0]),
            "p25": float(quantiles[1]),
            "median": float(quantiles[2]),
            "p75": float(quantiles[3]),
            "maximum": float(quantiles[4]),
        },
        "marker_criteria": {
            "benjamini_hochberg_q_at_most": MARKER_Q_THRESHOLD,
            "auroc_at_least": MARKER_AUROC_THRESHOLD,
            "positive_mean_difference": True,
            "qualified_markers_per_supported_cluster_at_least": MIN_QUALIFIED_MARKERS,
        },
        "gene_names_returned": False,
    }


def _thresholds() -> dict[str, Any]:
    """Return the fixed statistical and practical evidence thresholds."""
    return {
        "minimum_nonzero_cells": MIN_NONZERO_CELLS,
        "minimum_variable_features": MIN_VARIABLE_FEATURES,
        "minimum_cluster_and_rest_size": MIN_CLUSTER_SIDE,
        "strong": {
            "cross_view_enrichment_at_least": STRONG_COHERENCE_EFFECT,
            "permutation_p_value_at_most": 0.01,
            "ami_bootstrap_lower_bound_at_least": STRONG_AMI_LOWER_BOUND,
            "supported_cluster_fraction_at_least": STRONG_MARKER_COVERAGE,
            "supported_cell_fraction_at_least": STRONG_MARKER_COVERAGE,
        },
        "moderate": {
            "cross_view_enrichment_at_least": MODERATE_COHERENCE_EFFECT,
            "permutation_p_value_at_most": 0.05,
            "ami_bootstrap_lower_bound_above": 0.0,
            "supported_cluster_fraction_at_least": MODERATE_MARKER_COVERAGE,
            "supported_cell_fraction_at_least": MODERATE_MARKER_COVERAGE,
        },
        "basis": [
            (
                "Cross-view tests use disjoint genes so clustering cannot validate itself "
                "with the same features."
            ),
            (
                "Permutation p-values test localization beyond fixed-size random clusters; "
                "effect thresholds require a prespecified fraction of achievable enrichment."
            ),
            (
                "AUROC 0.70 means a marker ranks a random in-cluster cell above a random "
                "out-of-cluster cell at least 70 percent of the time."
            ),
            (
                "Three FDR-controlled held-out markers require redundant positive evidence "
                "rather than a single potentially technical gene."
            ),
        ],
    }


def _grade_readiness(
    coherence: dict[str, Any],
    markers_a_on_b: dict[str, Any],
    markers_b_on_a: dict[str, Any],
) -> tuple[str, dict[str, str]]:
    """Grade fixed coherence and held-out-marker evidence without selecting a method."""
    localizations = (
        coherence["clusters_from_view_a_in_view_b_graph"],
        coherence["clusters_from_view_b_in_view_a_graph"],
    )
    minimum_effect = min(item["chance_adjusted_enrichment"] for item in localizations)
    maximum_p = max(item["permutation_p_value"] for item in localizations)
    ami_lower = coherence["cross_view_cluster_agreement"]["bootstrap_95_percent_interval"][0]
    marker_results = (markers_a_on_b, markers_b_on_a)
    minimum_cluster_coverage = min(
        result["supported_cluster_fraction"] for result in marker_results
    )
    minimum_cell_coverage = min(result["supported_cell_fraction"] for result in marker_results)

    if (
        minimum_effect >= STRONG_COHERENCE_EFFECT
        and maximum_p <= 0.01
        and ami_lower >= STRONG_AMI_LOWER_BOUND
    ):
        coherence_grade = "strong"
    elif minimum_effect >= MODERATE_COHERENCE_EFFECT and maximum_p <= 0.05 and ami_lower > 0.0:
        coherence_grade = "moderate"
    else:
        coherence_grade = "weak"

    if (
        minimum_cluster_coverage >= STRONG_MARKER_COVERAGE
        and minimum_cell_coverage >= STRONG_MARKER_COVERAGE
    ):
        marker_grade = "strong"
    elif (
        minimum_cluster_coverage >= MODERATE_MARKER_COVERAGE
        and minimum_cell_coverage >= MODERATE_MARKER_COVERAGE
    ):
        marker_grade = "moderate"
    else:
        marker_grade = "weak"

    assessment = (
        "strong"
        if coherence_grade == marker_grade == "strong"
        else "moderate"
        if coherence_grade != "weak" and marker_grade != "weak"
        else "weak"
    )
    return assessment, {
        "coherence": coherence_grade,
        "held_out_positive_markers": marker_grade,
    }


def inspect_gptcelltype_readiness(
    path: Path,
    expression_inspection: dict[str, Any],
) -> dict[str, Any]:
    """Assess bounded query expression without reading query observation metadata."""
    readiness_profile = gptcelltype_readiness_profile()
    try:
        matrix, var, sampling = _read_bounded_expression(path)
        identifier_evidence = _identifier_readiness(var)
        if not identifier_evidence["suitable"]:
            return {
                "status": "not_assessable",
                "assessment": "not_assessable",
                "reason": "No complete unique gene-symbol-like representation was available.",
                "sampling": sampling,
                "gene_identifiers": identifier_evidence,
                "thresholds": _thresholds(),
                "readiness_profile": readiness_profile,
            }

        working, nonzero_mask, preprocessing = _prepare_sample_expression(
            matrix,
            expression_inspection,
        )
        n_nonzero = int(np.count_nonzero(nonzero_mask))
        if n_nonzero < MIN_NONZERO_CELLS:
            return {
                "status": "not_assessable",
                "assessment": "not_assessable",
                "reason": (
                    f"Only {n_nonzero} sampled cells had expression in the bounded feature set; "
                    f"at least {MIN_NONZERO_CELLS} are required."
                ),
                "sampling": {
                    **sampling,
                    "n_sampled_nonzero_cells": n_nonzero,
                },
                "preprocessing": preprocessing,
                "gene_identifiers": identifier_evidence,
                "thresholds": _thresholds(),
                "readiness_profile": readiness_profile,
            }

        view_a, view_b, feature_selection = _select_and_split_features(working)
        if feature_selection["n_selected_variable_features"] < MIN_VARIABLE_FEATURES:
            return {
                "status": "not_assessable",
                "assessment": "not_assessable",
                "reason": (
                    "Fewer than the prespecified minimum variable features remained for two "
                    "disjoint gene views."
                ),
                "sampling": {
                    **sampling,
                    "n_sampled_nonzero_cells": n_nonzero,
                },
                "preprocessing": preprocessing,
                "gene_identifiers": identifier_evidence,
                "feature_selection": feature_selection,
                "thresholds": _thresholds(),
                "readiness_profile": readiness_profile,
            }

        labels_a, graph_a, clustering_a = _cluster_view(view_a)
        labels_b, graph_b, clustering_b = _cluster_view(view_b)
        if clustering_a["n_clusters"] < 2 or clustering_b["n_clusters"] < 2:
            return {
                "status": "not_assessable",
                "assessment": "not_assessable",
                "reason": "At least one disjoint gene view produced fewer than two clusters.",
                "sampling": {
                    **sampling,
                    "n_sampled_nonzero_cells": n_nonzero,
                },
                "preprocessing": preprocessing,
                "gene_identifiers": identifier_evidence,
                "feature_selection": feature_selection,
                "clustering": {
                    "view_a": clustering_a,
                    "view_b": clustering_b,
                },
                "thresholds": _thresholds(),
                "readiness_profile": readiness_profile,
            }

        rng = np.random.default_rng(RANDOM_STATE)
        coherence = {
            "clusters_from_view_a_in_view_b_graph": _cross_view_localization(
                labels_a,
                graph_b,
                rng,
            ),
            "clusters_from_view_b_in_view_a_graph": _cross_view_localization(
                labels_b,
                graph_a,
                rng,
            ),
            "cross_view_cluster_agreement": _ami_summary(labels_a, labels_b, rng),
        }
        markers_a_on_b = _held_out_marker_support(labels_a, view_b)
        markers_b_on_a = _held_out_marker_support(labels_b, view_a)
        assessment, component_grades = _grade_readiness(
            coherence,
            markers_a_on_b,
            markers_b_on_a,
        )
        return {
            "status": "success",
            "assessment": assessment,
            "component_grades": component_grades,
            "sampling": {
                **sampling,
                "n_sampled_nonzero_cells": n_nonzero,
            },
            "preprocessing": preprocessing,
            "gene_identifiers": identifier_evidence,
            "feature_selection": feature_selection,
            "clustering": {
                "view_a": clustering_a,
                "view_b": clustering_b,
            },
            "coherence": coherence,
            "held_out_positive_markers": {
                "clusters_from_view_a_tested_on_view_b": markers_a_on_b,
                "clusters_from_view_b_tested_on_view_a": markers_b_on_a,
            },
            "thresholds": _thresholds(),
            "readiness_profile": readiness_profile,
            "limitations": [
                (
                    "Expression-only coherence can reflect technical or batch structure; this "
                    "diagnostic does not establish biological identity."
                ),
                "The bounded sample can miss rare populations.",
                (
                    "The evidence covers deterministic generated Leiden clusters, not a "
                    "user-supplied query observation cluster column."
                ),
            ],
            "leakage_safety": {
                "query_obs_columns_or_values_accessed": False,
                "query_obs_names_accessed": False,
                "query_uns_accessed": False,
                "benchmark_identity_accessed": False,
                "truth_or_mapping_accessed": False,
                "gene_names_returned": False,
                "cluster_assignments_returned": False,
            },
        }
    except Exception as exc:
        return {
            "status": "error",
            "assessment": "not_assessable",
            "error_type": type(exc).__name__,
            "message": f"Bounded GPTCellType readiness inspection failed: {exc}",
            "thresholds": _thresholds(),
            "readiness_profile": readiness_profile,
            "leakage_safety": {
                "query_obs_columns_or_values_accessed": False,
                "query_obs_names_accessed": False,
                "query_uns_accessed": False,
                "benchmark_identity_accessed": False,
                "truth_or_mapping_accessed": False,
                "gene_names_returned": False,
                "cluster_assignments_returned": False,
            },
        }
