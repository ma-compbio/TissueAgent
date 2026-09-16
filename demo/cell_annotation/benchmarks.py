"""Dataset manifests and preparation helpers for cell-annotation benchmarks."""

from __future__ import annotations

import hashlib
import json
import shutil
import time
from pathlib import Path
from typing import Any

import anndata as ad
import h5py
import numpy as np
import pandas as pd
import yaml
from anndata.io import read_elem
from scipy import sparse

from config import active_project_outputs
from demo.cell_annotation.benchmark_inputs import (
    benchmark_label_columns,
    remove_or_verify_benchmark_labels,
    validate_benchmark_query,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_DIR = Path(__file__).resolve().parent / "manifests"
DEMO_OUTPUT_DIR = REPO_ROOT / "demo" / "outputs" / "cell_annotation"
DATA_DIR = REPO_ROOT / "data"
QUICK_MAX_CELLS = 25_000
RANDOM_SEED = 42
BENCHMARK_UNS_PREFIX = "tissueagent_benchmark"
SELECTION_BLIND_NAMESPACE = "tissueagent-cell-annotation-selection-v1"
SELECTION_BLIND_METADATA_CONTAINERS = ("obs", "obsm", "obsp", "uns")
LABEL_CONTRACT_KEYS = (
    "mapping_version",
    "ontology",
    "target_labels",
    "target_label_definitions",
    "prediction_only_targets",
    "prediction_only_target_scope",
    "ground_truth_mapping",
    "primary_metric",
    "headline_label_space",
    "evaluation_notes",
    "primary_excluded_ground_truth_labels",
    "secondary_label_spaces",
)


def available_datasets() -> list[str]:
    """Return benchmark IDs backed by versioned manifests."""
    return sorted(path.stem for path in MANIFEST_DIR.glob("*.yaml"))


def load_manifest(dataset_id: str) -> dict[str, Any]:
    """Load and minimally validate one benchmark manifest."""
    manifest_path = MANIFEST_DIR / f"{dataset_id}.yaml"
    if not manifest_path.exists():
        raise KeyError(
            f"Unknown dataset '{dataset_id}'. Available: {', '.join(available_datasets())}"
        )
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    required = {"schema_version", "dataset_id", "query", "ground_truth", "mapping"}
    missing = sorted(required.difference(manifest))
    if missing:
        raise ValueError(f"Manifest '{manifest_path}' is missing: {', '.join(missing)}")
    if manifest["dataset_id"] != dataset_id:
        raise ValueError(f"Manifest ID '{manifest['dataset_id']}' does not match '{dataset_id}'.")
    manifest["_manifest_path"] = str(manifest_path.relative_to(REPO_ROOT))
    return manifest


def _repo_path(value: str) -> Path:
    path = Path(value).expanduser()
    resolved = (path if path.is_absolute() else REPO_ROOT / path).resolve()
    try:
        resolved.relative_to(REPO_ROOT)
    except ValueError as exc:
        raise ValueError(f"Benchmark path must remain in repository workspace: {value}") from exc
    return resolved


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024**2), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _label_contract_sha256(mapping: dict[str, Any]) -> str:
    contract = {key: mapping[key] for key in LABEL_CONTRACT_KEYS if key in mapping}
    encoded = json.dumps(
        contract,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _selection_blind_id(
    dataset_id: str,
    run_id: str,
    run_mode: str,
    random_seed: int,
    max_quick_cells: int,
) -> str:
    payload = {
        "dataset_id": dataset_id,
        "max_quick_cells": int(max_quick_cells),
        "namespace": SELECTION_BLIND_NAMESPACE,
        "random_seed": int(random_seed),
        "run_id": run_id,
        "run_mode": run_mode,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()[:32]


def _benchmark_uns_keys(dataset: ad.AnnData) -> list[str]:
    return sorted(str(key) for key in dataset.uns if str(key).startswith(BENCHMARK_UNS_PREFIX))


def _strip_benchmark_uns(dataset: ad.AnnData) -> list[str]:
    removed = _benchmark_uns_keys(dataset)
    for key in removed:
        del dataset.uns[key]
    return removed


def _selection_blind_metadata_audit(
    dataset: ad.AnnData,
    query_config: dict[str, Any] | None,
) -> dict[str, Any]:
    allowlist = (
        query_config.get("selection_blind_allowed_metadata") if query_config is not None else None
    )
    actual = {
        "obs": sorted(str(column) for column in dataset.obs.columns),
        "obsm": sorted(str(key) for key in dataset.obsm),
        "obsp": sorted(str(key) for key in dataset.obsp),
        "uns": sorted(str(key) for key in dataset.uns),
    }
    if allowlist is None:
        return {
            "status": "not_configured",
            "enforced": False,
            "present": actual,
            "unexpected": {},
        }
    if not isinstance(allowlist, dict):
        raise TypeError("query.selection_blind_allowed_metadata must be a mapping.")
    missing_containers = sorted(set(SELECTION_BLIND_METADATA_CONTAINERS).difference(allowlist))
    extra_containers = sorted(set(allowlist).difference(SELECTION_BLIND_METADATA_CONTAINERS))
    if missing_containers or extra_containers:
        raise ValueError(
            "query.selection_blind_allowed_metadata must define exactly "
            f"{', '.join(SELECTION_BLIND_METADATA_CONTAINERS)}; "
            f"missing={missing_containers}, unexpected={extra_containers}."
        )

    allowed: dict[str, list[str]] = {}
    unexpected: dict[str, list[str]] = {}
    for container in SELECTION_BLIND_METADATA_CONTAINERS:
        values = allowlist[container]
        if (
            not isinstance(values, list)
            or any(not isinstance(value, str) or not value for value in values)
            or len(values) != len(set(values))
        ):
            raise ValueError(
                "Each query.selection_blind_allowed_metadata entry must be a list of "
                f"unique non-empty strings; invalid {container!r} entry."
            )
        allowed[container] = sorted(values)
        extra = sorted(set(actual[container]).difference(values))
        if extra:
            unexpected[container] = extra
    audit = {
        "status": "passed" if not unexpected else "failed",
        "enforced": True,
        "allowed": allowed,
        "present": actual,
        "unexpected": unexpected,
    }
    if unexpected:
        details = "; ".join(f"{container}={keys}" for container, keys in unexpected.items())
        raise ValueError(
            "Selection-blind query contains metadata outside its explicit allowlist: " + details
        )
    return audit


def validate_selection_blind_query(
    path: Path,
    query_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Reject benchmark metadata that would reveal held-out evaluation information."""
    dataset = ad.read_h5ad(path, backed="r")
    try:
        forbidden = _benchmark_uns_keys(dataset)
        metadata_audit = _selection_blind_metadata_audit(dataset, query_config)
    finally:
        dataset.file.close()
    if forbidden:
        raise ValueError(
            "Selection-blind query contains forbidden benchmark .uns keys: " + ", ".join(forbidden)
        )
    return {
        "status": "passed",
        "forbidden_benchmark_uns_keys": forbidden,
        "metadata_allowlist": metadata_audit,
    }


def validate_selection_blind_input_pair(
    query_path: Path,
    reference_path: Path,
    query_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Enforce benchmark-only leakage and independent-reference contracts."""
    query_path = Path(query_path)
    reference_path = Path(reference_path)
    query_audit = validate_selection_blind_query(query_path, query_config)
    query = ad.read_h5ad(query_path, backed="r")
    reference = ad.read_h5ad(reference_path, backed="r")
    try:
        query_names = {str(value) for value in query.obs_names}
        reference_names = {str(value) for value in reference.obs_names}
        overlap_count = len(query_names.intersection(reference_names))
        overlap_audit = {
            "status": "passed" if overlap_count == 0 else "failed",
            "requirement": "exact_query_reference_observation_name_overlap_equals_zero",
            "exact_count": int(overlap_count),
            "query_n_obs": int(query.n_obs),
            "reference_n_obs": int(reference.n_obs),
            "query_obs_names_unique": bool(query.obs_names.is_unique),
            "reference_obs_names_unique": bool(reference.obs_names.is_unique),
        }
    finally:
        query.file.close()
        reference.file.close()
    if overlap_count:
        raise ValueError(
            "Selection-blind benchmark query/reference observation-name overlap must be "
            f"zero; found {overlap_count} shared identifier(s)."
        )
    return {
        "status": "passed",
        "scope": "selection_blind_query_and_selected_reference",
        "query_leakage_audit": query_audit,
        "reference_independence_audit": overlap_audit,
    }


def _link_or_copy(source: Path, destination: Path) -> None:
    if destination.exists():
        raise FileExistsError(f"Benchmark input already exists: {destination}")
    try:
        destination.hardlink_to(source)
    except OSError:
        shutil.copy2(source, destination)


def _verify_local_file(path: Path, config: dict[str, Any]) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Required local benchmark file is missing: {path}")
    if "size_bytes" in config and path.stat().st_size != int(config["size_bytes"]):
        raise ValueError(
            f"Size mismatch for '{path}': {path.stat().st_size} != {config['size_bytes']}."
        )
    if config.get("sha256") and _sha256(path) != config["sha256"].casefold():
        raise ValueError(f"SHA-256 mismatch for local benchmark file: {path}")


def _provenance_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _provenance_value(item) for key, item in value.items()}
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return [_provenance_value(item) for item in value.tolist()]
    if isinstance(value, (list, tuple)):
        return [_provenance_value(item) for item in value]
    return value


def _validate_cached_reference(path: Path, reference: dict[str, Any]) -> None:
    dataset = ad.read_h5ad(path, backed="r")
    try:
        if dataset.n_obs <= 0 or dataset.n_vars <= 0:
            raise ValueError(f"Cached reference is not a valid non-empty H5AD: {path}")
        label_column = reference.get("cell_type_column")
        if label_column is not None:
            if label_column not in dataset.obs:
                raise ValueError(
                    f"Cached reference lacks configured .obs['{label_column}']: {path}"
                )
            labels = dataset.obs[label_column]
            if labels.isna().any() or labels.astype(str).str.strip().eq("").any():
                raise ValueError(
                    f"Cached reference has missing configured .obs['{label_column}'] labels: {path}"
                )

        if reference["kind"] != "cellxgene_subset":
            return
        provenance = dataset.uns.get("tissueagent_cellxgene_subset")
        if not isinstance(provenance, dict):
            raise ValueError(f"Cached CELLxGENE reference lacks subset provenance: {path}")
        expected = {
            "dataset_ids": reference["dataset_ids"],
            "census_version": reference["census_version"],
            "label_column": reference["cell_type_column"],
            "max_cells_per_label": int(reference["max_cells_per_label"]),
            "random_state": int(reference["random_state"]),
            "include_labels": reference.get("include_labels", []),
            "organism": reference.get("organism", "Mus musculus"),
            "tissues": reference.get("tissues", []),
            "diseases": reference.get("diseases", []),
        }
        mismatches = [
            key
            for key, expected_value in expected.items()
            if _provenance_value(provenance.get(key)) != expected_value
        ]
        if mismatches:
            raise ValueError(
                "Cached CELLxGENE reference provenance does not match the benchmark manifest: "
                + ", ".join(mismatches)
            )
        configured_labels = set(reference.get("include_labels", []))
        if configured_labels:
            observed_labels = set(dataset.obs[label_column].astype(str))
            missing = sorted(configured_labels.difference(observed_labels))
            extra = sorted(observed_labels.difference(configured_labels))
            if missing or extra:
                raise ValueError(
                    "Cached CELLxGENE reference labels do not match include_labels: "
                    f"missing={missing}, extra={extra}."
                )
    finally:
        dataset.file.close()


def _ensure_query_source(manifest: dict[str, Any]) -> tuple[Path, Path | None]:
    query = manifest["query"]
    kind = query["kind"]
    source = _repo_path(query["path"])
    if kind == "local_h5ad":
        _verify_local_file(source, query)
        truth_config = manifest["ground_truth"]
        ground_truth_path = truth_config.get("path")
        if ground_truth_path is None:
            return source, None
        external_truth = _repo_path(ground_truth_path)
        _verify_local_file(external_truth, truth_config)
        return source, external_truth

    converted = _repo_path(query["converted_path"])
    if not converted.exists():
        if kind == "zenodo_8327576_mouse_cns_csv":
            from demo.cell_annotation.zenodo_mouse_cns import convert_zenodo_mouse_cns_csv

            converted.parent.mkdir(parents=True, exist_ok=True)
            result = convert_zenodo_mouse_cns_csv(
                source,
                converted,
                expected_n_obs=int(query["expected_n_obs"]),
                expected_n_vars=int(query["expected_n_vars"]),
                overwrite=False,
                evaluation_label_columns=list(benchmark_label_columns("mouse_cns")),
            )
        else:
            from agents.agent_registry.data_onboarding_agent.tools_impl.onboarding import (
                convert_spatial_data,
            )

            result = convert_spatial_data(
                str(source),
                str(converted),
                input_format=kind,
                expected_n_obs=int(query["expected_n_obs"]),
                expected_n_vars=int(query["expected_n_vars"]),
            )
        if result.get("status") != "success":
            raise RuntimeError(result.get("message", str(result)))

    ground_truth_path = converted.with_suffix(".ground_truth.tsv")
    if kind == "zenodo_8327576_mouse_cns_csv" and not ground_truth_path.exists():
        raise FileNotFoundError(f"Mouse CNS ground-truth sidecar is missing: {ground_truth_path}")
    return converted, ground_truth_path if ground_truth_path.exists() else None


def _ensure_reference(manifest: dict[str, Any]) -> Path:
    reference = manifest["reference"]
    destination = _repo_path(reference["path"])
    kind = reference["kind"]
    if kind == "local_h5ad":
        _verify_local_file(destination, reference)
        return destination
    if destination.exists():
        _validate_cached_reference(destination, reference)
        return destination

    if kind == "local_seurat_reference":
        source = _repo_path(reference["source_path"])
        _verify_local_file(
            source,
            {
                "size_bytes": reference["source_size_bytes"],
                "sha256": reference["source_sha256"],
            },
        )
        converted = _repo_path(reference["converted_full_path"])
        if not converted.exists():
            from agents.agent_registry.data_onboarding_agent.tools_impl.onboarding import (
                convert_spatial_data,
            )

            conversion = convert_spatial_data(
                str(source),
                str(converted),
                input_format="seurat_rds",
                expected_n_obs=int(reference["expected_n_obs"]),
                expected_n_vars=int(reference["expected_n_vars"]),
            )
            if conversion.get("status") != "success":
                raise RuntimeError(conversion.get("message", str(conversion)))
        full_reference = ad.read_h5ad(converted)
        label_column = reference["cell_type_column"]
        allowed_labels = reference["include_labels"]
        if label_column not in full_reference.obs:
            raise KeyError(f"Reference lacks .obs['{label_column}'].")
        eligible = full_reference.obs[label_column].isin(allowed_labels)
        eligible_indices = np.flatnonzero(eligible.to_numpy())
        if not len(eligible_indices):
            raise ValueError("No reference cells matched configured ovarian labels.")
        eligible_labels = full_reference.obs.iloc[eligible_indices][label_column]
        rng = np.random.default_rng(int(reference["random_state"]))
        local_indices: list[int] = []
        label_values = eligible_labels.astype(str).to_numpy()
        for label in allowed_labels:
            candidates = np.flatnonzero(label_values == label)
            count = min(len(candidates), int(reference["max_cells_per_label"]))
            local_indices.extend(rng.choice(candidates, size=count, replace=False).tolist())
        local_indices = sorted(local_indices)
        selected_indices = eligible_indices[local_indices]
        subset = full_reference[selected_indices].copy()
        missing_labels = sorted(set(allowed_labels).difference(subset.obs[label_column].unique()))
        if missing_labels:
            raise ValueError("Reference subset lacks labels: " + ", ".join(missing_labels))
        subset.uns["tissueagent_reference"] = {
            "source": str(source.relative_to(REPO_ROOT)),
            "query_cells_used": False,
            "max_cells_per_label": int(reference["max_cells_per_label"]),
            "random_state": int(reference["random_state"]),
        }
        destination.parent.mkdir(parents=True, exist_ok=True)
        partial = destination.with_name(f".{destination.stem}.partial.h5ad")
        subset.write_h5ad(partial, compression="gzip")
        partial.replace(destination)
        return destination

    if kind == "https_h5ad":
        from agents.agent_registry.data_onboarding_agent.tools_impl.onboarding import (
            download_spatial_data,
        )

        result = download_spatial_data(
            reference["url"],
            str(destination),
            expected_checksum=reference.get("checksum"),
            expected_size_bytes=int(reference["size_bytes"]),
            max_bytes=int(reference["size_bytes"]),
        )
    elif kind in {"cellxgene", "cellxgene_subset"}:
        from agents.agent_registry.single_cell_agent.tools_impl.retrieve_cellxgene_single_cell_tool import (  # noqa: E501
            retrieve_cellxgene_reference_subset,
            retrieve_cellxgene_single_cell,
        )

        try:
            project_output = destination.relative_to(active_project_outputs()).as_posix()
        except ValueError as exc:
            raise ValueError(
                "CELLxGENE benchmark references must be stored beneath workspace/project/outputs."
            ) from exc
        if kind == "cellxgene_subset":
            result = retrieve_cellxgene_reference_subset(
                reference["dataset_ids"],
                project_output,
                census_version=reference["census_version"],
                label_column=reference["cell_type_column"],
                max_cells_per_label=int(reference["max_cells_per_label"]),
                random_state=int(reference["random_state"]),
                include_labels=reference.get("include_labels"),
                organism=reference.get("organism", "Mus musculus"),
                tissues=reference.get("tissues"),
                diseases=reference.get("diseases"),
            )
        else:
            result = retrieve_cellxgene_single_cell(
                reference["dataset_id"],
                project_output,
                census_version=reference.get("census_version", "stable"),
            )
    else:
        raise ValueError(f"Unsupported reference kind '{kind}'.")
    if result.get("status") != "success":
        raise RuntimeError(result.get("message", str(result)))
    return destination


def _balanced_indices(labels: pd.Series, maximum: int, seed: int) -> np.ndarray:
    if len(labels) <= maximum:
        return np.arange(len(labels), dtype=np.int64)
    rng = np.random.default_rng(seed)
    label_values = labels.astype("string").fillna("Unassigned").astype(str).to_numpy()
    unique_labels = sorted(pd.unique(label_values))
    quota = max(1, maximum // len(unique_labels))
    selected: list[int] = []
    for label in unique_labels:
        candidates = np.flatnonzero(label_values == label)
        count = min(quota, len(candidates))
        selected.extend(rng.choice(candidates, size=count, replace=False).tolist())
    if len(selected) < maximum:
        remaining = np.setdiff1d(np.arange(len(labels)), np.asarray(selected), assume_unique=False)
        fill = min(maximum - len(selected), len(remaining))
        selected.extend(rng.choice(remaining, size=fill, replace=False).tolist())
    return np.asarray(sorted(selected), dtype=np.int64)


def _stratified_block_indices(length: int, maximum: int, block_size: int) -> np.ndarray:
    if length <= maximum:
        return np.arange(length, dtype=np.int64)
    if block_size < 1 or block_size > maximum:
        raise ValueError("quick_block_size must be between 1 and the quick cell limit.")
    block_count = int(np.ceil(maximum / block_size))
    block_lengths = [block_size] * block_count
    block_lengths[-1] = maximum - block_size * (block_count - 1)
    centers = np.linspace(0, length - 1, num=block_count, dtype=np.int64)
    blocks: list[np.ndarray] = []
    previous_stop = 0
    for center, current_length in zip(centers, block_lengths, strict=True):
        start = min(max(int(center) - current_length // 2, previous_stop), length - current_length)
        stop = start + current_length
        blocks.append(np.arange(start, stop, dtype=np.int64))
        previous_stop = stop
    return np.concatenate(blocks)


def _decode_hdf5_strings(values: np.ndarray) -> np.ndarray:
    return np.asarray(
        [value.decode() if isinstance(value, bytes) else str(value) for value in values],
        dtype=object,
    )


def _read_hdf5_column(
    dataframe: h5py.Group,
    column: str,
    indices: np.ndarray | None = None,
) -> pd.Series:
    if column not in dataframe:
        raise KeyError(f"H5AD dataframe is missing column '{column}'.")
    element = dataframe[column]
    if isinstance(element, h5py.Group):
        categories = element["categories"][:]
        if categories.dtype.kind in {"O", "S", "U"}:
            categories = _decode_hdf5_strings(categories)
        codes = element["codes"][:] if indices is None else element["codes"][indices]
        ordered = bool(element.attrs.get("ordered", False))
        return pd.Series(pd.Categorical.from_codes(codes, categories, ordered=ordered))
    values = element[:] if indices is None else element[indices]
    if values.dtype.kind in {"O", "S", "U"}:
        values = _decode_hdf5_strings(values)
    return pd.Series(values)


def _read_hdf5_csr_rows(matrix: h5py.Group, indices: np.ndarray) -> sparse.csr_matrix:
    if not len(indices):
        shape = tuple(int(value) for value in matrix.attrs["shape"])
        return sparse.csr_matrix((0, shape[1]), dtype=matrix["data"].dtype)
    if not np.all(indices[1:] > indices[:-1]):
        raise ValueError("CSR row indices must be sorted and unique.")
    indptr = matrix["indptr"][:]
    breaks = np.flatnonzero(np.diff(indices) != 1) + 1
    runs = np.split(indices, breaks)
    shape = tuple(int(value) for value in matrix.attrs["shape"])
    pieces: list[sparse.csr_matrix] = []
    for run in runs:
        row_start = int(run[0])
        row_stop = int(run[-1]) + 1
        data_start = int(indptr[row_start])
        data_stop = int(indptr[row_stop])
        run_indptr = indptr[row_start : row_stop + 1] - data_start
        pieces.append(
            sparse.csr_matrix(
                (
                    matrix["data"][data_start:data_stop],
                    matrix["indices"][data_start:data_stop],
                    run_indptr,
                ),
                shape=(row_stop - row_start, shape[1]),
            )
        )
    return sparse.vstack(pieces, format="csr")


def _reconstruct_scaled_log1p_counts(
    matrix: sparse.spmatrix,
    source_var: pd.DataFrame,
    source_obs: h5py.Group,
    indices: np.ndarray,
    config: dict[str, Any],
) -> sparse.csr_matrix:
    mean_column = config["mean_column"]
    std_column = config["std_column"]
    library_size_column = config["library_size_obs_column"]
    missing_var = [
        column for column in (mean_column, std_column) if column not in source_var.columns
    ]
    if missing_var:
        raise KeyError("H5AD var is missing scale parameters: " + ", ".join(missing_var))

    dense = matrix.toarray().astype(np.float64, copy=False)
    restored_log1p = (
        dense * source_var[std_column].to_numpy(dtype=np.float64)[None, :]
        + source_var[mean_column].to_numpy(dtype=np.float64)[None, :]
    )
    tolerance = float(config.get("negative_tolerance", 1e-7))
    if float(restored_log1p.min()) < -tolerance:
        raise ValueError(
            "Inverse scaling produced negative log1p expression below the configured tolerance."
        )
    np.maximum(restored_log1p, 0, out=restored_log1p)
    normalized = np.expm1(restored_log1p)
    normalized_totals = normalized.sum(axis=1)
    if np.any(normalized_totals <= 0):
        raise ValueError("Inverse scaling produced one or more zero-expression observations.")
    expected_total = config.get("normalized_target_sum")
    if expected_total is not None and not np.allclose(
        normalized_totals,
        float(expected_total),
        atol=float(config.get("target_sum_tolerance", 1e-5)),
        rtol=0,
    ):
        observed = np.quantile(normalized_totals, [0, 0.5, 1]).tolist()
        raise ValueError(
            f"Reconstructed normalized totals {observed} do not match {expected_total}."
        )
    library_sizes = _read_hdf5_column(source_obs, library_size_column, indices).to_numpy(
        dtype=np.float64
    )
    reconstructed = normalized * (library_sizes / normalized_totals)[:, None]
    rounded = np.rint(reconstructed)
    maximum_error = float(np.max(np.abs(reconstructed - rounded)))
    if maximum_error > float(config.get("integer_tolerance", 1e-5)):
        raise ValueError(
            "Count reconstruction was not integer-like; maximum rounding error was "
            f"{maximum_error:.6g}."
        )
    if float(rounded.max()) > np.iinfo(np.int32).max:
        raise OverflowError("Reconstructed counts exceed int32 capacity.")
    result = sparse.csr_matrix(rounded.astype(np.int32, copy=False))
    result.eliminate_zeros()
    return result


def _prepare_hdf5_csr_subset(
    source_path: Path,
    manifest: dict[str, Any],
    *,
    run_mode: str,
    max_quick_cells: int,
    random_seed: int,
) -> tuple[ad.AnnData, pd.DataFrame, np.ndarray, tuple[int, int]]:
    query_config = manifest["query"]
    truth_config = manifest["ground_truth"]
    with h5py.File(source_path, "r") as source:
        matrix = source["X"]
        if matrix.attrs.get("encoding-type") not in {"csr_matrix", b"csr_matrix"}:
            raise ValueError("The low-memory H5AD path currently requires CSR-encoded X.")
        shape = tuple(int(value) for value in matrix.attrs["shape"])
        label_column = truth_config["column"]
        if run_mode == "quick":
            sampling = query_config.get("quick_sampling", "balanced_labels")
            if sampling == "balanced_labels":
                labels = _read_hdf5_column(source["obs"], label_column)
                indices = _balanced_indices(labels, max_quick_cells, random_seed)
            elif sampling == "stratified_blocks":
                indices = _stratified_block_indices(
                    shape[0],
                    max_quick_cells,
                    int(query_config.get("quick_block_size", 500)),
                )
            else:
                raise ValueError(f"Unsupported quick sampling strategy '{sampling}'.")
        else:
            maximum = int(query_config.get("max_materialized_cells", shape[0]))
            if shape[0] > maximum:
                raise ValueError(
                    f"Full materialization of {shape[0]} cells exceeds the configured "
                    f"limit of {maximum}; use run_mode='quick'."
                )
            indices = np.arange(shape[0], dtype=np.int64)

        index_key = source["obs"].attrs.get("_index", "_index")
        if isinstance(index_key, bytes):
            index_key = index_key.decode()
        obs_names = pd.Index(
            _read_hdf5_column(source["obs"], str(index_key), indices).astype(str),
            name=None,
        )
        held_out = truth_config["held_out_columns"]
        truth = pd.DataFrame(
            {
                column: _read_hdf5_column(source["obs"], column, indices).to_numpy()
                for column in held_out
            },
            index=obs_names,
        )
        preserved_columns = query_config.get("preserve_obs_columns", [])
        obs = pd.DataFrame(
            {
                column: _read_hdf5_column(source["obs"], column, indices).to_numpy()
                for column in preserved_columns
            },
            index=obs_names,
        )
        source_var = read_elem(source["var"])
        preserved_var = query_config.get("preserve_var_columns", [])
        var = (
            source_var[preserved_var].copy()
            if preserved_var
            else pd.DataFrame(index=source_var.index.copy())
        )
        selected_matrix = _read_hdf5_csr_rows(matrix, indices)
        reconstruction = query_config.get("matrix_reconstruction")
        if reconstruction:
            if reconstruction.get("kind") != "inverse_scale_log1p_with_library_size":
                raise ValueError(
                    f"Unsupported matrix reconstruction kind: {reconstruction.get('kind')}"
                )
            selected_matrix = _reconstruct_scaled_log1p_counts(
                selected_matrix,
                source_var,
                source["obs"],
                indices,
                reconstruction,
            )
        else:
            selected_matrix = selected_matrix.tocsr()

        query = ad.AnnData(X=selected_matrix, obs=obs, var=var)
        spatial_key = query_config.get("spatial_obsm_key", "spatial")
        if spatial_key not in source["obsm"]:
            raise KeyError(f"H5AD is missing obsm['{spatial_key}'] coordinates.")
        query.obsm["spatial"] = source["obsm"][spatial_key][indices]
    return query, truth, indices, query.shape


def _read_truth(
    source: ad.AnnData,
    manifest: dict[str, Any],
    external_truth_path: Path | None,
) -> pd.DataFrame:
    truth_config = manifest["ground_truth"]
    held_out = truth_config["held_out_columns"]
    if external_truth_path is not None:
        truth = pd.read_csv(external_truth_path, sep="\t", index_col=0, low_memory=False)
        truth.index = truth.index.astype(str)
    else:
        missing = sorted(set(held_out).difference(source.obs.columns))
        if missing:
            raise KeyError(f"Query source is missing ground-truth columns: {', '.join(missing)}")
        truth = source.obs[held_out].copy()
    if truth_config["column"] not in truth:
        raise KeyError(f"Ground-truth sidecar is missing '{truth_config['column']}'.")
    if not truth.index.is_unique:
        raise ValueError("Ground-truth cell identifiers are not unique.")
    missing_truth = source.obs_names.difference(truth.index)
    if len(missing_truth):
        raise ValueError(f"Ground truth is missing {len(missing_truth)} query cells.")
    return truth.reindex(source.obs_names)


def _strip_query_artifacts(
    query: ad.AnnData,
    query_config: dict[str, Any],
) -> dict[str, list[str]]:
    configured = {
        "obs": list(query_config.get("strip_obs_columns", [])),
        "obsm": list(query_config.get("strip_obsm_keys", [])),
        "obsp": list(query_config.get("strip_obsp_keys", [])),
        "uns": list(query_config.get("strip_uns_keys", [])),
    }
    containers = {
        "obs": query.obs,
        "obsm": query.obsm,
        "obsp": query.obsp,
        "uns": query.uns,
    }
    missing = {
        kind: sorted(set(keys).difference(containers[kind]))
        for kind, keys in configured.items()
        if set(keys).difference(containers[kind])
    }
    if missing:
        details = "; ".join(f"{kind}={keys}" for kind, keys in missing.items())
        raise KeyError(f"Configured query artifacts are absent: {details}")
    if configured["obs"]:
        query.obs = query.obs.drop(columns=configured["obs"])
    for kind in ("obsm", "obsp", "uns"):
        for key in configured[kind]:
            del containers[kind][key]
    return configured


def prepare_benchmark(
    dataset_id: str,
    run_mode: str = "quick",
    run_id: str | None = None,
    max_quick_cells: int = QUICK_MAX_CELLS,
    random_seed: int = RANDOM_SEED,
) -> dict[str, Any]:
    """Create a leakage-free query plus evaluator-only truth and label contracts."""
    if run_mode not in {"quick", "full"}:
        raise ValueError("run_mode must be 'quick' or 'full'.")
    manifest = load_manifest(dataset_id)
    query_source, external_truth = _ensure_query_source(manifest)
    run_id = run_id or time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    run_dir = DEMO_OUTPUT_DIR / dataset_id / run_id
    if run_dir.exists() and any(run_dir.iterdir()):
        raise FileExistsError(f"Run directory already exists and is not empty: {run_dir}")
    selection_blind_id = _selection_blind_id(
        dataset_id,
        run_id,
        run_mode,
        random_seed,
        max_quick_cells,
    )
    data_run_dir = run_dir / "benchmark_input" / selection_blind_id
    query_output = data_run_dir / "query.h5ad"

    direct_copy = False
    source_benchmark_uns_keys: list[str] = []
    query_shape: tuple[int, int]
    label_column = manifest["ground_truth"]["column"]
    held_out = manifest["ground_truth"]["held_out_columns"]
    configured_columns = tuple(held_out)
    if configured_columns != benchmark_label_columns(dataset_id):
        raise ValueError(f"Manifest evaluation labels do not match the fixed {dataset_id} utility.")
    read_strategy = manifest["query"].get("read_strategy", "anndata")
    if read_strategy == "hdf5_csr_subset":
        if external_truth is not None:
            raise ValueError("The low-memory H5AD path does not accept an external truth sidecar.")
        query, selected_truth, indices, query_shape = _prepare_hdf5_csr_subset(
            query_source,
            manifest,
            run_mode=run_mode,
            max_quick_cells=max_quick_cells,
            random_seed=random_seed,
        )
    elif read_strategy == "anndata":
        source = ad.read_h5ad(query_source, backed="r")
        try:
            truth = _read_truth(source, manifest, external_truth)
            source_benchmark_uns_keys = _benchmark_uns_keys(source)
            if run_mode == "quick":
                indices = _balanced_indices(truth[label_column], max_quick_cells, random_seed)
            else:
                indices = np.arange(source.n_obs, dtype=np.int64)
            selected_truth = truth.iloc[indices].copy()
            direct_copy = (
                run_mode == "full"
                and external_truth is not None
                and not set(held_out).intersection(source.obs.columns)
                and not any(
                    manifest["query"].get(key)
                    for key in (
                        "strip_obs_columns",
                        "strip_obsm_keys",
                        "strip_obsp_keys",
                        "strip_uns_keys",
                    )
                )
                and not source_benchmark_uns_keys
            )
            if direct_copy:
                query_shape = source.shape
            else:
                query = source[indices].to_memory()
                query_shape = query.shape
        finally:
            source.file.close()
    else:
        raise ValueError(f"Unsupported H5AD read strategy '{read_strategy}'.")

    run_dir.mkdir(parents=True, exist_ok=True)
    data_run_dir.mkdir(parents=True, exist_ok=False)
    stripped_artifacts = {"obs": [], "obsm": [], "obsp": [], "uns": []}
    removed_benchmark_uns_keys: list[str] = []
    if direct_copy:
        shutil.copy2(query_source, query_output)
        copy_strategy = "direct_copy"
    else:
        remove_or_verify_benchmark_labels(dataset_id, query)
        stripped_artifacts = _strip_query_artifacts(query, manifest["query"])
        removed_benchmark_uns_keys = sorted(
            set(source_benchmark_uns_keys).union(_strip_benchmark_uns(query))
        )
        query.uns["species"] = manifest["species"]
        query.write_h5ad(query_output, compression="gzip")
        copy_strategy = (
            "low_memory_reconstruction"
            if read_strategy == "hdf5_csr_subset"
            else "sanitized_rewrite"
        )
    query_blinding_audit = validate_selection_blind_query(query_output, manifest["query"])

    truth_output = run_dir / "ground_truth.tsv"
    selected_truth.to_csv(truth_output, sep="\t", index=True)
    mapping_source = _repo_path(manifest["mapping"])
    mapping = json.loads(mapping_source.read_text(encoding="utf-8"))
    label_contract_sha256 = _label_contract_sha256(mapping)
    expected_label_contract_sha256 = manifest.get("label_contract_sha256")
    if (
        expected_label_contract_sha256 is not None
        and label_contract_sha256 != expected_label_contract_sha256
    ):
        raise ValueError("Mapping label-contract SHA-256 does not match the benchmark manifest.")
    if manifest.get("require_pending_label_mapping", False):
        if mapping.get("prediction_mapping_status") != "pending":
            raise ValueError("Benchmark preparation requires a pending label mapping.")
        nonempty_fields = []
        if mapping.get("common_prediction_mapping"):
            nonempty_fields.append("common_prediction_mapping")
        if any(mapping.get("method_prediction_mapping", {}).values()):
            nonempty_fields.append("method_prediction_mapping")
        if any(mapping.get("method_prediction_rules", {}).values()):
            nonempty_fields.append("method_prediction_rules")
        if nonempty_fields:
            raise ValueError(
                "Pending label mapping contains prediction-dependent crosswalks: "
                + ", ".join(nonempty_fields)
            )
    mapping_output = run_dir / "label_mapping.json"
    shutil.copy2(mapping_source, mapping_output)

    validation = validate_benchmark_query(
        dataset_id,
        str(query_output),
        expected_n_obs=len(indices),
        expected_n_vars=int(manifest["query"]["expected_n_vars"]),
        require_spatial=bool(manifest["query"].get("require_spatial", True)),
    )
    if validation["status"] != "success":
        raise RuntimeError(
            "Prepared benchmark failed validation: " + "; ".join(validation["errors"])
        )

    prepared = {
        "schema_version": "1.0",
        "dataset_id": dataset_id,
        "run_id": run_id,
        "run_mode": run_mode,
        "selection_blind_id": selection_blind_id,
        "query_h5ad": str(query_output.relative_to(REPO_ROOT)),
        "ground_truth_tsv": str(truth_output.relative_to(REPO_ROOT)),
        "ground_truth_column": label_column,
        "label_mapping_json": str(mapping_output.relative_to(REPO_ROOT)),
        "label_contract_sha256": label_contract_sha256,
        "run_dir": str(run_dir.relative_to(REPO_ROOT)),
        "n_obs": int(query_shape[0]),
        "n_vars": int(query_shape[1]),
        "random_seed": random_seed,
        "manifest": manifest["_manifest_path"],
        "query_preparation": {
            "run_mode": run_mode,
            "species": manifest["species"],
            "ground_truth_held_out": True,
            "random_seed": random_seed,
            "source_read_strategy": read_strategy,
            "copy_strategy": copy_strategy,
            "matrix_reconstruction": manifest["query"].get("matrix_reconstruction", {}),
            "stripped_query_artifacts": stripped_artifacts,
            "benchmark_uns_prefix": BENCHMARK_UNS_PREFIX,
            "benchmark_uns_keys_removed": removed_benchmark_uns_keys,
        },
        "selection_blind_query_audit": query_blinding_audit,
        "validation": validation,
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    run_manifest = run_dir / "prepared_run.json"
    run_manifest.write_text(json.dumps(prepared, indent=2), encoding="utf-8")
    prepared["prepared_run_json"] = str(run_manifest.relative_to(REPO_ROOT))
    return prepared
