"""Tool definitions for the critic agent."""
from typing import List
from langchain.tools import StructuredTool
from pathlib import Path
from config import DATA_DIR, LIBRARY_DIR, active_project_outputs

from agents.agent_utils import file_read_tools


def write_file_tool(file_path: str, content: str) -> str:
    """Write text content to a file in the active project's outputs/.

    Args:
        file_path: Path relative to the active project's outputs/ directory
            (e.g. "reports/criticism.json" lands at
            ``projects/<id>/outputs/reports/criticism.json``).
            Absolute paths are accepted but must resolve inside the
            workspace; writes into ``library/`` are refused.
        content: Text content to write.

    Returns:
        Success message with character count.
    """
    try:
        outputs_root = active_project_outputs()
        candidate = Path(file_path.strip())
        target = (
            candidate.resolve()
            if candidate.is_absolute()
            else (outputs_root / candidate).resolve()
        )

        # Refuse writes into the library — read-only.
        try:
            target.relative_to(LIBRARY_DIR.resolve())
        except ValueError:
            pass
        else:
            return (
                f"Error: writes into the library are not allowed (path '{target}'). "
                "Write outputs into your project's outputs/ directory instead."
            )

        # Stay inside the workspace.
        try:
            target.relative_to(DATA_DIR.resolve())
        except ValueError:
            return f"Error: path '{target}' must be inside the workspace '{DATA_DIR}'."

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        relative = target.relative_to(DATA_DIR.resolve())
        return f"Successfully wrote {len(content)} characters to {relative.as_posix()}"
    except Exception as e:
        return f"Error writing to {file_path}: {str(e)}"


# Export tools list
CriticTools: List[StructuredTool] = [
    *file_read_tools,
    StructuredTool.from_function(
        func=write_file_tool,
        name="write_file_tool",
        description=(
            "Write text content to a file in the active project's outputs/ directory. "
            "Provide a path relative to outputs/ (e.g., 'reports/criticism.json'). "
            "The library/ directory is read-only — writes there are refused."
        ),
    ),
]
