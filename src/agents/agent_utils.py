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
    shared_prompts = {p.stem: p.read_text().rstrip() for p in shared_prompts_dir.glob("*.txt")}
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
    formatted section with universal boilerplate. For folder-based skills whose bundled assets
    (``scripts/``, ``references/``) have been snapshotted under the active project, prepends the
    sandbox-visible absolute path so bare relative references in the skill body resolve.

    Returns empty string if no valid skills are found.
    """
    if not skill_names:
        return ""
    from agents.recruiter_agent.prompt import get_skill_metadata
    from config import CONTAINER_SKILLS_ROOT, active_project_skills
    from knowledge import SKILLS_DIR

    skills = get_skill_metadata()
    materialized_root = active_project_skills()
    skills_root = SKILLS_DIR.resolve()
    sections = []
    strict_names: list[str] = []
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
        # `strict: true` marks a procedural skill whose steps must be followed in
        # order (see the header built below).
        fm = parse_yaml_frontmatter(text) or {}
        if str(fm.get("strict", "")).strip().lower() in ("true", "yes", "1"):
            strict_names.append(name)
        assets_note = ""
        is_folder_skill = meta.path.parent.resolve() != skills_root
        if is_folder_skill and (materialized_root / name).exists():
            assets_note = (
                f"**Assets root:** `{CONTAINER_SKILLS_ROOT}/{name}/` (read-only). "
                "Any `scripts/` or `references/` paths cited below resolve under this root.\n\n"
            )
        sections.append(f"### Skill: {name}\n\n{assets_note}{body}")
    if not sections:
        return ""
    header = (
        "## Skills\n\n"
        "The following skill(s) are assigned to THIS step and define the REQUIRED "
        "method for it. Their code templates and call signatures are AUTHORITATIVE "
        "for the installed library versions — they were written and verified against "
        "the exact versions in this environment.\n\n"
        "When a skill below covers your task:\n"
        "- Use that skill's approach and libraries. Do NOT substitute a different "
        "library, resource, or database (e.g. do not reach for OmniPath/decoupler "
        "when the skill specifies a LIANA resource), and do NOT reinvent its method.\n"
        "- Copy its call signatures VERBATIM. Do NOT rediscover the API with "
        "`help`/`dir`/`__doc__` when the skill already gives the call — that just "
        "wastes turns and risks version drift the skill already resolved.\n"
        "- You MAY adapt dataset-specific details and file paths to the task, but "
        "NOT the choice of method or the library API.\n"
        "If your task instructions and a skill conflict on *how*, follow the skill."
    )
    if strict_names:
        # A procedural skill prescribes a sequence whose later stages verify the
        # earlier ones; adopting "parts" of it silently drops the verification and
        # ships an unchecked deliverable. Override the permissive default for these.
        listed = ", ".join(f"`{n}`" for n in strict_names)
        header += (
            f"\n\n**Exception — {listed}: follow the workflow exactly, in order, "
            "without skipping steps.** These are procedures, not suggestions: their "
            "later steps verify the earlier ones, so a skipped step means an "
            "unverified result. Run every step the skill lists, including its "
            "self-check and reflection stages, and use the values the skill tells you "
            "to measure rather than substituting your own choice. If a step genuinely "
            "cannot run (a missing dependency, a target the method does not fit), say "
            "so explicitly in your summary and name the step you skipped and why — "
            "never skip one silently, and never report the task complete as though a "
            "skipped check had passed."
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


def truncate_output(text: str, max_chars: int, *, spill: bool = False) -> str:
    """Truncate text to max_chars, keeping the head and tail with a notice in between.

    Args:
        text: The text to truncate.
        max_chars: Maximum characters to keep.
        spill: When True, write the *full* text to disk first and cite its path in
            the truncation notice, so the dropped middle stays recoverable via the
            ``read`` tool. Off by default: callers that truncate for display only
            (e.g. prompt previews) would otherwise litter the workspace with files
            nobody reads.

    Returns:
        The original text when it fits, else head + notice + tail.
    """
    if len(text) <= max_chars:
        return text

    half = max_chars // 2
    removed = len(text) - max_chars

    notice = f"[{removed} characters truncated]"
    if spill:
        # Import locally: agent_utils is imported by modules that don't need the
        # workspace, and output_spill pulls in project-dir config at import time.
        from agents.output_spill import spill_text_to_disk

        path = spill_text_to_disk(text)
        if path:
            notice = (
                f"[{removed} characters truncated — full output saved to {path} ; "
                f"read it with the read tool (use offset/limit to page) rather than "
                f"re-running this command]"
            )

    return f"{text[:half]}\n\n... {notice} ...\n\n{text[-half:]}"
