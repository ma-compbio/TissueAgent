"""Reporter tool that exports the current run's executed code as a notebook.

The notebook is built by walking the ``session.subagent_states`` map for
every Coding Agent invocation in this run, pulling each ``<execute>``
block from the agent's transcript, and writing one code cell per block
in execution order.

Design choices (matching the user's selection in the impeccable session):

* **Code-only.** No per-cell LLM-generated markdown descriptions; the
  cells contain the code that actually ran, nothing more. A short
  header cell records the user's request and a timestamp so the
  notebook is self-identifying.
* **Skip cleanly when there's no code.** Some runs (e.g. literature
  search, PDF analysis) never invoke the coding agent. In that case
  the tool returns a clear ``Skipped: ...`` string so the reporter
  doesn't lie about producing an artifact that wasn't created.
* **Timestamped filename.** Each run writes its own notebook;
  re-running the same query doesn't clobber prior outputs.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import nbformat as nbf
import nbformat.v4 as nbfv4
from langchain_core.tools import StructuredTool
from langchain_core.messages import AIMessage, BaseMessage

from agents.agent_utils import extract_block
from config import DATA_DIR, active_project_outputs


# Subagent state map keys for sub-agents whose transcripts contain
# executable code blocks. Currently only the Coding Agent; the
# Hypothesis Agent also emits ``<execute>`` blocks but those are for
# internal reasoning rather than user-reproducible analysis, so we
# leave it out of the notebook by default.
_CODE_PRODUCING_AGENT_NAMES = {"Coding Agent"}


def _collect_code_blocks() -> list[str]:
    """Return every ``<execute>`` block emitted in this run, in order.

    Inspects ``server.session_manager.session.subagent_states``. The
    entries are inserted as the manager finishes each specialist
    invocation, in the same order the manager executed them, so the
    resulting list reflects the actual execution sequence.
    """
    # Lazy import — keeps this module from pulling in the FastAPI
    # server on coding-agent imports.
    from server.session_manager import session

    blocks: list[str] = []
    # subagent_states is a dict {tool_id: (agent_name, final_state, invocation_id)}.
    # Python dicts are insertion-ordered, and the manager populates them
    # in execution order, so iterating in order gives us run order.
    for entry in session.subagent_states.values():
        if not isinstance(entry, tuple) or len(entry) < 2:
            continue
        agent_name, final_state = entry[0], entry[1]
        if agent_name not in _CODE_PRODUCING_AGENT_NAMES:
            continue
        if not isinstance(final_state, dict):
            continue
        messages: list[BaseMessage] = final_state.get("messages") or []
        for msg in messages:
            if not isinstance(msg, AIMessage):
                continue
            content = msg.content
            if not isinstance(content, str):
                continue
            code = extract_block("execute", content)
            if code and code.strip():
                blocks.append(code.strip())
    return blocks


def _user_request() -> str:
    """Best-effort lookup of the user's original prompt for the header."""
    from server.session_manager import session
    from langchain_core.messages import HumanMessage

    messages = session.agent_state.get("messages", [])
    for m in messages:
        if isinstance(m, HumanMessage):
            content = m.content
            if isinstance(content, str):
                return content.strip()
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        text = str(part.get("text", "")).strip()
                        if text:
                            return text
    return ""


def _normalize_filename(filename: Path | str | None) -> Path:
    """Pick where to write the notebook.

    Default: ``project/outputs/notebook/report_<ts>.ipynb`` so the
    notebook ships with the project. When a path is provided, anchor
    relative paths to the active project's outputs/ as well; absolute
    paths are accepted but must resolve inside the workspace.
    """
    outputs_root = active_project_outputs()
    if filename is None:
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        target = outputs_root / "notebook" / f"report_{stamp}.ipynb"
    else:
        target = Path(filename)
        if not target.is_absolute():
            target = outputs_root / target

    target = target.resolve()

    try:
        target.relative_to(DATA_DIR)
    except ValueError as exc:
        raise RuntimeError(
            f"Notebook path '{target}' must be inside the workspace '{DATA_DIR}'."
        ) from exc

    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def generate_jupyternb(filename: Path | str | None = None) -> str:
    """Build a Jupyter notebook from the coding agent's executed code.

    Args:
        filename: Optional output path. Relative paths anchor to the
            active project's ``outputs/`` directory; absolute paths must
            resolve inside the workspace. Defaults to
            ``project/outputs/notebook/report_<ts>.ipynb``.

    Returns:
        A short status string. Either:

        - ``"Success: notebook written to <relative-path> with N code cells."``
        - ``"Skipped: no coding-agent execution to capture."``
        - ``"Error: <reason>"`` on failure.
    """
    blocks = _collect_code_blocks()
    if not blocks:
        return (
            "Skipped: no coding-agent execution to capture in this run. "
            "No notebook was written."
        )

    try:
        target = _normalize_filename(filename)
    except Exception as exc:
        return f"Error: {exc}"

    nb = nbfv4.new_notebook()

    # Header — user request + timestamp so the file is self-describing
    # without needing to look up the saved session.
    request = _user_request()
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header_lines = ["# TissueAgent run", "", f"*Generated {stamp}*"]
    if request:
        header_lines.extend(["", "**Request:**", "", f"> {request}"])
    nb.cells.append(nbfv4.new_markdown_cell("\n".join(header_lines)))

    for code in blocks:
        nb.cells.append(nbfv4.new_code_cell(code))

    try:
        nbf.write(nb, target)
    except Exception as exc:
        return f"Error: notebook export failed with `{exc}`"

    # Report path relative to DATA_DIR per the project convention.
    try:
        rel = target.relative_to(DATA_DIR)
    except ValueError:
        rel = target
    return (
        f"Success: notebook written to {rel} with {len(blocks)} code "
        f"cell{'' if len(blocks) == 1 else 's'}."
    )


jupyternb_generator_tool = StructuredTool.from_function(
    func=generate_jupyternb,
    name="jupyternb_generator_tool",
    description=(
        "Generate a Jupyter notebook containing every Python code block "
        "the Coding Agent executed during this run. Pass no arguments — "
        "the tool walks the session state automatically. Returns a "
        "status string starting with 'Success:', 'Skipped:', or "
        "'Error:'. Call this once at the very end of a run that involved "
        "the Coding Agent; for runs that did not invoke the Coding Agent "
        "(e.g. pure literature search), call it anyway and accept the "
        "'Skipped' result."
    ),
)
