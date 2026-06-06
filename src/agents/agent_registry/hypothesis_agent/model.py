"""CodeAct-style hypothesis agent with a persistent Python REPL for hypothesis synthesis."""

import logging
from queue import Queue
from typing import Callable, List, Optional

from langchain.tools import StructuredTool
from langgraph.types import Command
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, MessagesState, START, StateGraph

from agents.agent_utils import extract_block
from agents.agent_registry.hypothesis_agent.tools import HypothesisTools
from agents.repl_history import compress_repl_history
from langchain_experimental.utilities import PythonREPL
from agents.agent_registry.hypothesis_agent.prompt import (
    HypothesisAgentPrompt,
    HypothesisAgentDescription,
)
from graph.graph_utils import log_message, subagent_invocation

from config import DATA_DIR, PDF_UPLOADS_DIR


class HypothesisState(MessagesState):
    """Extended message state carrying the current code/response block.

    The persistent ``PythonREPL`` used by ``exec_node`` is **not** part
    of this state — it lives in a closure-local holder in
    :func:`create_hypothesis_agent` so it never reaches the checkpointer
    (msgpack cannot serialise a ``PythonREPL``). The closure deliberately
    keeps the REPL alive across invocations so prior hypothesis variables
    remain accessible to later "test hypothesis" calls.
    """

    status_block: str  # content of <execute> or <response> block
    skill_prompt: str  # injected skill content for system prompt


def create_hypothesis_agent(
    state_queue: Queue,
    context_resolver=None,
):
    """Build and return the hypothesis agent as a StructuredTool.

    Args:
        state_queue: Queue to which finished agent states are posted for UI consumption.

    Returns:
        A StructuredTool that invokes the hypothesis agent graph with a text prompt.
    """
    graph = StateGraph(HypothesisState)
    id = "hypothesis_agent"

    ### Tools

    tools = HypothesisTools

    ### Model

    from agents.agent_registry.hypothesis_agent.params import model_ctor

    model = model_ctor()

    agent_node_id = "agent_node"
    exec_node_id = "exec_node"

    def agent_node(state: HypothesisState):
        """Invoke the LLM and route to exec or END based on block type."""
        messages = state["messages"]
        skill_text = state.get("skill_prompt", "")
        full_prompt = HypothesisAgentPrompt.replace("{{skill_prompt}}", skill_text)
        system_prompt = SystemMessage(full_prompt)

        # Strategy 2H: collapse older REPL iterations before re-sending.
        compressed = compress_repl_history(messages)

        logging.info(f"invoking {id} agent_node")
        response = model.invoke([system_prompt] + compressed)
        logging.info(f"finished invoking {id} agent_node")

        response.name = id
        log_message(response)

        response_text = str(response.content)
        code_block = extract_block("execute", response_text)
        response_block = extract_block("response", response_text)

        response_msg = [response]
        if code_block:
            logging.info("code block detected - transferring to exec_node")
            next_node = exec_node_id
        elif response_block:
            logging.info("response block detected - final output, exiting")
            next_node = END
        else:
            logging.info("no execute or response block - treating as direct response and exiting")
            next_node = END

        logging.info(f"transferring from agent_node to {next_node}")
        return Command(goto=next_node, update={"messages": response_msg})

    # Closure-local holder. Persists across multiple ``agent_invocation_tool``
    # calls so the hypothesis agent's Python namespace survives manager
    # round-trips (matches the prior ``_persistent_repl_state`` behavior).
    repl_holder: dict = {"repl": None}

    def exec_node(state: HypothesisState):
        """Extract and run the <execute> code block in a persistent Python REPL."""
        messages = state["messages"]
        last_message = messages[-1]
        code_block = extract_block("execute", str(last_message.content))

        logging.info(f"executing {id} exec_node")

        assert code_block is not None

        # Validate code doesn't call forbidden functions
        forbidden_calls = ["jupyternb_generator_tool", "generate_jupyternb"]
        for forbidden in forbidden_calls:
            if forbidden in code_block:
                error_msg = (
                    f"Error: {forbidden}() is not available in Hypothesis Agent.\n"
                    f"Only Reporter Agent can generate notebooks.\n"
                    f"Your role is to synthesize hypotheses, not generate notebooks."
                )
                logging.warning(f"Blocked forbidden function call: {forbidden}")
                return {
                    "messages": [HumanMessage(f"Python Error:\n{error_msg}")],
                }

        repl = repl_holder["repl"]
        if repl is None:
            repl = PythonREPL()
            # Share globals/locals so helper functions can see prior imports.
            repl.locals = repl.globals

            # Pre-import commonly needed packages
            import subprocess
            from pathlib import Path
            import anndata as ad
            from anndata import AnnData
            import json
            import re

            tools_context = {tool.name: tool.func for tool in tools}
            initial_context = {
                **tools_context,
                "DATA_DIR": DATA_DIR,
                "PDF_UPLOADS_DIR": PDF_UPLOADS_DIR,
                "subprocess": subprocess,
                "Path": Path,
                "ad": ad,
                "AnnData": AnnData,
                "json": json,
                "re": re,
            }

            for key, value in initial_context.items():
                repl.globals[key] = value

            repl_holder["repl"] = repl

        output = repl.run(code_block)

        logging.info(f"finished {id} exec_node")

        log_message(HumanMessage(f"Python Output:\n{output}"))
        return {"messages": [HumanMessage(f"Python Output:\n{output}")]}

    graph.add_node(agent_node_id, agent_node)
    graph.add_node(exec_node_id, exec_node)
    graph.add_edge(START, agent_node_id)
    graph.add_edge(exec_node_id, agent_node_id)

    agent = graph.compile()

    def agent_invocation_tool(prompt: str) -> str:
        """Run the hypothesis agent graph on a prompt and return the final message."""
        logging.info(f"Invoking agent `{id}`")

        skill_prompt_text = ""
        step_ctx = None
        if context_resolver:
            from graph.graph_utils import StepContext
            step_ctx = context_resolver("hypothesis_agent")
            if step_ctx and step_ctx.skills:
                from agents.agent_utils import format_skill_prompt

                skill_prompt_text = format_skill_prompt(step_ctx.skills)

        # REPL persistence across invocations is handled by ``repl_holder``
        # in the closure above — no state-threading needed.
        with subagent_invocation("Hypothesis Agent") as invocation_id:
            final_state = agent.invoke(
                {"messages": [HumanMessage(prompt)], "skill_prompt": skill_prompt_text}
            )

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

    return StructuredTool.from_function(
        func=agent_invocation_tool,
        name=f"{id}_transfer_tool",
        description=f"Transfer control to Hypothesis Agent: {HypothesisAgentDescription}",
    )
