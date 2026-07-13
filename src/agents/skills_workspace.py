"""Materialize recruiter-assigned skill folders into the active project workspace.

Skill markdown bodies are injected into sub-agent prompts by
``agent_utils.format_skill_prompt``; but folder-based skills also ship
bundled assets under ``scripts/`` and ``references/`` that the sub-agent
needs to reach at a stable, sandbox-visible path. This module snapshots
the assigned skill folders into ``<workspace>/project/skills/`` right
after the recruiter finalizes the plan, and chmods them read-only so
they can't be mutated during execution.

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
