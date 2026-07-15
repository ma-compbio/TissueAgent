"""Convert the Zenodo 8327576 mouse CNS CSV release into annotation-ready AnnData."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import sys
import time
from pathlib import Path
from typing import Any

import anndata as ad
import numpy as np
import pandas as pd
from scipy import sparse

from config import DATA_DIR, ROOT


TRUTH_COLUMNS = (
    "Main_molecular_cell_type",
    "Sub_molecular_cell_type",
    "Main_molecular_tissue_region",
    "Sub_molecular_tissue_region",
    "Molecular_spatial_cell_type",
)


def _md5(path: Path) -> str:
    digest = hashlib.md5()  # noqa: S324 - publisher supplies MD5 for integrity verification
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024**2), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024**2), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_typed_csv(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, skiprows=[1], low_memory=False)
    if "NAME" not in frame.columns:
        raise ValueError(f"Typed metadata CSV '{path.name}' is missing NAME.")
    frame = frame.set_index("NAME")
    frame.index = frame.index.astype(str)
    if not frame.index.is_unique:
        raise ValueError(f"Typed metadata CSV '{path.name}' has duplicate NAME values.")
    return frame


def _merge_obs(obs: pd.DataFrame, extra: pd.DataFrame, source_name: str) -> pd.DataFrame:
    aligned = extra.reindex(obs.index)
    for column in aligned.columns:
        if column not in obs:
            obs[column] = aligned[column]
            continue
        conflict = obs[column].notna() & aligned[column].notna() & (obs[column] != aligned[column])
        if conflict.any():
            raise ValueError(
                f"Conflicting '{column}' values while joining {source_name} for "
                f"{int(conflict.sum())} cells."
            )
        obs[column] = obs[column].where(obs[column].notna(), aligned[column])
    return obs


def _load_raw_expression(path: Path) -> tuple[sparse.csr_matrix, list[str], list[str]]:
    csv.field_size_limit(sys.maxsize)
    with path.open("r", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader, None)
        if not header or header[0].strip().casefold() != "gene":
            raise ValueError(f"'{path.name}' must begin with GENE,<cell ids>.")
        cell_ids = [value.strip() for value in header[1:]]
        if len(cell_ids) != len(set(cell_ids)):
            raise ValueError(f"'{path.name}' contains duplicate cell identifiers.")

        genes: list[str] = []
        data_chunks: list[np.ndarray] = []
        index_chunks: list[np.ndarray] = []
        indptr = [0]
        for line_number, row in enumerate(reader, start=2):
            if len(row) != len(cell_ids) + 1:
                raise ValueError(
                    f"'{path.name}' line {line_number} has {len(row) - 1} values; "
                    f"expected {len(cell_ids)}."
                )
            genes.append(row[0].strip())
            values = np.asarray(row[1:], dtype=np.int32)
            if np.any(values < 0):
                raise ValueError(f"'{path.name}' contains negative raw counts at line {line_number}.")
            nonzero = values != 0
            indices = np.flatnonzero(nonzero).astype(np.int32, copy=False)
            data_chunks.append(values[nonzero])
            index_chunks.append(indices)
            indptr.append(indptr[-1] + len(indices))

    if len(genes) != len(set(genes)):
        raise ValueError(f"'{path.name}' contains duplicate gene identifiers.")
    data = np.concatenate(data_chunks) if data_chunks else np.array([], dtype=np.int32)
    indices = np.concatenate(index_chunks) if index_chunks else np.array([], dtype=np.int32)
    matrix = sparse.csc_matrix(
        (data, indices, np.asarray(indptr, dtype=np.int64)),
        shape=(len(cell_ids), len(genes)),
        dtype=np.int32,
    ).tocsr()
    matrix.eliminate_zeros()
    return matrix, genes, cell_ids


def _verify_publisher_manifest(source_dir: Path, required: set[str]) -> dict[str, Any]:
    manifest_path = source_dir / "zenodo_8327576_manifest.tsv"
    if not manifest_path.exists():
        raise FileNotFoundError(
            "zenodo_8327576_manifest.tsv is required to verify local mouse CNS CSV inputs."
        )
    manifest = pd.read_csv(manifest_path, sep="\t")
    rows = manifest.set_index("key")
    missing_manifest = sorted(required.difference(rows.index))
    if missing_manifest:
        raise ValueError("Publisher manifest is missing required files: " + ", ".join(missing_manifest))
    verified = 0
    for filename in sorted(required):
        path = source_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"Required mouse CNS CSV is missing: {path}")
        row = rows.loc[filename]
        expected_size = int(row["size"])
        if path.stat().st_size != expected_size:
            raise ValueError(
                f"Size mismatch for '{filename}': {path.stat().st_size} != {expected_size}."
            )
        checksum = str(row["checksum"])
        if not checksum.startswith("md5:"):
            raise ValueError(f"Unsupported publisher checksum for '{filename}': {checksum}")
        if _md5(path) != checksum.split(":", 1)[1].casefold():
            raise ValueError(f"Publisher MD5 mismatch for '{filename}'.")
        verified += 1
    return {"manifest": str(manifest_path.relative_to(ROOT)), "n_files_verified": verified}


def _build_sample(
    sample: str,
    expression_path: Path,
    spatial_path: Path,
    metadata: pd.DataFrame,
    cluster: pd.DataFrame,
    h5ad_path: Path,
    truth_path: Path,
) -> tuple[int, int]:
    matrix, genes, cell_ids = _load_raw_expression(expression_path)
    obs = pd.DataFrame(index=pd.Index(cell_ids, name="cell_id"))
    obs["sample"] = sample
    obs = _merge_obs(obs, metadata, "metadata.csv")
    spatial_frame = _read_typed_csv(spatial_path).rename(
        columns={"X": "spatial_x", "Y": "spatial_y", "Z": "spatial_z"}
    )
    obs = _merge_obs(obs, spatial_frame, spatial_path.name)
    cluster_frame = cluster.rename(columns={"X": "cluster_x", "Y": "cluster_y"})
    obs = _merge_obs(obs, cluster_frame, "cluster.csv")

    missing_coordinates = obs[["spatial_x", "spatial_y"]].isna().any(axis=1)
    if missing_coordinates.any():
        raise ValueError(
            f"Sample '{sample}' has {int(missing_coordinates.sum())} cells without X/Y coordinates."
        )
    present_truth = [column for column in TRUTH_COLUMNS if column in obs]
    if not present_truth:
        raise ValueError(f"Sample '{sample}' has no ground-truth annotation columns.")
    truth = obs[present_truth].copy()
    truth.insert(0, "sample", sample)
    truth.to_csv(truth_path, sep="\t", index=True)
    obs = obs.drop(columns=present_truth)

    for column in obs:
        if pd.api.types.is_object_dtype(obs[column]) or pd.api.types.is_string_dtype(obs[column]):
            obs[column] = obs[column].astype("category")
    result = ad.AnnData(
        X=matrix,
        obs=obs,
        var=pd.DataFrame(index=pd.Index(genes, name="gene")),
    )
    result.obsm["spatial"] = result.obs[["spatial_x", "spatial_y"]].to_numpy(dtype=np.float32)
    if "spatial_z" in result.obs:
        result.obsm["spatial_3d"] = result.obs[
            ["spatial_x", "spatial_y", "spatial_z"]
        ].to_numpy(dtype=np.float32)
    result.uns["source"] = {
        "zenodo_record_id": "8327576",
        "sample": sample,
        "expression_csv": str(expression_path.relative_to(ROOT)),
        "spatial_csv": str(spatial_path.relative_to(ROOT)),
        "expression_kind": "raw_counts",
        "ground_truth_held_out": True,
    }
    result.write_h5ad(h5ad_path, compression="gzip")
    return result.shape


def _combine_truth(parts: list[Path], output: Path) -> None:
    temporary = output.with_name(output.name + ".partial")
    temporary.unlink(missing_ok=True)
    with temporary.open("wb") as sink:
        for index, part in enumerate(parts):
            with part.open("rb") as source:
                if index:
                    source.readline()
                shutil.copyfileobj(source, sink, length=8 * 1024**2)
    temporary.replace(output)


def convert_zenodo_mouse_cns_csv(
    source_dir: Path,
    destination: Path,
    *,
    expected_n_obs: int | None,
    expected_n_vars: int | None,
    overwrite: bool,
) -> dict[str, Any]:
    """Build mouse CNS H5AD from required raw-expression/metadata CSV files only."""
    operation = "convert_spatial_data"
    if destination.exists() and not overwrite:
        raise FileExistsError(f"Output '{destination}' already exists; overwrite is disabled.")

    raw_files = sorted(source_dir.glob("*raw_expression_pd.csv"))
    if not raw_files:
        raise FileNotFoundError("No *raw_expression_pd.csv files were found.")
    samples = [path.name.removesuffix("raw_expression_pd.csv") for path in raw_files]
    spatial_files = {sample: source_dir / f"{sample}_spatial.csv" for sample in samples}
    required = {"metadata.csv", "cluster.csv"}
    required.update(path.name for path in raw_files)
    required.update(path.name for path in spatial_files.values())
    verification = _verify_publisher_manifest(source_dir, required)

    metadata = _read_typed_csv(source_dir / "metadata.csv")
    cluster = _read_typed_csv(source_dir / "cluster.csv")
    parts_dir = destination.parent / f".{destination.stem}.parts"
    parts_dir.mkdir(parents=True, exist_ok=True)
    sample_h5ads: list[Path] = []
    truth_parts: list[Path] = []
    sample_shapes: dict[str, list[int]] = {}
    for sample, expression_path in zip(samples, raw_files, strict=True):
        h5ad_path = parts_dir / f"{sample}.h5ad"
        truth_path = parts_dir / f"{sample}.ground_truth.tsv"
        if h5ad_path.exists() and truth_path.exists():
            cached = ad.read_h5ad(h5ad_path, backed="r")
            shape = cached.shape
            cached.file.close()
        else:
            h5ad_path.unlink(missing_ok=True)
            truth_path.unlink(missing_ok=True)
            shape = _build_sample(
                sample,
                expression_path,
                spatial_files[sample],
                metadata,
                cluster,
                h5ad_path,
                truth_path,
            )
        sample_h5ads.append(h5ad_path)
        truth_parts.append(truth_path)
        sample_shapes[sample] = [int(shape[0]), int(shape[1])]

    temporary = destination.with_name(f".{destination.stem}.partial.h5ad")
    temporary.unlink(missing_ok=True)
    try:
        if len(sample_h5ads) == 1:
            shutil.copy2(sample_h5ads[0], temporary)
        else:
            ad.experimental.concat_on_disk(
                [str(path) for path in sample_h5ads],
                str(temporary),
                axis=0,
                join="outer",
                merge="same",
                uns_merge="same",
                index_unique=None,
            )
        combined = ad.read_h5ad(temporary, backed="r")
        n_obs, n_vars = combined.shape
        obs_unique = combined.obs_names.is_unique
        combined.file.close()
        if not obs_unique:
            raise ValueError("Combined mouse CNS cell identifiers are not unique.")
        if expected_n_obs is not None and n_obs != expected_n_obs:
            raise ValueError(f"Converted n_obs={n_obs}; expected {expected_n_obs}.")
        if expected_n_vars is not None and n_vars != expected_n_vars:
            raise ValueError(f"Converted n_vars={n_vars}; expected {expected_n_vars}.")
        temporary.replace(destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise

    truth_output = destination.with_suffix(".ground_truth.tsv")
    _combine_truth(truth_parts, truth_output)
    result = {
        "status": "success",
        "operation": operation,
        "input_path": str(source_dir.relative_to(ROOT)),
        "input_format": "zenodo_8327576_mouse_cns_csv",
        "output_path": str(destination.relative_to(DATA_DIR)),
        "ground_truth_path": str(truth_output.relative_to(DATA_DIR)),
        "n_obs": int(n_obs),
        "n_vars": int(n_vars),
        "n_samples": len(samples),
        "samples": sample_shapes,
        "sha256": _sha256(destination),
        "verification": verification,
        "ignored_file_roles": ["processed_expression", "spot_meta"],
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    provenance = destination.with_suffix(".conversion.json")
    provenance.write_text(json.dumps(result, indent=2), encoding="utf-8")
    result["provenance_path"] = str(provenance.relative_to(DATA_DIR))
    return result
