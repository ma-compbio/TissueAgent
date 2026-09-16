"""Acquire the versioned SpatialFusion OVCA evaluation source."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import time
import zipfile
import zlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .agent_inputs import ROOT
from .protocol import sha256, write_json

SOURCE_URL = "https://zenodo.org/records/20934900/files/benchmark_processed_data.zip?download=1"
ARCHIVE_MD5 = "26c8b75de035d6de7a8305875861caa4"
ARCHIVE_BYTES = 1620662647
ARCHIVE_MEMBER = "benchmark_processed_data/processed_OVCA.h5ad"
RANGE_BYTES = 4 * 1024**2
RAW_ROOT = ROOT / "demo/data/tissue_niche/raw/ovca_xenium_spatialfusion"


def _download_range(archive: Path, start: int) -> Path:
    end = min(start + RANGE_BYTES, ARCHIVE_BYTES) - 1
    chunk = archive.with_suffix(f".zip.chunk-{start}")
    if chunk.exists() and chunk.stat().st_size == end - start + 1:
        return chunk
    response = subprocess.check_output(
        [
            "curl",
            "--fail",
            "--silent",
            "--show-error",
            "--location",
            "--retry",
            "3",
            "--max-time",
            "60",
            "--range",
            f"{start}-{end}",
            "--output",
            str(chunk),
            "--write-out",
            "%{http_code}",
            SOURCE_URL,
        ],
        text=True,
    )
    if response != "206" or chunk.stat().st_size != end - start + 1:
        raise ValueError("Server did not return the requested OVCA archive byte range.")
    return chunk


def download(output_dir: Path = RAW_ROOT) -> Path:
    """Download the checksummed archive and extract only the OVCA H5AD member."""
    output_dir.mkdir(parents=True, exist_ok=True)
    archive = output_dir / "benchmark_processed_data.zip"
    if not archive.exists():
        partial = archive.with_suffix(".zip.partial")
        offset = partial.stat().st_size if partial.exists() else 0
        with ThreadPoolExecutor(max_workers=4) as pool:
            while offset < ARCHIVE_BYTES:
                print(f"Downloading OVCA archive: {offset}/{ARCHIVE_BYTES} bytes", flush=True)
                starts = range(offset, min(offset + 4 * RANGE_BYTES, ARCHIVE_BYTES), RANGE_BYTES)
                for chunk_path in pool.map(lambda start: _download_range(archive, start), starts):
                    with partial.open("ab") as output, chunk_path.open("rb") as source:
                        shutil.copyfileobj(source, output, length=8 * 1024**2)
                    offset += chunk_path.stat().st_size
                    chunk_path.unlink()
                if offset < ARCHIVE_BYTES:
                    time.sleep(2)
        candidate = partial
    else:
        candidate = archive
    digest = hashlib.md5()
    with candidate.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024**2), b""):
            digest.update(chunk)
    if digest.hexdigest() != ARCHIVE_MD5:
        raise ValueError("OVCA archive checksum differs from the versioned Zenodo record.")
    if candidate != archive:
        candidate.replace(archive)
    target = output_dir / Path(ARCHIVE_MEMBER).name
    with zipfile.ZipFile(archive) as handle:
        if handle.namelist().count(ARCHIVE_MEMBER) != 1:
            raise ValueError(f"Archive must contain exactly one {ARCHIVE_MEMBER}.")
        if not target.exists():
            partial = target.with_suffix(".h5ad.partial")
            with handle.open(ARCHIVE_MEMBER) as source, partial.open("wb") as output:
                shutil.copyfileobj(source, output, length=8 * 1024**2)
            partial.replace(target)
        member = handle.getinfo(ARCHIVE_MEMBER)
        crc = 0
        with target.open("rb") as existing:
            for chunk in iter(lambda: existing.read(8 * 1024**2), b""):
                crc = zlib.crc32(chunk, crc)
        if target.stat().st_size != member.file_size or crc != member.CRC:
            raise ValueError("Existing OVCA H5AD differs from the verified archive member.")
    write_json(
        output_dir / "acquisition.json",
        {
            "source_url": SOURCE_URL,
            "archive_md5": ARCHIVE_MD5,
            "member": ARCHIVE_MEMBER,
            "h5ad_sha256": sha256(target),
        },
    )
    return target


def main() -> None:
    """Download the OVCA source independently of model execution."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["download"])
    parser.add_argument("--output-dir", type=Path, default=RAW_ROOT)
    args = parser.parse_args()
    print(download(args.output_dir))


if __name__ == "__main__":
    main()
