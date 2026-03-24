"""Tool definitions for the hypothesis agent."""
from pathlib import Path
from typing import List
from langchain.tools import StructuredTool
from agents.agent_utils import file_retriever_tool
from config import DATA_DIR


def write_file_tool(file_path: str, content: str) -> str:
    """Write content to a file path relative to DATA_DIR.

    Args:
        file_path: Relative path from DATA_DIR (e.g., "hypotheses.json" or "tables/data.tsv")
        content: Content to write to the file

    Returns:
        Success message with the written file path
    """
    try:
        full_path = Path(DATA_DIR) / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
        return f"Successfully wrote {len(content)} characters to {file_path}"
    except Exception as e:
        return f"Error writing to {file_path}: {str(e)}"


write_file_structured_tool = StructuredTool.from_function(
    func=write_file_tool,
    name="write_file_tool",
    description="Write text content to a file at a path relative to DATA_DIR. Creates parent directories if needed.",
)

HypothesisTools: List[StructuredTool] = [
    file_retriever_tool,
    write_file_structured_tool,
]
