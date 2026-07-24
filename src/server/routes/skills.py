"""Read-only REST endpoints for inspecting skills from the trace UI.

The trace panel shows which skills were loaded into each sub-agent step (see
``message_serializer.serialize_subagent_state``). These endpoints let the UI
expand a skill to read its full markdown, and — for folder-based skills that
ship bundled ``scripts/`` / ``references/`` assets — list and preview those
files inline.

Everything here reads from the repo's canonical ``knowledge/skills/`` registry
(the same source the recruiter reads), never the per-project materialized
snapshot. It is strictly read-only and path-traversal guarded.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from agents.recruiter_agent.prompt import get_skill_metadata
from config import ROOT
from knowledge import SKILLS_DIR

router = APIRouter(prefix="/api/skills")

# Cap for inline file previews. Bundled skill assets are small text files
# (markdown, python, json); anything larger is almost certainly not meant to be
# eyeballed in a dropdown, so we refuse rather than stream megabytes.
_MAX_PREVIEW_BYTES = 512 * 1024


def _build_tree(directory: Path, root: Path) -> List[dict]:
    """Recursively build a file tree for *directory*, paths relative to *root*.

    Mirrors ``routes.files._build_tree`` but kept local so the two file-listing
    features stay independent.
    """
    entries: List[dict] = []
    if not directory.exists():
        return entries
    for child in sorted(directory.iterdir()):
        entry: dict = {
            "name": child.name,
            "path": str(child.relative_to(root)),
            "is_dir": child.is_dir(),
            "size": child.stat().st_size if child.is_file() else 0,
        }
        if child.is_dir():
            entry["children"] = _build_tree(child, root)
        entries.append(entry)
    return entries


def _repo_relative(path: Path) -> str:
    """Return *path* relative to the repo root, for display (e.g.
    ``knowledge/skills/figure-reproduce``). Falls back to the absolute path
    if it somehow lives outside the repo."""
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path)


@router.get("/{name}")
def get_skill(name: str) -> dict:
    """Return a skill's metadata, full markdown body, and (for folder skills)
    its bundled file tree.

    The ``content`` is the raw markdown of the skill's own file. For
    folder-based skills, ``files`` is the tree under the skill directory (paths
    relative to that directory) and ``dir_path`` is the repo-relative folder
    location shown in the UI; ``main_file`` names the skill markdown within it.
    """
    meta = get_skill_metadata().get(name)
    if meta is None:
        available = sorted(get_skill_metadata().keys())
        raise HTTPException(
            status_code=404,
            detail=f"Skill '{name}' not found. Available: {', '.join(available) or '(none)'}",
        )

    skill_md = meta.path
    skill_dir = skill_md.parent
    is_dir = skill_dir.resolve() != SKILLS_DIR.resolve()

    try:
        content = skill_md.read_text(encoding="utf-8")
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Could not read skill: {exc}")

    payload: dict = {
        "name": meta.name,
        "description": meta.description,
        "applies_to": list(meta.applies_to),
        "is_dir": is_dir,
        "content": content,
    }
    if is_dir:
        payload["dir_path"] = _repo_relative(skill_dir)
        payload["main_file"] = str(skill_md.relative_to(skill_dir))
        payload["files"] = _build_tree(skill_dir, skill_dir)
    return payload


@router.get("/{name}/file")
def get_skill_file(
    name: str, path: str = Query(..., description="Path relative to the skill folder.")
) -> dict:
    """Return the text content of a file bundled inside a folder-based skill.

    Guards against traversal outside the skill directory and refuses binary or
    oversized files (the UI shows a "not previewable" note for those instead).
    """
    meta = get_skill_metadata().get(name)
    if meta is None:
        raise HTTPException(status_code=404, detail=f"Skill '{name}' not found.")

    skill_dir = meta.path.parent
    if skill_dir.resolve() == SKILLS_DIR.resolve():
        raise HTTPException(status_code=400, detail="Flat skills have no bundled files.")

    full_path = skill_dir / path
    resolved = full_path.resolve()
    if not resolved.is_relative_to(skill_dir.resolve()):
        raise HTTPException(status_code=403, detail="Access denied")
    if not resolved.is_file():
        raise HTTPException(status_code=404, detail=f"File '{path}' not found.")
    if resolved.stat().st_size > _MAX_PREVIEW_BYTES:
        raise HTTPException(status_code=413, detail="File too large to preview.")

    try:
        content = resolved.read_text(encoding="utf-8")
    except (UnicodeDecodeError, ValueError):
        raise HTTPException(status_code=415, detail="File is not text and cannot be previewed.")
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Could not read file: {exc}")

    return {"path": path, "content": content}
