"""Coding agent with isolated Python/R execution via Docker sandbox."""

from __future__ import annotations

import logging
from queue import Queue


from langchain_core.tools import StructuredTool
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
from agents.agent_tools import file_read_write_tools
from graph.node_factories import AgentState, create_agent_node, create_tool_node
from graph.ui_events import emit_message, stash_completed_subagent, subagent_invocation


def new_exec_state() -> dict[str, int]:
    """Fresh per-step failure counters for the code-execution tools."""
    return {"consecutive_errors": 0, "step_errors": 0}


def apply_failure_budgets(exec_state: dict, *, had_error: bool) -> str | None:
    """Update the failure counters and return a stop-directive once one trips.

    Two budgets, because one is not enough:

    * ``consecutive_errors`` (``MAX_EXECUTOR_RETRIES``) fast-fails a hard stuck
      loop, and is zeroed by any success.
    * ``step_errors`` (``MAX_EXECUTOR_STEP_ERRORS``) counts every failure in the
      step and is **never** refunded by a success. Without it, a debug-thrash
      loop — execute, fail, glob, read, execute, fail — never accumulates enough
      *consecutive* failures to trip the first budget, and the step runs until
      LangGraph's ``recursion_limit`` aborts it, discarding the sub-agent's
      context and its partial work.

    Returns ``None`` while within budget.
    """
    from config import MAX_EXECUTOR_RETRIES, MAX_EXECUTOR_STEP_ERRORS

    if not had_error:
        exec_state["consecutive_errors"] = 0
        return None

    exec_state["consecutive_errors"] += 1
    exec_state["step_errors"] += 1

    if exec_state["consecutive_errors"] >= MAX_EXECUTOR_RETRIES:
        reason = (
            f"{exec_state['consecutive_errors']} consecutive code executions "
            f"have failed (limit MAX_EXECUTOR_RETRIES={MAX_EXECUTOR_RETRIES})"
        )
    # Checked second so a hard stuck loop reports the more specific reason.
    elif exec_state["step_errors"] >= MAX_EXECUTOR_STEP_ERRORS:
        reason = (
            f"{exec_state['step_errors']} code executions have failed during "
            f"this step (limit MAX_EXECUTOR_STEP_ERRORS="
            f"{MAX_EXECUTOR_STEP_ERRORS}); successes in between do not refund "
            "this budget"
        )
    else:
        return None

    return (
        f"[EXECUTOR RETRY LIMIT] {reason}. Do NOT run more code for this step. "
        "Stop, summarize what you attempted and the errors you hit, and hand "
        "control back so the manager can retry the step with new instructions "
        "or replan."
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

    # Per-step failure counters, bumped by the python/r tools via
    # ``apply_failure_budgets`` and reset at the start of each step invocation
    # (see ``_agent_invocation_tool``). Once either budget trips, the tools
    # refuse to run more code and instruct the agent to stop and summarize.
    _exec_state = new_exec_state()

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
        - library: Optional filter ('scanpy', 'squidpy', 'liana', or 'commot').
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
            " Optional `library` filter: 'scanpy', 'squidpy', 'liana', or 'commot'."
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

    def _emit_output(prefix: str, result: ExecutionResult) -> None:
        """Emit a code-output message to the UI trace.

        Carries any inline plots as project-relative file *paths* (in
        ``additional_kwargs``), not base64 — the pixels are spilled to disk
        and the frontend loads them from ``/api/files/download``. Keeping the
        content text-only preserves ``should_hide_message`` (these stay hidden
        from the main chat) and keeps the persisted ``.chat.json`` small.
        """
        msg = HumanMessage(prefix + result.text)
        if result.images:
            from agents.agent_registry.coding_agent.image_spill import (
                spill_images_to_disk,
            )

            paths = spill_images_to_disk(result.images)
            if paths:
                msg.additional_kwargs["trace_image_paths"] = paths
        emit_message(msg)

    def _update_retry_counter(result: ExecutionResult, language: str = "python") -> str | None:
        """Track consecutive failures; return a stop-directive when over budget.

        Returns ``None`` while within budget. A successful execution resets the
        counter to zero — which is why the run-level history is mirrored into
        ``executor_tracker`` here, before it is thrown away. Recording is
        strictly observational and never allowed to affect the run.
        """
        try:
            from graph.ui_events import _get_subagent_context
            from server.executor_tracker import executor_tracker

            _, _, step_id = _get_subagent_context()
            executor_tracker.record_execution(language, bool(result.error), step_id)
        except Exception as e:  # metrics must never break code execution
            logging.debug("executor_tracker: could not record execution: %s", e)

        return apply_failure_budgets(_exec_state, had_error=bool(result.error))

    def python(code: str) -> str | list:
        logging.info(f"python tool executing:\n{code}")
        result = kernel_client.execute(code, language="python")
        logging.info(f"python tool output:\n{result.text}")
        _emit_output("Python Output:\n", result)
        over_budget = _update_retry_counter(result)
        if over_budget is not None:
            return f"{result.text}\n\n{over_budget}"
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
        _emit_output("R Output:\n", result)
        over_budget = _update_retry_counter(result, language="r")
        if over_budget is not None:
            return f"{result.text}\n\n{over_budget}"
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

    # search_documentation is gated by config.DOC_SEARCH_ENABLED so the tool and
    # its prompt guidance (coding_agent/prompt.py) turn on/off together. It is
    # temporarily disabled for the CCC benchmark; the API context now lives in
    # the CCC skill files. Flip the flag to True to restore both.
    from config import DOC_SEARCH_ENABLED

    tools = [
        python_tool,
        r_tool,
        *([search_documentation_tool] if DOC_SEARCH_ENABLED else []),
        *file_read_write_tools,
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
        # Fresh retry budgets for each step invocation (the tool closures persist
        # across invocations, so the counters must be reset here). This is the
        # only place ``step_errors`` is cleared — that is what makes it a
        # per-step ceiling rather than a per-streak one.
        _exec_state.update(new_exec_state())
        try:
            from server.executor_tracker import executor_tracker

            executor_tracker.begin_step()
        except Exception as e:  # metrics must never break a dispatch
            logging.debug("executor_tracker: could not mark step boundary: %s", e)
        message = HumanMessage(prompt)

        skill_prompt_text = ""
        step_ctx = None
        if context_resolver:
            step_ctx = context_resolver("coding_agent")
            if step_ctx and step_ctx.skills:
                from agents.agent_utils import format_skill_prompt

                skill_prompt_text = format_skill_prompt(step_ctx.skills)
        # Per-invocation observability: the system prompt is only previewed at
        # build time (with an empty skill_prompt), so without this line there is
        # no way to tell from the logs whether a step's assigned skills actually
        # reached the executor. Warn loudly if a running step has skills but the
        # injection came back empty (a silent skill-delivery regression).
        if step_ctx and step_ctx.skills and not skill_prompt_text:
            logging.warning(
                "coding_agent: step %s assigned skills %s but skill_prompt is EMPTY "
                "(skill body not injected)", step_ctx.step_id, step_ctx.skills)
        else:
            logging.info(
                "coding_agent: injecting skills %s (%d chars) for step %s",
                (step_ctx.skills if step_ctx else []),
                len(skill_prompt_text),
                (step_ctx.step_id if step_ctx else None))

        with subagent_invocation(
            "Coding Agent",
            step_id=step_ctx.step_id if step_ctx else None,
        ) as invocation_id:
            from config import EXECUTOR_RECURSION_LIMIT

            final_state = agent.invoke(
                {"messages": [message], "skill_prompt": skill_prompt_text},
                config={"recursion_limit": EXECUTOR_RECURSION_LIMIT},
            )
        state_queue.put((id, final_state, invocation_id))
        # Hand off to the wrapping tool_node so it pairs this final state with
        # the dispatching ToolMessage.id and emits a subagent_state event
        # inline — otherwise the live-trace card lingers until run_complete
        # instead of flipping to the finished card when the agent is done.
        stash_completed_subagent(id, final_state, invocation_id)
        return final_state["messages"][-1].content

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
