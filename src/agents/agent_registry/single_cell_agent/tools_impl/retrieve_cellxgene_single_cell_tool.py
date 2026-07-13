"""Download one CELLxGENE Census source H5AD safely into DATA_DIR."""

import cellxgene_census
import anndata as ad
import numpy as np
import pandas as pd
from pathlib import Path

from config import DATA_DIR


def _resolve_output_path(filename: str) -> Path:
    raw_path = Path(filename).expanduser()
    candidates = [raw_path] if raw_path.is_absolute() else [DATA_DIR.parent / raw_path, DATA_DIR / raw_path]
    output_path = None
    for candidate in candidates:
        resolved = candidate.parent.resolve() / candidate.name
        try:
            resolved.relative_to(DATA_DIR.resolve())
        except ValueError:
            continue
        output_path = resolved
        break
    if output_path is None:
        raise ValueError(f"filename must resolve inside DATA_DIR: {DATA_DIR}")
    try:
        output_path.relative_to(DATA_DIR.resolve())
    except ValueError as exc:
        raise ValueError(f"filename must resolve inside DATA_DIR: {DATA_DIR}") from exc
    return output_path


def _valid_h5ad(path: Path) -> bool:
    try:
        dataset = ad.read_h5ad(path, backed="r")
        valid = dataset.n_obs > 0 and dataset.n_vars > 0
        dataset.file.close()
        return valid
    except Exception:
        return False


def retrieve_cellxgene_single_cell(
    dataset_id: str,
    filename: str,
    census_version: str = "stable",
):
    """Download a CELLxGENE dataset as an h5ad file into DATA_DIR.

    Args:
        dataset_id: CELLxGENE Census dataset identifier.
        filename: Target filename within DATA_DIR.

    Returns:
        census_version: Pinned Census release or the stable alias.

    Returns:
        Structured status and the exact downloaded artifact.
    """
    try:
        filepath = _resolve_output_path(filename)
    except ValueError as e:
        return {"status": "error", "error_type": type(e).__name__, "message": str(e)}

    if filepath.exists():
        if _valid_h5ad(filepath):
            return {
                "status": "success",
                "cache_hit": True,
                "dataset_id": dataset_id,
                "census_version": census_version,
                "output_path": str(filepath.relative_to(DATA_DIR)),
                "size_bytes": filepath.stat().st_size,
            }
        return {
            "status": "error",
            "error_type": "ValueError",
            "message": f"Existing target is not a valid non-empty H5AD: {filepath}",
        }
    filepath.parent.mkdir(parents=True, exist_ok=True)
    partial = filepath.with_name(filepath.name + ".partial")
    partial.unlink(missing_ok=True)

    try:
        cellxgene_census.download_source_h5ad(
            dataset_id,
            str(partial),
            census_version=census_version,
            progress_bar=True,
        )
        if not _valid_h5ad(partial):
            raise ValueError("Downloaded CELLxGENE artifact is not a valid non-empty H5AD.")
        partial.replace(filepath)
    except Exception as e:
        partial.unlink(missing_ok=True)
        return {"status": "error", "error_type": type(e).__name__, "message": str(e)}
    return {
        "status": "success",
        "cache_hit": False,
        "dataset_id": dataset_id,
        "census_version": census_version,
        "output_path": str(filepath.relative_to(DATA_DIR)),
        "size_bytes": filepath.stat().st_size,
    }


def retrieve_cellxgene_reference_subset(
    dataset_ids: list[str],
    filename: str,
    census_version: str,
    label_column: str = "cell_type",
    max_cells_per_label: int = 500,
    random_state: int = 42,
    include_labels: list[str] | None = None,
    organism: str = "Mus musculus",
    tissues: list[str] | None = None,
    diseases: list[str] | None = None,
):
    """Retrieve a reproducible label-balanced Census subset without full source downloads."""
    try:
        filepath = _resolve_output_path(filename)
        if not dataset_ids:
            raise ValueError("dataset_ids must contain at least one pinned dataset ID.")
        if max_cells_per_label < 1:
            raise ValueError("max_cells_per_label must be positive.")
        for dataset_id in dataset_ids:
            if not dataset_id or any(char not in "0123456789abcdef-" for char in dataset_id.casefold()):
                raise ValueError(f"Invalid CELLxGENE dataset ID: {dataset_id}")
        if filepath.exists():
            if _valid_h5ad(filepath):
                return {
                    "status": "success",
                    "cache_hit": True,
                    "dataset_ids": dataset_ids,
                    "census_version": census_version,
                    "output_path": str(filepath.relative_to(DATA_DIR)),
                    "size_bytes": filepath.stat().st_size,
                }
            raise ValueError(f"Existing target is not a valid non-empty H5AD: {filepath}")

        organism_key = organism.casefold().replace(" ", "_")
        if organism_key not in {"mus_musculus", "homo_sapiens"}:
            raise ValueError("organism must be 'Mus musculus' or 'Homo sapiens'.")

        def equals_any(column: str, values: list[str] | None) -> str | None:
            if not values:
                return None
            if any('"' in value or "\\" in value for value in values):
                raise ValueError(f"Unsafe character in {column} filter.")
            return "(" + " or ".join(f'{column} == "{value}"' for value in values) + ")"

        dataset_filter = " or ".join(f'dataset_id == "{dataset_id}"' for dataset_id in dataset_ids)
        clauses = [f"({dataset_filter})", "is_primary_data == True"]
        clauses.extend(
            clause
            for clause in (equals_any("tissue", tissues), equals_any("disease", diseases))
            if clause
        )
        value_filter = " and ".join(clauses)
        with cellxgene_census.open_soma(census_version=census_version) as census:
            obs = census["census_data"][organism_key].obs
            metadata = obs.read(
                value_filter=value_filter,
                column_names=["soma_joinid", "dataset_id", label_column],
            ).concat().to_pandas()
            metadata = metadata.dropna(subset=[label_column])
            if include_labels:
                metadata = metadata[metadata[label_column].isin(include_labels)]
                missing_labels = sorted(set(include_labels).difference(metadata[label_column].unique()))
                if missing_labels:
                    raise ValueError(
                        "Pinned CELLxGENE datasets lack requested labels: " + ", ".join(missing_labels)
                    )
            if metadata.empty:
                raise ValueError("Pinned CELLxGENE datasets returned no labeled primary cells.")
            selected = (
                metadata.groupby(label_column, observed=True, group_keys=False)
                .apply(
                    lambda group: group.sample(
                        n=min(len(group), max_cells_per_label),
                        random_state=random_state,
                    ),
                    include_groups=False,
                )
                .sort_values("soma_joinid")
            )
            join_ids = selected["soma_joinid"].to_numpy(dtype=np.int64)
            reference = cellxgene_census.get_anndata(
                census,
                organism=organism,
                X_name="raw",
                obs_coords=join_ids,
                obs_column_names=["dataset_id", label_column, "tissue", "disease", "assay"],
                var_column_names=["feature_id", "feature_name"],
            )
        if reference.n_obs != len(join_ids):
            raise ValueError(
                f"CELLxGENE returned {reference.n_obs} cells; expected {len(join_ids)} selected cells."
            )
        if label_column not in reference.obs or reference.obs[label_column].isna().any():
            raise ValueError(f"CELLxGENE subset lacks complete '{label_column}' labels.")
        reference.var_names = pd.Index(reference.var["feature_name"].astype(str))
        reference.var_names_make_unique()
        reference.var_names.name = "gene"
        reference.uns["tissueagent_cellxgene_subset"] = {
            "dataset_ids": dataset_ids,
            "census_version": census_version,
            "label_column": label_column,
            "max_cells_per_label": max_cells_per_label,
            "random_state": random_state,
            "include_labels": include_labels or [],
            "organism": organism,
            "tissues": tissues or [],
            "diseases": diseases or [],
        }
        filepath.parent.mkdir(parents=True, exist_ok=True)
        partial = filepath.with_name(filepath.name + ".partial")
        partial.unlink(missing_ok=True)
        try:
            reference.write_h5ad(partial, compression="gzip")
            if not _valid_h5ad(partial):
                raise ValueError("CELLxGENE subset output failed H5AD validation.")
            partial.replace(filepath)
        except Exception:
            partial.unlink(missing_ok=True)
            raise
        return {
            "status": "success",
            "cache_hit": False,
            "dataset_ids": dataset_ids,
            "census_version": census_version,
            "label_column": label_column,
            "n_cells": reference.n_obs,
            "n_genes": reference.n_vars,
            "n_labels": int(reference.obs[label_column].nunique()),
            "output_path": str(filepath.relative_to(DATA_DIR)),
            "size_bytes": filepath.stat().st_size,
        }
    except Exception as error:
        return {"status": "error", "error_type": type(error).__name__, "message": str(error)}
