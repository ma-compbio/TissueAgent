import logging
from queue import Queue
from typing import Optional

from langchain.tools import StructuredTool
from langgraph.types import Command
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, MessagesState, START, StateGraph

from agents.agent_utils import extract_block
from agents.agent_registry.hypothesis_agent.tools import HypothesisTools
from langchain_experimental.utilities import PythonREPL
from agents.agent_registry.hypothesis_agent.prompt import HypothesisAgentPrompt, HypothesisAgentDescription
from graph.graph_utils import log_message

from config import DATA_DIR, PDF_UPLOADS_DIR


class HypothesisState(MessagesState):
    status_block: str  # content of <execute> or <response> block
    repl: Optional[PythonREPL]


def create_hypothesis_agent(state_queue: Queue):
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
        messages = state["messages"]
        system_prompt = SystemMessage(HypothesisAgentPrompt)

        logging.info(f"invoking {id} agent_node")
        response = model.invoke([system_prompt] + messages)
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

    def exec_node(state: HypothesisState):
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
                return {"messages": [HumanMessage(f"Python Error:\n{error_msg}")], "repl": state.get("repl")}

        repl = state.get("repl")
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

        output = repl.run(code_block)

        logging.info(f"finished {id} exec_node")

        log_message(HumanMessage(f"Python Output:\n{output}"))
        return {"messages": [HumanMessage(f"Python Output:\n{output}")], "repl": repl}

    graph.add_node(agent_node_id, agent_node)
    graph.add_node(exec_node_id, exec_node)
    graph.add_edge(START, agent_node_id)
    graph.add_edge(exec_node_id, agent_node_id)

    agent = graph.compile()

    # Persistent REPL state shared across Manager invocations
    _persistent_repl_state = {}

    def agent_invocation_tool(prompt: str) -> str:
        logging.info(f"Invoking agent `{id}`")
        # Preserve REPL from previous invocation
        initial_state = {"messages": [HumanMessage(prompt)]}
        if "repl" in _persistent_repl_state:
            initial_state["repl"] = _persistent_repl_state["repl"]

        final_state = agent.invoke(initial_state)

        # Store REPL for next invocation
        if "repl" in final_state:
            _persistent_repl_state["repl"] = final_state["repl"]

        state_queue.put((id, final_state))
        return final_state["messages"][-1].content

    return StructuredTool.from_function(
        func=agent_invocation_tool,
        name=f"{id}_transfer_tool",
        description=f"Transfer control to Hypothesis Agent: {HypothesisAgentDescription}",
    )
