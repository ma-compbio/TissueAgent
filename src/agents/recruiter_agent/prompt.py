"""Prompt templates, description, and skill registry loader for the recruiter agent."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from agents.agent_utils import format_agent_id_descriptions, parse_yaml_frontmatter
from knowledge import SKILLS_DIR

_DIR = Path(__file__).parent

_SKILL_REGISTRY = SKILLS_DIR

_TEMPLATE = (_DIR / "prompt.txt").read_text()

RecruiterDescription = """
Takes the global plan and match each step to the most suitable expert agent from the Agent Registry.
""".strip()


# ---------------------------------------------------------------------------
# Skill registry loader
# ---------------------------------------------------------------------------


@dataclass
class SkillMeta:
    """Parsed skill frontmatter."""

    name: str
    description: str
    applies_to: list[str]
    status: str = "enable"
    path: Path = field(default_factory=Path)


# Subdirectories under the skill registry that are NOT skills — archives,
# examples, or asset folders — and must not be scanned for skill markdown.
_SKILL_DIR_IGNORE = {"cached_skills"}


def _skill_md_in_dir(d: Path) -> Path | None:
    """Return the skill's markdown file inside a skill folder, or ``None``.

    A folder-based skill keeps its markdown alongside ``scripts/`` and
    ``references/``. Prefer ``SKILL.md``, then ``<dirname>.md`` (the renamed
    convention), then a single ``*.md`` at the folder root as a fallback.
    """
    for candidate in (d / "SKILL.md", d / f"{d.name}.md"):
        if candidate.is_file():
            return candidate
    md_files = [p for p in d.glob("*.md") if p.name.lower() != "readme.md"]
    return md_files[0] if len(md_files) == 1 else None


def _skill_from_file(p: Path) -> SkillMeta | None:
    """Parse one skill markdown file into a :class:`SkillMeta`, if enabled."""
    fm = parse_yaml_frontmatter(p.read_text())
    if fm is None:
        return None
    status = str(fm.get("status", "enable")).strip().lower()
    if status != "enable":
        return None
    name = fm.get("name", p.stem)
    return SkillMeta(
        name=name,
        description=(fm.get("description") or "").strip(),
        applies_to=list(fm.get("applies_to") or []),
        status=status,
        path=p,
    )


def _parse_skills() -> dict[str, SkillMeta]:
    """Scan the skill registry and return enabled skills.

    Discovers both layouts:
      * **flat** — a top-level ``<name>.md`` file (except ``README.md``);
      * **folder** — a ``<name>/`` directory holding its skill markdown
        (``SKILL.md`` or ``<name>.md``) next to ``scripts/`` / ``references/``.
    Archive/asset folders in ``_SKILL_DIR_IGNORE`` (e.g. ``cached_skills``) are
    skipped. When a name is defined by both a folder and a flat file, the
    folder wins (it carries the bundled assets).
    """
    flat: dict[str, SkillMeta] = {}
    folder: dict[str, SkillMeta] = {}
    for entry in sorted(_SKILL_REGISTRY.iterdir()):
        if entry.is_dir():
            if entry.name in _SKILL_DIR_IGNORE:
                continue
            md = _skill_md_in_dir(entry)
            if md is None:
                continue
            meta = _skill_from_file(md)
            if meta is not None:
                folder[meta.name] = meta
        elif entry.suffix == ".md" and entry.name.lower() != "readme.md":
            meta = _skill_from_file(entry)
            if meta is not None:
                flat[meta.name] = meta
    # Folder skills take precedence over a flat file of the same name.
    return {**flat, **folder}


_SKILL_CACHE: dict[str, SkillMeta] | None = None


def get_skill_metadata() -> dict[str, SkillMeta]:
    """Return the name-to-metadata mapping for all enabled skills (cached)."""
    global _SKILL_CACHE
    if _SKILL_CACHE is None:
        _SKILL_CACHE = _parse_skills()
    return _SKILL_CACHE


def get_skill_index() -> str:
    """Build a compact skill listing for prompt injection."""
    lines = [""]
    for name, meta in sorted(get_skill_metadata().items()):
        agents = ", ".join(meta.applies_to)
        lines.append(f"- **{name}**: {meta.description} _(applies to: {agents})_")
    if len(lines) == 1:
        lines.append("_(No skills registered yet.)_")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

def RecruiterPrompt(agent_id_descriptions: dict[str, str]) -> str:
    """Build the recruiter agent system prompt with registry placeholders filled."""
    return _TEMPLATE.replace(
        "{{agent_registry}}", format_agent_id_descriptions(agent_id_descriptions)
    ).replace(
        "{{skill_registry}}", get_skill_index()
    )
