"""Shared utilities for agent prompt construction and file access.

Provides helpers for formatting agent descriptions, extracting XML-style
blocks from LLM responses, and file-access tools (glob, grep, read) that
operate within the DATA_DIR workspace.
"""

import base64
import mimetypes
import re
from langchain.tools import StructuredTool
from pathlib import Path
from typing import Dict, List, Literal, Optional

from config import DATA_DIR, MAX_OUTPUT_CHARS


def format_agent_id_descriptions(agent_id_descriptions: Dict[str, str]) -> str:
    """Format agent ID-to-description pairs as a bulleted list for prompts.

    Args:
        agent_id_descriptions: Mapping of agent node IDs to their
            human-readable descriptions.

    Returns:
        A newline-separated string with one \" - id: description\" entry
        per agent.
    """
    return "\n".join(
        [f" - {id}: {description}" for id, description in agent_id_descriptions.items()]
    )


def extract_block(pattern: str, text: str) -> Optional[str]:
    """Extract the content of an XML-style block from an LLM response.

    Searches *text* for ``<pattern>…</pattern>`` tags.  If a single
    complete match is found its inner text is returned.  When no closing
    tag exists, an unclosed match is accepted as a fallback.

    Args:
        pattern: Tag name to look for (e.g. ``"execute"``).
        text: The full LLM response text to search.

    Returns:
        The stripped inner content of the matched block, or ``None`` when
        zero or more than one match is found.
    """
    complete_matches = list(
        re.finditer(r"(?is)<" + pattern + r"(?:\s[^>]*)?>(.*?)</" + pattern + ">", text)
    )
    if len(complete_matches) == 1:
        block = complete_matches[0].group(1).strip()
        return block or None

    if len(complete_matches) == 0:
        open_matches = list(re.finditer(r"(?is)<" + pattern + r"(?:\s[^>]*)?>(.*?)$", text))
        if len(open_matches) == 1:
            block = open_matches[0].group(1).strip()
            return block or None
    return None


def truncate_output(text: str, max_chars: int) -> str:
    """Truncate text to max_chars, keeping the head and tail with a notice in between."""
    if len(text) <= max_chars:
        return text
    half = max_chars // 2
    removed = len(text) - max_chars
    return (
        f"{text[:half]}\n\n"
        f"... [{removed} characters truncated] ...\n\n"
        f"{text[-half:]}"
    )


### file read tools


def _glob(pattern: str) -> str:
    """Find workspace files and directories matching a glob pattern relative to DATA_DIR."""
    matches = sorted(str(p.relative_to(DATA_DIR)) for p in DATA_DIR.glob(pattern))
    if not matches:
        return f"No matches for '{pattern}'."
    return truncate_output("\n".join(matches), MAX_OUTPUT_CHARS)


def _grep(pattern: str, include: str = "**/*") -> str:
    """Search file contents in the workspace for a regex pattern. Binary files are skipped."""
    hits: List[str] = []
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


def _read(file_path: str, offset: int = 1, limit: Optional[int] = None):
    """Read a workspace file by path relative to DATA_DIR."""
    path = DATA_DIR / file_path
    if not path.exists():
        return f"File not found: {file_path}"

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

file_read_tools: List[StructuredTool] = [glob_tool, grep_tool, read_tool]


### write tool


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
        raise ValueError(f"Artifact path '{target}' must be inside DATA_DIR '{DATA_DIR}'.") from exc

    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def _write(
    relative_path: str,
    contents: str,
    mode: Literal["overwrite", "append", "error_if_exists"] = "overwrite",
) -> str:
    """Persist plain-text contents to a file inside DATA_DIR.

    Args:
        relative_path: Target path relative to DATA_DIR (or absolute under DATA_DIR).
        contents: Text payload to write.
        mode: How to write the file. `overwrite` replaces, `append` extends, `error_if_exists`
              fails if the file already exists.
    """
    try:
        target = _resolve_artifact_path(relative_path)
        mode_normalized = (mode or "overwrite").strip().lower()
        if mode_normalized not in {"overwrite", "append", "error_if_exists"}:
            raise ValueError("mode must be one of: 'overwrite', 'append', 'error_if_exists'.")

        if mode_normalized == "error_if_exists" and target.exists():
            raise FileExistsError(f"Artifact '{target.relative_to(DATA_DIR)}' already exists.")

        write_mode = "a" if mode_normalized == "append" else "w"
        with target.open(write_mode, encoding="utf-8") as file_handle:
            file_handle.write(contents)

        relative_target = target.relative_to(DATA_DIR)
        return f"Success: wrote {len(contents)} characters to '{relative_target.as_posix()}'."
    except Exception as exc:
        return f"Error: {exc}"


write_tool = StructuredTool.from_function(
    func=_write,
    name="write",
    description=(
        "Create or update a UTF-8 text artifact inside DATA_DIR. "
        "Provide a relative path (e.g., 'reports/search_summary.txt') and the text to persist."
    ),
)

file_tools: List[StructuredTool] = [glob_tool, grep_tool, read_tool, write_tool]
