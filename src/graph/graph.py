import anthropic
import logging
import openai

from functools import partial
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.rate_limiters import InMemoryRateLimiter
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from typing import Callable, Optional
from queue import Queue

from api_keys import APIKeys
from agents.agent_defns import create_agent_defns
from graph.state import AgentState
from graph.graph_utils import (create_agent_node,
                               create_tool_node,
                               create_agent_transition,
                               create_agent_invocation_tool)

# NEW imports
from agents.planner_agent.prompt import PlannerPrompt
from agents.planner_agent.tools import create_planner_tools
from agents.manager_agent.prompt import ManagerPrompt
from agents.manager_agent.tools import create_manager_tools


def create_spatialagent_graph(
    model_ctor: Callable[..., BaseChatModel],
    api_keys: APIKeys,
    state_queue: Queue,
    requests_per_second: Optional[float]=None,
    max_retries: int=0,
) -> StateGraph:

    model_ctor = partial(model_ctor, api_key=api_keys["llm"])

    if requests_per_second is not None:
        rate_limiter = InMemoryRateLimiter(
            requests_per_second=requests_per_second,
            check_every_n_seconds=0.1,
            max_bucket_size=10,
        )
        model_ctor = partial(model_ctor, rate_limiter=rate_limiter)

    bind_retry = (lambda m: m) if max_retries <= 0 else (
        lambda m: m.with_retry(
            retry_if_exception_type=(openai.RateLimitError, anthropic.RateLimitError),
            stop_after_attempt=max_retries,
        )
    )

    # ---------- 1) Build sub-agents as callable tools ----------
    agent_defns = create_agent_defns(api_keys)

    assign_agent_node_id = lambda id: f"{id}_agent"
    assign_tool_node_id = lambda id: f"{id}_tools"

    agent_id_descriptions = {assign_agent_node_id(a.id): a.description for a in agent_defns}

    agent_invocation_tools = []
    for agent in agent_defns:
        agent_subgraph = StateGraph(AgentState)

        agent_model = bind_retry(model_ctor().bind_tools(agent.tools))

        agent_node_id = assign_agent_node_id(agent.id)
        agent_node = create_agent_node(agent_node_id, agent_model, agent.prompt)
        agent_subgraph.add_node(agent_node_id, agent_node)

        tool_node_id = assign_tool_node_id(agent.id)
        tool_node = create_tool_node(agent.tools)
        agent_subgraph.add_node(tool_node_id, tool_node)

        agent_transition = create_agent_transition(tool_node_id, END)
        agent_subgraph.add_edge(START, agent_node_id)
        agent_subgraph.add_conditional_edges(agent_node_id, agent_transition, [tool_node_id, END])
        agent_subgraph.add_edge(tool_node_id, agent_node_id)

        subagent = agent_subgraph.compile()

        agent_invocation_tool = create_agent_invocation_tool(
            agent_node_id, agent.name, subagent, state_queue
        )
        agent_invocation_tools.append(agent_invocation_tool)

        logging.info("\n\n".join([
            "Agent Info",
            f"ID:          {agent.id}",
            f"Name:        {agent.name}",
            f"Description: {agent.description}",
            f"Prompt:      {agent.prompt}",
            f"Tools:       {[tool.name for tool in agent.tools]}",
        ]))

    # ---------- 2) Main Graph: Planner -> Manager ----------
    graph = StateGraph(AgentState)

    # --- Planner node ---
    planner_id = "planner"
    planner_tools = create_planner_tools(api_keys)  # registry/index + selector + file_retriever
    planner_model = bind_retry(model_ctor().bind_tools(planner_tools))
    planner_prompt = PlannerPrompt  # static string prompt

    planner_node_id = assign_agent_node_id(planner_id)
    planner_tool_node_id = assign_tool_node_id(planner_id)

    planner_node = create_agent_node(planner_node_id, planner_model, planner_prompt)
    planner_tool_node = ToolNode(planner_tools)

    graph.add_node(planner_node_id, planner_node)
    graph.add_node(planner_tool_node_id, planner_tool_node)

    # --- Manager node ---
    manager_id = "manager"
    manager_tools = create_manager_tools(api_keys)
    manager_tools.extend(agent_invocation_tools)  # Manager can call sub-agents

    manager_model = bind_retry(model_ctor().bind_tools(manager_tools))
    manager_prompt = ManagerPrompt(agent_id_descriptions)

    manager_node_id = assign_agent_node_id(manager_id)
    manager_tool_node_id = assign_tool_node_id(manager_id)

    manager_node = create_agent_node(manager_node_id, manager_model, manager_prompt)
    manager_tool_node = ToolNode(manager_tools)

    graph.add_node(manager_node_id, manager_node)
    graph.add_node(manager_tool_node_id, manager_tool_node)

    # --- Transitions ---
    # Planner loops Agent <-> Tools until it decides it's done (returns <final>),
    # then we move on to Manager.
    planner_transition = create_agent_transition(planner_tool_node_id, manager_node_id)
    graph.add_edge(START, planner_node_id)
    graph.add_conditional_edges(planner_node_id, planner_transition, [planner_tool_node_id, manager_node_id])
    graph.add_edge(planner_tool_node_id, planner_node_id)

    # Manager loops Agent <-> Tools until it returns <final>, then END.
    manager_transition = create_agent_transition(manager_tool_node_id, END)
    graph.add_conditional_edges(manager_node_id, manager_transition, [manager_tool_node_id, END])
    graph.add_edge(manager_tool_node_id, manager_node_id)

    return graph


# import anthropic
# import logging
# import openai

# from functools import partial
# from langchain_core.language_models.chat_models import BaseChatModel
# from langchain_core.rate_limiters import InMemoryRateLimiter
# from langgraph.graph import StateGraph, START, END
# from langgraph.prebuilt import ToolNode
# from typing import Callable, Optional
# from queue import Queue

# from api_keys import APIKeys
# from agents.agent_defns import create_agent_defns
# from agents.manager_agent.prompt import SupervisorPrompt
# from agents.manager_agent.tools import create_supervisor_tools
# from graph.state import AgentState
# from graph.graph_utils import (create_agent_node,
#                                create_tool_node,
#                                create_agent_transition,
#                                create_agent_invocation_tool)

# def create_spatialagent_graph(
#     model_ctor: Callable[..., BaseChatModel],
#     api_keys: APIKeys,
#     state_queue: Queue,
#     requests_per_second: Optional[float]=None,
#     max_retries: int=0,
# ) -> StateGraph:

#     model_ctor = partial(model_ctor, api_key=api_keys["llm"])

#     if requests_per_second is not None:
#         rate_limiter = InMemoryRateLimiter(
#             requests_per_second=requests_per_second,
#             check_every_n_seconds=0.1,
#             max_bucket_size=10,
#         )
#         model_ctor = partial(model_ctor, rate_limiter=rate_limiter)

#     if max_retries > 0:
#         bind_retry = lambda model: model.with_retry(
#             retry_if_exception_type=(openai.RateLimitError, anthropic.RateLimitError),
#             stop_after_attempt=max_retries,
#         )
#     else:
#         bind_retry = lambda model: model

#     agent_defns = create_agent_defns(api_keys)

#     assign_agent_node_id = lambda id: f"{id}_agent"
#     assign_tool_node_id = lambda id: f"{id}_tools"

#     agent_id_descriptions = {
#         assign_agent_node_id(agent.id): agent.description for agent in agent_defns
#     }

#     ### add nodes to workflow

#     agent_invocation_tools = []
#     for agent in agent_defns:
#         agent_subgraph = StateGraph(AgentState)

#         agent_model = bind_retry(model_ctor().bind_tools(agent.tools))

#         agent_node_id = assign_agent_node_id(agent.id)
#         agent_node = create_agent_node(agent_node_id, agent_model,
#                                        agent.prompt)
#         agent_subgraph.add_node(agent_node_id, agent_node)

#         tool_node = create_tool_node(agent.tools)
#         tool_node_id = assign_tool_node_id(agent.id)
#         agent_subgraph.add_node(tool_node_id, tool_node)

#         agent_transition = create_agent_transition(tool_node_id, END)
#         agent_subgraph.add_edge(START, agent_node_id)
#         agent_subgraph.add_conditional_edges(agent_node_id, agent_transition,
#                                              [tool_node_id, END])
#         agent_subgraph.add_edge(tool_node_id, agent_node_id)

#         subagent = agent_subgraph.compile()

#         agent_invocation_tool = create_agent_invocation_tool(agent_node_id, agent.name,
#                                                              subagent, state_queue)
#         agent_invocation_tools.append(agent_invocation_tool)

#         logging.info("\n\n".join([
#             "Agent Info",
#             f"ID:          {agent.id}",
#             f"Name:        {agent.name}",
#             f"Description: {agent.description}",
#             f"Prompt:      {agent.prompt}",
#             f"Tools:       {[tool.name for tool in agent.tools]}",
#         ]))

#     graph = StateGraph(AgentState)

#     supervisor_id = "supervisor"
#     supervisor_tools = create_supervisor_tools(api_keys)
#     supervisor_tools.extend(agent_invocation_tools)
#     supervisor_model = bind_retry(model_ctor().bind_tools(supervisor_tools))
#     supervisor_prompt = SupervisorPrompt(agent_id_descriptions)

#     logging.info("\n\n".join([
#         "Agent Info",
#         f"ID:          {supervisor_id}",
#         f"Prompt:      {supervisor_prompt}",
#         f"Tools:       {[tool.name for tool in agent_invocation_tools]}",
#     ]))

#     supervisor_node_id = assign_agent_node_id(supervisor_id)
#     supervisor_node = create_agent_node(supervisor_node_id,
#                                         supervisor_model,
#                                         supervisor_prompt)
#     graph.add_node(supervisor_node_id, supervisor_node)

#     supervisor_tool_node_id = assign_tool_node_id(supervisor_id)
#     supervisor_tool_node = ToolNode(supervisor_tools)
#     graph.add_node(supervisor_tool_node_id, supervisor_tool_node)

#     supervisor_agent_transition = create_agent_transition(supervisor_tool_node_id,
#                                                           END)

#     graph.add_edge(START, supervisor_node_id)
#     graph.add_conditional_edges(supervisor_node_id,
#                                    supervisor_agent_transition,
#                                    [supervisor_tool_node_id, END])
#     graph.add_edge(supervisor_tool_node_id, supervisor_node_id)

#     return graph
