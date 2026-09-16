"""CellTypist annotation with explicit model selection and reproducible outputs."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, Dict
from uuid import uuid4
import hashlib
import json
import os
import re
import threading
import time

import anndata as ad
import numpy as np
import pandas as pd
import scanpy as sc
from scipy import sparse
from scipy.special import expit

from agents.agent_registry.cell_annotater_agent.tools_impl.harmony_transfer import (
    ENSEMBL_GENE_RE,
    GENE_SYMBOL_COLUMNS,
    _inspect_expression_matrix,
    _resolve_path,
)
from agents.workspace_paths import workspace_relative


CELLTYPIST_CACHE_PATH = "cell_annotation/celltypist_cache"
CELLTYPIST_TARGET_SUM = 10_000.0
CELLTYPIST_TARGET_SUM_RELATIVE_TOLERANCE = 0.01
CELLTYPIST_TARGET_SUM_MIN_FRACTION = 0.95
CELLTYPIST_NORMALIZATION_MAX_ROWS = 256
CELLTYPIST_RANDOM_STATE = 0
CELLTYPIST_MAX_CENTERED_TRAINING_ELEMENTS = 10_000_000
CELLTYPIST_MAX_INFERENCE_BATCH_CELLS = 50_000
CELLTYPIST_MAX_INFERENCE_BATCH_ELEMENTS = 5_000_000
CELLTYPIST_THRESHOLD_UNASSIGNED_SENTINEL = "__tissueagent_celltypist_threshold_unassigned__"
_CELLTYPIST_CONFIG_LOCK = threading.RLock()
ANNOTATION_COLUMNS = (
    "celltypist_predicted_cell_type",
    "celltypist_prediction_confidence",
    "celltypist_status",
    "celltypist_exclusion_reason",
    "cell_annotation_predicted_cell_type",
    "cell_annotation_prediction_confidence",
    "cell_annotation_status",
    "cell_annotation_exclusion_reason",
    "cell_annotation_method",
    "label",
)


def _error_result(stage: str, exc: Exception, **details: Any) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "status": "error",
        "operation": "celltypist_annotation",
        "stage": stage,
        "error_type": type(exc).__name__,
        "message": f"CellTypist annotation failed during {stage}: {exc}",
    }
    result.update(details)
    return result


def _validate_matrix_values(dataset: ad.AnnData, role: str) -> None:
    values = dataset.X.data if sparse.issparse(dataset.X) else np.asarray(dataset.X).ravel()
    if values.size and not np.isfinite(values).all():
        raise ValueError(f"{role} expression contains non-finite values.")
    if values.size and np.any(values < 0):
        raise ValueError(
            f"{role} expression contains negative values and cannot be used by CellTypist."
        )


def _nonzero_observation_mask(dataset: ad.AnnData) -> np.ndarray:
    if sparse.issparse(dataset.X):
        detected = np.asarray((dataset.X != 0).sum(axis=1)).ravel()
    else:
        detected = np.count_nonzero(np.asarray(dataset.X), axis=1)
    return detected > 0


def _validate_log1p_target_sum(dataset: ad.AnnData, role: str) -> dict[str, Any]:
    row_indices = np.unique(
        np.linspace(
            0,
            dataset.n_obs - 1,
            num=min(dataset.n_obs, CELLTYPIST_NORMALIZATION_MAX_ROWS),
            dtype=np.int64,
        )
    )
    sampled = dataset[row_indices, :].X
    if sparse.issparse(sampled):
        linear = sampled.copy()
        linear.data = np.expm1(linear.data)
        totals = np.asarray(linear.sum(axis=1)).ravel()
    else:
        totals = np.expm1(np.asarray(sampled)).sum(axis=1)
    nonzero_totals = totals[totals > 0]
    if len(nonzero_totals) == 0:
        raise ValueError(f"{role} expression contains no nonzero observations.")
    relative_error = np.abs(nonzero_totals - CELLTYPIST_TARGET_SUM) / CELLTYPIST_TARGET_SUM
    within_tolerance = relative_error <= CELLTYPIST_TARGET_SUM_RELATIVE_TOLERANCE
    valid_fraction = float(np.mean(within_tolerance))
    if valid_fraction < CELLTYPIST_TARGET_SUM_MIN_FRACTION:
        raise ValueError(
            f"{role} log1p expression is not normalized to 10000 counts per nonzero "
            f"observation: only {valid_fraction:.1%} of sampled rows are within "
            f"{CELLTYPIST_TARGET_SUM_RELATIVE_TOLERANCE:.0%}."
        )
    return {
        "sampled_rows": int(len(row_indices)),
        "sampled_nonzero_rows": int(len(nonzero_totals)),
        "sampled_zero_rows": int(len(totals) - len(nonzero_totals)),
        "target_sum": CELLTYPIST_TARGET_SUM,
        "relative_tolerance": CELLTYPIST_TARGET_SUM_RELATIVE_TOLERANCE,
        "fraction_within_tolerance": valid_fraction,
        "minimum_nonzero_sum": float(np.min(nonzero_totals)),
        "maximum_nonzero_sum": float(np.max(nonzero_totals)),
    }


def _symbol_like_mask(values: pd.Index) -> np.ndarray:
    return np.asarray(
        [
            bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", value))
            and not ENSEMBL_GENE_RE.match(value)
            and not value.isdigit()
            for value in values
        ],
        dtype=bool,
    )


def _collapse_raw_gene_symbols(
    dataset: ad.AnnData,
    source: str,
    values: pd.Index,
    symbol_like_mask: np.ndarray,
) -> tuple[ad.AnnData, dict[str, Any]]:
    source_positions = np.flatnonzero(symbol_like_mask)
    symbols = values[symbol_like_mask]
    codes, unique_symbols = pd.factorize(symbols, sort=False)
    mapping = sparse.csr_matrix(
        (
            np.ones(len(source_positions), dtype=np.float32),
            (np.arange(len(source_positions), dtype=np.int64), codes),
        ),
        shape=(len(source_positions), len(unique_symbols)),
    )
    selected = dataset.X[:, source_positions]
    if sparse.issparse(selected):
        expression = selected.tocsr() @ mapping
    else:
        expression = np.asarray(selected) @ mapping.toarray()
    working = ad.AnnData(
        X=expression,
        obs=dataset.obs.copy(),
        var=pd.DataFrame(index=pd.Index(unique_symbols.astype(str))),
    )
    return working, {
        "source": source,
        "n_features": int(working.n_vars),
        "n_features_before_canonicalization": int(dataset.n_vars),
        "n_invalid_features_dropped": int(dataset.n_vars - len(source_positions)),
        "n_duplicate_symbols_collapsed": int(len(source_positions) - working.n_vars),
        "n_identifiers_changed": int(dataset.n_vars),
        "gene_symbol_like_fraction": float(np.mean(symbol_like_mask)),
        "ensembl_like_fraction": float(
            np.mean([bool(ENSEMBL_GENE_RE.match(value)) for value in values])
        ),
        "numeric_like_fraction": float(np.mean([value.isdigit() for value in values])),
        "canonicalization": "drop_non_symbols_and_sum_duplicate_raw_counts",
    }


def _select_gene_symbols(
    dataset: ad.AnnData,
    role: str,
    *,
    allow_raw_count_collapse: bool = True,
) -> tuple[ad.AnnData, dict[str, Any]]:
    original_names = pd.Index(dataset.var_names.astype(str))
    candidates: list[tuple[str, pd.Index]] = [("var_names", original_names)]
    for column in GENE_SYMBOL_COLUMNS:
        if column not in dataset.var:
            continue
        values = dataset.var[column].astype("string").fillna("").astype(str).str.strip()
        if not values.str.casefold().isin({"", "nan", "none", "na"}).any():
            candidates.append((f"var['{column}']", pd.Index(values)))

    valid_candidates: list[tuple[str, pd.Index, float, float, float]] = []
    collapsible_candidates: list[tuple[str, pd.Index, np.ndarray, float, float, float]] = []
    for source, values in candidates:
        ensembl_fraction = float(np.mean([bool(ENSEMBL_GENE_RE.match(value)) for value in values]))
        numeric_fraction = float(np.mean([value.isdigit() for value in values]))
        symbol_like_mask = _symbol_like_mask(values)
        symbol_like_fraction = float(np.mean(symbol_like_mask))
        if values.is_unique and symbol_like_fraction >= 0.8:
            valid_candidates.append(
                (
                    source,
                    values,
                    symbol_like_fraction,
                    ensembl_fraction,
                    numeric_fraction,
                )
            )
        elif allow_raw_count_collapse and symbol_like_fraction >= 0.5:
            collapsible_candidates.append(
                (
                    source,
                    values,
                    symbol_like_mask,
                    symbol_like_fraction,
                    ensembl_fraction,
                    numeric_fraction,
                )
            )
    if not valid_candidates:
        if not collapsible_candidates:
            raise ValueError(
                f"{role} requires complete, unique gene-symbol-like feature identifiers for "
                "CellTypist; no suitable var names or symbol column was found."
            )
        source, values, symbol_like_mask, _, _, _ = max(
            collapsible_candidates,
            key=lambda item: (
                item[3],
                -item[4],
                -item[5],
                item[0] != "var_names",
            ),
        )
        return _collapse_raw_gene_symbols(dataset, source, values, symbol_like_mask)

    source, symbols, symbol_like_fraction, ensembl_fraction, numeric_fraction = max(
        valid_candidates,
        key=lambda item: (
            item[2],
            -item[3],
            -item[4],
            item[0] == "var_names",
        ),
    )
    working = dataset.copy()
    if source != "var_names":
        working.var["celltypist_original_gene_identifier"] = original_names
        working.var_names = symbols
    return working, {
        "source": source,
        "n_features": int(working.n_vars),
        "n_identifiers_changed": int(np.count_nonzero(original_names != symbols)),
        "gene_symbol_like_fraction": symbol_like_fraction,
        "ensembl_like_fraction": ensembl_fraction,
        "numeric_like_fraction": numeric_fraction,
    }


def _prepare_expression(
    dataset: ad.AnnData,
    inspection: dict[str, Any],
    *,
    role: str,
) -> tuple[ad.AnnData, dict[str, Any]]:
    state = inspection["expression_state"]
    if state == "raw_count_like":
        _validate_matrix_values(dataset, role)
        working, gene_identifiers = _select_gene_symbols(
            dataset,
            role,
            allow_raw_count_collapse=True,
        )
        sc.pp.normalize_total(working, target_sum=1e4)
        sc.pp.log1p(working)
        preprocessing = "normalize_total_10000_log1p"
    elif state == "processed_continuous":
        if not inspection["log1p_metadata_present"]:
            raise ValueError(
                f"{role} expression appears processed but lacks explicit AnnData log1p metadata."
            )
        if inspection["sampled_negative_fraction"] > 0:
            raise ValueError(
                f"{role} expression has log1p metadata but contains sampled negative values."
            )
        _validate_matrix_values(dataset, role)
        working, gene_identifiers = _select_gene_symbols(
            dataset,
            role,
            allow_raw_count_collapse=False,
        )
        preprocessing = "accepted_existing_log1p"
    else:
        raise ValueError(
            f"{role} expression state '{state}' is not safe for CellTypist: "
            f"{inspection['rationale']}"
        )

    normalization = _validate_log1p_target_sum(working, role)
    return working, {
        "input_expression_state": state,
        "preprocessing": preprocessing,
        "log1p_metadata_present": bool(inspection["log1p_metadata_present"]),
        "n_genes": int(working.n_vars),
        "normalization": normalization,
        "gene_identifiers": gene_identifiers,
    }


def _load_celltypist(cache_path: Path) -> tuple[Any, Any, Callable[[], None]]:
    _CELLTYPIST_CONFIG_LOCK.acquire()
    previous_environment = os.environ.get("CELLTYPIST_FOLDER")
    models = None
    previous_paths = None
    try:
        cache_path.mkdir(parents=True, exist_ok=True)
        os.environ["CELLTYPIST_FOLDER"] = str(cache_path)
        try:
            import celltypist
            from celltypist import models
        finally:
            if previous_environment is None:
                os.environ.pop("CELLTYPIST_FOLDER", None)
            else:
                os.environ["CELLTYPIST_FOLDER"] = previous_environment

        previous_paths = (
            models.celltypist_path,
            models.data_path,
            models.models_path,
        )
        models.celltypist_path = str(cache_path)
        models.data_path = str(cache_path / "data")
        models.models_path = str(cache_path / "data" / "models")
        Path(models.models_path).mkdir(parents=True, exist_ok=True)
    except BaseException:
        try:
            if models is not None and previous_paths is not None:
                models.celltypist_path, models.data_path, models.models_path = previous_paths
        finally:
            _CELLTYPIST_CONFIG_LOCK.release()
        raise

    restored = False

    def restore_configuration() -> None:
        nonlocal restored
        if restored:
            return
        try:
            models.celltypist_path, models.data_path, models.models_path = previous_paths
        finally:
            restored = True
            _CELLTYPIST_CONFIG_LOCK.release()

    return celltypist, models, restore_configuration


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_model_description(description: Any) -> dict[str, str | int | float | bool]:
    if not isinstance(description, dict):
        return {}
    safe: dict[str, str | int | float | bool] = {}
    for key, value in description.items():
        if isinstance(value, (str, int, float, bool)):
            safe[str(key)] = value
        elif value is not None:
            safe[str(key)] = str(value)
    return safe


def _load_builtin_model(
    models,
    model_name: str,
) -> tuple[Any, Path, dict[str, Any]]:
    if Path(model_name).name != model_name or not model_name.endswith(".pkl"):
        raise ValueError("model_name must be an exact CellTypist catalog .pkl filename.")

    catalog = models.models_description()
    if "model" not in catalog or "description" not in catalog:
        raise ValueError("The CellTypist model catalog has an unexpected schema.")
    matching_rows = catalog.loc[catalog["model"].astype(str) == model_name]
    if matching_rows.empty:
        raise ValueError(f"'{model_name}' is not present in the official CellTypist model catalog.")

    models.download_models(model=model_name)
    model_path = Path(models.models_path) / model_name
    if not model_path.is_file() or model_path.stat().st_size == 0:
        raise FileNotFoundError(
            f"CellTypist did not create the selected model artifact: {model_path}"
        )

    model = models.Model.load(str(model_path.resolve()))
    if len(model.features) == 0 or len(model.cell_types) < 2:
        raise ValueError(f"The selected CellTypist model is invalid: '{model_name}'.")
    return (
        model,
        model_path,
        {
            "catalog_description": str(matching_rows.iloc[0]["description"]),
            "description": _safe_model_description(model.description),
        },
    )


def _validate_reference_labels(
    reference: ad.AnnData,
    cell_type_column: str,
) -> dict[str, int]:
    if cell_type_column not in reference.obs:
        raise KeyError(f"Reference missing .obs['{cell_type_column}'].")

    labels = reference.obs[cell_type_column].astype("string")
    invalid = labels.isna() | labels.fillna("").str.strip().eq("")
    if invalid.any():
        raise ValueError(
            f"Reference .obs['{cell_type_column}'] contains "
            f"{int(invalid.sum())} missing or empty labels."
        )
    counts = labels.astype(str).value_counts()
    if len(counts) < 2:
        raise ValueError("CellTypist custom training requires at least two reference cell types.")
    return {str(label): int(count) for label, count in counts.items()}


def _train_reference_model(
    celltypist,
    reference: ad.AnnData,
    *,
    reference_path: Path,
    cell_type_column: str,
    n_jobs: int,
) -> tuple[Any, dict[str, Any]]:
    reference.obs[cell_type_column] = (
        reference.obs[cell_type_column].astype("string").astype(str).to_numpy()
    )
    use_sgd = reference.n_obs >= 100_000
    feature_selection = reference.n_vars > 300
    training_elements = reference.n_obs * reference.n_vars
    with_mean = training_elements <= CELLTYPIST_MAX_CENTERED_TRAINING_ELEMENTS
    model = celltypist.train(
        reference,
        labels=cell_type_column,
        n_jobs=n_jobs,
        with_mean=with_mean,
        use_SGD=use_sgd,
        mini_batch=use_sgd,
        feature_selection=feature_selection,
        random_state=CELLTYPIST_RANDOM_STATE,
        details="TissueAgent reference-trained CellTypist model",
        source=workspace_relative(reference_path),
        version="tissueagent_reference_v1",
    )
    if model is None or len(model.features) == 0 or len(model.cell_types) < 2:
        raise ValueError("CellTypist did not produce a valid custom reference model.")
    return model, {
        "with_mean": with_mean,
        "training_elements": int(training_elements),
        "max_centered_training_elements": CELLTYPIST_MAX_CENTERED_TRAINING_ELEMENTS,
        "use_sgd": use_sgd,
        "mini_batch": use_sgd,
        "feature_selection": feature_selection,
        "random_state": CELLTYPIST_RANDOM_STATE,
        "mini_batch_sampling_reproducible": not use_sgd,
        "reproducibility_note": (
            "CellTypist 1.7.1 mini-batch sampling uses the process-global NumPy RNG and is not "
            "controlled by classifier random_state."
            if use_sgd
            else "Training does not use CellTypist mini-batch sampling."
        ),
    }


def _align_query_gene_case(
    query: ad.AnnData,
    model_features: np.ndarray,
) -> dict[str, Any]:
    features = [str(feature) for feature in model_features]
    feature_set = set(features)
    folded_features: dict[str, list[str]] = {}
    for feature in features:
        folded_features.setdefault(feature.casefold(), []).append(feature)

    if not query.var_names.is_unique:
        raise ValueError("Query gene symbols must be unique before CellTypist case alignment.")
    aligned_names = [str(name) for name in query.var_names]
    used_model_features: set[str] = set()
    case_aligned = 0
    collisions = 0
    for index, name in enumerate(aligned_names):
        if name in feature_set:
            target = name
        else:
            candidates = folded_features.get(name.casefold(), [])
            target = candidates[0] if len(candidates) == 1 else None
        if target is None:
            continue
        if target in used_model_features:
            collisions += 1
            continue
        used_model_features.add(target)
        if target != name:
            aligned_names[index] = target
            case_aligned += 1

    query.var_names = pd.Index(aligned_names)
    if not query.var_names.is_unique:
        raise ValueError(
            "CellTypist model-derived case alignment created duplicate query gene symbols."
        )
    matched_features = pd.Index(features).intersection(query.var_names, sort=False)
    return {
        "n_query_genes": int(query.n_vars),
        "n_model_features": int(len(features)),
        "n_matched_features": int(len(matched_features)),
        "model_feature_fraction": float(len(matched_features) / len(features)),
        "query_gene_fraction": float(len(matched_features) / query.n_vars),
        "n_case_aligned_query_genes": case_aligned,
        "n_case_alignment_collisions": collisions,
        "matched_feature_examples": [str(value) for value in matched_features[:20]],
    }


def _overclustering_resolution(n_obs: int) -> int:
    if n_obs < 5_000:
        return 5
    if n_obs < 20_000:
        return 10
    if n_obs < 40_000:
        return 15
    if n_obs < 100_000:
        return 20
    if n_obs < 200_000:
        return 25
    return 30


def _create_transcriptomic_overclustering(
    query: ad.AnnData,
) -> tuple[np.ndarray, dict[str, Any]]:
    if query.n_obs <= 50:
        raise ValueError("CellTypist majority voting requires more than 50 query observations.")

    clustering = query.copy()
    sc.pp.filter_genes(clustering, min_cells=min(5, clustering.n_obs))
    if clustering.n_vars < 3:
        raise ValueError(
            "At least three detected genes are required for transcriptomic over-clustering."
        )
    sc.pp.highly_variable_genes(
        clustering,
        n_top_genes=min(2_500, clustering.n_vars),
        flavor="seurat",
        inplace=True,
    )
    clustering = clustering[:, clustering.var["highly_variable"]].copy()
    if clustering.n_vars < 3:
        raise ValueError("CellTypist over-clustering retained fewer than three variable genes.")
    sc.pp.scale(clustering, max_value=10)

    n_pcs = min(50, clustering.n_obs - 1, clustering.n_vars - 1)
    if n_pcs < 2:
        raise ValueError("Transcriptomic over-clustering requires at least two PCA axes.")

    sc.pp.pca(
        clustering,
        n_comps=n_pcs,
        random_state=CELLTYPIST_RANDOM_STATE,
    )
    n_neighbors = min(10, clustering.n_obs - 1)
    sc.pp.neighbors(
        clustering,
        n_neighbors=n_neighbors,
        n_pcs=n_pcs,
        random_state=CELLTYPIST_RANDOM_STATE,
    )
    resolution = _overclustering_resolution(clustering.n_obs)
    sc.tl.leiden(
        clustering,
        resolution=resolution,
        key_added="_celltypist_over_clustering",
        random_state=CELLTYPIST_RANDOM_STATE,
        flavor="igraph",
        n_iterations=2,
        directed=False,
    )
    clusters = clustering.obs["_celltypist_over_clustering"].astype(str).to_numpy()
    return clusters, {
        "source": "celltypist_canonical_transcriptomic_graph",
        "n_variable_genes": int(clustering.n_vars),
        "n_pcs": int(n_pcs),
        "n_neighbors": int(n_neighbors),
        "resolution": int(resolution),
        "scale_zero_center": True,
        "scale_max_value": 10,
        "random_state": CELLTYPIST_RANDOM_STATE,
        "n_clusters": int(pd.Series(clusters).nunique()),
    }


def _run_celltypist_inference(
    model: Any,
    query: ad.AnnData,
    *,
    mode: str,
    p_thres: float,
    majority_voting: bool,
    over_clustering: np.ndarray | None,
) -> tuple[np.ndarray, np.ndarray, str, np.ndarray, dict[str, Any]]:
    features = pd.Index(np.asarray(model.features, dtype=str))
    if not features.is_unique:
        raise ValueError("CellTypist model features must be unique.")
    classes = np.asarray(model.cell_types, dtype=str)
    if len(classes) < 2 or len(set(classes)) != len(classes):
        raise ValueError("CellTypist model cell types must contain at least two unique labels.")
    if CELLTYPIST_THRESHOLD_UNASSIGNED_SENTINEL in classes:
        raise ValueError("CellTypist model contains a reserved internal cell-type label.")

    classifier = model.classifier
    scaler = model.scaler
    coefficients = np.asarray(classifier.coef_, dtype=float)
    if coefficients.ndim != 2 or coefficients.shape[1] != len(features):
        raise ValueError("CellTypist classifier coefficients do not match the model features.")
    scale = np.asarray(scaler.scale_, dtype=float)
    if scale.shape != (len(features),) or not np.isfinite(scale).all() or np.any(scale <= 0):
        raise ValueError("CellTypist scaler contains invalid feature scales.")
    with_mean = bool(scaler.with_mean)
    if with_mean:
        means = np.asarray(scaler.mean_, dtype=float)
        if means.shape != (len(features),) or not np.isfinite(means).all():
            raise ValueError("CellTypist scaler contains invalid feature means.")
    else:
        means = np.zeros(len(features), dtype=float)

    feature_positions = {feature: index for index, feature in enumerate(features)}
    query_feature_indices: list[int] = []
    model_feature_indices: list[int] = []
    for query_index, feature in enumerate(query.var_names.astype(str)):
        model_index = feature_positions.get(feature)
        if model_index is not None:
            query_feature_indices.append(query_index)
            model_feature_indices.append(model_index)
    if not query_feature_indices:
        raise ValueError("No query genes overlap the CellTypist model.")

    query_indices = np.asarray(query_feature_indices, dtype=np.int64)
    model_indices = np.asarray(model_feature_indices, dtype=np.int64)
    selected_coefficients = coefficients[:, model_indices]
    selected_scale = scale[model_indices]
    selected_means = means[model_indices]
    intercept = np.asarray(classifier.intercept_, dtype=float).reshape(1, -1)
    if intercept.shape[1] != coefficients.shape[0] or not np.isfinite(intercept).all():
        raise ValueError("CellTypist classifier intercepts do not match its coefficients.")

    query_is_sparse = sparse.issparse(query.X)
    batch_width = max(len(classes), len(query_indices))
    batch_size = max(
        1,
        min(
            query.n_obs,
            CELLTYPIST_MAX_INFERENCE_BATCH_CELLS,
            CELLTYPIST_MAX_INFERENCE_BATCH_ELEMENTS // batch_width,
        ),
    )

    def probability_batches():
        for start in range(0, query.n_obs, batch_size):
            stop = min(start + batch_size, query.n_obs)
            expression = query.X[start:stop, query_indices]
            if sparse.issparse(expression) and not with_mean:
                scaled = expression.tocsr(copy=True).multiply(1.0 / selected_scale).tocsr()
                scaled.data[scaled.data > 10] = 10
            else:
                if sparse.issparse(expression):
                    scaled = expression.toarray()
                else:
                    scaled = np.asarray(expression, dtype=float).copy()
                scaled = (scaled - selected_means) / selected_scale
                np.minimum(scaled, 10, out=scaled)

            scores = np.asarray(scaled @ selected_coefficients.T, dtype=float) + intercept
            if coefficients.shape[0] == 1 and len(classes) == 2:
                binary_scores = scores.reshape(-1)
                scores = np.column_stack((-binary_scores, binary_scores))
            elif scores.shape[1] != len(classes):
                raise ValueError(
                    "CellTypist classifier score dimensions do not match its cell types."
                )
            probabilities = expit(scores)
            if not np.isfinite(probabilities).all():
                raise ValueError("CellTypist produced non-finite prediction probabilities.")
            yield start, stop, probabilities

    labels = np.empty(query.n_obs, dtype=object)
    threshold_unassigned = np.zeros(query.n_obs, dtype=bool)
    raw_confidence = np.empty(query.n_obs, dtype=float)
    for start, stop, probabilities in probability_batches():
        raw_confidence[start:stop] = probabilities.max(axis=1)
        if mode == "best match":
            labels[start:stop] = classes[probabilities.argmax(axis=1)]
        else:
            threshold_flags = probabilities > p_thres
            threshold_unassigned[start:stop] = ~threshold_flags.any(axis=1)
            labels[start:stop] = [
                "|".join(classes[row_flags]) or "Unassigned" for row_flags in threshold_flags
            ]

    inference_passes = 1
    n_confidence_fallbacks = 0
    if majority_voting:
        if over_clustering is None or len(over_clustering) != query.n_obs:
            raise ValueError(
                "CellTypist majority voting requires one over-clustering label per query cell."
            )
        clusters = pd.Series(np.asarray(over_clustering, dtype=str), dtype="string")
        if clusters.isna().any() or clusters.str.strip().eq("").any():
            raise ValueError("CellTypist over-clustering labels must be complete.")
        vote_labels = labels.copy()
        vote_labels[threshold_unassigned] = CELLTYPIST_THRESHOLD_UNASSIGNED_SENTINEL
        votes = pd.crosstab(pd.Series(vote_labels, dtype="string"), clusters)
        if votes.empty:
            raise ValueError("CellTypist majority voting received no cluster votes.")
        majority_by_cluster = votes.idxmax(axis=0).astype(str)
        majority_labels = np.asarray(
            [majority_by_cluster[cluster] for cluster in clusters],
            dtype=object,
        )
        threshold_unassigned = majority_labels == CELLTYPIST_THRESHOLD_UNASSIGNED_SENTINEL
        labels = majority_labels.copy()
        labels[threshold_unassigned] = "Unassigned"

        class_positions = {label: index for index, label in enumerate(classes)}
        confidence = raw_confidence.copy()
        for start, stop, probabilities in probability_batches():
            for offset, label in enumerate(labels[start:stop]):
                position = start + offset
                class_index = (
                    None if threshold_unassigned[position] else class_positions.get(str(label))
                )
                if class_index is not None:
                    confidence[position] = probabilities[offset, class_index]
                else:
                    n_confidence_fallbacks += 1
        inference_passes = 2
    else:
        confidence = raw_confidence
    if not np.isfinite(confidence).all():
        raise ValueError("CellTypist returned non-finite prediction confidence values.")
    prediction_column = "majority_voting" if majority_voting else "predicted_labels"
    return (
        labels.astype(str),
        confidence,
        prediction_column,
        threshold_unassigned,
        {
            "implementation": "tissueagent_batched_celltypist_logistic_v1",
            "batch_size": int(batch_size),
            "n_batches_per_pass": int((query.n_obs + batch_size - 1) // batch_size),
            "n_inference_passes": inference_passes,
            "scaler_with_mean": with_mean,
            "sparse_query_matrix": query_is_sparse,
            "n_matched_features": int(len(query_indices)),
            "n_threshold_unassigned": int(np.count_nonzero(threshold_unassigned)),
            "n_confidence_fallbacks": n_confidence_fallbacks,
            "confidence_definition": (
                "probability_of_majority_label_with_maximum_class_probability_fallback"
                if majority_voting and n_confidence_fallbacks
                else (
                    "probability_of_majority_label"
                    if majority_voting
                    else "maximum_class_probability"
                )
            ),
        },
    )


def _attach_predictions(
    output: ad.AnnData,
    annotated_obs_names: pd.Index,
    labels: np.ndarray,
    confidence: np.ndarray,
    threshold_unassigned: np.ndarray,
) -> dict[str, int]:
    if (
        len(labels) != len(annotated_obs_names)
        or len(confidence) != len(annotated_obs_names)
        or len(threshold_unassigned) != len(annotated_obs_names)
    ):
        raise ValueError("Prediction arrays do not match the CellTypist query subset.")
    positions = output.obs_names.get_indexer(annotated_obs_names)
    if np.any(positions < 0) or len(np.unique(positions)) != len(positions):
        raise ValueError("CellTypist query subset does not map uniquely to the original query.")

    prediction_values = np.empty(output.n_obs, dtype=object)
    prediction_values[:] = None
    confidence_values = np.full(output.n_obs, np.nan)
    status_values = np.full(output.n_obs, "excluded_from_annotation", dtype=object)
    reason_values = np.full(output.n_obs, "zero_expression", dtype=object)
    prediction_values[positions] = labels.astype(str)
    confidence_values[positions] = confidence
    status_values[positions] = np.where(threshold_unassigned, "unassigned", "annotated")
    reason_values[positions] = np.where(
        threshold_unassigned,
        "celltypist_probability_threshold",
        "not_excluded",
    )

    categories = sorted(
        {str(value) for value in prediction_values if value is not None},
        key=str.casefold,
    )
    categorical_labels = pd.Categorical(prediction_values, categories=categories)
    annotation_status = pd.Categorical(
        status_values,
        categories=["annotated", "unassigned", "excluded_from_annotation"],
    )
    exclusion_reason = pd.Categorical(reason_values)
    method = pd.Categorical(["celltypist"] * output.n_obs)

    output.obs["celltypist_predicted_cell_type"] = categorical_labels
    output.obs["celltypist_prediction_confidence"] = confidence_values
    output.obs["celltypist_status"] = annotation_status
    output.obs["celltypist_exclusion_reason"] = exclusion_reason
    output.obs["cell_annotation_predicted_cell_type"] = categorical_labels
    output.obs["cell_annotation_prediction_confidence"] = confidence_values
    output.obs["cell_annotation_status"] = annotation_status
    output.obs["cell_annotation_exclusion_reason"] = exclusion_reason
    output.obs["cell_annotation_method"] = method
    output.obs["label"] = categorical_labels
    return {
        "n_annotated_cells": int(np.count_nonzero(status_values == "annotated")),
        "n_unassigned_cells": int(np.count_nonzero(status_values == "unassigned")),
        "n_excluded_cells": int(np.count_nonzero(status_values == "excluded_from_annotation")),
    }


def _publish_temp_exclusively(temporary_path: Path, output_path: Path) -> None:
    try:
        os.link(temporary_path, output_path)
    except FileExistsError as exc:
        raise FileExistsError(f"Refusing to overwrite existing artifact: {output_path}") from exc
    finally:
        temporary_path.unlink(missing_ok=True)


def _write_model_exclusively(model: Any, output_path: Path) -> None:
    temporary_path = output_path.with_name(f".{output_path.stem}.{uuid4().hex}.tmp.pkl")
    try:
        model.write(str(temporary_path))
        if not temporary_path.is_file() or temporary_path.stat().st_size == 0:
            raise OSError(f"CellTypist did not write the custom model to {temporary_path}.")
        _publish_temp_exclusively(temporary_path, output_path)
    finally:
        temporary_path.unlink(missing_ok=True)


def _write_h5ad_exclusively(dataset: ad.AnnData, output_path: Path) -> None:
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


def _write_json_exclusively(payload: dict[str, Any], output_path: Path) -> None:
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


def _output_columns_are_available(dataset: ad.AnnData) -> None:
    collisions = sorted(set(ANNOTATION_COLUMNS).intersection(dataset.obs.columns))
    if collisions:
        raise ValueError(
            "Query .obs already contains CellTypist output-contract columns: "
            + ", ".join(collisions)
        )
    if "tissueagent_cell_annotation" in dataset.uns:
        raise ValueError(
            "Query .uns already contains 'tissueagent_cell_annotation'; refusing to replace "
            "prior annotation provenance."
        )


def celltypist_annotation_tool(
    spatial_anndata_path: str,
    output_path: str,
    selection_rationale: str,
    model_name: str | None = None,
    reference_anndata_path: str | None = None,
    cell_type_column: str = "cell_type",
    majority_voting: bool = False,
    mode: str = "best match",
    p_thres: float = 0.5,
    n_jobs: int = 1,
    min_feature_overlap: int = 50,
    execution_contract: dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Annotate a cell-resolved query with an explicit CellTypist label source."""
    start_time = time.monotonic()
    operation = "celltypist_annotation"

    if not isinstance(selection_rationale, str) or not selection_rationale.strip():
        return _error_result(
            "validate_selection",
            ValueError("selection_rationale must be a non-empty string."),
        )
    if len(selection_rationale.strip()) > 4_000:
        return _error_result(
            "validate_selection",
            ValueError("selection_rationale must contain at most 4000 characters."),
        )
    if model_name is not None and not isinstance(model_name, str):
        return _error_result(
            "validate_label_source",
            ValueError("model_name must be None or a CellTypist catalog filename."),
        )
    if reference_anndata_path is not None and not isinstance(reference_anndata_path, str):
        return _error_result(
            "validate_label_source",
            ValueError("reference_anndata_path must be None or a non-empty string."),
        )
    selected_model = model_name.strip() if isinstance(model_name, str) else None
    selected_reference = (
        reference_anndata_path.strip() if isinstance(reference_anndata_path, str) else None
    )
    if bool(selected_model) == bool(selected_reference):
        return _error_result(
            "validate_label_source",
            ValueError("Provide exactly one of model_name or reference_anndata_path, never both."),
        )
    if mode not in {"best match", "prob match"}:
        return _error_result(
            "validate_parameters",
            ValueError("mode must be either 'best match' or 'prob match'."),
        )
    if isinstance(p_thres, bool) or not isinstance(p_thres, (int, float)) or not 0 <= p_thres <= 1:
        return _error_result(
            "validate_parameters",
            ValueError("p_thres must be a number between 0 and 1."),
        )
    if isinstance(n_jobs, bool) or not isinstance(n_jobs, int) or n_jobs == 0 or n_jobs < -1:
        return _error_result(
            "validate_parameters",
            ValueError("n_jobs must be -1 or a positive integer."),
        )
    if (
        isinstance(min_feature_overlap, bool)
        or not isinstance(min_feature_overlap, int)
        or min_feature_overlap < 1
    ):
        return _error_result(
            "validate_parameters",
            ValueError("min_feature_overlap must be a positive integer."),
        )
    if not isinstance(majority_voting, bool):
        return _error_result(
            "validate_parameters",
            ValueError("majority_voting must be a boolean."),
        )
    if not isinstance(cell_type_column, str) or not cell_type_column.strip():
        return _error_result(
            "validate_parameters",
            ValueError("cell_type_column must be a non-empty string."),
        )

    try:
        spatial_path = _resolve_path(spatial_anndata_path, must_exist=True)
        annotated_path = _resolve_path(output_path, must_exist=False)
        if spatial_path.suffix.casefold() != ".h5ad":
            raise ValueError("spatial_anndata_path must resolve to an .h5ad file.")
        if annotated_path.suffix.casefold() != ".h5ad":
            raise ValueError("output_path must end with '.h5ad'.")
        reference_path = (
            _resolve_path(selected_reference, must_exist=True) if selected_reference else None
        )
        if reference_path is not None and reference_path.suffix.casefold() != ".h5ad":
            raise ValueError("reference_anndata_path must resolve to an .h5ad file.")
        if reference_path is not None and spatial_path.samefile(reference_path):
            raise ValueError(
                "reference_anndata_path must not resolve to the query itself; self-training "
                "would leak query labels into predictions."
            )
        cache_path = _resolve_path(CELLTYPIST_CACHE_PATH, must_exist=False)
    except Exception as exc:
        return _error_result("resolve_paths", exc)

    annotated_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path = annotated_path.with_suffix(".run_meta.json")
    custom_model_path = (
        annotated_path.with_suffix(".celltypist_model.pkl") if reference_path is not None else None
    )
    protected_paths = [annotated_path, meta_path]
    if custom_model_path is not None:
        protected_paths.append(custom_model_path)
    existing_paths = [path for path in protected_paths if path.exists()]
    if existing_paths:
        return _error_result(
            "validate_output_path",
            FileExistsError(
                "Existing output artifacts would be overwritten: "
                + ", ".join(workspace_relative(path) for path in existing_paths)
            ),
        )

    diagnostics: dict[str, Any] = {}
    created_paths: list[Path] = []
    restore_celltypist_configuration: Callable[[], None] | None = None
    stage = "validate_output_path"
    try:
        existing_paths = [path for path in protected_paths if path.exists()]
        if existing_paths:
            raise FileExistsError(
                "Existing output artifacts would be overwritten: "
                + ", ".join(workspace_relative(path) for path in existing_paths)
            )

        stage = "inspect_spatial_expression"
        spatial_inspection = _inspect_expression_matrix(spatial_path, role="spatial")
        diagnostics["spatial_expression"] = spatial_inspection

        stage = "load_spatial"
        spatial_original = ad.read_h5ad(spatial_path)
        if spatial_original.n_obs == 0 or spatial_original.n_vars == 0:
            raise ValueError(f"Query AnnData is empty: shape={spatial_original.shape}.")
        if not spatial_original.obs_names.is_unique:
            raise ValueError("Query observation identifiers must be unique.")
        original_obs_names = pd.Index(spatial_original.obs_names.copy())
        _output_columns_are_available(spatial_original)

        stage = "prepare_spatial_expression"
        spatial_working, spatial_preprocessing = _prepare_expression(
            spatial_original,
            spatial_inspection,
            role="spatial",
        )
        diagnostics["spatial_preprocessing"] = spatial_preprocessing
        spatial_nonzero_mask = _nonzero_observation_mask(spatial_working)
        if not np.any(spatial_nonzero_mask):
            raise ValueError("Query expression contains no nonzero observations.")
        spatial_annotation = spatial_working[spatial_nonzero_mask, :].copy()
        spatial_preprocessing["n_zero_expression_observations"] = int(
            np.count_nonzero(~spatial_nonzero_mask)
        )

        stage = "initialize_celltypist"
        celltypist, models, restore_celltypist_configuration = _load_celltypist(cache_path)

        reference_inspection = None
        reference_preprocessing = None
        reference_label_counts = None
        custom_training_metadata = None
        try:
            if selected_model:
                label_source = "celltypist_builtin"
                stage = "download_builtin_model"
                model, model_path, model_metadata = _load_builtin_model(models, selected_model)
            else:
                label_source = "reference"
                if reference_path is None:
                    raise ValueError("Internal error: missing selected reference path.")
                stage = "inspect_reference_expression"
                reference_inspection = _inspect_expression_matrix(reference_path, role="reference")
                diagnostics["reference_expression"] = reference_inspection

                stage = "load_reference"
                reference_original = ad.read_h5ad(reference_path)
                if reference_original.n_obs == 0 or reference_original.n_vars == 0:
                    raise ValueError(
                        f"Reference AnnData is empty: shape={reference_original.shape}."
                    )
                if not reference_original.obs_names.is_unique:
                    raise ValueError("Reference observation identifiers must be unique.")
                reference_label_counts = _validate_reference_labels(
                    reference_original,
                    cell_type_column,
                )

                stage = "prepare_reference_expression"
                reference_working, reference_preprocessing = _prepare_expression(
                    reference_original,
                    reference_inspection,
                    role="reference",
                )
                diagnostics["reference_preprocessing"] = reference_preprocessing
                reference_nonzero_mask = _nonzero_observation_mask(reference_working)
                n_zero_reference = int(np.count_nonzero(~reference_nonzero_mask))
                reference_preprocessing["n_zero_expression_observations"] = n_zero_reference
                if n_zero_reference:
                    raise ValueError(
                        f"Reference contains {n_zero_reference} zero-expression observations; "
                        "remove them before custom CellTypist training."
                    )

                stage = "train_reference_model"
                model, custom_training_metadata = _train_reference_model(
                    celltypist,
                    reference_working,
                    reference_path=reference_path,
                    cell_type_column=cell_type_column,
                    n_jobs=n_jobs,
                )
                model_path = custom_model_path
                if model_path is None:
                    raise ValueError("Internal error: missing custom model output path.")
                model_metadata = {
                    "catalog_description": "",
                    "description": _safe_model_description(model.description),
                }
        finally:
            if restore_celltypist_configuration is not None:
                restore_celltypist_configuration()
                restore_celltypist_configuration = None

        stage = "align_and_validate_features"
        feature_overlap = _align_query_gene_case(spatial_annotation, model.features)
        diagnostics["feature_overlap"] = feature_overlap
        if feature_overlap["n_matched_features"] < min_feature_overlap:
            raise ValueError(
                f"Only {feature_overlap['n_matched_features']} query genes overlap the selected "
                f"CellTypist model; at least {min_feature_overlap} are required."
            )

        over_clustering = None
        clustering_metadata = None
        if majority_voting:
            stage = "create_transcriptomic_over_clustering"
            over_clustering, clustering_metadata = _create_transcriptomic_overclustering(
                spatial_annotation
            )

        stage = "annotate_query"
        (
            labels,
            confidence,
            prediction_column,
            threshold_unassigned,
            inference_metadata,
        ) = _run_celltypist_inference(
            model,
            spatial_annotation,
            mode=mode,
            p_thres=float(p_thres),
            majority_voting=majority_voting,
            over_clustering=over_clustering,
        )

        stage = "attach_predictions"
        output = spatial_original.copy()
        if not pd.Index(output.obs_names).equals(original_obs_names):
            raise ValueError("The output query observation order changed before annotation.")
        attachment_summary = _attach_predictions(
            output,
            pd.Index(spatial_annotation.obs_names),
            labels,
            confidence,
            threshold_unassigned,
        )
        if output.n_obs != len(original_obs_names) or not pd.Index(output.obs_names).equals(
            original_obs_names
        ):
            raise ValueError("The annotated output does not preserve the original query rows.")

        stage = "write_model"
        if custom_model_path is not None:
            _write_model_exclusively(model, custom_model_path)
            created_paths.append(custom_model_path)
        if model_path is None:
            raise ValueError("Internal error: missing model artifact path.")
        model_sha256 = _sha256(model_path)
        model_description = model_metadata["description"]

        provenance: dict[str, Any] = {
            "annotation_method": "celltypist",
            "label_source": label_source,
            "selection_rationale": selection_rationale.strip(),
            "mode": mode,
            "majority_voting": majority_voting,
            "prediction_column": prediction_column,
            "model_name": selected_model or "reference_trained",
            "model_version": str(model_description.get("version", "")),
            "model_source": str(model_description.get("source", "")),
            "model_details": str(
                model_description.get("details", model_metadata["catalog_description"])
            ),
            "model_artifact": workspace_relative(model_path),
            "model_sha256": model_sha256,
            "n_model_features": feature_overlap["n_model_features"],
            "n_matched_features": feature_overlap["n_matched_features"],
            "min_feature_overlap": min_feature_overlap,
            "n_case_aligned_query_genes": feature_overlap["n_case_aligned_query_genes"],
            "run_meta_json": workspace_relative(meta_path),
            "confidence_available": True,
            "confidence_definition": inference_metadata["confidence_definition"],
            "n_zero_expression_observations": int(np.count_nonzero(~spatial_nonzero_mask)),
            "inference_implementation": inference_metadata["implementation"],
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
        }
        if reference_path is not None:
            provenance["reference_anndata_path"] = workspace_relative(reference_path)
            provenance["reference_cell_type_column"] = cell_type_column
        output.uns["tissueagent_cell_annotation"] = provenance

        cell_type_counts = {
            str(label): int(count)
            for label, count in pd.Series(labels, dtype="object").value_counts().items()
        }
        metadata = {
            "status": "success",
            "operation": operation,
            "method": "celltypist",
            "annotation_method": "celltypist",
            "label_source": label_source,
            "selection_rationale": selection_rationale.strip(),
            "execution_contract": execution_contract,
            "runtime": {
                "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "duration_seconds": float(time.monotonic() - start_time),
                "celltypist_version": str(celltypist.__version__),
            },
            "parameters": {
                "model_name": selected_model,
                "cell_type_column": cell_type_column,
                "majority_voting": majority_voting,
                "mode": mode,
                "p_thres": float(p_thres),
                "n_jobs": n_jobs,
                "min_feature_overlap": min_feature_overlap,
                "custom_training": custom_training_metadata,
            },
            "inputs": {
                "spatial_anndata_path": workspace_relative(spatial_path),
                "reference_anndata_path": (
                    workspace_relative(reference_path) if reference_path is not None else None
                ),
            },
            "expression_inspection": {
                "spatial": spatial_inspection,
                "reference": reference_inspection,
            },
            "preprocessing": {
                "spatial": spatial_preprocessing,
                "reference": reference_preprocessing,
            },
            "model": {
                "artifact_path": workspace_relative(model_path),
                "sha256": model_sha256,
                "catalog_description": model_metadata["catalog_description"],
                "description": model_description,
                "n_cell_types": int(len(model.cell_types)),
                "cell_types": [str(value) for value in model.cell_types],
                "custom_training": custom_training_metadata,
            },
            "feature_overlap": feature_overlap,
            "inference": inference_metadata,
            "majority_voting_clustering": clustering_metadata,
            "reference_label_counts": reference_label_counts,
            "outputs": {
                "annotated_object_h5ad": workspace_relative(annotated_path),
                "run_meta_json": workspace_relative(meta_path),
                "custom_model_pkl": (
                    workspace_relative(custom_model_path) if custom_model_path is not None else None
                ),
            },
            "summary": {
                "n_input_cells": int(len(original_obs_names)),
                "n_output_cells": int(output.n_obs),
                **attachment_summary,
                "n_unique_cell_types": int(len(cell_type_counts)),
                "cell_type_counts": cell_type_counts,
                "mean_confidence": float(np.mean(confidence)),
                "min_confidence": float(np.min(confidence)),
                "max_confidence": float(np.max(confidence)),
                "annotation_columns": list(ANNOTATION_COLUMNS),
            },
        }

        stage = "write_annotated_h5ad"
        _write_h5ad_exclusively(output, annotated_path)
        created_paths.append(annotated_path)
        stage = "write_run_metadata"
        _write_json_exclusively(metadata, meta_path)
        created_paths.append(meta_path)

        return {
            "status": "success",
            "operation": operation,
            "method": "celltypist",
            "annotation_method": "celltypist",
            "label_source": label_source,
            "selection_rationale": selection_rationale.strip(),
            "execution_contract": execution_contract,
            "annotated_object_h5ad": workspace_relative(annotated_path),
            "run_meta_json": workspace_relative(meta_path),
            "model_artifact": workspace_relative(model_path),
            "model_sha256": model_sha256,
            "n_input_cells": int(len(original_obs_names)),
            "n_output_cells": int(output.n_obs),
            **attachment_summary,
            "n_unique_cell_types": int(len(cell_type_counts)),
            "cell_type_counts": cell_type_counts,
            "mean_confidence": float(np.mean(confidence)),
            "n_matched_features": feature_overlap["n_matched_features"],
            "min_feature_overlap": min_feature_overlap,
            "majority_voting": majority_voting,
            "prediction_column": prediction_column,
        }
    except Exception as exc:
        if restore_celltypist_configuration is not None:
            restore_celltypist_configuration()
        for path in reversed(created_paths):
            path.unlink(missing_ok=True)
        return _error_result(stage, exc, **diagnostics)
