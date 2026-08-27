"""Path resolution for tools that read and write agent-visible artifacts."""

from __future__ import annotations

from pathlib import Path

import config


def workspace_relative(path: Path) -> str:
    """Return a canonical path relative to the agent-visible workspace."""
    return path.resolve().relative_to(config.DATA_DIR.resolve()).as_posix()


def _allowed_input_roots() -> tuple[Path, ...]:
    return (
        config.ACTIVE_PROJECT_DIR / config.PROJECT_UPLOADS_DIRNAME,
        config.ACTIVE_PROJECT_DIR / config.PROJECT_OUTPUTS_DIRNAME,
        config.DATASET_DIR,
        config.LIBRARY_FILES_DIR,
    )


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root.resolve())
    except ValueError:
        return False
    return True


def resolve_workspace_input(path_like: str) -> Path:
    """Resolve an existing input from the active project or approved library roots."""
    if not path_like or not path_like.strip():
        raise ValueError("Input path must be a non-empty string.")
    raw_path = Path(path_like.strip()).expanduser()
    if ".." in raw_path.parts:
        raise ValueError(f"Input path traversal is not allowed: '{path_like}'.")

    allowed_roots = tuple(root.resolve() for root in _allowed_input_roots())
    if raw_path.is_absolute():
        candidates = [raw_path]
    elif raw_path.parts and raw_path.parts[0] in {"project", "library"}:
        candidates = [config.DATA_DIR / raw_path]
    elif raw_path.parts and raw_path.parts[0] in {"uploads", "outputs"}:
        candidates = [config.ACTIVE_PROJECT_DIR / raw_path]
    else:
        candidates = [root / raw_path for root in allowed_roots]

    searched: list[str] = []
    for candidate in candidates:
        resolved = candidate.resolve()
        searched.append(str(resolved))
        if not any(_is_within(resolved, root) for root in allowed_roots):
            continue
        if resolved.exists():
            return resolved
    raise FileNotFoundError(
        f"Input '{path_like}' was not found in active-project uploads/outputs or approved "
        f"library directories. Searched: {', '.join(searched)}"
    )


def resolve_project_output(path_like: str, *, suffix: str | None = None) -> Path:
    """Resolve a relative output beneath the active project's outputs directory."""
    if not path_like or not path_like.strip():
        raise ValueError("Output path must be a non-empty string.")
    raw_path = Path(path_like.strip()).expanduser()
    if raw_path.is_absolute():
        raise ValueError("Output paths must be relative to the active project.")
    if ".." in raw_path.parts:
        raise ValueError(f"Output path traversal is not allowed: '{path_like}'.")
    if raw_path.parts and raw_path.parts[0] == "library":
        raise ValueError("Library paths are read-only; write beneath project/outputs instead.")
    if (
        raw_path.parts
        and raw_path.parts[0] == "project"
        and raw_path.parts[:2]
        != (
            "project",
            "outputs",
        )
    ):
        raise ValueError("Project writes are allowed only beneath project/outputs.")

    if raw_path.parts[:2] == ("project", "outputs"):
        relative = Path(*raw_path.parts[2:])
    elif raw_path.parts and raw_path.parts[0] == "outputs":
        relative = Path(*raw_path.parts[1:])
    else:
        relative = raw_path
    if not relative.parts:
        raise ValueError("Output path must name an artifact beneath project/outputs.")

    output_root = config.active_project_outputs().resolve()
    resolved = (output_root / relative).resolve()
    if not _is_within(resolved, output_root):
        raise ValueError(f"Output '{path_like}' must be beneath project/outputs.")
    if suffix and resolved.suffix.casefold() != suffix.casefold():
        raise ValueError(f"Output '{path_like}' must end with '{suffix}'.")
    return resolved
