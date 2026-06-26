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


def _parse_skills() -> dict[str, SkillMeta]:
    """Scan ``*.md`` files (except README) in the skill registry and return enabled skills."""
    skills: dict[str, SkillMeta] = {}
    for p in sorted(_SKILL_REGISTRY.glob("*.md")):
        if p.name.lower() == "readme.md":
            continue
        fm = parse_yaml_frontmatter(p.read_text())
        if fm is None:
            continue
        status = str(fm.get("status", "enable")).strip().lower()
        if status != "enable":
            continue
        name = fm.get("name", p.stem)
        skills[name] = SkillMeta(
            name=name,
            description=(fm.get("description") or "").strip(),
            applies_to=list(fm.get("applies_to") or []),
            status=status,
            path=p,
        )
    return skills


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
