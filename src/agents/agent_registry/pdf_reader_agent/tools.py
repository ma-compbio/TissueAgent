"""Tool definitions for the PDF reader agent."""

from __future__ import annotations

from langchain.tools import StructuredTool
from pathlib import Path
from config import DATA_DIR

from agents.agent_tools import file_read_tools


def write_file_tool(file_path: str, content: str) -> str:
    """Write text content to a file.

    Args:
        file_path: Path relative to DATA_DIR (e.g., "briefs/paper_summary.txt")
        content: Text content to write

    Returns:
        Success message with character count
    """
    try:
        full_path = Path(DATA_DIR) / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
        return f"Successfully wrote {len(content)} characters to {file_path}"
    except Exception as e:
        return f"Error writing to {file_path}: {str(e)}"


# Export tools list
PDFReaderTools: list[StructuredTool] = [
    *file_read_tools,
    StructuredTool.from_function(
        func=write_file_tool,
        name="write_file_tool",
        description="Write text content to a file (path relative to DATA_DIR)",
    ),
]
