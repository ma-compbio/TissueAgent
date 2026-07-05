"""Shared utilities for agent prompt construction.

Provides helpers for formatting agent descriptions, extracting XML-style blocks from LLM responses,
and text truncation.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import yaml

def substitute_shared_prompts(text: str) -> str:
    """Replace ``{{<stem>}}`` placeholders with the contents of ``shared_prompts/<stem>.txt``.

    Idempotent: re-applying it on already-substituted text is a no-op because the placeholder
    string is consumed by the first pass. New shared fragments can be added by dropping a ``.txt``
    file into ``src/agents/shared_prompts/``; any prompt that references ``{{<stem>}}`` will then
    pick it up automatically.
    """
    shared_prompts_dir = Path(__file__).parent / "shared_prompts"
    shared_prompts = 
     {p.stem: p.read_text().rstrip() for p in _SHARED_PROMPTS_DIR.glob("*.txt")}
    for name, content in shared_prompts.items():
        text = text.replace(f"{{{{{name}}}}}", content)
    return text


def parse_yaml_frontmatter(text: str) -> dict | None:
    """Extract YAML frontmatter from a Markdown string.

    Expects the text to start with ``---``, followed by YAML content, closed by another ``---``.
    Returns the parsed dict, or ``None`` if the text has no valid frontmatter.
    """
    if not text.startswith("---"):
        return None
    try:
        end = text.index("---", 3)
    except ValueError:
        return None
    result = yaml.safe_load(text[3:end])
    return result if isinstance(result, dict) else None


def format_skill_prompt(skill_names: list[str]) -> str:
    """Build the skill injection block for a sub-agent system prompt.

    Loads skill content from the skill registry, strips YAML frontmatter, and wraps each skill in a
    formatted section with universal boilerplate.

    Returns empty string if no valid skills are found.
    """
    if not skill_names:
        return ""
    from agents.recruiter_agent.prompt import get_skill_metadata

    skills = get_skill_metadata()
    sections = []
    for name in skill_names:
        meta = skills.get(name)
        if meta is None:
            logging.warning(f"Skill '{name}' not found in registry, skipping.")
            continue
        text = meta.path.read_text()
        # Strip YAML frontmatter
        if text.startswith("---"):
            try:
                end = text.index("---", 3)
                body = text[end + 3 :].strip()
            except ValueError:
                body = text
        else:
            body = text
        sections.append(f"### Skill: {name}\n\n{body}")
    if not sections:
        return ""
    header = (
        "## Skills\n\n"
        "The following skill templates have been assigned to guide your approach "
        "for this task. You may adopt parts of a skill's approach without following "
        "it exactly, adapting it to fit the specific requirements of the current task."
    )
    return header + "\n\n" + "\n\n---\n\n".join(sections)


def format_agent_id_descriptions(agent_id_descriptions: dict[str, str]) -> str:
    """Format agent ID-to-description pairs as a bulleted list for prompts.

    Args:
        agent_id_descriptions: Mapping of agent node IDs to their
            human-readable descriptions.

    Returns:
        A newline-separated string with one " - id: description" entry
        per agent.
    """
    return "\n".join(
        [f" - {id}: {description}" for id, description in agent_id_descriptions.items()]
    )


def extract_block(pattern: str, text: str) -> str | None:
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
    return f"{text[:half]}\n\n... [{removed} characters truncated] ...\n\n{text[-half:]}"
