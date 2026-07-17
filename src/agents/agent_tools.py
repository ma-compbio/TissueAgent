"""File-access tools (glob, grep, read, write) for agents.

These tools operate within the DATA_DIR workspace and are used by sub-agents to interact with
project files.
"""

from __future__ import annotations

import base64
import mimetypes
import re
from pathlib import Path
from typing import Literal

from langchain.tools import StructuredTool

from agents.agent_utils import truncate_output
from agents.workspace_paths import resolve_project_output, workspace_relative
from config import ACTIVE_PROJECT_DIR, DATA_DIR, LIBRARY_DIR, MAX_OUTPUT_CHARS, NOTEBOOK_DIR

### file read tools


# Roots the agent is allowed to traverse. Anything else inside DATA_DIR
# (or outside it) is unreachable through these tools — defense in depth
# on top of the DATA_DIR boundary check in _resolve_artifact_path.
_AGENT_VISIBLE_ROOTS: tuple[Path, ...] = (
    ACTIVE_PROJECT_DIR,
    LIBRARY_DIR,
    NOTEBOOK_DIR,
)


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


def _has_hidden_component(path: Path, root: Path) -> bool:
    """True if any path component below *root* starts with a dot.

    Hidden files (dotfiles) carry internal persistence data — ``.chat.json``,
    ``.project_id`` — and the agent should not see them unless it asks
    for them explicitly by name. ``Path.glob('**/*')`` doesn't filter
    these out automatically, so we do it here.
    """
    try:
        rel = path.relative_to(root)
    except ValueError:
        return False
    return any(part.startswith(".") for part in rel.parts)


def _iter_visible_files(pattern: str):
    """Yield files matching *pattern* under each agent-visible root.

    The pattern may include a leading root component (e.g. ``project/...``
    or ``library/...``); in that case only the matching root is walked.
    Otherwise the pattern is evaluated against every visible root and the
    results unioned. Hidden (dot-prefixed) files and directories are
    skipped unless the pattern explicitly names them.
    """
    parts = Path(pattern).parts
    root_name = parts[0] if parts else ""
    by_name = {r.name: r for r in _AGENT_VISIBLE_ROOTS}
    explicit_dot = any(part.startswith(".") for part in parts)

    if root_name in by_name:
        rest = str(Path(*parts[1:])) if len(parts) > 1 else "*"
        for p in by_name[root_name].glob(rest):
            if not explicit_dot and _has_hidden_component(p, by_name[root_name]):
                continue
            yield p
        return

    for root in _AGENT_VISIBLE_ROOTS:
        for p in root.glob(pattern):
            if not explicit_dot and _has_hidden_component(p, root):
                continue
            yield p


def _glob(pattern: str) -> str:
    """Find workspace files and directories matching a glob pattern relative to DATA_DIR."""
    matches = sorted({str(p.relative_to(DATA_DIR)) for p in _iter_visible_files(pattern)})
    if not matches:
        return f"No matches for '{pattern}'."
    return truncate_output("\n".join(matches), MAX_OUTPUT_CHARS)


# Cap grep at 10 MB per file. Larger files are skipped rather than pulled
# into RAM in full — a match on a random .h5ad picked up by **/* would
# otherwise OOM the worker before the UnicodeDecodeError even fires.
_GREP_MAX_FILE_BYTES = 10 * 1024 * 1024


def _grep(pattern: str, include: str = "**/*") -> str:
    """Search file contents in the workspace for a regex pattern.

    Binary files and files over ~10 MB are skipped. Matching is line-by-line
    from a streaming read so total memory stays bounded regardless of the
    corpus.
    """
    hits: list[str] = []
    seen: set[Path] = set()
    try:
        compiled = re.compile(pattern)
    except re.error as exc:
        return f"Error: invalid regex pattern: {exc}"

    for path in sorted(_iter_visible_files(include)):
        if not path.is_file() or path in seen:
            continue
        seen.add(path)
        try:
            if path.stat().st_size > _GREP_MAX_FILE_BYTES:
                continue
        except OSError:
            continue
        try:
            with path.open("r", encoding="utf-8") as fh:
                for lineno, line in enumerate(fh, 1):
                    if compiled.search(line):
                        hits.append(f"{path.relative_to(DATA_DIR)}:{lineno}: {line.rstrip()}")
        except (UnicodeDecodeError, PermissionError, OSError):
            continue
    if not hits:
        return "No matches found."
    return truncate_output("\n".join(hits), MAX_OUTPUT_CHARS)


def _read(file_path: str, offset: int = 1, limit: int | None = None):
    """Read a workspace file by path relative to DATA_DIR.

    Line numbers are 1-based: ``offset=1`` returns the file starting at the
    first line. Passing an offset past the end of the file surfaces a clear
    error instead of a silent empty string.
    """
    try:
        if offset is None or offset < 1:
            return "Error: offset must be a 1-based line number (>= 1)."

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
        start = offset - 1
        if start >= len(lines):
            return (
                f"Error: offset {offset} is past the end of the file "
                f"(file has {len(lines)} line(s))."
            )
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
    """Persist plain-text contents beneath the active project's outputs directory.

    Args:
        file_path: Target path relative to the active project's outputs directory.
        contents: Text payload to write.
        mode: How to write the file. `overwrite` replaces, `append` extends, `error_if_exists`
              fails if the file already exists.
    """
    try:
        path = resolve_project_output(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        mode_normalized = (mode or "overwrite").strip().lower()
        if mode_normalized not in {"overwrite", "append", "error_if_exists"}:
            raise ValueError("mode must be one of: 'overwrite', 'append', 'error_if_exists'.")

        if mode_normalized == "error_if_exists" and path.exists():
            raise FileExistsError(f"Artifact '{workspace_relative(path)}' already exists.")

        write_mode = "a" if mode_normalized == "append" else "w"
        with path.open(write_mode, encoding="utf-8") as file_handle:
            file_handle.write(contents)

        return f"Success: wrote {len(contents)} characters to '{workspace_relative(path)}'."
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
        " Text files support `offset` (1-based line to start from) and `limit` "
        "(max lines to return)."
        " Image files (PNG, JPEG, etc.) are returned as inline content for visual inspection."
    ),
)


write_tool = StructuredTool.from_function(
    func=_write,
    name="write",
    description=(
        "Create or update a UTF-8 text artifact. "
        "Provide a path relative to active-project outputs (e.g., "
        "'reports/search_summary.txt') and the text to persist."
    ),
)

file_read_tools: list[StructuredTool] = [glob_tool, grep_tool, read_tool]
file_read_write_tools: list[StructuredTool] = file_read_tools + [write_tool]
