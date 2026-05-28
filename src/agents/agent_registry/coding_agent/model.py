"""Coding agent with isolated Python/R execution via Docker sandbox."""

import logging
from queue import Queue

from langchain.tools import StructuredTool
from langchain_core.messages import HumanMessage, RemoveMessage
from langgraph.graph import END, MessagesState, START, StateGraph

from agents.agent_registry.coding_agent.sandbox import ExecutionResult, KernelClient
from config import ROOT
from agents.agent_registry.coding_agent.tools_impl.documentation_index import (
    DocumentationIndex,
)
from agents.agent_registry.coding_agent.tools_impl.tutorial_index import TutorialIndex
from agents.agent_registry.coding_agent.params import (
    retrieval_agent_model_ctor,
    execution_agent_model_ctor,
    doc_filepaths,
    tutorial_directories,
)
from agents.agent_registry.coding_agent.prompt import RetrievalAgentPrompt, ExecutionAgentPrompt
from graph.graph_utils import (
    create_agent_node,
    create_tool_node,
    get_latest_user_image_parts,
    log_message,
    subagent_invocation,
)


class CodingAgentState(MessagesState):
    """Extended state that carries the retrieval plan between subagents."""
    retrieval_plan: str


def create_coding_agent(state_queue: Queue, kernel_client: KernelClient):
    """Build and return the coding agent as a StructuredTool.

    Args:
        state_queue: Queue to which finished agent states are posted for UI consumption.
        kernel_client: Client for executing code on the Docker sandbox kernels.

    Returns:
        A StructuredTool that invokes the coding agent graph with a text prompt.
    """
    graph = StateGraph(CodingAgentState)
    id = "coding_agent"

    ### Documentation / tutorial tools

    documentation_index = DocumentationIndex(doc_filepaths)
    tutorial_index = TutorialIndex(tutorial_directories)

    def search_documentation(
        name: str | None = None,
        keyword: str | None = None,
        library: str | None = None,
    ) -> str:
        """Search API documentation for spatial transcriptomics libraries.

        Provide exactly one of `name` or `keyword`:
        - name: Look up a specific method by name (supports fuzzy matching).
        - keyword: Find methods related to a topic.
        - library: Optional filter ('scanpy', 'squidpy', or 'liana').
        """
        if name and keyword:
            return "Error: provide either 'name' or 'keyword', not both."
        if name:
            results = documentation_index.lookup_by_name(name, library=library)
            return documentation_index.format_results(results, verbose=True)
        if keyword:
            results = documentation_index.search_by_keyword(keyword, library=library)
            return documentation_index.format_results(results, verbose=False)
        return "Error: provide either 'name' or 'keyword'."

    def search_tutorials(
        name: str | None = None,
        keyword: str | None = None,
        library: str | None = None,
    ) -> str:
        """Search tutorials for spatial transcriptomics workflows.

        Provide exactly one of `name` or `keyword`:
        - name: Retrieve a specific tutorial by title (supports fuzzy matching).
        - keyword: Find tutorials related to a topic.
        - library: Optional filter ('liana' or 'squidpy').
        """
        if name and keyword:
            return "Error: provide either 'name' or 'keyword', not both."
        if name:
            results = tutorial_index.lookup_by_name(name, library=library)
            return tutorial_index.format_results(results, verbose=True)
        if keyword:
            results = tutorial_index.search_by_keyword(keyword, library=library)
            return tutorial_index.format_results(results, verbose=False)
        return "Error: provide either 'name' or 'keyword'."

    search_documentation_tool = StructuredTool.from_function(
        func=search_documentation,
        name="search_documentation",
        description=(
            "Search API documentation for spatial transcriptomics libraries."
            " Use `name` for a specific method (fuzzy matching supported),"
            " or `keyword` to find methods by topic."
            " Optional `library` filter: 'scanpy', 'squidpy', or 'liana'."
        ),
    )

    search_tutorials_tool = StructuredTool.from_function(
        func=search_tutorials,
        name="search_tutorials",
        description=(
            "Search tutorials for spatial transcriptomics workflows."
            " Use `name` for a specific tutorial by title (fuzzy matching),"
            " or `keyword` to find tutorials by topic."
            " Optional `library` filter: 'liana' or 'squidpy'."
        ),
    )

    ### Code execution tools (Docker sandbox)

    def _format_execution_result(result: ExecutionResult) -> str | list:
        """Convert an ExecutionResult into a plain string or multimodal content list."""
        if not result.images:
            return result.text
        parts: list[dict] = [{"type": "text", "text": result.text}]
        for data_uri in result.images:
            parts.append({"type": "image_url", "image_url": {"url": data_uri}})
        return parts

    def python(code: str) -> str | list:
        logging.info(f"python tool executing:\n{code}")
        result = kernel_client.execute(code, language="python")
        logging.info(f"python tool output:\n{result.text}")
        log_message(HumanMessage("Python Output:\n" + result.text))
        return _format_execution_result(result)

    python_tool = StructuredTool.from_function(
        func=python,
        name="python",
        description=(
            "Execute Python code in a persistent Jupyter kernel and return its output."
            " The kernel retains state (variables, imports, definitions) across calls."
            " Use print() to surface values you need to inspect."
        ),
    )

    def r(code: str) -> str | list:
        logging.info(f"r tool executing:\n{code}")
        result = kernel_client.execute(code, language="r")
        logging.info(f"r tool output:\n{result.text}")
        log_message(HumanMessage("R Output:\n" + result.text))
        return _format_execution_result(result)

    r_tool = StructuredTool.from_function(
        func=r,
        name="r",
        description=(
            "Execute R code in a persistent Jupyter kernel and return its output."
            " The kernel retains state (variables, libraries, definitions) across calls."
            " Use cat() or print() to surface values you need to inspect."
        ),
    )

    retrieval_tools = [
        search_documentation_tool,
        search_tutorials_tool,
    ]

    execution_tools = [
        python_tool,
        r_tool,
    ]

    ### Build the graph with retrieval and execution subagents

    retrieval_model = retrieval_agent_model_ctor().bind_tools(retrieval_tools)
    execution_model = execution_agent_model_ctor().bind_tools(execution_tools)

    retrieval_agent_node_id = "retrieval_agent_node"
    retrieval_tool_node_id = "retrieval_tool_node"
    handoff_node_id = "handoff_node"
    execution_agent_node_id = "execution_agent_node"
    execution_tool_node_id = "execution_tool_node"

    # Retrieval agent: searches docs/tutorials, produces a plan, then hands off
    retrieval_agent_node = create_agent_node(
        retrieval_agent_node_id, retrieval_model, RetrievalAgentPrompt,
        retrieval_tool_node_id, handoff_node_id,
    )
    retrieval_tool_node = create_tool_node(retrieval_tools)

    def handoff_node(state: CodingAgentState) -> CodingAgentState:
        """Extract the retrieval plan and reset messages for the execution agent.

        Stores the retrieval agent's final message as the plan, then removes
        all messages except the original user message so the execution agent
        starts with a clean context.
        """
        retrieval_plan = state["messages"][-1].content
        user_message = next(
            m for m in state["messages"] if isinstance(m, HumanMessage)
        )
        # Remove all messages except the original user message
        removals = [
            RemoveMessage(id=m.id)
            for m in state["messages"]
            if m.id != user_message.id
        ]
        return {
            "retrieval_plan": retrieval_plan,
            "messages": removals,
        }

    # Execution agent: receives plan via system prompt, executes code
    def _execution_prompt(state: CodingAgentState) -> str:
        return ExecutionAgentPrompt(state.get("retrieval_plan", ""))

    execution_agent_node = create_agent_node(
        execution_agent_node_id, execution_model, _execution_prompt,
        execution_tool_node_id, END,
    )
    execution_tool_node = create_tool_node(execution_tools)

    graph.add_node(retrieval_agent_node_id, retrieval_agent_node)
    graph.add_node(retrieval_tool_node_id, retrieval_tool_node)
    graph.add_node(handoff_node_id, handoff_node)
    graph.add_node(execution_agent_node_id, execution_agent_node)
    graph.add_node(execution_tool_node_id, execution_tool_node)

    graph.add_edge(START, retrieval_agent_node_id)
    graph.add_edge(retrieval_tool_node_id, retrieval_agent_node_id)
    graph.add_edge(handoff_node_id, execution_agent_node_id)
    graph.add_edge(execution_tool_node_id, execution_agent_node_id)

    agent = graph.compile()

    def agent_invocation_tool(prompt: str) -> str:
        """Run the coding agent graph on a prompt and return the final message."""
        logging.info(f"Invoking agent `{id}`")

        image_parts = get_latest_user_image_parts()
        if image_parts:
            logging.info("Forwarding latest user image attachments to coding agent.")
            content = [{"type": "text", "text": prompt}, *image_parts]
            message = HumanMessage(content=content)
        else:
            message = HumanMessage(prompt)
        with subagent_invocation("Coding Agent") as invocation_id:
            final_state = agent.invoke({"messages": [message]})
        kernel_client.shutdown_kernels()
        state_queue.put((id, final_state, invocation_id))
        return final_state["messages"][-1].content

    return StructuredTool.from_function(
        func=agent_invocation_tool,
        name="coding_agent_transfer_tool",
        description="Transfer control to {id}",
    )

PRESETS: dict[int, dict] = {
    1: {
        "setup": "cp datasets/dataset_lohoff_et_al_seqfish.h5ad data/",
        "prompt": (
            "I have uploaded a spatial transcriptomics dataset in datasets/dataset_lohoff_et_al_seqfish.h5ad."
            "Help me plot a UMAP colored by cell type."
        ),
    },
}

if __name__ == "__main__":
    import argparse
    import shlex
    import subprocess
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

    parser = argparse.ArgumentParser(description="Run the coding agent directly.")
    parser.add_argument("--preset", type=int, default=0, help="Preset number (0 = interactive prompt)")
    parser.add_argument("prompt", nargs="*", help="Prompt text (ignored when --preset is used)")
    args = parser.parse_args()

    from agents.agent_registry.coding_agent.sandbox import ContainerManager
    from server.utils import reset_data_directories
    reset_data_directories()

    if args.preset > 0:
        preset = PRESETS.get(args.preset)
        if preset is None:
            print(f"Unknown preset {args.preset}. Available: {list(PRESETS.keys())}")
            sys.exit(1)
        if "setup" in preset:
            logging.info(f"Running preset setup: {preset['setup']}")
            subprocess.run(preset["setup"], shell=True, check=True, cwd=str(ROOT))
        prompt = preset["prompt"]
    elif args.prompt:
        prompt = " ".join(args.prompt)
    else:
        prompt = input("Prompt: ")

    container_mgr = ContainerManager()
    container_mgr.ensure_running()

    client = KernelClient()
    queue = Queue()
    tool = create_coding_agent(queue, client)

    try:
        result = tool.invoke({"prompt": prompt})
        print(result)
    finally:
        container_mgr.stop()
