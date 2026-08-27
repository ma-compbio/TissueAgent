"""Harmony-based label transfer from reference to spatial transcriptomics data."""

from __future__ import annotations

from typing import Any, Dict
from pathlib import Path
import json
import logging
import re
import time
import anndata as ad
import scanpy as sc
import pandas as pd
import numpy as np
from scipy import sparse
from sklearn.neural_network import MLPClassifier
from sklearn.neighbors import KNeighborsClassifier
from sklearn.preprocessing import StandardScaler
import mygene

from agents.workspace_paths import (
    resolve_project_output,
    resolve_workspace_input,
    workspace_relative,
)


ENSEMBL_GENE_RE = re.compile(r"^ENS[A-Z0-9]*G\d+", re.IGNORECASE)
GENE_SYMBOL_COLUMNS = (
    "gene_symbol",
    "gene_symbols",
    "feature_name",
    "SYMBOL",
    "symbol",
    "gene_name",
)
GENE_ID_COLUMNS = (
    "gene_id",
    "feature_id",
    "ENSEMBL",
    "ensembl",
    "ensembl_id",
)
SPECIES_ALIASES = {
    "homo sapiens": "human",
    "human": "human",
    "9606": "9606",
    "mus musculus": "mouse",
    "mouse": "mouse",
    "10090": "10090",
    "rattus norvegicus": "rat",
    "rat": "rat",
    "10116": "10116",
    "danio rerio": "zebrafish",
    "zebrafish": "zebrafish",
    "7955": "7955",
    "drosophila melanogaster": "fruitfly",
    "fruitfly": "fruitfly",
    "7227": "7227",
    "caenorhabditis elegans": "nematode",
    "nematode": "nematode",
    "6239": "6239",
}
DETECTED_GENE_QC_MAX_ROWS = 256
HARMONY_PCA_FEATURE_MASK = "_tissueagent_harmony_pca_feature"


def _resolve_path(path_like: str, *, must_exist: bool) -> Path:
    """Resolve a user-provided path inside the workspace.

    For inputs (``must_exist=True``) the function tries multiple common
    roots so the agent can pass a bare filename and we'll find the file
    wherever it lives: library/datasets/, library/files/, the active
    project's uploads/ / outputs/, or the legacy dataset/ root.

    For outputs (``must_exist=False``) the path is anchored under the
    active project's outputs/ directory. Absolute paths are accepted
    but must resolve inside the workspace.
    """
    if must_exist:
        return resolve_workspace_input(path_like)
    return resolve_project_output(path_like)


def _resolve_output_h5ad_path(
    *,
    output_dir: str,
    output_path: str | None,
    output_filename: str | None,
    input_stem: str,
) -> Path:
    if output_path is None and str(output_dir).lower().endswith(".h5ad"):
        output_path = output_dir

    if output_path is not None:
        resolved_output_path = _resolve_path(output_path, must_exist=False)
        if resolved_output_path.suffix != ".h5ad":
            raise ValueError("output_path must end with '.h5ad'.")
        return resolved_output_path

    output_dir_path = _resolve_path(output_dir, must_exist=False)
    output_filename = output_filename or f"{input_stem}_annotated.h5ad"
    filename_path = Path(output_filename)
    if filename_path.is_absolute() or filename_path.name != output_filename:
        raise ValueError("output_filename must be a file name, not a path.")
    if filename_path.suffix != ".h5ad":
        raise ValueError("output_filename must end with '.h5ad'.")

    return resolve_project_output(
        f"{workspace_relative(output_dir_path)}/{filename_path.name}", suffix=".h5ad"
    )


def _default_artifact_stem(input_path: Path) -> str:
    raw_stem = f"{input_path.parent.name}_{input_path.stem}"
    return re.sub(r"[^A-Za-z0-9._-]+", "_", raw_stem).strip("._-") or "spatial"


def _write_h5ad_atomically(dataset: ad.AnnData, output_path: Path) -> None:
    temporary_path = output_path.with_name(f".{output_path.stem}.tmp{output_path.suffix}")
    previous_allow_nullable_strings = ad.settings.allow_write_nullable_strings
    try:
        temporary_path.unlink(missing_ok=True)
        ad.settings.allow_write_nullable_strings = True
        dataset.write_h5ad(temporary_path, compression="gzip")
        temporary_path.replace(output_path)
    finally:
        ad.settings.allow_write_nullable_strings = previous_allow_nullable_strings
        temporary_path.unlink(missing_ok=True)


def _evenly_spaced_indices(length: int, maximum: int) -> np.ndarray:
    """Return deterministic sorted indices without materializing a large axis."""
    if length <= maximum:
        return np.arange(length, dtype=np.int64)
    return np.unique(np.linspace(0, length - 1, num=maximum, dtype=np.int64))


def _detected_gene_summary(dataset: ad.AnnData, maximum_rows: int) -> dict[str, Any]:
    row_indices = _evenly_spaced_indices(
        dataset.n_obs, min(maximum_rows, DETECTED_GENE_QC_MAX_ROWS)
    )
    matrix = dataset[row_indices, :].to_memory().X
    if sparse.issparse(matrix):
        detected = np.asarray((matrix != 0).sum(axis=1)).ravel()
    else:
        detected = np.count_nonzero(np.asarray(matrix), axis=1)
    quantiles = np.quantile(detected, [0.05, 0.25, 0.5, 0.75, 0.95])
    return {
        "sampled_rows": int(len(row_indices)),
        "total_genes": int(dataset.n_vars),
        "minimum": int(detected.min()),
        "p05": float(quantiles[0]),
        "p25": float(quantiles[1]),
        "median": float(quantiles[2]),
        "p75": float(quantiles[3]),
        "p95": float(quantiles[4]),
        "maximum": int(detected.max()),
        "zero_expression_rows": int(np.count_nonzero(detected == 0)),
        "zero_expression_fraction": float(np.mean(detected == 0)),
    }


def _inspect_expression_matrix(
    path: Path,
    *,
    role: str,
    max_rows: int = 2048,
    max_columns: int = 2048,
) -> dict[str, Any]:
    """Classify a bounded, deterministic AnnData sample as count-like or processed."""
    dataset = ad.read_h5ad(path, backed="r")
    try:
        if dataset.n_obs == 0 or dataset.n_vars == 0:
            raise ValueError(f"{role} AnnData is empty: shape={dataset.shape}.")
        row_indices = _evenly_spaced_indices(dataset.n_obs, max_rows)
        # Backed AnnData/HDF5 permits only one fancy-indexed axis. Sampling rows
        # across the complete observation axis and a bounded contiguous gene
        # slice keeps the read deterministic and memory-bounded.
        column_slice = slice(0, min(dataset.n_vars, max_columns))
        matrix = dataset[row_indices, column_slice].to_memory().X
        if sparse.issparse(matrix):
            values = matrix.data.astype(np.float64, copy=False)
            sampled_entries = int(matrix.shape[0] * matrix.shape[1])
        else:
            dense = np.asarray(matrix, dtype=np.float64)
            values = dense.ravel()
            sampled_entries = int(dense.size)

        finite_values = values[np.isfinite(values)]
        nonzero_values = finite_values[finite_values != 0]
        sampled_nonzero = int(nonzero_values.size)
        nonfinite_values = int(values.size - finite_values.size)
        negative_fraction = float(np.mean(nonzero_values < 0)) if nonzero_values.size else 0.0
        integer_like_fraction = (
            float(np.mean(np.isclose(nonzero_values, np.rint(nonzero_values), atol=1e-6, rtol=0)))
            if nonzero_values.size
            else None
        )
        log1p_metadata = "log1p" in dataset.uns
        log1p_base = None
        if log1p_metadata and isinstance(dataset.uns["log1p"], dict):
            configured_base = dataset.uns["log1p"].get("base")
            if configured_base is not None:
                log1p_base = float(configured_base)
        layer_names = sorted(str(name) for name in dataset.layers.keys())
        detected_genes = _detected_gene_summary(dataset, max_rows)
        processed_expression_state = None

        if nonfinite_values:
            state = "invalid"
            confidence = "high"
            rationale = f"The sampled matrix contains {nonfinite_values} non-finite stored values."
        elif nonzero_values.size == 0:
            state = "ambiguous"
            confidence = "low"
            rationale = "The bounded sample contains no nonzero expression values."
        elif negative_fraction > 0:
            state = "processed_continuous"
            processed_expression_state = "scaled_or_centered"
            confidence = "high"
            rationale = (
                "Negative expression values are incompatible with counts or log1p-normalized "
                "expression and indicate scaling, centering, or another signed transform."
            )
        elif log1p_metadata:
            state = "processed_continuous"
            processed_expression_state = "log1p_normalized"
            confidence = "high"
            rationale = "AnnData .uns contains explicit log1p preprocessing metadata."
        elif integer_like_fraction is not None and integer_like_fraction >= 0.99:
            state = "raw_count_like"
            confidence = "high"
            rationale = (
                f"{integer_like_fraction:.3%} of sampled nonzero values are integer-like and "
                "all sampled values are nonnegative."
            )
        elif integer_like_fraction is not None and integer_like_fraction <= 0.05:
            state = "processed_continuous"
            processed_expression_state = "nonnegative_continuous_unknown"
            confidence = "high"
            rationale = (
                f"Only {integer_like_fraction:.3%} of sampled nonzero values are integer-like, "
                "indicating nonnegative normalized or otherwise processed expression without "
                "explicit transform metadata."
            )
        else:
            state = "ambiguous"
            confidence = "low"
            rationale = (
                f"The sampled integer-like fraction ({integer_like_fraction:.3%}) is not "
                "decisive for raw counts versus processed expression."
            )

        return {
            "role": role,
            "path": workspace_relative(path),
            "shape": [int(dataset.n_obs), int(dataset.n_vars)],
            "matrix_dtype": str(dataset.X.dtype),
            "sampled_rows": int(len(row_indices)),
            "sampled_columns": int(matrix.shape[1]),
            "sampled_entries": sampled_entries,
            "sampled_stored_values": int(values.size),
            "sampled_nonzero_values": sampled_nonzero,
            "sampled_nonfinite_stored_values": nonfinite_values,
            "sampled_negative_fraction": negative_fraction,
            "sampled_integer_like_fraction": integer_like_fraction,
            "sampled_nonzero_min": float(nonzero_values.min()) if nonzero_values.size else None,
            "sampled_nonzero_median": (
                float(np.median(nonzero_values)) if nonzero_values.size else None
            ),
            "sampled_nonzero_max": float(nonzero_values.max()) if nonzero_values.size else None,
            "log1p_metadata_present": log1p_metadata,
            "log1p_base": log1p_base,
            "raw_attribute_present": dataset.raw is not None,
            "layers": layer_names,
            "detected_genes_per_observation": detected_genes,
            "expression_state": state,
            "processed_expression_state": processed_expression_state,
            "confidence": confidence,
            "rationale": rationale,
        }
    finally:
        dataset.file.close()


def inspect_anndata_preprocessing_tool(
    spatial_anndata_path: str,
    reference_anndata_path: str,
    max_rows: int = 2048,
    max_columns: int = 2048,
) -> Dict[str, Any]:
    """Inspect both matrices so the agent can make an explicit preprocessing decision."""
    operation = "inspect_anndata_preprocessing"
    if max_rows < 1 or max_columns < 1:
        return {
            "status": "error",
            "operation": operation,
            "stage": "validate_sampling_parameters",
            "error_type": "ValueError",
            "message": "max_rows and max_columns must both be at least 1.",
        }
    try:
        spatial_path = _resolve_path(spatial_anndata_path, must_exist=True)
        reference_path = _resolve_path(reference_anndata_path, must_exist=True)
    except Exception as exc:
        return _error_result("inspect_expression_state", exc, operation=operation)

    return _inspect_anndata_preprocessing_paths(
        spatial_path,
        reference_path,
        max_rows=max_rows,
        max_columns=max_columns,
    )


def _inspect_anndata_preprocessing_paths(
    spatial_path: Path,
    reference_path: Path,
    *,
    max_rows: int,
    max_columns: int,
) -> Dict[str, Any]:
    operation = "inspect_anndata_preprocessing"
    try:
        spatial = _inspect_expression_matrix(
            spatial_path,
            role="spatial",
            max_rows=max_rows,
            max_columns=max_columns,
        )
        reference = _inspect_expression_matrix(
            reference_path,
            role="reference",
            max_rows=max_rows,
            max_columns=max_columns,
        )
    except Exception as exc:
        return _error_result("inspect_expression_state", exc, operation=operation)

    states = {spatial["expression_state"], reference["expression_state"]}
    if states == {"raw_count_like"}:
        return {
            "status": "success",
            "operation": operation,
            "decision": "preprocess_both",
            "recommended_skip_preprocessing": False,
            "recommended_preprocess_spatial": True,
            "recommended_preprocess_reference": True,
            "spatial": spatial,
            "reference": reference,
            "rationale": (
                "Both matrices are nonnegative and strongly count-like. Run the standard "
                "filter, total-normalization, and log1p preprocessing on working copies."
            ),
        }
    if states == {"processed_continuous"}:
        spatial_processed_state = spatial["processed_expression_state"]
        reference_processed_state = reference["processed_expression_state"]
        if spatial_processed_state != reference_processed_state:
            return {
                "status": "error",
                "operation": operation,
                "stage": "choose_preprocessing",
                "error_type": "UnsafePreprocessingDecision",
                "decision": "incompatible_processed_expression_states",
                "recommended_skip_preprocessing": None,
                "recommended_preprocess_spatial": None,
                "recommended_preprocess_reference": None,
                "message": (
                    "Both inputs are processed, but their bounded expression signatures are "
                    "incompatible: spatial is "
                    f"{spatial_processed_state!r} and reference is "
                    f"{reference_processed_state!r}. Harmony cannot safely combine differently "
                    "transformed matrices."
                ),
                "spatial": spatial,
                "reference": reference,
            }
        if (
            spatial_processed_state == "log1p_normalized"
            and spatial["log1p_base"] != reference["log1p_base"]
        ):
            return {
                "status": "error",
                "operation": operation,
                "stage": "choose_preprocessing",
                "error_type": "UnsafePreprocessingDecision",
                "decision": "incompatible_log1p_bases",
                "recommended_skip_preprocessing": None,
                "recommended_preprocess_spatial": None,
                "recommended_preprocess_reference": None,
                "message": (
                    "Both inputs report log1p preprocessing, but their logarithm bases differ. "
                    "Harmony cannot safely combine them without harmonizing the transforms."
                ),
                "spatial": spatial,
                "reference": reference,
            }
        return {
            "status": "success",
            "operation": operation,
            "decision": "skip_combined_preprocessing",
            "recommended_skip_preprocessing": True,
            "recommended_preprocess_spatial": False,
            "recommended_preprocess_reference": False,
            "spatial": spatial,
            "reference": reference,
            "rationale": (
                "Both matrices show the same processed-expression signature "
                f"({spatial_processed_state}). Reapplying the combined normalization/log1p "
                "routine would transform them a second time."
            ),
        }

    if states == {"raw_count_like", "processed_continuous"}:
        preprocess_spatial = spatial["expression_state"] == "raw_count_like"
        preprocess_reference = reference["expression_state"] == "raw_count_like"
        return {
            "status": "success",
            "operation": operation,
            "decision": "preprocess_raw_input_only",
            "recommended_skip_preprocessing": None,
            "recommended_preprocess_spatial": preprocess_spatial,
            "recommended_preprocess_reference": preprocess_reference,
            "spatial": spatial,
            "reference": reference,
            "rationale": (
                "The raw-count-like input can be normalized and log-transformed on its working "
                "copy while the processed-continuous input is preserved. The backend records "
                "both independent decisions and uses Harmony to model the remaining input batch."
            ),
        }

    if "invalid" in states:
        decision = "invalid_expression_values"
        message = "At least one input contains non-finite sampled expression values."
    elif "ambiguous" in states:
        decision = "ambiguous_expression_state"
        message = "At least one input could not be classified safely as raw or processed."
    else:
        decision = "mixed_expression_states"
        message = (
            "The spatial and reference matrices have different preprocessing states. The current "
            "Harmony routine cannot safely preprocess them independently."
        )
    return {
        "status": "error",
        "operation": operation,
        "stage": "choose_preprocessing",
        "error_type": "UnsafePreprocessingDecision",
        "decision": decision,
        "recommended_skip_preprocessing": None,
        "recommended_preprocess_spatial": None,
        "recommended_preprocess_reference": None,
        "message": message,
        "spatial": spatial,
        "reference": reference,
    }


def harmony_transfer_tool(
    spatial_anndata_path: str,
    reference_anndata_path: str,
    output_dir: str = "cell_annotation",
    output_path: str | None = None,
    output_filename: str | None = None,
    cell_type_column: str = "cell_type",
    skip_preprocessing: bool | None = None,
    preprocess_spatial: bool | None = None,
    preprocess_reference: bool | None = None,
    preserve_all_spatial_obs: bool = True,
    reference_min_genes: int | None = None,
    min_cells: int = 10,
    target_sum: float = 1e4,
    n_top_genes: int = 2000,
    n_pcs: int = 30,
    min_shared_genes: int | None = None,
    harmony_key: str = "batch",
    harmony_max_iter: int = 20,
    mlp_hidden_layers: tuple = (100, 50),
    mlp_max_iter: int = 500,
    mlp_random_state: int = 42,
    classifier: str = "mlp",
    knn_neighbors: int = 51,
    map_spatial_gene_names: bool = True,
    gene_mapping_species: str = "auto",
    gene_mapping_target: str = "symbol",
    selection_rationale: str = "",
    execution_contract: dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Transfer reference cell-type labels to spatial data using Harmony."""
    if preprocess_spatial is None and preprocess_reference is None:
        if not isinstance(skip_preprocessing, bool):
            return {
                "status": "error",
                "stage": "validate_preprocessing_decision",
                "error_type": "ValueError",
                "message": (
                    "Pass both preprocess_spatial and preprocess_reference from "
                    "inspect_anndata_preprocessing_tool, or pass its legacy "
                    "skip_preprocessing boolean for a matched-state pair."
                ),
            }
        preprocess_spatial = not skip_preprocessing
        preprocess_reference = not skip_preprocessing
    elif not isinstance(preprocess_spatial, bool) or not isinstance(
        preprocess_reference, bool
    ):
        return {
            "status": "error",
            "stage": "validate_preprocessing_decision",
            "error_type": "ValueError",
            "message": (
                "preprocess_spatial and preprocess_reference must both be explicit booleans "
                "returned by inspect_anndata_preprocessing_tool."
            ),
        }
    if skip_preprocessing is not None and (
        not isinstance(skip_preprocessing, bool)
        or preprocess_spatial is skip_preprocessing
        or preprocess_reference is skip_preprocessing
    ):
        return {
            "status": "error",
            "stage": "validate_preprocessing_decision",
            "error_type": "ValueError",
            "message": (
                "skip_preprocessing conflicts with the explicit per-input preprocessing "
                "decisions. Use null for a mixed-state pair."
            ),
        }
    if reference_min_genes is not None and (
        isinstance(reference_min_genes, bool)
        or not isinstance(reference_min_genes, int)
        or reference_min_genes < 1
    ):
        return {
            "status": "error",
            "stage": "validate_reference_min_genes_decision",
            "error_type": "ValueError",
            "message": "reference_min_genes must be a positive integer when provided.",
        }
    if preprocess_reference and reference_min_genes is None:
        return {
            "status": "error",
            "stage": "validate_reference_min_genes_decision",
            "error_type": "ValueError",
            "message": (
                "reference_min_genes must be chosen explicitly from the reference QC evidence "
                "returned by inspect_anndata_preprocessing_tool when preprocessing raw inputs."
            ),
        }
    if not preprocess_reference and reference_min_genes is not None:
        return {
            "status": "error",
            "stage": "validate_reference_min_genes_decision",
            "error_type": "ValueError",
            "message": (
                "reference_min_genes must be omitted when preprocess_reference=False because "
                "no reference cell filtering will run."
            ),
        }
    if (
        min_shared_genes is None
        or isinstance(min_shared_genes, bool)
        or not isinstance(min_shared_genes, int)
        or min_shared_genes < 2
    ):
        return {
            "status": "error",
            "stage": "validate_shared_gene_decision",
            "error_type": "ValueError",
            "message": (
                "min_shared_genes must be an explicit integer of at least 2 chosen for the "
                "assay and gene panel."
            ),
        }
    if classifier not in {"mlp", "knn"}:
        return {
            "status": "error",
            "stage": "validate_classifier",
            "error_type": "ValueError",
            "message": "classifier must be either 'mlp' or 'knn'.",
        }
    if isinstance(knn_neighbors, bool) or not isinstance(knn_neighbors, int) or knn_neighbors < 1:
        return {
            "status": "error",
            "stage": "validate_classifier",
            "error_type": "ValueError",
            "message": "knn_neighbors must be a positive integer.",
        }
    if not isinstance(selection_rationale, str) or not selection_rationale.strip():
        return {
            "status": "error",
            "stage": "validate_selection",
            "error_type": "ValueError",
            "message": "selection_rationale must be a non-empty string.",
        }
    if len(selection_rationale.strip()) > 4_000:
        return {
            "status": "error",
            "stage": "validate_selection",
            "error_type": "ValueError",
            "message": "selection_rationale must contain at most 4000 characters.",
        }
    try:
        spatial_path = _resolve_path(spatial_anndata_path, must_exist=True)
    except FileNotFoundError as exc:
        return {"status": "error", "message": str(exc)}
    except ValueError as exc:
        return {"status": "error", "message": str(exc)}

    try:
        reference_path = _resolve_path(reference_anndata_path, must_exist=True)
    except FileNotFoundError as exc:
        return {"status": "error", "message": str(exc)}
    except ValueError as exc:
        return {"status": "error", "message": str(exc)}
    if spatial_path.samefile(reference_path):
        return {
            "status": "error",
            "stage": "validate_reference_identity",
            "error_type": "ValueError",
            "message": (
                "reference_anndata_path must not resolve to the query itself; self-training "
                "would leak query labels into predictions."
            ),
        }

    preprocessing_inspection = _inspect_anndata_preprocessing_paths(
        spatial_path,
        reference_path,
        max_rows=2048,
        max_columns=2048,
    )
    if preprocessing_inspection.get("status") != "success":
        return {
            "status": "error",
            "stage": "validate_preprocessing_preflight",
            "error_type": preprocessing_inspection.get(
                "error_type", "UnsafePreprocessingDecision"
            ),
            "message": (
                "Harmony's internal preprocessing preflight could not make a safe decision: "
                f"{preprocessing_inspection.get('message', 'unknown inspection failure')}"
            ),
            "preprocessing_audit": preprocessing_inspection,
        }
    recommended_preprocess_spatial = preprocessing_inspection.get(
        "recommended_preprocess_spatial"
    )
    recommended_preprocess_reference = preprocessing_inspection.get(
        "recommended_preprocess_reference"
    )
    if not isinstance(recommended_preprocess_spatial, bool) or not isinstance(
        recommended_preprocess_reference, bool
    ):
        return {
            "status": "error",
            "stage": "validate_preprocessing_preflight",
            "error_type": "UnsafePreprocessingDecision",
            "message": (
                "Harmony's internal preprocessing preflight did not return two boolean "
                "per-input recommendations."
            ),
            "preprocessing_audit": preprocessing_inspection,
        }
    preprocessing_audit = {
        **preprocessing_inspection,
        "performed_by": "harmony_transfer_tool",
        "provided_skip_preprocessing": skip_preprocessing,
        "provided_preprocess_spatial": preprocess_spatial,
        "provided_preprocess_reference": preprocess_reference,
        "decision_matches": (
            preprocess_spatial == recommended_preprocess_spatial
            and preprocess_reference == recommended_preprocess_reference
        ),
    }
    if not preprocessing_audit["decision_matches"]:
        return {
            "status": "error",
            "stage": "validate_preprocessing_preflight",
            "error_type": "PreprocessingDecisionMismatch",
            "message": (
                "The supplied per-input preprocessing decisions do not match Harmony's "
                "internal bounded inspection."
            ),
            "preprocessing_audit": preprocessing_audit,
        }

    try:
        annotated_output_path = _resolve_output_h5ad_path(
            output_dir=output_dir,
            output_path=output_path,
            output_filename=output_filename,
            input_stem=_default_artifact_stem(spatial_path),
        )
    except ValueError as exc:
        return {"status": "error", "message": str(exc)}

    output_dir_path = annotated_output_path.parent
    output_dir_path.mkdir(parents=True, exist_ok=True)
    meta_path = annotated_output_path.with_suffix(".run_meta.json")
    if annotated_output_path.exists() or meta_path.exists():
        return {
            "status": "error",
            "stage": "validate_output_path",
            "error_type": "FileExistsError",
            "message": (
                "An output artifact already exists for "
                f"{workspace_relative(annotated_output_path)}. "
                "Choose a different output_path."
            ),
        }

    stage = "load_inputs"
    try:
        adata_spatial = sc.read(spatial_path)
        spatial_input_n_obs = int(adata_spatial.n_obs)
        adata_spatial_original = adata_spatial.copy() if preserve_all_spatial_obs else None
        adata_ref = sc.read(reference_path)
        reference_input_n_obs = int(adata_ref.n_obs)
    except Exception as exc:
        return _error_result(stage, exc)

    if cell_type_column not in adata_ref.obs:
        return {
            "status": "error",
            "stage": "validate_reference_labels",
            "error_type": "KeyError",
            "message": f"Reference missing '{cell_type_column}' column in .obs",
        }
    missing_reference_labels = adata_ref.obs[cell_type_column].isna()
    if missing_reference_labels.any():
        return {
            "status": "error",
            "stage": "validate_reference_labels",
            "error_type": "ValueError",
            "message": (
                f"Reference .obs['{cell_type_column}'] contains "
                f"{int(missing_reference_labels.sum())} missing labels."
            ),
        }

    try:
        stage = "harmonize_gene_identifiers"
        gene_mapping_stats = {}

        # Standardize gene names if requested. The legacy flag name is retained,
        # but harmonization must be symmetric for reference/spatial transfer.
        if map_spatial_gene_names:
            resolved_species = _resolve_gene_mapping_species(
                gene_mapping_species, adata_spatial, adata_ref
            )
            adata_ref, ref_mapping_stats = harmonize_gene_identifiers(
                adata_ref,
                species=resolved_species,
                target_namespace=gene_mapping_target,
                dataset_name="reference",
            )
            adata_spatial, spatial_mapping_stats = harmonize_gene_identifiers(
                adata_spatial,
                species=resolved_species,
                target_namespace=gene_mapping_target,
                dataset_name="spatial",
            )
            symbol_casing_stats = {}
            if _normalize_target_namespace(gene_mapping_target) == "symbol":
                adata_ref, adata_spatial, symbol_casing_stats = (
                    _align_symbol_casing_between_datasets(adata_ref, adata_spatial)
                )
                ref_mapping_stats["n_output_genes_after_symbol_casing"] = int(adata_ref.n_vars)
                spatial_mapping_stats["n_output_genes_after_symbol_casing"] = int(
                    adata_spatial.n_vars
                )
            gene_mapping_stats = {
                "species": resolved_species,
                "target_namespace": gene_mapping_target,
                "reference": ref_mapping_stats,
                "spatial": spatial_mapping_stats,
                "symbol_casing": symbol_casing_stats,
            }

        spatial_obs_before_preprocessing = pd.Index(adata_spatial.obs_names)
        reference_obs_before_preprocessing = pd.Index(adata_ref.obs_names)

        stage = "preprocess_inputs"
        if preprocess_reference:
            adata_ref = _preprocess_dataset(
                adata_ref,
                reference_min_genes,
                min_cells,
                target_sum,
                n_top_genes,
                dataset_name="reference",
            )
        else:
            adata_ref = _preserve_processed_dataset(adata_ref, n_top_genes)
        if preprocess_spatial:
            adata_spatial = _preprocess_dataset(
                adata_spatial,
                None,
                min_cells,
                target_sum,
                n_top_genes,
                dataset_name="spatial",
            )
        else:
            adata_spatial = _preserve_processed_dataset(adata_spatial, n_top_genes)
        spatial_obs_after_preprocessing = pd.Index(adata_spatial.obs_names)
        spatial_obs_filtered_by_preprocessing = spatial_obs_before_preprocessing.difference(
            spatial_obs_after_preprocessing
        )
        reference_obs_filtered_by_preprocessing = reference_obs_before_preprocessing.difference(
            pd.Index(adata_ref.obs_names)
        )

        stage = "select_shared_genes"
        shared_genes = adata_ref.var_names.intersection(adata_spatial.var_names)
        if len(shared_genes) < min_shared_genes:
            return {
                "status": "error",
                "stage": stage,
                "message": (
                    f"Too few shared genes: {len(shared_genes)}. "
                    f"The explicit minimum is {min_shared_genes}."
                ),
                "min_shared_genes": min_shared_genes,
                "gene_mapping": gene_mapping_stats,
            }

        # Subset to shared genes
        adata_ref = adata_ref[:, shared_genes].copy()
        adata_spatial = adata_spatial[:, shared_genes].copy()
        pca_feature_mask, pca_feature_selection_policy = _shared_harmony_feature_mask(
            adata_ref,
            adata_spatial,
        )
        n_pca_selected_genes = int(np.count_nonzero(pca_feature_mask))

        # Keep labels outside AnnData.concat. Reference-only .obs columns are not
        # guaranteed to survive concat across supported AnnData versions.
        y_ref = adata_ref.obs[cell_type_column].astype(str).to_numpy(copy=True)

        stage = "combine_inputs"
        reference_batch_strategy = "single_reference_batch"
        reference_batch_source_column = None
        if "dataset_id" in adata_ref.obs:
            reference_source_ids = adata_ref.obs["dataset_id"].dropna().astype(str)
            reference_source_ids = reference_source_ids[reference_source_ids.str.len() > 0]
            if reference_source_ids.nunique() > 1:
                source_ids = adata_ref.obs["dataset_id"].astype("string").fillna("unknown")
                source_ids = source_ids.mask(source_ids.str.len() == 0, "unknown")
                adata_ref.obs[harmony_key] = "reference:" + source_ids.astype(str)
                reference_batch_strategy = "source_aware_reference_batches"
                reference_batch_source_column = "dataset_id"
            else:
                adata_ref.obs[harmony_key] = "reference"
        else:
            adata_ref.obs[harmony_key] = "reference"
        adata_spatial.obs[harmony_key] = "spatial"
        harmony_batch_counts = {
            str(batch): int(count)
            for batch, count in pd.concat(
                [adata_ref.obs[harmony_key], adata_spatial.obs[harmony_key]]
            ).value_counts().items()
        }
        adata_combined = ad.concat(
            {"reference": adata_ref, "spatial": adata_spatial},
            axis=0,
            join="inner",
            merge="same",
            label="_harmony_dataset",
            index_unique="-",
        )
        adata_combined.var[HARMONY_PCA_FEATURE_MASK] = pca_feature_mask

        adata_combined = _ensure_floating_matrix(adata_combined)
        effective_n_pcs = _effective_n_pcs(
            adata_combined,
            n_pcs,
            n_features=n_pca_selected_genes,
        )

        stage = "pca"
        sc.pp.pca(
            adata_combined,
            n_comps=effective_n_pcs,
            mask_var=HARMONY_PCA_FEATURE_MASK,
        )

        stage = "harmony_integration"
        harmony_messages: list[str] = []

        class HarmonyLogCapture(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                harmony_messages.append(record.getMessage())

        harmony_logger = logging.getLogger("harmonypy")
        harmony_handler = HarmonyLogCapture()
        harmony_logger.addHandler(harmony_handler)
        try:
            sc.external.pp.harmony_integrate(
                adata_combined,
                key=harmony_key,
                max_iter_harmony=harmony_max_iter,
            )
        finally:
            harmony_logger.removeHandler(harmony_handler)
        if any("Stopped before convergence" in message for message in harmony_messages):
            harmony_convergence_status = "iteration_limit_reached"
            harmony_warnings = [
                "Harmony reached its configured iteration limit before declaring convergence."
            ]
        elif any("Converged after" in message for message in harmony_messages):
            harmony_convergence_status = "converged"
            harmony_warnings = []
        else:
            harmony_convergence_status = "not_reported"
            harmony_warnings = ["Harmony did not report a convergence status through its logger."]

        # # # Extract Harmony-corrected PCA (use X_pca_harmony if available, else X_pca)
        harmony_pca_key = "X_pca_harmony" if "X_pca_harmony" in adata_combined.obsm else "X_pca"

        # # Split back into reference and spatial
        reference_mask = adata_combined.obs["_harmony_dataset"] == "reference"
        spatial_mask = adata_combined.obs["_harmony_dataset"] == "spatial"

        X_ref_pca = adata_combined.obsm[harmony_pca_key][reference_mask]
        X_spatial_pca = adata_combined.obsm[harmony_pca_key][spatial_mask]

        if X_ref_pca.shape[0] != len(y_ref):
            raise RuntimeError(
                "Reference embedding row count changed during integration: "
                f"{X_ref_pca.shape[0]} != {len(y_ref)}."
            )

        stage = "train_classifier"
        scaler = StandardScaler()
        X_ref_scaled = scaler.fit_transform(X_ref_pca)
        X_spatial_scaled = scaler.transform(X_spatial_pca)

        if classifier == "mlp":
            label_classifier = MLPClassifier(
                hidden_layer_sizes=mlp_hidden_layers,
                max_iter=mlp_max_iter,
                random_state=mlp_random_state,
                verbose=False,
            )
            effective_knn_neighbors = None
        else:
            effective_knn_neighbors = min(knn_neighbors, len(y_ref))
            label_classifier = KNeighborsClassifier(
                n_neighbors=effective_knn_neighbors,
                weights="distance",
                n_jobs=-1,
            )

        label_classifier.fit(X_ref_scaled, y_ref)

        stage = "predict_spatial_labels"
        predicted_labels = label_classifier.predict(X_spatial_scaled)
        prediction_probs = label_classifier.predict_proba(X_spatial_scaled)

        # Get prediction confidence (max probability)
        prediction_confidence = np.max(prediction_probs, axis=1)

        stage = "attach_predictions"
        # Add predictions to the output object. By default, preserve the input
        # spatial object shape and mark rows that were excluded from transfer.
        if preserve_all_spatial_obs:
            adata_output = adata_spatial_original
        else:
            adata_output = adata_spatial
        if adata_output is None:
            raise ValueError("Internal error: missing output AnnData.")
        _apply_spatial_predictions(
            adata_output,
            pd.Index(adata_spatial.obs_names),
            predicted_labels,
            prediction_confidence,
            excluded_obs_names=spatial_obs_filtered_by_preprocessing,
            exclusion_reason="not_transferred",
        )
        adata_output.uns["tissueagent_cell_annotation"] = {
            "annotation_method": "harmony",
            "label_source": "reference",
            "selection_rationale": selection_rationale.strip(),
            "reference_anndata_path": workspace_relative(reference_path),
            "reference_cell_type_column": cell_type_column,
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

        stage = "write_outputs"
        _write_h5ad_atomically(adata_output, annotated_output_path)

        # Aggregate statistics for reporting
        cell_type_counts = pd.Series(predicted_labels).value_counts()

        # Write run metadata
        metadata = {
            "status": "success",
            "method": f"Harmony integration + {classifier.upper()} classifier",
            "annotation_method": "harmony",
            "label_source": "reference",
            "selection_rationale": selection_rationale.strip(),
            "execution_contract": execution_contract,
            "preprocessing_audit": preprocessing_audit,
            "parameters": {
                "skip_preprocessing": skip_preprocessing,
                "preprocess_spatial": preprocess_spatial,
                "preprocess_reference": preprocess_reference,
                "output_path": output_path,
                "output_filename": output_filename,
                "preserve_all_spatial_obs": preserve_all_spatial_obs,
                "reference_min_genes": reference_min_genes,
                "min_cells": min_cells,
                "target_sum": target_sum,
                "n_top_genes": n_top_genes,
                "pca_feature_selection_policy": pca_feature_selection_policy,
                "n_pca_selected_genes": n_pca_selected_genes,
                "n_pcs": n_pcs,
                "min_shared_genes": min_shared_genes,
                "effective_n_pcs": effective_n_pcs,
                "harmony_key": harmony_key,
                "reference_batch_strategy": reference_batch_strategy,
                "reference_batch_source_column": reference_batch_source_column,
                "harmony_max_iter": harmony_max_iter,
                "mlp_hidden_layers": list(mlp_hidden_layers),
                "mlp_max_iter": mlp_max_iter,
                "mlp_random_state": mlp_random_state,
                "classifier": classifier,
                "knn_neighbors": knn_neighbors,
                "effective_knn_neighbors": effective_knn_neighbors,
                "map_spatial_gene_names": map_spatial_gene_names,
                "gene_mapping_species": gene_mapping_species,
                "gene_mapping_target": gene_mapping_target,
            },
            "runtime": {
                "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },
            "inputs": {
                "spatial_anndata_path": workspace_relative(spatial_path),
                "reference_anndata_path": workspace_relative(reference_path),
            },
            "outputs": {
                "annotated_object_h5ad": workspace_relative(annotated_output_path),
            },
            "summary": {
                "n_cells_transferred": int(len(predicted_labels)),
                "n_input_spatial_cells": spatial_input_n_obs,
                "n_output_cells": int(adata_output.n_obs),
                "n_cells_excluded_from_transfer": int(adata_output.n_obs - len(predicted_labels)),
                "n_spatial_cells_filtered_by_preprocessing": int(
                    len(spatial_obs_filtered_by_preprocessing)
                ),
                "n_reference_input_cells": reference_input_n_obs,
                "n_reference_cells_after_preprocessing": int(adata_ref.n_obs),
                "n_reference_cells_filtered_by_preprocessing": int(
                    len(reference_obs_filtered_by_preprocessing)
                ),
                "n_unique_cell_types": int(len(cell_type_counts)),
                "mean_prediction_confidence": float(np.mean(prediction_confidence)),
                "n_shared_genes": int(len(shared_genes)),
                "pca_feature_selection_policy": pca_feature_selection_policy,
                "n_pca_selected_genes": n_pca_selected_genes,
                "min_shared_genes": min_shared_genes,
                "gene_mapping": gene_mapping_stats,
                "harmony_convergence_status": harmony_convergence_status,
                "harmony_batch_counts": harmony_batch_counts,
                "warnings": harmony_warnings,
            },
        }
        with meta_path.open("w", encoding="utf-8") as fh:
            json.dump(metadata, fh, indent=2)

        return {
            "status": "success",
            "annotation_method": "harmony",
            "label_source": "reference",
            "selection_rationale": selection_rationale.strip(),
            "execution_contract": execution_contract,
            "output_dir": workspace_relative(output_dir_path),
            "annotated_object_h5ad": workspace_relative(annotated_output_path),
            "run_meta_json": workspace_relative(meta_path),
            "n_cells_transferred": len(predicted_labels),
            "n_input_spatial_cells": spatial_input_n_obs,
            "n_output_cells": int(adata_output.n_obs),
            "n_cells_excluded_from_transfer": int(adata_output.n_obs - len(predicted_labels)),
            "n_spatial_cells_filtered_by_preprocessing": int(
                len(spatial_obs_filtered_by_preprocessing)
            ),
            "n_reference_input_cells": reference_input_n_obs,
            "n_reference_cells_after_preprocessing": int(adata_ref.n_obs),
            "n_reference_cells_filtered_by_preprocessing": int(
                len(reference_obs_filtered_by_preprocessing)
            ),
            "reference_min_genes": reference_min_genes,
            "n_unique_cell_types": len(cell_type_counts),
            "cell_type_counts": cell_type_counts.to_dict(),
            "mean_prediction_confidence": float(np.mean(prediction_confidence)),
            "n_shared_genes": len(shared_genes),
            "pca_feature_selection_policy": pca_feature_selection_policy,
            "n_pca_selected_genes": n_pca_selected_genes,
            "min_shared_genes": min_shared_genes,
            "gene_mapping": gene_mapping_stats,
            "harmony_convergence_status": harmony_convergence_status,
            "reference_batch_strategy": reference_batch_strategy,
            "reference_batch_source_column": reference_batch_source_column,
            "harmony_batch_counts": harmony_batch_counts,
            "warnings": harmony_warnings,
        }
    except Exception as exc:
        return _error_result(stage, exc, gene_mapping=gene_mapping_stats)


def _error_result(stage: str, exc: Exception, **details: Any) -> Dict[str, Any]:
    """Return a structured, user-visible tool failure without hiding its cause."""
    result: Dict[str, Any] = {
        "status": "error",
        "stage": stage,
        "error_type": type(exc).__name__,
        "message": f"Harmony transfer failed during {stage}: {exc}",
    }
    result.update(details)
    return result


def _apply_spatial_predictions(
    adata_output: sc.AnnData,
    predicted_obs_names: pd.Index,
    predicted_labels: np.ndarray,
    prediction_confidence: np.ndarray,
    *,
    excluded_obs_names: pd.Index,
    exclusion_reason: str,
) -> None:
    """Attach transfer predictions while preserving unpredicted spatial rows."""
    output_obs_names = pd.Index(adata_output.obs_names)
    missing_obs_names = predicted_obs_names.difference(output_obs_names)
    if len(missing_obs_names) > 0:
        examples = ", ".join(missing_obs_names.astype(str)[:5])
        raise ValueError(
            "Predicted spatial observations were not found in the output AnnData "
            f"index. Examples: {examples}"
        )

    label_categories = list(pd.unique(pd.Series(predicted_labels, dtype="object").astype(str)))
    label_series = pd.Series(
        pd.Categorical([pd.NA] * adata_output.n_obs, categories=label_categories),
        index=output_obs_names,
    )
    confidence_series = pd.Series(np.nan, index=output_obs_names, dtype=float)
    status_series = pd.Series("not_transferred", index=output_obs_names, dtype="object")
    reason_series = pd.Series("not_transferred", index=output_obs_names, dtype="object")

    label_series.loc[predicted_obs_names] = predicted_labels
    confidence_series.loc[predicted_obs_names] = prediction_confidence
    status_series.loc[predicted_obs_names] = "transferred"
    reason_series.loc[predicted_obs_names] = "not_excluded"

    excluded_obs_names = excluded_obs_names.intersection(output_obs_names)
    if len(excluded_obs_names) > 0:
        status_series.loc[excluded_obs_names] = "excluded_from_transfer"
        reason_series.loc[excluded_obs_names] = exclusion_reason

    adata_output.obs["harmony_predicted_cell_type"] = label_series
    adata_output.obs["harmony_prediction_confidence"] = confidence_series
    adata_output.obs["harmony_transfer_status"] = pd.Categorical(status_series)
    adata_output.obs["harmony_exclusion_reason"] = pd.Categorical(reason_series)
    adata_output.obs["cell_annotation_predicted_cell_type"] = label_series.copy()
    adata_output.obs["cell_annotation_prediction_confidence"] = confidence_series
    adata_output.obs["cell_annotation_status"] = pd.Categorical(status_series)
    adata_output.obs["cell_annotation_exclusion_reason"] = pd.Categorical(reason_series)
    adata_output.obs["cell_annotation_method"] = pd.Categorical(
        ["harmony"] * adata_output.n_obs
    )
    adata_output.obs["label"] = adata_output.obs["harmony_predicted_cell_type"]


def _preprocess_dataset(
    adata: sc.AnnData,
    min_genes: int | None,
    min_cells: int,
    target_sum: float,
    n_top_genes: int,
    percent_top: tuple[int, ...] = (50, 100, 200),
    *,
    dataset_name: str = "dataset",
) -> sc.AnnData:
    """Preprocess a working copy and retain panel-safe QC information."""
    adata = adata.copy()
    valid_percent_top = tuple(value for value in percent_top if 0 < value < adata.n_vars)
    sc.pp.calculate_qc_metrics(
        adata,
        percent_top=valid_percent_top or None,
        inplace=True,
    )
    if min_genes is not None:
        sc.pp.filter_cells(adata, min_genes=min_genes)
        if adata.n_obs == 0:
            raise ValueError(
                f"Preprocessing removed every {dataset_name} cell with min_genes={min_genes}."
            )

    sc.pp.filter_genes(adata, min_cells=min_cells)
    if adata.n_vars == 0:
        raise ValueError(
            f"Preprocessing removed every {dataset_name} gene with min_cells={min_cells}."
        )

    sc.pp.normalize_total(adata, target_sum=target_sum)
    sc.pp.log1p(adata)
    _mark_highly_variable_genes(adata, n_top_genes)

    return adata


def _mark_highly_variable_genes(adata: sc.AnnData, n_top_genes: int) -> None:
    """Mark the highest-variance genes without failing on small/constant panels."""
    selected = np.zeros(adata.n_vars, dtype=bool)
    if n_top_genes <= 0 or adata.n_vars == 0:
        adata.var["highly_variable"] = selected
        return
    if n_top_genes >= adata.n_vars:
        selected[:] = True
        adata.var["highly_variable"] = selected
        return

    if sparse.issparse(adata.X):
        means = np.asarray(adata.X.mean(axis=0)).ravel()
        squared_means = np.asarray(adata.X.power(2).mean(axis=0)).ravel()
    else:
        values = np.asarray(adata.X)
        means = values.mean(axis=0)
        squared_means = np.square(values).mean(axis=0)
    variances = np.maximum(squared_means - np.square(means), 0.0)
    top_indices = np.argsort(variances, kind="stable")[-n_top_genes:]
    selected[top_indices] = True
    adata.var["highly_variable"] = selected


def _ensure_floating_matrix(adata: sc.AnnData) -> sc.AnnData:
    """Return an AnnData whose working matrix is suitable for PCA."""
    if np.issubdtype(adata.X.dtype, np.floating) or np.issubdtype(
        adata.X.dtype, np.complexfloating
    ):
        return adata
    adata = adata.copy()
    adata.X = adata.X.astype(np.float32)
    return adata


def _preserve_processed_dataset(adata: sc.AnnData, n_top_genes: int) -> sc.AnnData:
    """Preserve processed values while recording an input-specific PCA feature mask."""
    adata = _ensure_floating_matrix(adata.copy())
    _mark_highly_variable_genes(adata, n_top_genes)
    return adata


def _shared_harmony_feature_mask(
    adata_ref: sc.AnnData,
    adata_spatial: sc.AnnData,
) -> tuple[np.ndarray, str]:
    """Build one explicit PCA mask from aligned reference and query features."""
    if not adata_ref.var_names.equals(adata_spatial.var_names):
        raise ValueError(
            "Reference and spatial genes must be aligned before PCA feature selection."
        )

    masks = []
    sources = []
    for source, dataset in (("reference", adata_ref), ("spatial", adata_spatial)):
        if "highly_variable" not in dataset.var:
            continue
        mask = dataset.var["highly_variable"].fillna(False).to_numpy(dtype=bool)
        masks.append(mask)
        sources.append(source)

    if not masks:
        return np.ones(adata_ref.n_vars, dtype=bool), "all_shared_genes_no_hvg_masks"

    shared_mask = np.logical_or.reduce(masks)
    if not np.any(shared_mask):
        return np.ones(adata_ref.n_vars, dtype=bool), "all_shared_genes_empty_hvg_union"
    if sources == ["reference", "spatial"]:
        policy = "union_of_reference_and_spatial_hvgs"
    else:
        policy = f"{sources[0]}_hvg_mask"
    return shared_mask, policy


def _effective_n_pcs(
    adata: sc.AnnData,
    requested_n_pcs: int,
    *,
    n_features: int | None = None,
) -> int:
    """Choose a PCA dimension valid for dense and sparse Scanpy solvers."""
    if requested_n_pcs < 1:
        raise ValueError("n_pcs must be at least 1.")
    feature_count = adata.n_vars if n_features is None else n_features
    maximum = min(adata.n_obs - 1, feature_count - 1)
    if maximum < 1:
        raise ValueError(
            "Harmony transfer requires at least two combined observations and two shared genes."
        )
    return min(requested_n_pcs, maximum)


def map_genes(
    genes,
    species: str = "human",
    from_field: str = "symbol,alias",
    to_field: str = "ensembl.gene",
) -> pd.DataFrame:
    """Map gene identifiers using the MyGene.info API.

    Parameters
    ----------
    genes : list[str]
        List of gene identifiers to map.
    species : str, default="human"
        Species name or alias recognized by MyGene (e.g., "human", "mouse").
    from_field : str, default="symbol"
        The type of identifier being provided (e.g., "symbol", "ensembl.gene").
    to_field : str, default="ensembl.gene"
        The target identifier field to map to (e.g., "symbol", "entrezgene").

    Returns:
    -------
    pd.DataFrame
        DataFrame with columns: ["query", "mapped_id"] and potentially "notfound".
    """
    mg = mygene.MyGeneInfo()

    to_field_query = _normalize_mygene_field(to_field)
    result_column = "ensembl" if to_field_query.startswith("ensembl") else to_field_query

    # Query MyGene.info API
    results = mg.querymany(
        genes,
        scopes=from_field,
        fields=to_field_query,
        species=species,
        as_dataframe=False,
        returnall=False,
    )

    df = pd.DataFrame(results)
    if df.empty:
        return pd.DataFrame(columns=["query", "mapped_id"])

    # Extract the mapped ID (handling lists or dicts)
    def extract_mapped(x):
        if isinstance(x, list):
            # Take the first match if multiple
            x = x[0]
        if isinstance(x, dict):
            return x.get("gene") or x.get("primary") or next(iter(x.values()), None)
        return x

    if result_column in df.columns:
        df["mapped_id"] = df[result_column].apply(extract_mapped)
    elif to_field in df.columns:
        df["mapped_id"] = df[to_field].apply(extract_mapped)
    else:
        df["mapped_id"] = None

    # Drop rows without a mapping
    df = df[["query", "mapped_id"]]
    df = df[df["mapped_id"].notna()]
    df["query"] = df["query"].astype(str)
    df["mapped_id"] = df["mapped_id"].astype(str)
    df = df.drop_duplicates(subset=["query"])

    return df


def replace_var_names_with_mapping(
    adata: sc.AnnData,
    mapping_df: pd.DataFrame,
    source_values: pd.Index | None = None,
    source_name: str = "var_names",
) -> sc.AnnData:
    """Replace adata.var_names using a mapping DataFrame from map_genes().

    Parameters
    ----------
    adata : anndata.AnnData
        Input AnnData object whose var_names will be replaced.
    mapping_df : pd.DataFrame
        Must contain columns ["query", "mapped_id"] as returned by map_genes().

    Returns:
    -------
    adata : anndata.AnnData
        A new AnnData object with updated var_names (mapped IDs).
    """
    # Ensure mapping_df has the expected columns
    if not {"query", "mapped_id"}.issubset(mapping_df.columns):
        raise ValueError("mapping_df must contain columns: ['query', 'mapped_id'].")

    # Create a mapping dict: {old_name -> new_name}
    mapping_dict = dict(zip(mapping_df["query"], mapping_df["mapped_id"]))

    original_var_names = pd.Index(adata.var_names.astype(str))
    if source_values is None:
        source_values = original_var_names
    source_values = pd.Index(source_values.astype(str))

    # Map old → new names
    new_var_names = source_values.map(mapping_dict)

    fallback_values = pd.Series(source_values, index=original_var_names).where(
        source_values != "", original_var_names
    )

    # Use the selected source identifier when mapping failed.
    new_var_names = pd.Series(new_var_names, index=original_var_names).where(
        pd.notnull(new_var_names), fallback_values
    )

    adata.var["original_var_name"] = original_var_names
    adata.var["gene_identifier_source"] = source_values
    adata.var["gene_identifier_source_name"] = source_name
    adata.var_names = pd.Index(new_var_names)

    return adata


def harmonize_gene_identifiers(
    adata: sc.AnnData,
    *,
    species: str,
    target_namespace: str = "symbol",
    dataset_name: str = "dataset",
) -> tuple[sc.AnnData, Dict[str, object]]:
    """Map AnnData features into a common gene namespace for transfer."""
    target_namespace = _normalize_target_namespace(target_namespace)
    source_values, source_name = _select_gene_identifier_source(adata, target_namespace)
    source_kind = _infer_gene_identifier_kind(source_values)
    from_field = "ensembl.gene" if source_kind == "ensembl" else "symbol,alias"

    cleaned_source_values = _clean_gene_identifiers(source_values, source_kind)

    if target_namespace == source_kind:
        mapping_df = pd.DataFrame(
            {"query": cleaned_source_values, "mapped_id": cleaned_source_values}
        )
    else:
        mapping_df = map_genes(
            cleaned_source_values.to_list(),
            species=species,
            from_field=from_field,
            to_field=target_namespace,
        )

    mapped = replace_var_names_with_mapping(
        adata,
        mapping_df,
        source_values=cleaned_source_values,
        source_name=source_name,
    )
    n_before_dedup = mapped.n_vars
    duplicate_mask = mapped.var_names.duplicated(keep="first")
    n_duplicates = int(np.sum(duplicate_mask))
    if n_duplicates:
        mapped = mapped[:, ~duplicate_mask].copy()

    stats: Dict[str, object] = {
        "dataset": dataset_name,
        "source": source_name,
        "source_kind": source_kind,
        "target_namespace": target_namespace,
        "species": species,
        "n_input_genes": int(len(source_values)),
        "n_mapped_genes": int(mapping_df["query"].nunique()) if "query" in mapping_df else 0,
        "n_output_genes": int(mapped.n_vars),
        "n_duplicate_mapped_genes_dropped": n_duplicates,
        "n_genes_before_dedup": int(n_before_dedup),
    }
    return mapped, stats


def _align_symbol_casing_between_datasets(
    adata_ref: sc.AnnData,
    adata_spatial: sc.AnnData,
) -> tuple[sc.AnnData, sc.AnnData, Dict[str, object]]:
    ref_names = pd.Index(adata_ref.var_names.astype(str))
    spatial_names = pd.Index(adata_spatial.var_names.astype(str))
    canonical_by_upper = _canonical_symbol_case_map(ref_names.append(spatial_names))

    adata_ref, ref_stats = _apply_symbol_case_map(adata_ref, canonical_by_upper, "reference")
    adata_spatial, spatial_stats = _apply_symbol_case_map(
        adata_spatial, canonical_by_upper, "spatial"
    )

    return (
        adata_ref,
        adata_spatial,
        {
            "n_symbol_groups": int(len(canonical_by_upper)),
            "reference": ref_stats,
            "spatial": spatial_stats,
        },
    )


def _canonical_symbol_case_map(values: pd.Index) -> Dict[str, str]:
    canonical_by_upper: Dict[str, str] = {}
    candidates_by_upper: Dict[str, list[str]] = {}
    for value in values.astype(str):
        if not value:
            continue
        candidates_by_upper.setdefault(value.upper(), []).append(value)

    for upper, candidates in candidates_by_upper.items():
        unique_candidates = list(dict.fromkeys(candidates))
        preferred = next(
            (
                candidate
                for candidate in unique_candidates
                if not candidate.isupper() and not candidate.islower()
            ),
            unique_candidates[0],
        )
        canonical_by_upper[upper] = preferred
    return canonical_by_upper


def _apply_symbol_case_map(
    adata: sc.AnnData,
    canonical_by_upper: Dict[str, str],
    dataset_name: str,
) -> tuple[sc.AnnData, Dict[str, object]]:
    old_names = pd.Index(adata.var_names.astype(str))
    new_names = pd.Index([canonical_by_upper.get(name.upper(), name) for name in old_names])
    n_changed = int(np.sum(old_names != new_names))
    if n_changed:
        adata.var["gene_identifier_pre_case_alignment"] = old_names
        adata.var_names = new_names

    n_before_dedup = adata.n_vars
    duplicate_mask = adata.var_names.duplicated(keep="first")
    n_duplicates = int(np.sum(duplicate_mask))
    if n_duplicates:
        adata = adata[:, ~duplicate_mask].copy()

    return adata, {
        "dataset": dataset_name,
        "n_case_aligned_genes": n_changed,
        "n_duplicate_genes_dropped_after_case_alignment": n_duplicates,
        "n_genes_before_case_dedup": int(n_before_dedup),
        "n_output_genes": int(adata.n_vars),
    }


def _normalize_target_namespace(target_namespace: str) -> str:
    normalized = str(target_namespace).strip().lower()
    if normalized in {"ensembl", "ensembl.gene", "ensembl_gene_id"}:
        return "ensembl"
    if normalized in {"symbol", "gene_symbol", "gene_symbols"}:
        return "symbol"
    raise ValueError("gene_mapping_target must be one of: 'symbol', 'ensembl', 'ensembl.gene'.")


def _normalize_mygene_field(field: str) -> str:
    normalized = str(field).strip().lower()
    if normalized in {"ensembl", "ensembl.gene", "ensembl_gene_id"}:
        return "ensembl.gene"
    if normalized in {"symbol", "gene_symbol", "gene_symbols"}:
        return "symbol"
    return str(field).strip()


def _select_gene_identifier_source(
    adata: sc.AnnData, target_namespace: str
) -> tuple[pd.Index, str]:
    var_names = pd.Index(adata.var_names.astype(str))

    if target_namespace == "ensembl":
        if _infer_gene_identifier_kind(var_names) == "ensembl":
            return _clean_gene_identifiers(var_names, "ensembl"), "var_names"
        for column in GENE_ID_COLUMNS:
            if column in adata.var:
                values = _clean_var_column(adata.var[column])
                if _is_usable_identifier_column(values):
                    return values, f"var['{column}']"

    for column in GENE_SYMBOL_COLUMNS:
        if column in adata.var:
            values = _clean_var_column(adata.var[column])
            if _is_usable_identifier_column(values):
                return values, f"var['{column}']"

    return var_names, "var_names"


def _clean_var_column(values: pd.Series) -> pd.Index:
    cleaned = values.astype("string").fillna("").astype(str).str.strip()
    cleaned = cleaned.mask(cleaned.str.lower().isin({"", "nan", "none", "na"}), "")
    return pd.Index(cleaned)


def _is_usable_identifier_column(values: pd.Index) -> bool:
    if len(values) == 0:
        return False
    return float(np.mean(pd.Index(values).astype(str) != "")) >= 0.5


def _clean_gene_identifiers(values: pd.Index, source_kind: str) -> pd.Index:
    cleaned = pd.Series(values.astype(str), dtype="string").fillna("").str.strip()
    if source_kind == "ensembl":
        cleaned = cleaned.str.replace(r"\.\d+$", "", regex=True)
    return pd.Index(cleaned.astype(str))


def _infer_gene_identifier_kind(values: pd.Index) -> str:
    values = pd.Index(values.astype(str))
    non_empty = values[values != ""]
    if len(non_empty) == 0:
        return "symbol"
    ensembl_fraction = float(
        np.mean(non_empty.map(lambda value: bool(ENSEMBL_GENE_RE.match(value))))
    )
    return "ensembl" if ensembl_fraction >= 0.5 else "symbol"


def _resolve_gene_mapping_species(
    requested_species: str, adata_spatial: sc.AnnData, adata_ref: sc.AnnData
) -> str:
    requested = str(requested_species or "").strip()
    if requested and requested.casefold() not in {"auto", "infer", "detect"}:
        return _normalize_species_for_mygene(requested)

    for adata in (adata_ref, adata_spatial):
        inferred = _species_from_anndata(adata)
        if inferred:
            return inferred

    raise ValueError(
        "Could not infer species from reference or spatial AnnData metadata. "
        "Pass gene_mapping_species explicitly (for example, 'human' or 'mouse')."
    )


def _species_from_anndata(adata: sc.AnnData) -> str | None:
    for key in ("organism", "organism_ontology_term_id", "species", "species__ontology_label"):
        value = adata.uns.get(key)
        normalized = _normalize_species_for_mygene(value)
        if normalized:
            return normalized

    for column in ("organism", "organism_ontology_term_id", "species", "species__ontology_label"):
        if column not in adata.obs:
            continue
        values = adata.obs[column].dropna().astype(str)
        if values.empty:
            continue
        normalized = _normalize_species_for_mygene(values.iloc[0])
        if normalized:
            return normalized
    return None


def _normalize_species_for_mygene(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.startswith("NCBITaxon:"):
        text = text.split(":", 1)[1]
    return SPECIES_ALIASES.get(text.casefold(), text)
