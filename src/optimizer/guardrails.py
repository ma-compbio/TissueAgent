"""Hard guardrails on the optimizer's edit surface.

The optimizer may only touch Markdown files under ``knowledge/skills/`` and
``knowledge/plans/`` — never ``src/``, never a skill's bundled ``scripts/`` or
``references/``. The shipped scripts are validated pipelines and double as the
generator of the benchmark's reference outputs, so letting the optimizer edit
them would let agent output and reference co-drift and corrupt the accuracy
signal. Enforcement lives here, in code the model cannot bypass.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from agents.agent_utils import parse_yaml_frontmatter
from knowledge import KNOWLEDGE_ROOT, PLANS_DIR, SKILLS_DIR

REPO_ROOT = KNOWLEDGE_ROOT.parent

ALLOWED_ROOTS: tuple[Path, ...] = (SKILLS_DIR.resolve(), PLANS_DIR.resolve())

# Directory names inside a skill folder whose contents are frozen assets.
FORBIDDEN_DIR_NAMES = frozenset({"scripts", "references"})

# Mirrors the archive/asset folders the skill scanner ignores.
SKILL_DIR_IGNORE = frozenset({"cached_skills"})

MAX_EDIT_CHARS = 4000  # old_str + new_str combined, per edit
MAX_EDITS_PER_ROUND = 12


class GuardrailError(Exception):
    """An edit was rejected by a hard guardrail."""


def resolve_editable(path_str: str, roots: tuple[Path, ...] | None = None) -> Path:
    """Resolve ``path_str`` to an editable knowledge file or raise GuardrailError.

    Accepts absolute paths or paths relative to the repo root. The resolved
    (symlink-free) path must live under one of ``roots``, end in ``.md``, and
    not sit inside a ``scripts/`` or ``references/`` directory.
    """
    roots = tuple(r.resolve() for r in (roots or ALLOWED_ROOTS))
    raw = Path(path_str)
    if not raw.is_absolute():
        raw = REPO_ROOT / raw
    resolved = raw.resolve()

    root = next((r for r in roots if resolved.is_relative_to(r)), None)
    if root is None:
        raise GuardrailError(
            f"'{path_str}' is outside the editable roots "
            f"({', '.join(str(r) for r in roots)}). Only skill and plan-template "
            "markdown may be edited."
        )
    if resolved.suffix.lower() != ".md":
        raise GuardrailError(f"'{path_str}' is not a Markdown file; only .md files are editable.")
    rel_parts = resolved.relative_to(root).parts[:-1]
    frozen = FORBIDDEN_DIR_NAMES.intersection(rel_parts)
    if frozen:
        raise GuardrailError(
            f"'{path_str}' sits inside a frozen asset directory ({', '.join(sorted(frozen))}); "
            "skill scripts and references must not be edited."
        )
    if not resolved.is_file():
        raise GuardrailError(f"'{path_str}' does not exist; only existing files can be edited.")
    return resolved


def check_edit_size(old_str: str, new_str: str) -> None:
    """Reject a single str-replace whose combined payload exceeds the cap."""
    size = len(old_str) + len(new_str)
    if size > MAX_EDIT_CHARS:
        raise GuardrailError(
            f"Edit payload is {size} chars (cap {MAX_EDIT_CHARS}). Make a smaller, "
            "more surgical change, or split it into several edits."
        )


def _skill_registry_markdown(skills_dir: Path) -> list[Path]:
    """The markdown files the skill scanner would actually load.

    Mirrors ``agents.recruiter_agent.prompt._parse_skills`` discovery: flat
    ``<name>.md`` files plus one skill markdown per folder (``SKILL.md``, then
    ``<dirname>.md``, then a single other ``*.md``).
    """
    found: list[Path] = []
    for entry in sorted(skills_dir.iterdir()):
        if entry.is_dir():
            if entry.name in SKILL_DIR_IGNORE:
                continue
            for candidate in (entry / "SKILL.md", entry / f"{entry.name}.md"):
                if candidate.is_file():
                    found.append(candidate)
                    break
            else:
                md_files = [p for p in entry.glob("*.md") if p.name.lower() != "readme.md"]
                if len(md_files) == 1:
                    found.append(md_files[0])
        elif entry.suffix == ".md" and entry.name.lower() != "readme.md":
            found.append(entry)
    return found


def validate_knowledge(
    skills_dir: Path | None = None, plans_dir: Path | None = None
) -> list[str]:
    """Re-parse the knowledge registry and return a list of problems (empty = OK).

    Catches the silent failure mode of a bad edit: broken or missing YAML
    frontmatter makes a skill or template vanish from the registry without any
    runtime error. Also flags duplicate enabled names (two enabled plan
    templates sharing a ``name`` would collide in the planner's index).
    """
    skills_dir = (skills_dir or SKILLS_DIR).resolve()
    plans_dir = (plans_dir or PLANS_DIR).resolve()
    errors: list[str] = []

    enabled_plans: dict[str, list[str]] = {}
    for p in sorted(plans_dir.glob("*.md")):
        if p.name.lower() == "readme.md":
            continue
        fm, err = _safe_frontmatter(p)
        if err:
            errors.append(err)
            continue
        name = fm.get("name", p.stem)
        # Absent status defaults to enabled, mirroring the planner's index.
        if str(fm.get("status", "enabled")).strip().lower() in ("enabled", "enable"):
            enabled_plans.setdefault(str(name), []).append(p.name)
    for name, files in enabled_plans.items():
        if len(files) > 1:
            errors.append(
                f"plan template name '{name}' is enabled in multiple files: {sorted(files)}"
            )

    enabled_skills: dict[str, list[str]] = {}
    for p in _skill_registry_markdown(skills_dir):
        fm, err = _safe_frontmatter(p)
        if err:
            errors.append(err)
            continue
        name = fm.get("name", p.stem)
        # Skills default to "enable"; mirror the recruiter's accepted spellings.
        if str(fm.get("status", "enable")).strip().lower() in ("enable", "enabled"):
            enabled_skills.setdefault(str(name), []).append(str(p.relative_to(skills_dir)))
    for name, files in enabled_skills.items():
        if len(files) > 1:
            errors.append(f"skill name '{name}' is enabled in multiple files: {sorted(files)}")

    return errors


def _safe_frontmatter(p: Path) -> tuple[dict, str | None]:
    """Parse a file's frontmatter, returning (frontmatter, error_message)."""
    try:
        fm = parse_yaml_frontmatter(p.read_text())
    except yaml.YAMLError as e:
        return {}, f"{p}: invalid YAML frontmatter ({e})"
    if fm is None:
        return {}, f"{p}: missing or unparseable YAML frontmatter"
    return fm, None
