"""Artifact / coverage metrics — cheap checks on produced files and counts.

These have no heavy dependencies and are the artifact-tier backbone of every benchmark:
"did the run produce the file it was supposed to, and is it non-trivial?"
"""

from __future__ import annotations

from pathlib import Path

from eval_registry.metrics import metric


@metric("file_exists", kind="artifact")
def file_exists(path: str | Path) -> bool:
    """True if *path* exists and is a regular file."""
    return Path(path).is_file()


@metric("csv_nonempty", kind="artifact")
def csv_nonempty(path: str | Path) -> bool:
    """True if *path* is a CSV with at least one data row beyond the header."""
    p = Path(path)
    if not p.is_file():
        return False
    with p.open("r", encoding="utf-8") as fh:
        header = fh.readline()
        if not header.strip():
            return False
        for line in fh:
            if line.strip():
                return True
    return False


@metric("row_count", kind="artifact", higher_is_better=True)
def row_count(path: str | Path) -> float:
    """Number of non-empty data rows in a CSV (excludes the header). 0 if absent."""
    p = Path(path)
    if not p.is_file():
        return 0.0
    n = 0
    with p.open("r", encoding="utf-8") as fh:
        fh.readline()  # header
        for line in fh:
            if line.strip():
                n += 1
    return float(n)
