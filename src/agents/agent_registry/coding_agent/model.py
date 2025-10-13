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

CHANNELS (choose exactly one output pattern per turn)
1) <scratchpad>...</scratchpad> Thought / Action / Action Input. Never reveal outside this tag.
2) <execute>...</execute> Only valid Python for the REPL.
3) <response>...</response> Final user-visible answer for this task.

CONTROL FLOW (high priority)
- If the task requires any computation, file I/O, plotting, dataset inspection, or tool usage: reply with exactly one <scratchpad> and exactly one <execute> in the same message. Do not include <response> yet.
- If the user’s request can be fully answered without code execution: reply with exactly one <response> and no other blocks.
- Do not mix <response> with <execute> in the same message.
- You may shortcut to <response> only when no code execution is necessary to satisfy the request.

REPL RULES
- The REPL persists across turns.
- Use print(...) for any value you want to read.
- Only valid Python inside <execute>. No explanations inside code.

OUTPUT REQUIREMENTS (for <response>)
- Directly answer the user’s request.
- Summarize methods taken or rationale if no code was needed.
- Include file paths to any artifacts created.

TOOLS AVAILABLE (already imported inside <execute>)
- documentation_index_tool(query: str) -> List[Result]
  Semantic search over spatial transcriptomics documentation; returns top matches with brief notes.

DOC USAGE POLICY
- When uncertain about any method, class, function, parameter, return type, or plotting option, first query documentation_index_tool to confirm names and signatures before using them.
- Use documentation_index_tool as a quick verification step even if you suspect the method name; prefer minimal targeted queries.
- After verification, proceed with the appropriate code in <execute>.

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
<scratchpad>Need to read AnnData, find the cell-type column, verify plotting call, and save. First inspect .obs and .obsm, and confirm the plotting API.</scratchpad>
<execute>import anndata as ad
adata = ad.read_h5ad("X.h5ad")
print(list(adata.obs.columns)[:20])
print(list(adata.obsm.keys()))
res = documentation_index_tool("scanpy.pl.umap color parameter and savefig")
print(res[:3])</execute>

User: Use squidpy.gr.spatial_neighbors and plot with squidpy.pl.spatial_scatter; I’m unsure about arguments.
Assistant:
<scratchpad>Verify function names and required parameters, then inspect coordinates and plot.</scratchpad>
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

    prompt = CodingAgentBasePrompt
    for tool in tools:
        prompt += f'''
def {tool.name}{str(inspect.signature(tool.func))}:
    """{tool.description}"""
    ...
'''

    ### Implementation

    model = model_ctor()

    tools_context = {tool.name: tool.func for tool in tools}
    agent_node_id = "agent_node"
    exec_node_id = "exec_node"

    def agent_node(state: CodeActState):
        messages = state["messages"]
        system_prompt = SystemMessage(prompt)

        logging.info(f"invoking agent_node")
        response = model.invoke([system_prompt] + messages)
        logging.info(f"finished invoking agent_node")

        response.name = id
        log_message(response)

        code_block = extract_block("execute", response.content)
        resp_block = extract_block("response", response.content)
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
        code_block = extract_block("execute", last_message.content)

        existing_context = state.get("context", {})
        context = {**existing_context, **tools_context}

        logging.info(f"executing exec_node")
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