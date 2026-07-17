"""Safe, deterministic spatial-transcriptomics data onboarding operations."""

from __future__ import annotations

import gzip
import hashlib
import ipaddress
import json
import os
import shutil
import socket
import ssl
import subprocess
import tarfile
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

import anndata as ad
import numpy as np
import pandas as pd
import scanpy as sc
from scipy import sparse

from agents.workspace_paths import (
    resolve_project_output,
    resolve_workspace_input,
    workspace_relative,
)
from config import ROOT


DEFAULT_MAX_DOWNLOAD_BYTES = 2 * 1024**3
DEFAULT_MAX_ARCHIVE_BYTES = 20 * 1024**3
DEFAULT_MAX_ARCHIVE_MEMBERS = 10_000
CHUNK_SIZE = 8 * 1024**2
EXECUTABLE_SUFFIXES = {
    ".app",
    ".bat",
    ".cmd",
    ".com",
    ".dll",
    ".dylib",
    ".exe",
    ".jar",
    ".msi",
    ".pl",
    ".py",
    ".r",
    ".rb",
    ".sh",
    ".ps1",
    ".scr",
    ".so",
}


def _result_error(operation: str, exc: Exception, **details: Any) -> dict[str, Any]:
    result = {
        "status": "error",
        "operation": operation,
        "error_type": type(exc).__name__,
        "message": f"{operation} failed: {exc}",
    }
    result.update(details)
    return result


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_checksum(value: str | None) -> tuple[str, str] | None:
    if not value:
        return None
    if ":" not in value:
        return "sha256", value.casefold()
    algorithm, expected = value.split(":", 1)
    algorithm = algorithm.casefold()
    if algorithm not in {"md5", "sha256"}:
        raise ValueError("expected_checksum must use md5: or sha256:.")
    return algorithm, expected.casefold()


def _file_checksum(path: Path, algorithm: str) -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_remote_url(url: str) -> None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme.casefold() != "https":
        raise ValueError("Only HTTPS downloads are allowed.")
    if not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Download URL must contain a hostname and no embedded credentials.")
    try:
        addresses = {
            entry[4][0] for entry in socket.getaddrinfo(parsed.hostname, parsed.port or 443)
        }
    except socket.gaierror as exc:
        raise ValueError(f"Could not resolve download host '{parsed.hostname}': {exc}") from exc
    if not addresses:
        raise ValueError(f"Download host '{parsed.hostname}' resolved to no addresses.")
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if not ip.is_global:
            raise ValueError(
                f"Download host '{parsed.hostname}' resolves to disallowed address '{address}'."
            )


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def __init__(self, maximum_redirects: int) -> None:
        self.maximum_redirects = maximum_redirects
        self.redirect_count = 0

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        self.redirect_count += 1
        if self.redirect_count > self.maximum_redirects:
            raise urllib.error.HTTPError(newurl, code, "Too many redirects", headers, fp)
        _validate_remote_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download_spatial_data(
    url: str,
    output_path: str,
    expected_checksum: str | None = None,
    expected_size_bytes: int | None = None,
    max_bytes: int = DEFAULT_MAX_DOWNLOAD_BYTES,
    retries: int = 3,
    timeout_seconds: int = 120,
) -> dict[str, Any]:
    """Download exactly one HTTPS file with bounded, verified behavior."""
    operation = "download_spatial_data"
    try:
        _validate_remote_url(url)
        if max_bytes <= 0:
            raise ValueError("max_bytes must be positive.")
        if expected_size_bytes is not None and expected_size_bytes > max_bytes:
            raise ValueError(
                f"Expected file size {expected_size_bytes} exceeds max_bytes={max_bytes}."
            )
        destination = resolve_project_output(output_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        checksum = _parse_checksum(expected_checksum)

        if destination.exists():
            size_matches = (
                expected_size_bytes is None or destination.stat().st_size == expected_size_bytes
            )
            checksum_matches = (
                checksum is None or _file_checksum(destination, checksum[0]) == checksum[1]
            )
            if size_matches and checksum_matches:
                return {
                    "status": "success",
                    "operation": operation,
                    "cache_hit": True,
                    "output_path": workspace_relative(destination),
                    "size_bytes": destination.stat().st_size,
                    "sha256": _sha256(destination),
                }
            raise FileExistsError(
                f"Existing destination '{destination}' does not match declared size/checksum."
            )

        free_bytes = shutil.disk_usage(destination.parent).free
        required_bytes = expected_size_bytes or max_bytes
        if free_bytes < required_bytes:
            raise OSError(
                f"Insufficient free space: {free_bytes} bytes available, {required_bytes} required."
            )

        partial = destination.with_name(destination.name + ".partial")
        partial.unlink(missing_ok=True)
        last_error: Exception | None = None
        final_url = url
        try:
            for attempt in range(1, retries + 1):
                try:
                    redirect_handler = _SafeRedirectHandler(maximum_redirects=5)
                    try:
                        import certifi

                        tls_context = ssl.create_default_context(cafile=certifi.where())
                    except ImportError:
                        tls_context = ssl.create_default_context()
                    opener = urllib.request.build_opener(
                        redirect_handler,
                        urllib.request.HTTPSHandler(context=tls_context),
                    )
                    request = urllib.request.Request(
                        url,
                        headers={"User-Agent": "TissueAgent-safe-downloader/1.0"},
                    )
                    with (
                        opener.open(request, timeout=timeout_seconds) as response,
                        partial.open("wb") as handle,
                    ):
                        final_url = response.geturl()
                        _validate_remote_url(final_url)
                        declared_length = response.headers.get("Content-Length")
                        if declared_length and int(declared_length) > max_bytes:
                            raise ValueError(
                                f"Server declared {declared_length} bytes, exceeding "
                                f"max_bytes={max_bytes}."
                            )
                        copied = 0
                        while True:
                            chunk = response.read(CHUNK_SIZE)
                            if not chunk:
                                break
                            copied += len(chunk)
                            if copied > max_bytes:
                                raise ValueError(f"Download exceeded max_bytes={max_bytes}.")
                            handle.write(chunk)
                    last_error = None
                    break
                except Exception as exc:
                    last_error = exc
                    partial.unlink(missing_ok=True)
                    if attempt < retries:
                        time.sleep(min(2**attempt, 10))
            if last_error is not None:
                raise last_error

            actual_size = partial.stat().st_size
            if expected_size_bytes is not None and actual_size != expected_size_bytes:
                raise ValueError(
                    f"Downloaded size {actual_size} does not match expected {expected_size_bytes}."
                )
            if checksum is not None:
                actual_checksum = _file_checksum(partial, checksum[0])
                if actual_checksum != checksum[1]:
                    raise ValueError(
                        f"{checksum[0]} mismatch: expected {checksum[1]}, got {actual_checksum}."
                    )
            sha256 = _sha256(partial)
            partial.replace(destination)
        except Exception:
            partial.unlink(missing_ok=True)
            raise

        metadata = {
            "status": "success",
            "operation": operation,
            "cache_hit": False,
            "requested_url": url,
            "final_url": final_url,
            "output_path": workspace_relative(destination),
            "size_bytes": destination.stat().st_size,
            "publisher_checksum": expected_checksum or "",
            "sha256": sha256,
            "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        provenance_path = destination.with_name(destination.name + ".download.json")
        provenance_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        metadata["provenance_path"] = workspace_relative(provenance_path)
        return metadata
    except Exception as exc:
        return _result_error(operation, exc, url=url, output_path=output_path)


def _safe_archive_target(root: Path, member_name: str) -> Path:
    if "\x00" in member_name:
        raise ValueError("Archive member contains a NUL byte.")
    member = PurePosixPath(member_name.replace("\\", "/"))
    if member.is_absolute() or ".." in member.parts:
        raise ValueError(f"Unsafe archive path '{member_name}'.")
    if not member.parts:
        raise ValueError("Archive contains an empty member name.")
    target = (root / Path(*member.parts)).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"Archive member escapes destination: '{member_name}'.") from exc
    if target.suffix.casefold() in EXECUTABLE_SUFFIXES:
        raise ValueError(f"Executable archive member is not allowed: '{member_name}'.")
    return target


def extract_spatial_archive(
    archive_path: str,
    output_dir: str,
    max_members: int = DEFAULT_MAX_ARCHIVE_MEMBERS,
    max_uncompressed_bytes: int = DEFAULT_MAX_ARCHIVE_BYTES,
) -> dict[str, Any]:
    """Extract a data archive after validating every member."""
    operation = "extract_spatial_archive"
    try:
        archive = resolve_workspace_input(archive_path)
        destination = resolve_project_output(output_dir)
        if destination.exists():
            if any(destination.iterdir()) if destination.is_dir() else True:
                raise FileExistsError(f"Extraction destination '{destination}' is not empty.")
            destination.rmdir()
        destination.parent.mkdir(parents=True, exist_ok=True)
        temp_root = Path(tempfile.mkdtemp(prefix=f".{destination.name}-", dir=destination.parent))
        extracted_files: list[str] = []
        total_bytes = 0
        try:
            if zipfile.is_zipfile(archive):
                with zipfile.ZipFile(archive) as handle:
                    members = handle.infolist()
                    if len(members) > max_members:
                        raise ValueError(
                            f"Archive contains {len(members)} members; limit is {max_members}."
                        )
                    for member in members:
                        unix_mode = (member.external_attr >> 16) & 0o170000
                        if unix_mode == 0o120000:
                            raise ValueError(
                                f"Archive symlink is not allowed: '{member.filename}'."
                            )
                        permissions = (member.external_attr >> 16) & 0o777
                        if permissions & 0o111:
                            raise ValueError(
                                f"Executable archive member is not allowed: '{member.filename}'."
                            )
                        target = _safe_archive_target(temp_root, member.filename)
                        total_bytes += member.file_size
                        if total_bytes > max_uncompressed_bytes:
                            raise ValueError("Archive exceeds configured uncompressed size limit.")
                        if member.is_dir():
                            target.mkdir(parents=True, exist_ok=True)
                            continue
                        target.parent.mkdir(parents=True, exist_ok=True)
                        with handle.open(member) as source, target.open("wb") as sink:
                            shutil.copyfileobj(source, sink, length=CHUNK_SIZE)
                        extracted_files.append(str(target.relative_to(temp_root)))
            elif tarfile.is_tarfile(archive):
                with tarfile.open(archive, mode="r:*") as handle:
                    members = handle.getmembers()
                    if len(members) > max_members:
                        raise ValueError(
                            f"Archive contains {len(members)} members; limit is {max_members}."
                        )
                    for member in members:
                        if (
                            member.issym()
                            or member.islnk()
                            or not (member.isfile() or member.isdir())
                        ):
                            raise ValueError(f"Unsupported archive member type: '{member.name}'.")
                        if member.isfile() and member.mode & 0o111:
                            raise ValueError(
                                f"Executable archive member is not allowed: '{member.name}'."
                            )
                        target = _safe_archive_target(temp_root, member.name)
                        total_bytes += member.size
                        if total_bytes > max_uncompressed_bytes:
                            raise ValueError("Archive exceeds configured uncompressed size limit.")
                        if member.isdir():
                            target.mkdir(parents=True, exist_ok=True)
                            continue
                        source = handle.extractfile(member)
                        if source is None:
                            raise ValueError(f"Could not read archive member '{member.name}'.")
                        target.parent.mkdir(parents=True, exist_ok=True)
                        with source, target.open("wb") as sink:
                            shutil.copyfileobj(source, sink, length=CHUNK_SIZE)
                        extracted_files.append(str(target.relative_to(temp_root)))
            elif archive.suffix.casefold() == ".gz":
                target = _safe_archive_target(temp_root, archive.stem)
                target.parent.mkdir(parents=True, exist_ok=True)
                copied = 0
                with gzip.open(archive, "rb") as source, target.open("wb") as sink:
                    while True:
                        chunk = source.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        copied += len(chunk)
                        if copied > max_uncompressed_bytes:
                            raise ValueError("GZIP output exceeds configured size limit.")
                        sink.write(chunk)
                total_bytes = copied
                extracted_files.append(target.name)
            else:
                raise ValueError(
                    "Supported archives are ZIP, TAR, TAR.GZ, TGZ, and single GZIP files."
                )
            temp_root.replace(destination)
        except Exception:
            shutil.rmtree(temp_root, ignore_errors=True)
            raise

        return {
            "status": "success",
            "operation": operation,
            "archive_path": workspace_relative(archive),
            "output_dir": workspace_relative(destination),
            "n_files": len(extracted_files),
            "uncompressed_bytes": total_bytes,
            "files": extracted_files[:100],
            "files_truncated": len(extracted_files) > 100,
        }
    except Exception as exc:
        return _result_error(operation, exc, archive_path=archive_path, output_dir=output_dir)


def _detect_format(path: Path) -> tuple[str, list[str], list[str]]:
    required: list[str] = []
    missing: list[str] = []
    if path.is_file():
        suffixes = "".join(path.suffixes).casefold()
        if suffixes.endswith(".h5ad"):
            return "h5ad", required, missing
        if suffixes.endswith(".loom"):
            return "loom", required, missing
        if suffixes.endswith(".h5seurat"):
            return "h5seurat", required, missing
        if suffixes.endswith(".rds"):
            return "seurat_rds", required, missing
        if suffixes.endswith(".mtx") or suffixes.endswith(".mtx.gz"):
            return "matrix_market", required, missing
        if suffixes.endswith((".csv", ".csv.gz", ".tsv", ".tsv.gz", ".txt", ".txt.gz")):
            return "delimited", required, missing
        if suffixes.endswith((".h5", ".hdf5")):
            return "10x_h5_or_platform_h5", required, missing
        return "unknown", required, missing

    names = {item.name for item in path.iterdir()}
    if "cell_by_gene.csv" in names and "cell_metadata.csv" in names:
        return "merscope", ["cell_by_gene.csv", "cell_metadata.csv"], missing
    if any(name.endswith("exprMat_file.csv") for name in names):
        required = ["*exprMat_file.csv", "*metadata_file.csv"]
        if not any(name.endswith("metadata_file.csv") for name in names):
            missing.append("*metadata_file.csv")
        return "cosmx", required, missing
    if "cell_feature_matrix.h5" in names and ({"cells.csv.gz", "cells.parquet"} & names):
        return "xenium", ["cell_feature_matrix.h5", "cells.csv.gz or cells.parquet"], missing
    if any(name.endswith("feature_slice.h5") for name in names) and "binned_outputs" in names:
        return "visium_hd", ["*feature_slice.h5", "binned_outputs/"], missing
    if "spatial" in names and any("filtered_feature_bc_matrix" in name for name in names):
        return "visium", ["filtered_feature_bc_matrix", "spatial/"], missing
    if {"matrix.mtx", "barcodes.tsv"}.issubset(names) or {
        "matrix.mtx.gz",
        "barcodes.tsv.gz",
    }.issubset(names):
        return "10x_mtx", ["matrix.mtx[.gz]", "barcodes.tsv[.gz]", "features.tsv[.gz]"], missing
    h5ads = sorted(name for name in names if name.endswith(".h5ad"))
    if len(h5ads) == 1:
        return "stereoseq_h5ad", [h5ads[0]], missing
    return "unknown_directory", required, missing


def inspect_spatial_data(input_path: str) -> dict[str, Any]:
    """Inspect a local file/directory without loading large expression matrices."""
    operation = "inspect_spatial_data"
    try:
        path = resolve_workspace_input(input_path)
        detected, required, missing = _detect_format(path)
        contents = []
        dimensions = None
        spatial_keys: list[str] = []
        checksum = None
        if path.is_dir():
            contents = [
                {
                    "name": item.name,
                    "kind": "directory" if item.is_dir() else "file",
                    "size_bytes": item.stat().st_size,
                }
                for item in sorted(path.iterdir())[:200]
            ]
        elif detected == "h5ad":
            dataset = ad.read_h5ad(path, backed="r")
            try:
                dimensions = {"n_obs": int(dataset.n_obs), "n_vars": int(dataset.n_vars)}
                spatial_keys = sorted(str(key) for key in dataset.obsm.keys())
            finally:
                dataset.file.close()
            checksum = _sha256(path)
        return {
            "status": "success",
            "operation": operation,
            "input_path": workspace_relative(path),
            "kind": "directory" if path.is_dir() else "file",
            "size_bytes": path.stat().st_size if path.is_file() else None,
            "detected_format": detected,
            "conversion_supported": detected not in {"unknown", "unknown_directory"},
            "recommended_next_agent": (
                "coding_agent" if detected in {"unknown", "unknown_directory"} else None
            ),
            "dimensions": dimensions,
            "spatial_keys": spatial_keys,
            "sha256": checksum,
            "required_files": required,
            "missing_files": missing,
            "contents": contents,
            "contents_truncated": path.is_dir() and len(list(path.iterdir())) > 200,
        }
    except Exception as exc:
        return _result_error(operation, exc, input_path=input_path)


def _read_delimited(path: Path, delimiter: str | None, orientation: str) -> ad.AnnData:
    separator = delimiter or ("\t" if ".tsv" in "".join(path.suffixes).casefold() else ",")
    frame = pd.read_csv(path, sep=separator, index_col=0)
    if orientation == "auto":
        orientation = (
            "genes_by_cells"
            if str(frame.index.name or "").casefold() == "gene"
            else "cells_by_genes"
        )
    if orientation == "genes_by_cells":
        frame = frame.T
    elif orientation != "cells_by_genes":
        raise ValueError("orientation must be auto, genes_by_cells, or cells_by_genes.")
    if not all(np.issubdtype(dtype, np.number) for dtype in frame.dtypes):
        raise ValueError("Delimited expression matrix contains non-numeric value columns.")
    return ad.AnnData(
        X=sparse.csr_matrix(frame.to_numpy()),
        obs=pd.DataFrame(index=pd.Index(frame.index.astype(str), name="cell_id")),
        var=pd.DataFrame(index=pd.Index(frame.columns.astype(str), name="gene")),
    )


def _read_cosmx(path: Path) -> ad.AnnData:
    counts_files = list(path.glob("*exprMat_file.csv"))
    metadata_files = list(path.glob("*metadata_file.csv"))
    if len(counts_files) != 1 or len(metadata_files) != 1:
        raise ValueError("CosMx conversion requires exactly one expression and one metadata CSV.")
    counts = pd.read_csv(counts_files[0], index_col=[0, 1])
    obs = pd.read_csv(metadata_files[0], index_col=[0, 1])
    counts.index = counts.index.map(lambda value: f"{value[0]}-{value[1]}")
    obs.index = obs.index.map(lambda value: f"{value[0]}-{value[1]}")
    if not counts.index.equals(obs.index):
        raise ValueError("CosMx expression and metadata cell identifiers do not match exactly.")
    gene_mask = ~counts.columns.str.casefold().str.contains("systemcontrol")
    result = ad.AnnData(X=sparse.csr_matrix(counts.loc[:, gene_mask].to_numpy()), obs=obs.copy())
    coordinate_columns = ["CenterX_global_px", "CenterY_global_px"]
    if set(coordinate_columns).issubset(result.obs.columns):
        result.obsm["spatial"] = result.obs[coordinate_columns].to_numpy(dtype=np.float32)
    return result


def _read_merscope(path: Path) -> ad.AnnData:
    counts = pd.read_csv(path / "cell_by_gene.csv", index_col=0)
    obs = pd.read_csv(path / "cell_metadata.csv", index_col=0)
    counts.index = counts.index.astype(str)
    obs.index = obs.index.astype(str)
    if not counts.index.equals(obs.index):
        raise ValueError("MERSCOPE expression and metadata cell identifiers do not match exactly.")
    gene_mask = ~counts.columns.str.casefold().str.contains("blank")
    result = ad.AnnData(X=sparse.csr_matrix(counts.loc[:, gene_mask].to_numpy()), obs=obs.copy())
    if {"center_x", "center_y"}.issubset(result.obs.columns):
        result.obsm["spatial"] = result.obs[["center_x", "center_y"]].to_numpy(dtype=np.float32)
    return result


def _read_spatialdata(path: Path, reader_name: str) -> ad.AnnData:
    import spatialdata_io as spatial_io
    from spatialdata_io.experimental import to_legacy_anndata

    reader = getattr(spatial_io, reader_name)
    spatial_data = reader(path)
    if not spatial_data.tables:
        raise ValueError(f"{reader_name} reader returned no expression tables.")
    table_name = sorted(map(str, spatial_data.tables))[0]
    coordinate_systems = sorted(map(str, spatial_data.coordinate_systems))
    if not coordinate_systems:
        raise ValueError(f"{reader_name} reader returned no coordinate systems.")
    last_error: Exception | None = None
    for coordinate_system in coordinate_systems:
        try:
            return to_legacy_anndata(
                spatial_data,
                coordinate_system=coordinate_system,
                table_name=table_name,
            )
        except Exception as exc:
            last_error = exc
    raise ValueError(f"Could not convert {reader_name} SpatialData table: {last_error}")


def _read_seurat(path: Path, temp_dir: Path) -> ad.AnnData:
    rscript = shutil.which("Rscript")
    if not rscript:
        raise RuntimeError("Rscript is required for Seurat conversion but was not found.")
    converter = Path(__file__).with_name("convert_seurat_to_mtx.R")
    if not converter.exists():
        raise RuntimeError(f"Required controlled converter is missing: {converter}")
    command = [rscript, str(converter), str(path), str(temp_dir)]
    environment = os.environ.copy()
    local_r_library = ROOT / ".venv" / "R" / "library"
    if local_r_library.exists() and not environment.get("R_LIBS_USER"):
        environment["R_LIBS_USER"] = str(local_r_library)
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        timeout=3600,
        env=environment,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "Seurat conversion failed without installing packages. "
            f"stdout={completed.stdout[-2000:]} stderr={completed.stderr[-2000:]}"
        )
    result = sc.read_10x_mtx(temp_dir / "matrix", var_names="gene_symbols", make_unique=True)
    metadata_path = temp_dir / "metadata.csv"
    if metadata_path.exists():
        obs = pd.read_csv(metadata_path, index_col=0, low_memory=False)
        obs.index = obs.index.astype(str)
        missing = result.obs_names.difference(obs.index)
        if len(missing):
            raise ValueError(f"Seurat metadata is missing {len(missing)} matrix barcodes.")
        result.obs = obs.reindex(result.obs_names)
    spatial_path = temp_dir / "spatial.csv"
    if spatial_path.exists():
        coordinates = pd.read_csv(spatial_path, index_col=0).reindex(result.obs_names)
        if coordinates.shape[1] >= 2:
            result.obsm["spatial"] = coordinates.iloc[:, :2].to_numpy(dtype=np.float32)
    elif {"x", "y"}.issubset(result.obs.columns):
        result.obsm["spatial"] = result.obs[["x", "y"]].to_numpy(dtype=np.float32)
    elif {"center_x", "center_y"}.issubset(result.obs.columns):
        result.obsm["spatial"] = result.obs[["center_x", "center_y"]].to_numpy(dtype=np.float32)
    return result


def _source_files(path: Path) -> tuple[list[str], bool]:
    files = [path] if path.is_file() else sorted(item for item in path.rglob("*") if item.is_file())
    relative = [workspace_relative(item) for item in files[:500]]
    return relative, len(files) > len(relative)


def convert_spatial_data(
    input_path: str,
    output_path: str,
    input_format: str = "auto",
    orientation: str = "auto",
    delimiter: str | None = None,
    overwrite: bool = False,
    expected_n_obs: int | None = None,
    expected_n_vars: int | None = None,
) -> dict[str, Any]:
    """Convert one supported spatial source into a validated H5AD."""
    operation = "convert_spatial_data"
    source: Path | None = None
    destination: Path | None = None
    try:
        source = resolve_workspace_input(input_path)
        destination = resolve_project_output(output_path, suffix=".h5ad")
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() and not overwrite:
            raise FileExistsError(f"Output '{destination}' already exists; overwrite is disabled.")
        detected, _, missing = _detect_format(source)
        selected_format = detected if input_format.casefold() == "auto" else input_format.casefold()
        if missing:
            raise FileNotFoundError(f"Missing required companion files: {', '.join(missing)}")

        temporary_output = destination.with_name(destination.name + ".partial")
        temporary_output.unlink(missing_ok=True)
        temp_dir = Path(tempfile.mkdtemp(prefix="tissueagent-convert-", dir=destination.parent))
        try:
            if selected_format == "h5ad":
                shutil.copy2(source, temporary_output)
                result = ad.read_h5ad(temporary_output, backed="r")
                n_obs, n_vars = result.shape
                result.file.close()
            else:
                if selected_format == "loom":
                    result = sc.read_loom(source)
                elif selected_format in {"delimited", "csv", "tsv"}:
                    result = _read_delimited(source, delimiter, orientation)
                elif selected_format in {"matrix_market", "mtx"}:
                    matrix = sc.read_mtx(source)
                    result = matrix.T
                elif selected_format == "10x_mtx":
                    result = sc.read_10x_mtx(source, var_names="gene_symbols", make_unique=True)
                elif selected_format in {"10x_h5", "10x_h5_or_platform_h5"}:
                    result = sc.read_10x_h5(source)
                elif selected_format == "cosmx":
                    result = _read_cosmx(source)
                elif selected_format == "merscope":
                    result = _read_merscope(source)
                elif selected_format == "visium":
                    result = sc.read_visium(source)
                elif selected_format == "visium_hd":
                    result = _read_spatialdata(source, "visium_hd")
                elif selected_format == "xenium":
                    result = _read_spatialdata(source, "xenium")
                elif selected_format == "stereoseq_h5ad":
                    h5ads = list(source.glob("*.h5ad"))
                    result = ad.read_h5ad(h5ads[0])
                    if "raw_counts" in result.layers:
                        result.X = result.layers["raw_counts"].copy()
                elif selected_format in {"seurat_rds", "h5seurat"}:
                    result = _read_seurat(source, temp_dir)
                else:
                    raise ValueError(
                        f"Unsupported or ambiguous input format '{selected_format}'. "
                        "Use the Coding Agent to convert it, then validate the resulting H5AD "
                        "with validate_spatial_data_tool."
                    )

                result.obs_names = result.obs_names.astype(str)
                result.var_names = result.var_names.astype(str)
                result.obs_names_make_unique()
                result.var_names_make_unique()
                if not sparse.issparse(result.X):
                    result.X = sparse.csr_matrix(result.X)
                result.write_h5ad(temporary_output, compression="gzip")
                n_obs, n_vars = result.shape

            if expected_n_obs is not None and n_obs != expected_n_obs:
                raise ValueError(f"Converted n_obs={n_obs}; expected {expected_n_obs}.")
            if expected_n_vars is not None and n_vars != expected_n_vars:
                raise ValueError(f"Converted n_vars={n_vars}; expected {expected_n_vars}.")
            temporary_output.replace(destination)
        except Exception:
            temporary_output.unlink(missing_ok=True)
            raise
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        output_dataset = ad.read_h5ad(destination, backed="r")
        try:
            spatial_keys = sorted(str(key) for key in output_dataset.obsm.keys())
        finally:
            output_dataset.file.close()
        source_files, source_files_truncated = _source_files(source)
        warnings = [] if "spatial" in spatial_keys else ["No obsm['spatial'] coordinates found."]
        metadata = {
            "status": "success",
            "operation": operation,
            "input_path": workspace_relative(source),
            "input_format": selected_format,
            "detected_format": detected,
            "output_path": workspace_relative(destination),
            "n_obs": int(n_obs),
            "n_vars": int(n_vars),
            "spatial_keys": spatial_keys,
            "source_files": source_files,
            "source_files_truncated": source_files_truncated,
            "warnings": warnings,
            "sha256": _sha256(destination),
            "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        provenance = destination.with_suffix(".conversion.json")
        provenance.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        metadata["provenance_path"] = workspace_relative(provenance)
        return metadata
    except Exception as exc:
        return _result_error(
            operation,
            exc,
            input_path=str(source) if source else input_path,
            output_path=str(destination) if destination else output_path,
        )


def validate_spatial_data(
    h5ad_path: str,
    expected_n_obs: int | None = None,
    expected_n_vars: int | None = None,
    require_spatial: bool = False,
) -> dict[str, Any]:
    """Validate an H5AD without materializing its expression matrix."""
    operation = "validate_spatial_data"
    try:
        path = resolve_workspace_input(h5ad_path)
        if path.suffix.casefold() != ".h5ad":
            raise ValueError("Validation input must be an .h5ad file.")
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
            if not has_spatial:
                warnings.append("No obsm['spatial'] coordinates were found.")
        finally:
            dataset.file.close()

        return {
            "status": "success" if not errors else "error",
            "operation": operation,
            "h5ad_path": workspace_relative(path),
            "n_obs": int(n_obs),
            "n_vars": int(n_vars),
            "has_spatial": has_spatial,
            "errors": errors,
            "warnings": warnings,
            "sha256": _sha256(path),
        }
    except Exception as exc:
        return _result_error(operation, exc, h5ad_path=h5ad_path)
