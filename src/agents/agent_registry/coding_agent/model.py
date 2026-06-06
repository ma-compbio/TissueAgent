"""Coding agent with isolated Python/R execution via Docker sandbox."""

from __future__ import annotations

import logging
from queue import Queue


from langchain.tools import StructuredTool
from langchain_core.messages import HumanMessage
from langgraph.graph import END, START, StateGraph

from agents.agent_registry.coding_agent.sandbox import ExecutionResult, KernelClient
from agents.agent_registry.coding_agent.tools_impl.documentation_index import (
    DocumentationIndex,
)
from agents.agent_registry.coding_agent.params import (
    coding_agent_model_ctor,
    doc_filepaths,
)
import agent_settings
from agents.agent_registry.coding_agent.prompt import CodingAgentPrompt
from config import DATA_DIR, ROOT
from graph.graph_utils import (
    AgentState,
    create_agent_node,
    create_tool_node,
    get_latest_user_image_parts,
    log_message,
    subagent_invocation,
)


def create_coding_agent(
    state_queue: Queue,
    kernel_client: KernelClient,
    context_resolver=None,
):
    """Build and return the coding agent as a StructuredTool.

    Args:
        state_queue: Queue to which finished agent states are posted for UI consumption.
        kernel_client: Client for executing code on the Docker sandbox kernels.
        context_resolver: Optional callable that resolves skill/artifact context for a step.

    Returns:
        A StructuredTool that invokes the coding agent graph with a text prompt.
    """
    graph = StateGraph(AgentState)
    id = "coding_agent"

    ### Documentation tool

    documentation_index = DocumentationIndex(doc_filepaths)

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

    tools = [
        python_tool,
        r_tool,
        search_documentation_tool,
    ]

    ### Build the graph

    model = coding_agent_model_ctor().bind_tools(tools)

    agent_node_id = "coding_agent_node"
    tool_node_id = "tool_node"

    def _prompt(state) -> str:
        base = CodingAgentPrompt(
            sandbox_enabled=agent_settings.get_sandbox_enabled(),
        )
        skill_text = state.get("skill_prompt", "")
        return base.replace("{{skill_prompt}}", skill_text)

    agent_node = create_agent_node(
        agent_node_id, model, _prompt,
        tool_node_id, END,
    )
    tool_node = create_tool_node(tools)

    graph.add_node(agent_node_id, agent_node)
    graph.add_node(tool_node_id, tool_node)

    graph.add_edge(START, agent_node_id)
    graph.add_edge(tool_node_id, agent_node_id)

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

        skill_prompt_text = ""
        step_ctx = None
        if context_resolver:
            step_ctx = context_resolver("coding_agent")
            if step_ctx and step_ctx.skills:
                from agents.agent_utils import format_skill_prompt

                skill_prompt_text = format_skill_prompt(step_ctx.skills)

        with subagent_invocation("Coding Agent") as invocation_id:
            final_state = agent.invoke(
                {"messages": [message], "skill_prompt": skill_prompt_text}
            )
        kernel_client.shutdown_kernels()
        state_queue.put((id, final_state, invocation_id))
        result = final_state["messages"][-1].content

        if step_ctx and step_ctx.expected_artifacts:
            from graph.graph_utils import (
                _validate_step_artifacts,
                _update_step_status,
                _format_validation_summary,
            )

            found, missing = _validate_step_artifacts(step_ctx.expected_artifacts)
            _update_step_status(step_ctx.step_id, found, missing)
            summary = _format_validation_summary(step_ctx.step_id, found, missing)
            logging.info(summary)
            result += summary

        return result

    tool = StructuredTool.from_function(
        func=agent_invocation_tool,
        name="coding_agent_transfer_tool",
        description=f"Transfer control to {id}",
    )
    tool._agent = agent  # type: ignore[attr-defined]
    return tool

PRESETS: dict[int, dict] = {
    1: {
        "setup": f"cp datasets/dataset_lohoff_et_al_seqfish.h5ad {DATA_DIR}/datasets",
        "prompt": (
            "I have uploaded a spatial transcriptomics dataset in datasets/dataset_lohoff_et_al_seqfish.h5ad."
            "Help me plot a spatial scatterplot colored by cell type, saved to figures/spatial_scatter.png."
        ),
    },
}

if __name__ == "__main__":
    import argparse
    import subprocess
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

    parser = argparse.ArgumentParser(description="Run the coding agent directly.")
    parser.add_argument("--preset", type=int, default=0, help="Preset number (0 = interactive prompt)")
    parser.add_argument(
        "--disable-docker",
        action="store_true",
        help="Skip Docker sandbox startup; connect to a local Jupyter Kernel Gateway instead",
    )
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

    if args.disable_docker:
        agent_settings.set_sandbox_enabled(False)
        logging.info("Docker sandbox disabled — expecting a local Jupyter Kernel Gateway.")
        container_mgr = None
    else:
        container_mgr = ContainerManager()
        container_mgr.ensure_running()

    client = KernelClient()
    queue = Queue()
    tool = create_coding_agent(queue, client)

    try:
        result = tool.invoke({"prompt": prompt})
        print(result)
    finally:
        if container_mgr is not None:
            container_mgr.stop()
