"""Prepare the BCL benchmark query without annotation or immune-receptor leakage."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import anndata as ad
import numpy as np
import pandas as pd
from scipy import sparse


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = (
    REPO_ROOT / "demo" / "data" / "cell_annotation" / "bcl" / "scRNA_BCR_TCR.h5ad"
)
DEFAULT_OUTPUT = (
    REPO_ROOT
    / "demo"
    / "data"
    / "cell_annotation"
    / "intermediates"
    / "benchmarks"
    / "bcl"
    / "full.h5ad"
)
GROUND_TRUTH_COLUMN = "refined_clusters"
SAFE_OBS_COLUMNS = ("sample",)
SAFE_VAR_COLUMNS = ("gene_ids", "feature_types")


@dataclass(frozen=True)
class SourceArtifact:
    """Immutable identity and shape for the downloaded benchmark source."""

    size_bytes: int
    md5: str
    sha256: str
    shape: tuple[int, int]


SOURCE_ARTIFACT = SourceArtifact(
    size_bytes=1_002_653_573,
    md5="7c99d5a06a29187f0779f5595cc0c5aa",
    sha256="c92d05f0a163fa0fcd25a1d25c34f6389a8322dfb6b2bc1e112dc328b2592bd3",
    shape=(49_910, 36_601),
)


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(REPO_ROOT))
    except ValueError:
        return str(resolved)


def _file_checksums(path: Path) -> dict[str, str]:
    md5 = hashlib.md5(usedforsecurity=False)
    sha256 = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024**2), b""):
            md5.update(chunk)
            sha256.update(chunk)
    return {"md5": md5.hexdigest(), "sha256": sha256.hexdigest()}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024**2), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_source(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"BCL source H5AD is missing: {path}")
    if path.stat().st_size != SOURCE_ARTIFACT.size_bytes:
        raise ValueError(
            f"BCL source size mismatch: {path.stat().st_size} != "
            f"{SOURCE_ARTIFACT.size_bytes}."
        )
    checksums = _file_checksums(path)
    if checksums["md5"] != SOURCE_ARTIFACT.md5:
        raise ValueError("BCL source MD5 does not match the frozen publisher artifact.")
    if checksums["sha256"] != SOURCE_ARTIFACT.sha256:
        raise ValueError("BCL source SHA-256 does not match the frozen publisher artifact.")
    return {
        "path": _display_path(path),
        "size_bytes": path.stat().st_size,
        **checksums,
    }


def _matrix_sha256(matrix: Any, shape: tuple[int, int], chunk_rows: int = 1_024) -> str:
    digest = hashlib.sha256()
    digest.update(np.asarray(shape, dtype=np.int64).tobytes())
    for start in range(0, shape[0], chunk_rows):
        stop = min(start + chunk_rows, shape[0])
        block = matrix[start:stop]
        digest.update(np.asarray((start, stop), dtype=np.int64).tobytes())
        if sparse.issparse(block):
            normalized = block.tocsr(copy=True)
            normalized.sum_duplicates()
            normalized.sort_indices()
            digest.update(b"csr")
            digest.update(str(normalized.data.dtype).encode())
            digest.update(np.asarray(normalized.indptr, dtype=np.int64).tobytes())
            digest.update(np.asarray(normalized.indices, dtype=np.int64).tobytes())
            digest.update(np.ascontiguousarray(normalized.data).tobytes())
        else:
            values = np.asarray(block)
            digest.update(b"dense")
            digest.update(str(values.dtype).encode())
            digest.update(np.ascontiguousarray(values).tobytes())
    return digest.hexdigest()


def _primary_matrix_to_memory(source: ad.AnnData) -> Any:
    if source.X is None:
        raise ValueError("BCL source has no primary expression matrix.")
    to_memory = getattr(source.X, "to_memory", None)
    if callable(to_memory):
        return to_memory()
    return np.asarray(source.X[:])


def _validate_source_schema(source: ad.AnnData) -> None:
    if source.shape != SOURCE_ARTIFACT.shape:
        raise ValueError(
            f"BCL source shape mismatch: {source.shape} != {SOURCE_ARTIFACT.shape}."
        )
    if not source.obs_names.is_unique:
        raise ValueError("BCL source observation identifiers are not unique.")
    if not source.var_names.is_unique:
        raise ValueError("BCL source feature identifiers are not unique.")
    required_obs = {GROUND_TRUTH_COLUMN, *SAFE_OBS_COLUMNS}
    missing_obs = sorted(required_obs.difference(source.obs.columns))
    if missing_obs:
        raise KeyError("BCL source is missing required .obs columns: " + ", ".join(missing_obs))
    missing_var = sorted(set(SAFE_VAR_COLUMNS).difference(source.var.columns))
    if missing_var:
        raise KeyError("BCL source is missing required .var columns: " + ", ".join(missing_var))
    ground_truth = source.obs[GROUND_TRUTH_COLUMN]
    if ground_truth.isna().any() or ground_truth.astype(str).str.strip().eq("").any():
        raise ValueError("BCL source contains missing or empty refined_clusters labels.")


def _validate_prepared_outputs(
    source_path: Path,
    query_path: Path,
    truth_path: Path,
) -> dict[str, Any]:
    source = ad.read_h5ad(source_path, backed="r")
    query = ad.read_h5ad(query_path, backed="r")
    try:
        _validate_source_schema(source)
        if query.shape != source.shape:
            raise ValueError(f"Prepared BCL query shape changed: {query.shape} != {source.shape}.")
        if not query.obs_names.equals(source.obs_names):
            raise ValueError("Prepared BCL query changed observation identifiers or order.")
        if not query.var_names.equals(source.var_names):
            raise ValueError("Prepared BCL query changed feature identifiers or order.")
        if tuple(query.obs.columns) != SAFE_OBS_COLUMNS:
            raise ValueError(
                f"Prepared BCL query has unsafe .obs columns: {list(query.obs.columns)}."
            )
        if tuple(query.var.columns) != SAFE_VAR_COLUMNS:
            raise ValueError(
                f"Prepared BCL query has unsafe .var columns: {list(query.var.columns)}."
            )
        if not query.obs["sample"].equals(source.obs["sample"]):
            raise ValueError("Prepared BCL query changed sample metadata.")
        for column in SAFE_VAR_COLUMNS:
            if not query.var[column].equals(source.var[column]):
                raise ValueError(f"Prepared BCL query changed .var[{column!r}].")
        auxiliary = {
            "obsm": list(query.obsm),
            "varm": list(query.varm),
            "obsp": list(query.obsp),
            "varp": list(query.varp),
            "layers": list(query.layers),
            "uns": list(query.uns),
        }
        if any(auxiliary.values()) or query.raw is not None:
            raise ValueError(
                "Prepared BCL query contains embeddings, graphs, layers, raw data, or .uns "
                f"metadata: {auxiliary}, raw={query.raw is not None}."
            )
        source_expression_sha256 = _matrix_sha256(source.X, source.shape)
        query_expression_sha256 = _matrix_sha256(query.X, query.shape)
        if query_expression_sha256 != source_expression_sha256:
            raise ValueError("Prepared BCL query changed the primary expression matrix.")
        query_ids = query.obs_names.astype(str)
        expected_truth = source.obs.loc[
            :, [GROUND_TRUTH_COLUMN, *SAFE_OBS_COLUMNS]
        ].astype("string")
        expected_truth.index = pd.Index(query_ids, name="cell_id")
    finally:
        source.file.close()
        query.file.close()

    truth = pd.read_csv(truth_path, sep="\t", index_col="cell_id", low_memory=False)
    expected_truth_columns = [GROUND_TRUTH_COLUMN, *SAFE_OBS_COLUMNS]
    if list(truth.columns) != expected_truth_columns:
        raise ValueError(f"Unexpected BCL truth-sidecar columns: {list(truth.columns)}.")
    if not truth.index.equals(pd.Index(query_ids, name="cell_id")):
        raise ValueError("BCL truth sidecar changed observation identifiers or order.")
    if truth[GROUND_TRUTH_COLUMN].isna().any():
        raise ValueError("BCL truth sidecar contains missing ground-truth labels.")
    observed_truth = truth.astype("string")
    if not observed_truth.equals(expected_truth):
        raise ValueError("BCL truth sidecar changed ground-truth or sample values.")
    return {
        "n_obs": len(query_ids),
        "n_vars": SOURCE_ARTIFACT.shape[1],
        "expression_sha256": source_expression_sha256,
    }


def build_bcl_benchmark(
    source_path: str | Path = DEFAULT_SOURCE,
    output: str | Path = DEFAULT_OUTPUT,
    *,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Build a label-free BCL query and exact-order external truth sidecar."""
    source_path = Path(source_path)
    output = Path(output)
    truth_path = output.with_suffix(".ground_truth.tsv")
    provenance_path = output.with_suffix(".preparation.json")
    existing = [path for path in (output, truth_path, provenance_path) if path.exists()]
    if existing and not overwrite:
        raise FileExistsError(
            "Prepared BCL artifacts already exist and overwrite is disabled: "
            + ", ".join(str(path) for path in existing)
        )
    artifact_paths = {
        source_path.resolve(),
        output.resolve(),
        truth_path.resolve(),
        provenance_path.resolve(),
    }
    if len(artifact_paths) < 4:
        raise ValueError("BCL source, query, truth, and provenance paths must be distinct.")

    source_audit = _verify_source(source_path)
    source = ad.read_h5ad(source_path, backed="r")
    try:
        _validate_source_schema(source)
        removed = {
            "obs": [
                column for column in source.obs.columns if column not in SAFE_OBS_COLUMNS
            ],
            "var": [
                column for column in source.var.columns if column not in SAFE_VAR_COLUMNS
            ],
            "obsm": list(source.obsm),
            "varm": list(source.varm),
            "obsp": list(source.obsp),
            "varp": list(source.varp),
            "layers": list(source.layers),
            "uns": list(source.uns),
            "raw": source.raw is not None,
        }
        query = ad.AnnData(
            X=_primary_matrix_to_memory(source),
            obs=source.obs.loc[:, list(SAFE_OBS_COLUMNS)].copy(),
            var=source.var.loc[:, list(SAFE_VAR_COLUMNS)].copy(),
        )
        query.obs_names = source.obs_names.copy()
        query.var_names = source.var_names.copy()
        truth = source.obs.loc[:, [GROUND_TRUTH_COLUMN, *SAFE_OBS_COLUMNS]].copy()
        truth.index = pd.Index(source.obs_names.astype(str), name="cell_id")
    finally:
        source.file.close()

    output.parent.mkdir(parents=True, exist_ok=True)
    token = f"{os.getpid()}-{uuid.uuid4().hex}"
    query_temporary = output.with_name(f".{output.stem}.{token}.partial.h5ad")
    truth_temporary = truth_path.with_name(f".{truth_path.stem}.{token}.partial.tsv")
    provenance_temporary = provenance_path.with_name(
        f".{provenance_path.stem}.{token}.partial.json"
    )
    try:
        query.write_h5ad(query_temporary, compression="gzip")
        truth.to_csv(truth_temporary, sep="\t", index=True)
        validation = _validate_prepared_outputs(
            source_path,
            query_temporary,
            truth_temporary,
        )
        result = {
            "schema_version": "1.0",
            "status": "success",
            "operation": "prepare_bcl_benchmark",
            "source": source_audit,
            "outputs": {
                "query_h5ad": {
                    "path": _display_path(output),
                    "sha256": _sha256(query_temporary),
                },
                "ground_truth_tsv": {
                    "path": _display_path(truth_path),
                    "sha256": _sha256(truth_temporary),
                    "columns": [GROUND_TRUTH_COLUMN, *SAFE_OBS_COLUMNS],
                },
                "provenance_json": {
                    "path": _display_path(provenance_path),
                },
            },
            **validation,
            "leakage_policy": {
                "query_obs_allowlist": list(SAFE_OBS_COLUMNS),
                "query_var_allowlist": list(SAFE_VAR_COLUMNS),
                "ground_truth_storage": "external_sidecar",
                "query_uns_policy": "empty",
                "removed": removed,
            },
            "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        provenance_temporary.write_text(json.dumps(result, indent=2), encoding="utf-8")
        query_temporary.replace(output)
        truth_temporary.replace(truth_path)
        provenance_temporary.replace(provenance_path)
    except Exception:
        query_temporary.unlink(missing_ok=True)
        truth_temporary.unlink(missing_ok=True)
        provenance_temporary.unlink(missing_ok=True)
        raise
    return result


def main() -> None:
    """Run the reproducible BCL preprocessing command."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Explicitly replace query, truth, and provenance outputs.",
    )
    args = parser.parse_args()
    result = build_bcl_benchmark(args.source, args.output, overwrite=args.overwrite)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
