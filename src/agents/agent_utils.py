"""Shared utilities for agent prompt construction and file access.

Provides helpers for formatting agent descriptions, extracting XML-style
blocks from LLM responses, and a simple file-retriever tool that lists
files in the data directory.
"""

import re
from langchain.tools import StructuredTool
from typing import Dict, Optional

from config import DATA_DIR


def format_agent_id_descriptions(agent_id_descriptions: Dict[str, str]) -> str:
    """Format agent ID-to-description pairs as a bulleted list for prompts.

    Args:
        agent_id_descriptions: Mapping of agent node IDs to their
            human-readable descriptions.

    Returns:
        A newline-separated string with one ``" - id: description"`` entry
        per agent.
    """
    return "\n".join(
        [f" - {id}: {description}" for id, description in agent_id_descriptions.items()]
    )


def extract_block(pattern: str, text: str) -> Optional[str]:
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


### file retriever tool


def file_retriever() -> str:
    """List all files currently stored under ``DATA_DIR``.

    Returns:
        A human-readable string containing the ``DATA_DIR`` path and a
        list of every file path found recursively within it.
    """
    filenames = [str(path) for path in DATA_DIR.rglob("*") if path.is_file()]
    return "\n".join(
        [
            "Files are stored in the DATA_DIR subdirectory.",
            f"DATA_DIR: '{DATA_DIR}'",
            f"File Paths: {filenames}",
        ]
    )


file_retriever_tool = StructuredTool.from_function(
    func=file_retriever,
    name="file_retriever_tool",
    description="Returns a list of file names in the data directory.",
)
