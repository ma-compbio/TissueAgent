"""Prompt templates and description for the coding agent."""

from pathlib import Path

from agents.agent_utils import substitute_shared_prompts

_DIR = Path(__file__).parent

# Sentinel lines wrapping search_documentation-specific guidance in the prompt
# files. Kept in one place so the tool (coding_agent/model.py) and its prompt
# text are gated by the SAME flag -- flipping config.DOC_SEARCH_ENABLED restores
# both. See config.DOC_SEARCH_ENABLED.
_DOCSEARCH_START = "<!--DOCSEARCH-->"
_DOCSEARCH_END = "<!--/DOCSEARCH-->"


def _apply_doc_search_gate(text: str, enabled: bool) -> str:
    """Keep or drop the <!--DOCSEARCH-->...<!--/DOCSEARCH--> blocks.

    enabled=True  -> keep the block content, remove only the marker lines.
    enabled=False -> remove the marker lines AND everything between them.
    """
    out: list[str] = []
    skipping = False
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if stripped == _DOCSEARCH_START:
            skipping = not enabled
            continue
        if stripped == _DOCSEARCH_END:
            skipping = False
            continue
        if not skipping:
            out.append(line)
    return "".join(out)


def _render(filename: str) -> str:
    """Read a coding-agent prompt file and substitute shared prompt blocks."""
    # Imported lazily to avoid any import-time cycle through config.
    from config import DOC_SEARCH_ENABLED

    text = substitute_shared_prompts((_DIR / filename).read_text())
    return _apply_doc_search_gate(text, DOC_SEARCH_ENABLED)


def CodingAgentPrompt(sandbox_enabled: bool = True) -> str:
    """Build the coding agent system prompt.

    When ``sandbox_enabled`` is False the no-sandbox variant is used, which adds an explicit
    file-access policy restricting the agent to the workspace root.
    """
    filename = (
        "coding_agent_prompt.txt" if sandbox_enabled else "coding_agent_prompt_no_sandbox.txt"
    )
    return _render(filename)


CodingAgentDescription = (_DIR / "coding_agent_description.txt").read_text().strip()
