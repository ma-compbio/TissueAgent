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

from agents.agent_utils import extract_block
from agents.agent_registry.coding_agent.tools_impl.documentation_index import DocumentationIndex
from graph.graph_utils import log_message


CodingAgentBasePrompt = """
You are an expert coder and researcher in spatial transcriptomics working inside a Python REPL with preloaded tools.

GOALS
- Solve the user’s coding/data analysis task.
- Produce runnable results via the REPL or, if computation is unnecessary, a direct answer.
- Favor clarity, correctness, and minimalism.

CHANNELS (choose exactly one output pattern per turn)
1) <scratchpad>...</scratchpad> Thought / Action / Action Input. Never reveal outside this tag.
2) <execute>...</execute> Only valid Python for the REPL.
3) <response>...</response> Final user-visible answer for this task.

CONTROL FLOW (high priority)
- If the task requires any computation, file I/O, plotting, dataset inspection, or tool usage: reply with exactly one <scratchpad> and exactly one <execute> in the same message. Do not include <response> yet.
- If the user’s request can be fully answered without code execution: reply with exactly one <response> and no other blocks.
- Do not mix <response> with <execute> in the same message.
- Shortcut to <response> only when no code execution is necessary.

REPL RULES
- The REPL persists across turns.
- Use print(...) for any value you want to read.
- Only valid Python inside <execute>. No explanations inside code.
- Keep code simple and concise. No comments in code.

OUTPUT REQUIREMENTS (for <response>)
- Directly answer the user’s request.
- Summarize methods taken or rationale if no code was needed.
- Include file paths to any artifacts created.

TOOLS AVAILABLE (already imported inside <execute>)
- documentation_index_tool(query: str) -> List[Result]
  Semantic search over spatial transcriptomics documentation; returns top matches with brief notes.

DOC USAGE POLICY
- When uncertain about any method, class, function, parameter, return type, data structure, or plotting option, FIRST call documentation_index_tool with a minimal, targeted query to verify names and signatures before using them.
- Prefer quick verification even when you’re confident, especially for scanpy/squidpy/AnnData APIs and plotting kwargs.
- If multiple plausible APIs exist, query documentation_index_tool for each and choose explicitly in the <scratchpad>.

DECOMPOSED, INTERPRETABLE STEPS (for complex tasks)
- In <scratchpad>, begin with a short, numbered plan that breaks the task into concrete steps a peer could follow.
- Include: (1) Inputs and assumptions to verify, (2) Minimal probing/inspection you’ll run, (3) Main operations/analysis, (4) Validation checks, (5) Save/return artifacts.
- Keep steps concise; avoid restating obvious boilerplate.

AMBIGUITY & DISAMBIGUATION
- If any ambiguity exists (filenames, column names, keys, layers, coordinate slots, species, batch labels, plotting fields, normalization choices), explicitly list the uncertain items in <scratchpad>, then resolve them by:
  - Probing via minimal code (e.g., print(adata.obs.columns), list(adata.obsm.keys())).
  - Or calling documentation_index_tool to confirm API usage.
- Do not ask the user to clarify if you can resolve by inspection or safe defaults.

BEST-PRACTICE EXECUTION (from stepwise reasoning)
- Verify assumptions early:
  - File paths exist.
  - AnnData shapes align; required keys present in .obs/.var/.obsm/.uns.
  - Coordinate embeddings present before plotting; compute if absent when appropriate.
- Prefer minimal, explicit function calls with named parameters.
- Log essential shapes/keys via print(...) for transparency.

VALIDATION & GUARDRAILS
- Before finishing a computation turn, include quick sanity checks (e.g., counts, unique value checks, NaN checks, embedding presence).
- For plots: verify figure saved to an explicit path; use dpi and bbox_inches="tight".
- For randomness-sensitive steps, set a fixed seed when available.
- If something fails or data are missing, degrade gracefully: explain the issue in <response> or proceed with partial results and clearly note limitations.

ERROR HANDLING
- Catch problems early via probes rather than broad try/except.
- If an operation is unsupported or signature mismatched, re-check with documentation_index_tool and adjust.

STYLE & SAFETY
- Be concise and specific. Prefer concrete file paths, function names, and parameters.
- If uncertain about a path/key/column name, probe via minimal code in <execute> to verify.
- Never include Thoughts/Actions outside <scratchpad>. Never put explanations inside code.

FORMAT GUARD
- Compute path: output exactly one <scratchpad> block followed by exactly one <execute> block, nothing else.
- Shortcut path: output exactly one <response> block, nothing else.

FEW-SHOT EXAMPLES

User: What is scanpy.pl.embedding used for?
Assistant:
<response>scanpy.pl.embedding renders 2D embeddings such as UMAP or TSNE from AnnData, with options to color by .obs and control legends and layout. Use it when coordinates already exist and you want a plotting-only call without additional preprocessing.</response>

User: Load X.h5ad, detect the cell-type column, and save a UMAP colored by cell type.
Assistant:
<scratchpad>Plan: (1) Read AnnData. (2) Inspect .obs to infer cell-type column via common name patterns. (3) Verify embedding availability in .obsm; compute UMAP if missing. (4) Plot and save. (5) Print paths and checks. Confirm plotting API via docs.</scratchpad>
<execute>import anndata as ad
adata = ad.read_h5ad("X.h5ad")
print(list(adata.obs.columns)[:20])
print(list(adata.obsm.keys()))
res = documentation_index_tool("scanpy.pl.umap color parameter and savefig")
print(res[:3])</execute>

User: Use squidpy.gr.spatial_neighbors and plot with squidpy.pl.spatial_scatter; I’m unsure about arguments.
Assistant:
<scratchpad>Plan: (1) Verify signatures for squidpy.gr.spatial_neighbors and squidpy.pl.spatial_scatter. (2) Inspect adata.obsm for spatial coordinates. (3) Compute spatial neighbors. (4) Plot spatial scatter with color from .obs. (5) Save and print checks.</scratchpad>
<execute>res1 = documentation_index_tool("squidpy.gr.spatial_neighbors signature")
print(res1[:3])
res2 = documentation_index_tool("squidpy.pl.spatial_scatter color argument")
print(res2[:3])</execute>
""".strip()

CodingAgentDescription = """
Expert coder equipped with spatial transcriptomics analysis tools.
""".strip()

def python_repl_eval(
    code: str,
    _locals: Dict[str, Any]
) -> Tuple[str, Dict[str, Any], Dict[str, Any], Set[str]]:
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
    current_keys = set(_locals.keys())
    new_vars = {k: _locals[k] for k in current_keys - original_keys}
    deleted_keys = original_keys - current_keys
    modified_vars = {}
    for k in original_keys & current_keys:
        old = originals[k]; new = _locals[k]
        try:
            if hasattr(new, '__array__') and hasattr(old, '__array__'):
                try:
                    import numpy as np
                    changed = not np.array_equal(new, old)
                except Exception:
                    changed = id(new) != id(old)
            else:
                changed = new != old
        except Exception:
            changed = id(new) != id(old)
        if changed:
            modified_vars[k] = new
    return result, new_vars, modified_vars, deleted_keys


class CodeActState(MessagesState):
    status_block: str # content of <execute> or <response> block
    context: Dict[str, Any]
    
def create_coding_agent(state_queue: Queue):
    graph = StateGraph(CodeActState)
    id = "coding_agent"

    ### Hyperparameters

    model_ctor = partial(ChatOpenAI, model="gpt-5", reasoning_effort="low")

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

    tools = [documentation_index_tool]

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
        resp_block = extract_block("response", response_text)
        response = [response]
        if code_block:
            logging.info("code block detected")
            next_node = exec_node_id
        elif resp_block:
            logging.info("response block detected")
            next_node = END
        else:
            logging.info("no block detected")
            next_node = agent_node_id
            response.append(HumanMessage("<no code or response block found, try again>"))
        logging.info(f"transferring from agent_node to {next_node}")
        return Command(goto=next_node, update = {"messages": response})

    def exec_node(state: CodeActState):
        messages = state["messages"]
        last_message = messages[-1]
        code_block = extract_block("execute", str(last_message.content))

        existing_context = state.get("context", {})
        context = {**existing_context, **tools_context}

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
        final_state = agent.invoke({"messages": [HumanMessage(prompt)]})
        state_queue.put((id, final_state))
        return final_state["messages"][-1].content

    return StructuredTool.from_function(
        func = agent_invocation_tool,
        name = f"coding_agent_transfer_tool",
        description = "Transfer control to {id}"
    )