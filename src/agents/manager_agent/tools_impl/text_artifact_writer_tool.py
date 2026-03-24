"""Tool implementation for writing text artifacts to disk."""
from pathlib import Path
from typing import Literal

from langchain.tools import StructuredTool

from config import DATA_DIR


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


def write_text_artifact(
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


text_artifact_writer_tool = StructuredTool.from_function(
    func=write_text_artifact,
    name="text_artifact_writer_tool",
    description=(
        "Create or update a UTF-8 text artifact inside DATA_DIR. "
        "Provide a relative path (e.g., 'reports/search_summary.txt') and the text to persist."
    ),
)
