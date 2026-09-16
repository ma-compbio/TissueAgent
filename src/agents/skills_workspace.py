"""Materialize recruiter-assigned skill folders into the active project workspace.

Skill markdown bodies are injected into sub-agent prompts by
``agent_utils.format_skill_prompt``; but folder-based skills also ship
bundled assets under ``scripts/`` and ``references/`` that the sub-agent
needs to reach at a stable, sandbox-visible path. This module snapshots
the assigned skill folders into ``<workspace>/project/skills/`` and chmods
them read-only so they can't be mutated during execution.

Snapshotting is lazy and per-step: :func:`sync_workspace_skills` runs right
before each sub-agent invocation with only the *current* step's skills, so a
step never sees a later step's skill files on disk (symmetric with the
per-step prompt injection in ``agent_utils.format_skill_prompt``).

The recruiter itself continues to read from the repo's canonical
``knowledge/skills/`` — this snapshot is for sub-agents only.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from config import active_project_skills
from knowledge import SKILLS_DIR


def _chmod_writable(path: Path) -> None:
    """Recursively grant owner +w on files and +wx on dirs under *path*.

    Used before removing a previously-materialized read-only tree.
    """
    if not path.exists():
        return
    for p in [path, *path.rglob("*")]:
        try:
            mode = p.stat().st_mode
            if p.is_dir():
                p.chmod(mode | 0o300)
            else:
                p.chmod(mode | 0o200)
        except OSError as e:
            logging.warning("skills_workspace: chmod +w failed for %s: %s", p, e)


def _chmod_readonly(root: Path) -> None:
    """Recursively chmod dirs to 0555 and files to 0444."""
    for p in [root, *root.rglob("*")]:
        try:
            p.chmod(0o555 if p.is_dir() else 0o444)
        except OSError as e:
            logging.warning("skills_workspace: chmod -w failed for %s: %s", p, e)


def clear_workspace_skills() -> None:
    """Remove any previously-materialized skills tree, ignoring read-only bits."""
    root = active_project_skills()
    if root.exists():
        _chmod_writable(root)
        shutil.rmtree(root, ignore_errors=True)


def materialize_skills(skill_names: set[str] | list[str]) -> list[str]:
    """Snapshot the given folder-based skills under the active project.

    Flat single-file skills have no bundled assets and are skipped;
    their markdown body is still injected into the sub-agent prompt by
    ``format_skill_prompt`` — nothing here to snapshot.

    Returns the sorted list of skill names actually materialized (so
    callers can build the injection block from the same set).
    """
    from agents.recruiter_agent.prompt import get_skill_metadata

    clear_workspace_skills()
    if not skill_names:
        return []

    dest_root = active_project_skills()
    dest_root.mkdir(parents=True, exist_ok=True)

    registry = get_skill_metadata()
    materialized: list[str] = []
    skills_root = SKILLS_DIR.resolve()
    for name in sorted(set(skill_names)):
        meta = registry.get(name)
        if meta is None:
            logging.warning(
                "skills_workspace: skill '%s' not in registry, skipping snapshot", name
            )
            continue
        src_dir = meta.path.parent
        if src_dir.resolve() == skills_root:
            # Flat-file skill — nothing to copy, prompt injection handles it.
            continue
        dest = dest_root / name
        shutil.copytree(src_dir, dest)
        _chmod_readonly(dest)
        materialized.append(name)

    # Make the outer skills/ directory read-only too, once populated.
    if materialized:
        try:
            dest_root.chmod(0o555)
        except OSError as e:
            logging.warning("skills_workspace: chmod -w failed for %s: %s", dest_root, e)

    return materialized


def _folder_skill_names(skill_names: set[str] | list[str]) -> set[str]:
    """Subset of *skill_names* that are folder-based skills.

    Only folder skills leave anything on disk under ``project/skills/`` — flat
    single-file skills have no bundled assets and are excluded, so the caller
    can compare this set against the materialized directory names.
    """
    from agents.recruiter_agent.prompt import get_skill_metadata

    registry = get_skill_metadata()
    skills_root = SKILLS_DIR.resolve()
    out: set[str] = set()
    for name in skill_names:
        meta = registry.get(name)
        if meta is not None and meta.path.parent.resolve() != skills_root:
            out.add(name)
    return out


def sync_workspace_skills(skill_names: set[str] | list[str]) -> list[str]:
    """Make the workspace skills tree hold exactly *skill_names*' folder assets.

    Called before each sub-agent invocation with the current step's skills, so a
    step never sees a later step's skill files on disk. Idempotent and cheap:
    when the on-disk folder-skill set already matches, it skips the wipe/rebuild
    entirely; otherwise it delegates to :func:`materialize_skills` (which clears
    the old tree first). Passing an empty list clears the tree.

    Returns the sorted list of folder-skill names now present on disk.
    """
    wanted = _folder_skill_names(skill_names)
    root = active_project_skills()
    current = {p.name for p in root.iterdir() if p.is_dir()} if root.exists() else set()
    if current == wanted:
        return sorted(wanted)
    return materialize_skills(skill_names)
