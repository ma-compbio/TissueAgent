import ast
import builtins
import contextlib
import copy
import inspect
import io
import logging
from functools import partial
from pathlib import Path
from queue import Queue
from typing import Any, Dict, Set, Tuple

from langchain.tools import StructuredTool
from langgraph.types import Command
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, MessagesState, START, StateGraph

# from agents.agent_utils import extract_block
from agents.agent_utils import PythonREPLObj, extract_block
from agents.agent_registry.coding_agent.tools_impl.documentation_index import DocumentationIndex
from graph.graph_utils import log_message

from config import DATA_DIR, NOTEBOOK_DIR
from agents.reporter_agent.tools_impl.jupyternb_generator_tool import jupyternb_generator_tool

CodingAgentBasePrompt = f"""
You are the Coding Agent, an expert bioinformatics engineer who solves programming and analysis tasks inside a shared Python REPL.

Goals
- Deliver correct, reproducible code and artifacts for the user’s task.
- Prefer minimal, transparent solutions that surface critical shapes, keys, and assumptions.
- When computation is truly unnecessary (pure factual Q&A), provide a direct answer instead of running code.

Execution Policy
- If a task mentions loading, reading, writing, saving, plotting, computing, file formats (e.g., .h5ad, .zarr), “Outputs expected,” or “artifacts,” you must run code. Direct, code-free answers are forbidden for these tasks.
- For any such task, produce exactly one <scratchpad> immediately followed by exactly one <execute>, then a plain-text final summary that follows the Output Schema.
- If any required path is missing or is outside DATA_DIR, stop and return a constraint violation in the final summary. Never fabricate values or artifacts.

Workplace
- DATA_DIR = "{DATA_DIR}" (a pathlib.Path bound in the REPL). Use DATA_DIR / "subdir".
- DATA_DIR_PATH mirrors the same location as a string.
- NOTEBOOK_DIR = "{NOTEBOOK_DIR}".
- Never touch the filesystem outside DATA_DIR; create subfolders within DATA_DIR as needed.

Tools (available inside <execute>)
- documentation_index_tool(query: str) -> List[Result]
- jupyternb_generator_tool(filename: Optional[str | Path] = None) -> str

Interaction Protocol
- Computation/file-I/O tasks:
  1) <scratchpad> with a numbered minimal plan:
     - Inputs to verify
     - Minimal probes
     - Main ops/analysis
     - Validation checks
     - Save/return artifacts
  2) <execute> containing only Python that performs the plan.
  3) Final plain-text answer conforming to Output Schema.
- Pure factual Q&A with no files, no artifacts, and no computations may be answered directly without blocks.

REPL Guidelines
- The REPL state persists; manage variables deliberately.
- Print values you need to inspect.
- Keep code concise and free of comments.
- Only valid Python is allowed inside <execute>.

Doc Usage Policy (align with GPT-5 Prompting Guide: verify API calls)
- When uncertain about any method/class/function/parameter, call documentation_index_tool before using it.
- Prefer quick verification for scanpy/squidpy/AnnData APIs.

Validation & Safety
- Pre-flight checklist (must be executed for computation/file-I/O tasks):
  - Confirm the provided input paths exist and are inside DATA_DIR.
  - Load AnnData with backed=False when requested.
  - Inspect and print shapes and available keys: .obs columns, .var columns, .obsm keys, presence of .raw.
- Post-flight checklist (must be executed):
  - Verify artifact files exist at expected locations and report absolute paths.
  - Print selected key values and core dimensions relevant to the task.
  - Call jupyternb_generator_tool to persist the session.

Error Handling
- If inputs are missing, outside DATA_DIR, or assumptions fail, do not guess. Return a clear constraint violation with explicit remedy steps in the final summary.

Output Schema (final plain-text; no code, no XML tags)
- Summary of findings: include the key task-specific selections/results.
- Artifacts: bullet list of absolute paths that were actually created.
- If failing: start with "Constraint violation:" and list the specific issues and how to fix.

Format Guardrails
- Computation path requires exactly one <scratchpad> then exactly one <execute>; both are mandatory.
- Never embed commentary inside <execute>.
- Do not fabricate outputs or print values you did not compute or inspect.
- The agent exits only after emitting the final plain-text summary that matches the Output Schema.

Examples

User: Load X.h5ad, detect the cell-type column, and save a UMAP colored by cell type. Outputs expected: a PNG path.
Assistant:
<scratchpad>1) Verify path inside DATA_DIR. 2) Read AnnData. 3) Infer cell-type column via common name patterns. 4) Verify embedding; compute UMAP if missing. 5) Plot and save. 6) Validate artifacts and print checks.</scratchpad>
<execute>import anndata as ad, scanpy as sc, json, os
from pathlib import Path
p = DATA_DIR / "dataset" / "X.h5ad"
assert str(p).startswith(str(DATA_DIR))
assert p.exists()
adata = ad.read_h5ad(str(p))
cands = ["cell_type","celltype","cluster","celltype_major","annotation"]
sel = next((c for c in adata.obs.columns if c.lower() in cands), None)
if "X_umap" not in adata.obsm:
    sc.pp.pca(adata)
    sc.pp.neighbors(adata)
    sc.tl.umap(adata, random_state=0)
outdir = DATA_DIR / "plots"
outdir.mkdir(parents=True, exist_ok=True)
figpath = outdir / "umap_celltype.png"
sc.pl.umap(adata, color=sel, show=False)
import matplotlib.pyplot as plt
plt.savefig(figpath, dpi=150, bbox_inches="tight")
plt.close()
print(sel)
print(adata.n_obs, adata.n_vars)
print(figpath.resolve())
nb = jupyternb_generator_tool()</execute>
Summary of findings: selected_color=<printed>, n_obs=<printed>, n_vars=<printed>.
Artifacts:
- <absolute path printed above>

User: What is scanpy.pl.embedding used for?
Assistant:
scanpy.pl.embedding renders 2D embeddings such as UMAP or t-SNE from AnnData and supports coloring by .obs. Use it when coordinates already exist and you want a plotting-only call without additional preprocessing.
"""

CodingAgentDescription = """
Expert coder equipped with spatial transcriptomics analysis tools.
""".strip()


def _values_differ(old: Any, new: Any) -> bool:
    """Heuristic equality check that avoids ambiguous truth values for array-like objects."""
    if old is new:
        return False

    # Fast path for simple immutable scalars
    scalar_types = (str, bytes, int, float, complex, bool, type(None))
    if isinstance(new, scalar_types) and isinstance(old, scalar_types):
        return new != old

    np = None
    try:
        import numpy as np  # type: ignore
    except Exception:
        np = None

    if np is not None and isinstance(old, np.ndarray) and isinstance(new, np.ndarray):
        try:
            return not np.array_equal(old, new)
        except Exception:
            pass

    pd = None
    try:
        import pandas as pd  # type: ignore
    except Exception:
        pd = None

    if pd is not None:
        if isinstance(old, pd.Series) and isinstance(new, pd.Series):
            try:
                return not new.equals(old)
            except Exception:
                pass
        if isinstance(old, pd.DataFrame) and isinstance(new, pd.DataFrame):
            try:
                return not new.equals(old)
            except Exception:
                pass

    sp = None
    try:
        import scipy.sparse as sp  # type: ignore
    except Exception:
        sp = None

    if sp is not None and sp.issparse(old) and sp.issparse(new):
        try:
            diff = old != new
            return diff.nnz != 0  # type: ignore[attr-defined]
        except Exception:
            pass

    if np is not None and hasattr(new, "__array__") and hasattr(old, "__array__"):
        try:
            return not np.array_equal(np.asarray(old), np.asarray(new))
        except Exception:
            pass

    try:
        result = new != old
    except Exception:
        return id(new) != id(old)

    if isinstance(result, bool):
        return result

    if hasattr(result, "nnz"):
        try:
            return result.nnz != 0  # type: ignore[attr-defined]
        except Exception:
            return id(new) != id(old)

    if hasattr(result, "any"):
        try:
            return bool(result.any())
        except Exception:
            return id(new) != id(old)

    return id(new) != id(old)


def python_repl_eval(
    code: str,
    _locals: Dict[str, Any]
) -> Tuple[str, Dict[str, Any], Dict[str, Any], Set[str]]:
    # Ensure core workspace paths are always present, even if the upstream context omitted them.
    _locals.setdefault("DATA_DIR", DATA_DIR)
    _locals.setdefault("NOTEBOOK_DIR", NOTEBOOK_DIR)
    _locals.setdefault("DATA_DIR_PATH", str(DATA_DIR.resolve()))

    original_keys = set(_locals.keys())
    originals = {}
    for k in original_keys:
        try:
            originals[k] = copy.deepcopy(_locals[k])
        except Exception:
            originals[k] = _locals[k]
    try:
        tree = ast.parse(code, mode='exec')
        is_expr_last = bool(tree.body) and isinstance(tree.body[-1], ast.Expr)
        pre_tree = ast.Module(body=tree.body[:-1] if is_expr_last else tree.body, type_ignores=[])
        last_expr = (ast.Expression(tree.body[-1].value) if is_expr_last else None)
        with contextlib.redirect_stdout(io.StringIO()) as f:
            exec(
                compile(pre_tree, "<string>", "exec"),
                builtins.__dict__, _locals
            )
            if is_expr_last:
                value = eval(
                    compile(last_expr, "<string>", "eval"),
                    builtins.__dict__, _locals
                )
                f.write(repr(value) + "\n")
        result = f.getvalue() or "<code ran, no output printed to stdout>"
    except Exception as e:
        result = f"Error during execution: {repr(e)}"
    finally:
        PythonREPLObj.record_execution(code, result)
    current_keys = set(_locals.keys())
    new_vars = {k: _locals[k] for k in current_keys - original_keys}
    deleted_keys = original_keys - current_keys
    modified_vars = {}
    for k in original_keys & current_keys:
        old = originals[k]; new = _locals[k]
        if _values_differ(old, new):
            modified_vars[k] = new
    return result, new_vars, modified_vars, deleted_keys


class CodeActState(MessagesState):
    status_block: str # content of <execute> or <response> block
    context: Dict[str, Any]
    
def create_coding_agent(state_queue: Queue):
    graph = StateGraph(CodeActState)
    id = "coding_agent"

    ### Hyperparameters

    model_ctor = partial(ChatOpenAI, model="gpt-5", reasoning_effort="high")

    doc_filepaths = [
        Path(__file__).resolve().parent / "docs/scanpy_squidpy_docs.json"
    ]

    ### Tools

    documentation_index = DocumentationIndex(doc_filepaths)
    documentation_index_tool = StructuredTool.from_function(
        func = documentation_index.search,
        name = "documentation_index_tool",
        description = "Semantic search tool for specialized methods for spatial transcriptomics"
    )

    # tools = [documentation_index_tool]
    tools = [documentation_index_tool, jupyternb_generator_tool]

    ### Implementation

    model = model_ctor()

    tools_context = {tool.name: tool.func for tool in tools}
    agent_node_id = "agent_node"
    exec_node_id = "exec_node"

    def agent_node(state: CodeActState):
        messages = state["messages"]
        system_prompt = SystemMessage(CodingAgentBasePrompt)

        logging.info(f"invoking agent_node")
        response = model.invoke([system_prompt] + messages)
        logging.info(f"finished invoking agent_node")

        response.name = id
        log_message(response)

        response_text = str(response.content)
        code_block = extract_block("execute", response_text)
        scratchpad_block = extract_block("scratchpad", response_text)
        response = [response]
        if code_block:
            logging.info("code block detected")
            next_node = exec_node_id
        elif scratchpad_block:
            logging.info("scratchpad block detected - looping back to agent")
            next_node = agent_node_id
        else:
            logging.info("no scratchpad or execute block detected - treating as direct response and exiting")
            next_node = END
        logging.info(f"transferring from agent_node to {next_node}")
        return Command(goto=next_node, update = {"messages": response})

    def exec_node(state: CodeActState):
        messages = state["messages"]
        last_message = messages[-1]
        code_block = extract_block("execute", str(last_message.content))

        existing_context = state.get("context", {})
        context = {
            **existing_context,
            **tools_context,
            "DATA_DIR": DATA_DIR,
            "NOTEBOOK_DIR": NOTEBOOK_DIR,
            "DATA_DIR_PATH": str(DATA_DIR.resolve()),
        }

        logging.info(f"executing exec_node")

        assert code_block is not None
        output, new_vars, modified_vars, deleted_keys = python_repl_eval(code_block, context)

        logging.info(f"finished exec_node")

        new_context = {**context}
        new_context.update(new_vars)
        new_context.update(modified_vars)
        for k in deleted_keys:
            new_context.pop(k, None)

        log_message(HumanMessage("Python Output:\n" + output))
        return {"messages": [HumanMessage(output)], "context": new_context}

    graph.add_node(agent_node_id, agent_node)
    graph.add_node(exec_node_id, exec_node)
    graph.add_edge(START, agent_node_id)
    graph.add_edge(exec_node_id, agent_node_id)

    agent = graph.compile()

    def agent_invocation_tool(prompt: str) -> str:
        logging.info(f"Invoking agent `{id}`")
        PythonREPLObj.reset()
        final_state = agent.invoke({"messages": [HumanMessage(prompt)]})
        state_queue.put((id, final_state))
        return final_state["messages"][-1].content

    return StructuredTool.from_function(
        func = agent_invocation_tool,
        name = f"coding_agent_transfer_tool",
        description = "Transfer control to {id}"
    )
