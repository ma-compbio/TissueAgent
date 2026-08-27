"""Download CELLxGENE Census source h5ad files into the active project."""

import json
from datetime import datetime, timezone
from typing import Any

import cellxgene_census
import anndata as ad
import fsspec
import numpy as np
import pandas as pd
from pathlib import Path

from agents.workspace_paths import resolve_project_output, workspace_relative


MAX_AUTOMATIC_SOURCE_H5AD_BYTES = 2 * 1024**3


def _source_h5ad_size(dataset_id: str, census_version: str) -> int:
    locator = cellxgene_census.get_source_h5ad_uri(
        dataset_id,
        census_version=census_version,
    )
    uri = str(locator["uri"])
    region = locator.get("s3_region")
    storage_options: dict[str, Any] = {"anon": True}
    if region:
        storage_options["client_kwargs"] = {"region_name": region}
    filesystem, path = fsspec.core.url_to_fs(uri, **storage_options)
    return int(filesystem.info(path)["size"])


def _write_provenance(filepath: Path, details: dict[str, Any]) -> Path:
    provenance_path = filepath.with_suffix(".provenance.json")
    payload = {
        **details,
        "output_path": workspace_relative(filepath),
        "size_bytes": filepath.stat().st_size,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }
    partial = provenance_path.with_name(provenance_path.name + ".partial")
    partial.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    partial.replace(provenance_path)
    return provenance_path


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
    dataset_title: str | None = None,
    dataset_url: str | None = None,
    selection_filters: dict[str, Any] | None = None,
    allow_large_download: bool = False,
):
    """Download a CELLxGENE dataset as an h5ad file into DATA_DIR.

    Args:
        dataset_id: CELLxGENE Census dataset identifier.
        filename: Target filename. Lands at
            ``project/outputs/datasets/<filename>`` so the user
            can see the downloaded dataset in the Files panel and the
            agent can read it back from a stable relative path.
        census_version: Pinned Census release or the stable alias.
        dataset_title: Optional title returned by the preceding CELLxGENE query.
        dataset_url: Optional dataset or collection URL returned by the query.
        selection_filters: Optional filters used to choose this dataset.
        allow_large_download: Permit a complete source H5AD larger than the automatic 2 GiB
            operational limit. Use only when the user explicitly requests the complete source
            object, never for a downstream annotation reference.

    Returns:
        Structured status and the exact downloaded artifact.
    """
    try:
        filepath = resolve_project_output(filename, suffix=".h5ad")
    except ValueError as e:
        return {"status": "error", "error_type": type(e).__name__, "message": str(e)}
    if allow_large_download and "references" in filepath.parts:
        return {
            "status": "error",
            "error_type": "ValueError",
            "message": (
                "allow_large_download cannot be used for an annotation reference path; use "
                "retrieve_cellxgene_reference_subset_tool for project/outputs/references/."
            ),
        }

    if filepath.exists():
        if _valid_h5ad(filepath):
            provenance_path = _write_provenance(
                filepath,
                {
                    "operation": "retrieve_cellxgene_single_cell",
                    "cache_hit": True,
                    "dataset_id": dataset_id,
                    "dataset_title": dataset_title,
                    "dataset_url": dataset_url,
                    "census_version": census_version,
                    "selection_filters": selection_filters or {},
                },
            )
            return {
                "status": "success",
                "cache_hit": True,
                "dataset_id": dataset_id,
                "census_version": census_version,
                "output_path": workspace_relative(filepath),
                "size_bytes": filepath.stat().st_size,
                "provenance_path": workspace_relative(provenance_path),
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
        source_size_bytes = _source_h5ad_size(dataset_id, census_version)
        if source_size_bytes > MAX_AUTOMATIC_SOURCE_H5AD_BYTES and not allow_large_download:
            raise ValueError(
                "Complete CELLxGENE source H5AD is "
                f"{source_size_bytes / 1024**3:.2f} GiB, above the automatic 2 GiB limit. "
                "For a cell-annotation reference, use "
                "retrieve_cellxgene_reference_subset_tool. Set allow_large_download=true only "
                "when the user explicitly requested the complete source object."
            )
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
    provenance_path = _write_provenance(
        filepath,
        {
            "operation": "retrieve_cellxgene_single_cell",
            "cache_hit": False,
            "dataset_id": dataset_id,
            "dataset_title": dataset_title,
            "dataset_url": dataset_url,
            "census_version": census_version,
            "selection_filters": selection_filters or {},
            "source_size_bytes": source_size_bytes,
            "allow_large_download": allow_large_download,
        },
    )
    return {
        "status": "success",
        "cache_hit": False,
        "dataset_id": dataset_id,
        "census_version": census_version,
        "output_path": workspace_relative(filepath),
        "size_bytes": filepath.stat().st_size,
        "provenance_path": workspace_relative(provenance_path),
    }


def retrieve_cellxgene_reference_subset(
    dataset_ids: list[str],
    filename: str,
    census_version: str,
    label_column: str = "cell_type",
    max_cells_per_label: int = 500,
    max_source_cells: int = 1_000_000,
    random_state: int = 42,
    include_labels: list[str] | None = None,
    organism: str = "Mus musculus",
    tissues: list[str] | None = None,
    diseases: list[str] | None = None,
):
    """Retrieve a reproducible label-balanced Census subset without full source downloads."""
    try:
        filepath = resolve_project_output(filename, suffix=".h5ad")
        if not dataset_ids:
            raise ValueError("dataset_ids must contain at least one pinned dataset ID.")
        if max_cells_per_label < 1:
            raise ValueError("max_cells_per_label must be positive.")
        if max_source_cells < 1:
            raise ValueError("max_source_cells must be positive.")
        for dataset_id in dataset_ids:
            if not dataset_id or any(
                char not in "0123456789abcdef-" for char in dataset_id.casefold()
            ):
                raise ValueError(f"Invalid CELLxGENE dataset ID: {dataset_id}")
        if filepath.exists():
            if _valid_h5ad(filepath):
                provenance_path = _write_provenance(
                    filepath,
                    {
                        "operation": "retrieve_cellxgene_reference_subset",
                        "cache_hit": True,
                        "dataset_ids": dataset_ids,
                        "census_version": census_version,
                        "label_column": label_column,
                        "max_cells_per_label": max_cells_per_label,
                        "max_source_cells": max_source_cells,
                        "random_state": random_state,
                        "include_labels": include_labels or [],
                        "organism": organism,
                        "tissues": tissues or [],
                        "diseases": diseases or [],
                    },
                )
                return {
                    "status": "success",
                    "cache_hit": True,
                    "dataset_ids": dataset_ids,
                    "census_version": census_version,
                    "output_path": workspace_relative(filepath),
                    "size_bytes": filepath.stat().st_size,
                    "provenance_path": workspace_relative(provenance_path),
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
            source_metadata = (
                census["census_info"]["datasets"]
                .read(
                    value_filter=f"({dataset_filter})",
                    column_names=["dataset_id", "dataset_total_cell_count"],
                )
                .concat()
                .to_pandas()
            )
            source_cell_counts = {
                str(row.dataset_id): int(row.dataset_total_cell_count)
                for row in source_metadata.itertuples(index=False)
            }
            missing_source_ids = sorted(set(dataset_ids).difference(source_cell_counts))
            if missing_source_ids:
                raise ValueError(
                    "Pinned CELLxGENE dataset IDs are absent from the selected Census release: "
                    + ", ".join(missing_source_ids)
                )
            oversized_sources = {
                dataset_id: count
                for dataset_id, count in source_cell_counts.items()
                if count > max_source_cells
            }
            if oversized_sources:
                details = ", ".join(
                    f"{dataset_id} ({count:,} cells)"
                    for dataset_id, count in sorted(oversized_sources.items())
                )
                raise ValueError(
                    "Pinned source exceeds the automatic bounded-reference scan limit of "
                    f"{max_source_cells:,} cells: {details}. Select a smaller sufficient atlas "
                    "from the discovery results."
                )
            obs = census["census_data"][organism_key].obs
            metadata = (
                obs.read(
                    value_filter=value_filter,
                    column_names=["soma_joinid", "dataset_id", label_column],
                )
                .concat()
                .to_pandas()
            )
            metadata = metadata.dropna(subset=[label_column])
            if include_labels:
                metadata = metadata[metadata[label_column].isin(include_labels)]
                missing_labels = sorted(
                    set(include_labels).difference(metadata[label_column].unique())
                )
                if missing_labels:
                    raise ValueError(
                        "Pinned CELLxGENE datasets lack requested labels: "
                        + ", ".join(missing_labels)
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
                f"CELLxGENE returned {reference.n_obs} cells; expected "
                f"{len(join_ids)} selected cells."
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
            "max_source_cells": max_source_cells,
            "source_cell_counts": source_cell_counts,
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
        provenance_path = _write_provenance(
            filepath,
            {
                "operation": "retrieve_cellxgene_reference_subset",
                "cache_hit": False,
                "dataset_ids": dataset_ids,
                "census_version": census_version,
                "label_column": label_column,
                "max_cells_per_label": max_cells_per_label,
                "max_source_cells": max_source_cells,
                "source_cell_counts": source_cell_counts,
                "random_state": random_state,
                "include_labels": include_labels or [],
                "organism": organism,
                "tissues": tissues or [],
                "diseases": diseases or [],
                "n_cells": reference.n_obs,
                "n_genes": reference.n_vars,
                "n_labels": int(reference.obs[label_column].nunique()),
            },
        )
        return {
            "status": "success",
            "cache_hit": False,
            "dataset_ids": dataset_ids,
            "census_version": census_version,
            "label_column": label_column,
            "n_cells": reference.n_obs,
            "n_genes": reference.n_vars,
            "n_labels": int(reference.obs[label_column].nunique()),
            "output_path": workspace_relative(filepath),
            "size_bytes": filepath.stat().st_size,
            "provenance_path": workspace_relative(provenance_path),
        }
    except Exception as error:
        return {"status": "error", "error_type": type(error).__name__, "message": str(error)}
