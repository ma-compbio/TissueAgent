"""Leakage controls for the fixed cell-annotation benchmarks."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import anndata as ad


BENCHMARK_LABEL_COLUMNS = {
    "bcl": ("refined_clusters",),
    "developing_human_heart": ("populations",),
    "mouse_cns": (
        "Main_molecular_cell_type",
        "Sub_molecular_cell_type",
        "Main_molecular_tissue_region",
        "Sub_molecular_tissue_region",
        "Molecular_spatial_cell_type",
    ),
    "mouse_spinal_cord": (
        "1st round cluster",
        "2nd round subcluster",
        "MERFISH cell type annotation",
        "Region",
        "Excitatory_vs_Inhibitory",
        "Markers",
        "Note",
        "Neurotransmitter",
        "Laminae",
    ),
    "ovarian_cancer": ("cell.types", "cell.subtypes"),
    "human_skin_atlas": (
        "labels_scanvi",
        "scrna_predicted_id",
        "cell_type.broad",
        "cell_category",
        "cell_type.detailed",
    ),
    "mouse_brain_merfish": ("subclass",),
    "allen_mouse_brain_organism_2": ("subclass",),
    "han_mouse_brain_stereoseq": ("cell_subclass",),
}


def benchmark_label_columns(dataset_id: str) -> tuple[str, ...]:
    """Return evaluation-only columns for one fixed benchmark."""
    try:
        return BENCHMARK_LABEL_COLUMNS[dataset_id]
    except KeyError as exc:
        raise KeyError(f"Unsupported cell-annotation benchmark: {dataset_id}") from exc


def remove_benchmark_labels(dataset_id: str, dataset: ad.AnnData) -> list[str]:
    """Remove every configured evaluation label from an in-memory benchmark query."""
    columns = benchmark_label_columns(dataset_id)
    missing = [column for column in columns if column not in dataset.obs]
    if missing:
        raise KeyError(f"{dataset_id} source is missing evaluation labels: {', '.join(missing)}")
    dataset.obs = dataset.obs.drop(columns=list(columns))
    leaked = [column for column in columns if column in dataset.obs]
    if leaked:
        raise RuntimeError(f"Failed to remove evaluation labels: {', '.join(leaked)}")
    return list(columns)


def remove_or_verify_benchmark_labels(dataset_id: str, dataset: ad.AnnData) -> list[str]:
    """Remove configured labels, accepting a query that was already stripped in full."""
    columns = benchmark_label_columns(dataset_id)
    present = [column for column in columns if column in dataset.obs]
    if not present:
        return list(columns)
    if len(present) != len(columns):
        missing = sorted(set(columns).difference(present))
        raise KeyError(
            f"{dataset_id} query has a partial evaluation-label set; missing: {', '.join(missing)}"
        )
    return remove_benchmark_labels(dataset_id, dataset)


def validate_benchmark_query(
    dataset_id: str,
    h5ad_path: str | Path,
    *,
    expected_n_obs: int | None = None,
    expected_n_vars: int | None = None,
    require_spatial: bool = True,
) -> dict[str, Any]:
    """Validate an evaluation query, including the benchmark-only leakage check."""
    path = Path(h5ad_path)
    dataset = ad.read_h5ad(path, backed="r")
    try:
        n_obs, n_vars = dataset.shape
        errors: list[str] = []
        warnings: list[str] = []
        if n_obs == 0 or n_vars == 0:
            errors.append("Dataset must contain at least one observation and one variable.")
        if not dataset.obs_names.is_unique:
            errors.append("Observation identifiers are not unique.")
        if not dataset.var_names.is_unique:
            errors.append("Gene identifiers are not unique.")
        if expected_n_obs is not None and n_obs != expected_n_obs:
            errors.append(f"n_obs={n_obs}, expected {expected_n_obs}.")
        if expected_n_vars is not None and n_vars != expected_n_vars:
            errors.append(f"n_vars={n_vars}, expected {expected_n_vars}.")
        has_spatial = "spatial" in dataset.obsm
        if require_spatial and not has_spatial:
            errors.append("Required obsm['spatial'] coordinates are missing.")
        elif not has_spatial:
            warnings.append("No obsm['spatial'] coordinates were found.")
        leaked = sorted(set(benchmark_label_columns(dataset_id)).intersection(dataset.obs.columns))
        if leaked:
            errors.append("Evaluation-only columns remain in query: " + ", ".join(leaked))
    finally:
        dataset.file.close()
    return {
        "status": "success" if not errors else "error",
        "h5ad_path": str(path),
        "n_obs": int(n_obs),
        "n_vars": int(n_vars),
        "has_spatial": has_spatial,
        "evaluation_columns_present": leaked,
        "errors": errors,
        "warnings": warnings,
    }
