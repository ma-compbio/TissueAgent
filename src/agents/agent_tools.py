"""File-access tools (glob, grep, read, write) for agents.

These tools operate within the DATA_DIR workspace and are used by sub-agents to interact with project files.
"""

from __future__ import annotations

import base64
import mimetypes
import re
from pathlib import Path
from typing import Literal

from langchain.tools import StructuredTool

from agents.agent_utils import truncate_output
from config import DATA_DIR, MAX_OUTPUT_CHARS

### file read tools


def _resolve_artifact_path(relative_path: str) -> Path:
    """Convert a provided relative or absolute path into a normalized path inside DATA_DIR."""
    if not relative_path or not relative_path.strip():
        raise ValueError("relative_path must be a non-empty string.")

    candidate = Path(relative_path.strip())
    target = candidate if candidate.is_absolute() else (DATA_DIR / candidate)
    target = target.resolve()

    try:
        target.relative_to(DATA_DIR)
    except ValueError as exc:
        raise ValueError(f"Artifact path '{target}' must be inside '{DATA_DIR}'.") from exc

    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def _glob(pattern: str) -> str:
    """Find workspace files and directories matching a glob pattern relative to DATA_DIR."""
    matches = sorted(str(p.relative_to(DATA_DIR)) for p in DATA_DIR.glob(pattern))
    if not matches:
        return f"No matches for '{pattern}'."
    return truncate_output("\n".join(matches), MAX_OUTPUT_CHARS)


def _grep(pattern: str, include: str = "**/*") -> str:
    """Search file contents in the workspace for a regex pattern.

    Binary files are skipped.
    """
    hits: list[str] = []
    for path in sorted(DATA_DIR.glob(include)):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, PermissionError):
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            if re.search(pattern, line):
                hits.append(f"{path.relative_to(DATA_DIR)}:{lineno}: {line}")
    if not hits:
        return "No matches found."
    return truncate_output("\n".join(hits), MAX_OUTPUT_CHARS)


def _read(file_path: str, offset: int = 1, limit: int | None = None):
    """Read a workspace file by path relative to DATA_DIR."""
    try:
        path = _resolve_artifact_path(file_path)

        mime, _ = mimetypes.guess_type(str(path))
        if mime and mime.startswith("image/"):
            b64 = base64.b64encode(path.read_bytes()).decode()
            return [
                {"type": "text", "text": f"Image: {file_path}"},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
            ]

        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return f"Cannot read binary file: {file_path}"

        lines = text.splitlines(keepends=True)
        start = max(0, offset - 1)
        end = start + limit if limit is not None else len(lines)
        selected = "".join(lines[start:end])
        return truncate_output(selected, MAX_OUTPUT_CHARS)
    except Exception as e:
        return f"Error: {e}"


def _write(
    file_path: str,
    contents: str,
    mode: Literal["overwrite", "append", "error_if_exists"] = "overwrite",
) -> str:
    """Persist plain-text contents to a file inside DATA_DIR.

    Args:
        file_path: Target path relative to DATA_DIR (or absolute under DATA_DIR).
        contents: Text payload to write.
        mode: How to write the file. `overwrite` replaces, `append` extends, `error_if_exists`
              fails if the file already exists.
    """
    try:
        path = _resolve_artifact_path(file_path)
        mode_normalized = (mode or "overwrite").strip().lower()
        if mode_normalized not in {"overwrite", "append", "error_if_exists"}:
            raise ValueError("mode must be one of: 'overwrite', 'append', 'error_if_exists'.")

        if mode_normalized == "error_if_exists" and path.exists():
            raise FileExistsError(f"Artifact '{path.relative_to(DATA_DIR)}' already exists.")

        write_mode = "a" if mode_normalized == "append" else "w"
        with path.open(write_mode, encoding="utf-8") as file_handle:
            file_handle.write(contents)

        relative_target = path.relative_to(DATA_DIR)
        return f"Success: wrote {len(contents)} characters to '{relative_target.as_posix()}'."
    except Exception as e:
        return f"Error: {e}"


glob_tool = StructuredTool.from_function(
    func=_glob,
    name="glob",
    description=(
        "List workspace files and directories matching a glob pattern relative to DATA_DIR."
        " Example: '**/*.h5ad' finds all HDF5 files, 'figures/*' lists the figures directory."
    ),
)

grep_tool = StructuredTool.from_function(
    func=_grep,
    name="grep",
    description=(
        "Search file contents in the workspace for a regex pattern."
        " Optional `include` glob filters which files to search (default: all files)."
        " Binary files are skipped automatically."
    ),
)

read_tool = StructuredTool.from_function(
    func=_read,
    name="read",
    description=(
        "Read a workspace file by path relative to DATA_DIR."
        " Text files support `offset` (1-based line to start from) and `limit` (max lines to return)."
        " Image files (PNG, JPEG, etc.) are returned as inline content for visual inspection."
    ),
)


write_tool = StructuredTool.from_function(
    func=_write,
    name="write",
    description=(
        "Create or update a UTF-8 text artifact. "
        "Provide a relative path (e.g., 'reports/search_summary.txt') and the text to persist."
    ),
)

file_read_tools: list[StructuredTool] = [glob_tool, grep_tool, read_tool]
file_read_write_tools: list[StructuredTool] = file_read_tools + [write_tool]
