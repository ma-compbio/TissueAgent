# src/agents/agent_registry/pdf_reader_agent/tools.py
from typing import List
from langchain.tools import StructuredTool
from pathlib import Path
from config import DATA_DIR

def write_file_tool(file_path: str, content: str) -> str:
    """
    Write text content to a file.

    Args:
        file_path: Path relative to DATA_DIR (e.g., "briefs/paper_summary.txt")
        content: Text content to write

    Returns:
        Success message with character count
    """
    try:
        full_path = Path(DATA_DIR) / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding='utf-8')
        return f"Successfully wrote {len(content)} characters to {file_path}"
    except Exception as e:
        return f"Error writing to {file_path}: {str(e)}"

def file_retriever_tool() -> str:
    """
    List files in DATA_DIR to verify outputs.

    Returns:
        Directory structure showing created files
    """
    try:
        data_path = Path(DATA_DIR)
        if not data_path.exists():
            return f"DATA_DIR does not exist: {DATA_DIR}"

        result = [f"Files are stored in the DATA_DIR subdirectory.\nDATA_DIR: '{DATA_DIR}'\nFile Paths: ["]

        for item in sorted(data_path.rglob("*")):
            if item.is_file():
                rel_path = item.relative_to(data_path)
                result.append(f"  '{rel_path}',")

        result.append("]")
        return "\n".join(result)
    except Exception as e:
        return f"Error listing files: {str(e)}"

# Export tools list
PDFReaderTools: List[StructuredTool] = [
    StructuredTool.from_function(
        func=write_file_tool,
        name="write_file_tool",
        description="Write text content to a file (path relative to DATA_DIR)",
    ),
    StructuredTool.from_function(
        func=file_retriever_tool,
        name="file_retriever_tool",
        description="List all files in DATA_DIR",
    ),
]
