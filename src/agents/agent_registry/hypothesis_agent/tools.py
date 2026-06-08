"""Tool definitions for the hypothesis agent."""
from pathlib import Path
from typing import List
from langchain.tools import StructuredTool
from agents.agent_utils import file_read_tools
from config import DATA_DIR, LIBRARY_DIR, active_project_outputs


def write_file_tool(file_path: str, content: str) -> str:
    """Write content to a file in the active project's outputs/.

    Args:
        file_path: Path relative to ``projects/<id>/outputs/`` (e.g.
            ``"hypotheses.json"`` or ``"tables/data.tsv"``). Absolute
            paths are accepted but must resolve inside the workspace;
            writes into ``library/`` are refused.
        content: Content to write to the file.

    Returns:
        Success message with the written file path (relative to the
        workspace root so it appears in the projects panel).
    """
    try:
        outputs_root = active_project_outputs()
        candidate = Path(file_path.strip())
        target = (
            candidate.resolve()
            if candidate.is_absolute()
            else (outputs_root / candidate).resolve()
        )

        try:
            target.relative_to(LIBRARY_DIR.resolve())
        except ValueError:
            pass
        else:
            return (
                f"Error: writes into the library are not allowed (path '{target}'). "
                "Write outputs into your project's outputs/ directory instead."
            )

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


write_file_structured_tool = StructuredTool.from_function(
    func=write_file_tool,
    name="write_file_tool",
    description=(
        "Write text content to a file in the active project's outputs/. "
        "Provide a path relative to outputs/ (e.g., 'hypotheses.json'). "
        "Creates parent directories if needed. The library/ directory is read-only."
    ),
)

HypothesisTools: List[StructuredTool] = [
    *file_read_tools,
    write_file_structured_tool,
]
