"""CodeAct-style coding agent with a persistent Python REPL for spatial transcriptomics tasks."""

import logging
from queue import Queue
from typing import Optional

from langchain.tools import StructuredTool
from langgraph.types import Command
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, MessagesState, START, StateGraph

from agents.agent_utils import extract_block
from langchain_experimental.utilities import PythonREPL
from agents.agent_registry.coding_agent.tools_impl.documentation_index import (
    DocumentationIndex,
)
from agents.agent_registry.coding_agent.tools_impl.tutorial_index import TutorialIndex

# from agents.agent_registry.coding_agent.tools_impl.tutorial_rag import TutorialRAG
from agents.agent_registry.coding_agent.params import (
    model_ctor,
    doc_filepaths,
    tutorial_directories,
)
from agents.agent_registry.coding_agent.prompt import CodingAgentBasePrompt
from graph.graph_utils import get_latest_user_image_parts, log_message, subagent_invocation

from config import DATA_DIR, NOTEBOOK_DIR


class CodeActState(MessagesState):
    """Extended message state carrying the current code/response block and a persistent REPL."""

    status_block: str  # content of <execute> or <response> block
    repl: Optional[PythonREPL]


def create_coding_agent(state_queue: Queue):
    """Build and return the coding agent as a StructuredTool.

    Args:
        state_queue: Queue to which finished agent states are posted for UI consumption.

    Returns:
        A StructuredTool that invokes the coding agent graph with a text prompt.
    """
    graph = StateGraph(CodeActState)
    id = "coding_agent"

    ### Tools

    documentation_index = DocumentationIndex(doc_filepaths)
    documentation_index_tool = StructuredTool.from_function(
        func=documentation_index.search,
        name="documentation_index_tool",
        description=(
            "Semantic search tool for specialized methods for spatial transcriptomics."
            " Use library parameter to search specific libraries like 'scanpy' or 'squidpy'."
        ),
    )

    tutorial_index = TutorialIndex(tutorial_directories)
    # tutorial_index_tool = StructuredTool.from_function(
    #     func = tutorial_index.search,
    #     name = "tutorial_index_tool",
    #     description = ("Search tool for tutorial files that returns entire file content."
    #         " Use library parameter to search specific libraries like 'liana' or 'squidpy'.")
    # )

    tutorial_list_names_tool = StructuredTool.from_function(
        func=tutorial_index.list_tutorial_names,
        name="tutorial_list_names_tool",
        description="List available tutorial titles. Optionally filter by library like 'liana' or 'squidpy'.",
    )

    tutorial_get_by_name_tool = StructuredTool.from_function(
        func=tutorial_index.get_tutorial_by_name,
        name="tutorial_get_by_name_tool",
        description=(
            "Retrieve a tutorial by its exact title."
            " Returns the doc content and library; optionally filter by library."
        ),
    )

    tutorial_list_keywords_tool = StructuredTool.from_function(
        func=tutorial_index.list_keywords,
        name="tutorial_list_keywords_tool",
        description="List unique tutorial keywords. Optionally filter by library like 'liana' or 'squidpy'.",
    )

    tutorial_get_by_keyword_tool = StructuredTool.from_function(
        func=tutorial_index.get_tutorials_by_keyword,
        name="tutorial_get_by_keyword_tool",
        description="Retrieve tutorials by keyword match (case-insensitive substring). Optionally filter by library.",
    )

    tools = [
        documentation_index_tool,
        # tutorial_index_tool,
        tutorial_list_keywords_tool,
        tutorial_get_by_keyword_tool,
        tutorial_list_names_tool,
        tutorial_get_by_name_tool,
    ]

    ### Implementation

    model = model_ctor()

    agent_node_id = "agent_node"
    exec_node_id = "exec_node"

    def agent_node(state: CodeActState):
        """Invoke the LLM and route to exec, self-loop, or END based on block type."""
        messages = state["messages"]
        system_prompt = SystemMessage(CodingAgentBasePrompt)

        logging.info("invoking agent_node")
        response = model.invoke([system_prompt] + messages)
        logging.info("finished invoking agent_node")

        response.name = id
        log_message(response)

        response_text = str(response.content)
        code_block = extract_block("execute", response_text)
        scratchpad_block = extract_block("scratchpad", response_text)
        response = [response]
        if code_block:
            logging.info(f"code block detected\n\n{code_block}")
            next_node = exec_node_id
        elif scratchpad_block:
            logging.info("scratchpad block detected - looping back to agent\n\n" + scratchpad_block)
            next_node = agent_node_id
        else:
            logging.info(
                "no scratchpad or execute block detected - treating as direct response and exiting"
            )
            next_node = END
        logging.info(f"transferring from agent_node to {next_node}")
        return Command(goto=next_node, update={"messages": response})

    def exec_node(state: CodeActState):
        """Extract and run the <execute> code block in a persistent Python REPL."""
        messages = state["messages"]
        last_message = messages[-1]
        code_block = extract_block("execute", str(last_message.content))

        logging.info("executing exec_node")

        assert code_block is not None

        repl = state.get("repl")
        if repl is None:
            repl = PythonREPL()
            # Keep globals/locals shared so imports & defs stay visible inside functions.
            repl.locals = repl.globals
            tools_context = {tool.name: tool.func for tool in tools}

            g = getattr(repl, "globals", None) or {}
            repl.globals = g
            repl.locals = g

            initial_context = {
                **tools_context,
                "DATA_DIR": DATA_DIR,
                "NOTEBOOK_DIR": NOTEBOOK_DIR,
            }

            g.update(initial_context)

        output = repl.run(code_block)

        logging.info("finished exec_node")

        log_message(HumanMessage("Python Output:\n" + output))
        return {"messages": [HumanMessage(output)], "repl": repl}

    graph.add_node(agent_node_id, agent_node)
    graph.add_node(exec_node_id, exec_node)
    graph.add_edge(START, agent_node_id)
    graph.add_edge(exec_node_id, agent_node_id)

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
        state_queue.put((id, final_state, invocation_id))
        return final_state["messages"][-1].content

    return StructuredTool.from_function(
        func=agent_invocation_tool,
        name="coding_agent_transfer_tool",
        description="Transfer control to {id}",
    )


# import logging
# from queue import Queue
# from typing import Any, Dict, Optional

# from langchain.tools import StructuredTool
# from langgraph.types import Command
# from langchain_core.messages import HumanMessage, SystemMessage
# from langgraph.graph import END, MessagesState, START, StateGraph

# from agents.agent_utils import extract_block
# from langchain_experimental.utilities import PythonREPL
# from agents.agent_registry.coding_agent.tools_impl.documentation_index import DocumentationIndex
# from agents.agent_registry.coding_agent.tools_impl.tutorial_index import TutorialIndex
# from agents.agent_registry.coding_agent.tools_impl.tutorial_rag import TutorialRAG
# from agents.agent_registry.coding_agent.params import model_ctor, doc_filepaths, tutorial_directories
# from agents.agent_registry.coding_agent.prompt import CodingAgentBasePrompt, CodingAgentDescription
# from graph.graph_utils import log_message

# from config import DATA_DIR, NOTEBOOK_DIR
# # from agents.reporter_agent.tools_impl.jupyternb_generator_tool import jupyternb_generator_tool


# class CodeActState(MessagesState):
#     status_block: str # content of <execute> or <response> block
#     repl: Optional[PythonREPL]

# def create_coding_agent(state_queue: Queue):
#     graph = StateGraph(CodeActState)
#     id = "coding_agent"

#     ### Tools

#     documentation_index = DocumentationIndex(doc_filepaths)
#     documentation_index_tool = StructuredTool.from_function(
#         func = documentation_index.search,
#         name = "documentation_index_tool",
#         description = ("Semantic search tool for specialized methods for spatial"
#             " transcriptomics. Use library parameter to search specific"
#             " libraries like 'scanpy' or 'squidpy'.")
#     )

#     tutorial_index = TutorialIndex(tutorial_directories)
#     tutorial_index_tool = StructuredTool.from_function(
#         func = tutorial_index.search,
#         name = "tutorial_index_tool",
#         description = ("Search tool for tutorial files that returns entire file"
#             " content. Use library parameter to search specific"
#             " libraries like 'liana' or 'squidpy'.")
#     )

#     # tutorial_rag = TutorialRAG(tutorial_directories)
#     # tutorial_rag_tool = StructuredTool.from_function(
#     #     func = tutorial_rag.search,
#     #     name = "tutorial_rag_tool",
#     #     description = ("Semantic search tool for tutorial files that returns"
#     #         " relevant chunks of content. Use library parameter to search"
#     #         " specific libraries like 'liana' or 'squidpy'.")
#     # )

#     tools = [documentation_index_tool, tutorial_index_tool]

#     ### Implementation

#     model = model_ctor()

#     agent_node_id = "agent_node"
#     exec_node_id = "exec_node"

#     def agent_node(state: CodeActState):
#         messages = state["messages"]
#         system_prompt = SystemMessage(CodingAgentBasePrompt)

#         logging.info(f"invoking agent_node")
#         response = model.invoke([system_prompt] + messages)
#         logging.info(f"finished invoking agent_node")

#         response.name = id
#         log_message(response)

#         response_text = str(response.content)
#         code_block = extract_block("execute", response_text)
#         scratchpad_block = extract_block("scratchpad", response_text)
#         response = [response]
#         if code_block:
#             logging.info("code block detected")
#             next_node = exec_node_id
#         elif scratchpad_block:
#             logging.info("scratchpad block detected - looping back to agent")
#             next_node = agent_node_id
#         else:
#             logging.info("no scratchpad or execute block detected - treating as direct response and exiting")
#             next_node = END
#         logging.info(f"transferring from agent_node to {next_node}")
#         return Command(goto=next_node, update = {"messages": response})

#     def exec_node(state: CodeActState):
#         messages = state["messages"]
#         last_message = messages[-1]
#         code_block = extract_block("execute", str(last_message.content))

#         logging.info(f"executing exec_node")

#         assert code_block is not None

#         repl = state.get("repl")
#         if repl is None:
#             repl = PythonREPL()
#             tools_context = {tool.name: tool.func for tool in tools}
#             initial_context = {**tools_context, "DATA_DIR": DATA_DIR, "NOTEBOOK_DIR": NOTEBOOK_DIR}

#             for key, value in initial_context.items():
#                 repl.globals[key] = value

#         output = repl.run(code_block)

#         logging.info(f"finished exec_node")

#         log_message(HumanMessage("Python Output:\n" + output))
#         return {"messages": [HumanMessage(output)], "repl": repl}

#     graph.add_node(agent_node_id, agent_node)
#     graph.add_node(exec_node_id, exec_node)
#     graph.add_edge(START, agent_node_id)
#     graph.add_edge(exec_node_id, agent_node_id)

#     agent = graph.compile()

#     def agent_invocation_tool(prompt: str) -> str:
#         logging.info(f"Invoking agent `{id}`")
#         final_state = agent.invoke({"messages": [HumanMessage(prompt)]})
#         state_queue.put((id, final_state))
#         return final_state["messages"][-1].content

#     return StructuredTool.from_function(
#         func = agent_invocation_tool,
#         name = f"coding_agent_transfer_tool",
#         description = "Transfer control to {id}"
#     )
