import logging
from queue import Queue
from typing import Callable
from api_keys import APIKeys
from langchain_core.runnables import Runnable
from langgraph.graph import END, MessagesState, START, StateGraph

from agents.agent_defns import (
    create_agent_defns, CustomAgent, PlannerAgent, ManagerAgent, ReActAgent, RecruiterAgent, EvaluatorAgent, ReporterAgent
)
from graph.graph_utils import create_agent_node, create_tool_node, create_agent_invocation_tool


def create_tissueagent_graph(
    state_queue: Queue,
    model_proc_fn: Callable[[Runnable], Runnable],
    api_key: APIKeys,
) -> StateGraph:
    assign_agent_node_id = lambda id: f"{id}_agent"
    assign_tool_node_id = lambda id: f"{id}_tools"

    agent_defn = create_agent_defns(api_key)
    agent_id_descriptions = {
        assign_agent_node_id(a.id): a.description for a in agent_defn 
    }

    print("25 Agent ID Descriptions:", agent_id_descriptions)

    ## Build Subagents

    agent_invocation_tools = []
    for agent in agent_defn:
        if isinstance(agent, ReActAgent):
            agent_subgraph = StateGraph(MessagesState)
            agent_model = model_proc_fn(agent.model_ctor().bind_tools(agent.tools))

            agent_node_id = assign_agent_node_id(agent.id)
            tool_node_id = assign_tool_node_id(agent.id)

            tool_node = create_tool_node(agent.tools)
            agent_node = create_agent_node(
                agent_node_id,
                agent_model,
                agent.prompt,
                tool_node,
                END
            )

            agent_subgraph.add_node(agent_node_id, agent_node)
            agent_subgraph.add_node(tool_node_id, tool_node)
            agent_subgraph.add_edge(START, agent_node_id)
            agent_subgraph.add_edge(tool_node_id, agent_node_id)
            subagent = agent_subgraph.compile()

            agent_invocation_tool = create_agent_invocation_tool(
                agent_node_id, agent.name, subagent, state_queue
            )
            agent_invocation_tools.append(agent_invocation_tool)

            logging.info("\n\n".join([
                "ReAct Agent Info",
                f"ID:          {agent.id}",
                f"Name:        {agent.name}",
                f"Description: {agent.description}",
                f"Prompt:      {agent.prompt}",
                f"Tools:       {[tool.name for tool in agent.tools]}",
            ]))

        elif isinstance(agent, CustomAgent):
            agent_invocation_tool = agent.ctor(state_queue)
            agent_invocation_tools.append(agent_invocation_tool)

            logging.info("\n\n".join([
                "Custom Agent Info",
                f"ID:          {agent.id}",
                f"Name:        {agent.name}",
                f"Description: {agent.description}",
            ]))

    ### Planner agent

    planner_model = model_proc_fn(PlannerAgent.model_ctor().bind_tools(PlannerAgent.tools))
    planner_node_id = assign_agent_node_id(PlannerAgent.id)
    planner_tool_node_id = assign_tool_node_id(PlannerAgent.id)

    ### Recruiter agent

    recruiter_model = model_proc_fn(RecruiterAgent.model_ctor().bind_tools(RecruiterAgent.tools))
    recruiter_prompt = RecruiterAgent.prompt(agent_id_descriptions)
    recruiter_node_id = assign_agent_node_id(RecruiterAgent.id)
    recruiter_tool_node_id = assign_tool_node_id(RecruiterAgent.id)

    ### Manager agent

    manager_model = model_proc_fn(ManagerAgent.model_ctor().bind_tools(ManagerAgent.tools))
    manager_prompt = ManagerAgent.prompt(agent_id_descriptions)
    manager_tools = ManagerAgent.tools + agent_invocation_tools
    manager_node_id = assign_agent_node_id(ManagerAgent.id)
    manager_tool_node_id = assign_tool_node_id(ManagerAgent.id)

    ### Evaluator agent

    evaluator_model = model_proc_fn(EvaluatorAgent.model_ctor().bind_tools(EvaluatorAgent.tools))
    evaluator_prompt = EvaluatorAgent.prompt
    evaluator_node_id = assign_agent_node_id(EvaluatorAgent.id)
    evaluator_tool_node_id = assign_tool_node_id(EvaluatorAgent.id)

    ### Reporter agent

    reporter_model = model_proc_fn(ReporterAgent.model_ctor().bind_tools(ReporterAgent.tools))
    reporter_prompt = ReporterAgent.prompt
    reporter_node_id = assign_agent_node_id(ReporterAgent.id)
    reporter_tool_node_id = assign_tool_node_id(ReporterAgent.id)


    # Create graph nodes

    ### Planner Node

    planner_tool_node = create_tool_node(PlannerAgent.tools)

    def planner_router(text: str) -> str:
        """PlannerAgent transition fn"""
        text = text.strip()
        head = text.splitlines()[0].upper() if text else ""
        if head.startswith("ROUTE: DIRECT"):
            return END
        if head.startswith("ROUTE: CLARIFY"):
            return END
        return recruiter_node_id

    planner_node = create_agent_node(
        planner_node_id,
        planner_model,
        PlannerAgent.prompt,
        planner_tool_node_id,
        exit_node_id_fn = planner_router
    )

    ### Recruiter Node

    recruiter_tool_node = create_tool_node(RecruiterAgent.tools)

    recruiter_node = create_agent_node(
        recruiter_node_id, 
        recruiter_model, 
        recruiter_prompt,
        recruiter_tool_node_id,
        manager_node_id
    )

    ### Manager Node

    manager_tool_node = create_tool_node(manager_tools)

    manager_node = create_agent_node(
        manager_node_id,
        manager_model,
        manager_prompt,
        manager_tool_node_id,
        evaluator_node_id
    )

    ### Evaluator node

    evaluator_tool_node = create_tool_node(EvaluatorAgent.tools)

    def evaluator_router(text: str) -> str:
        """EvaluatorAgent transition fn"""
        text = text.strip()
        head = text.splitlines()[0].upper() if text else ""
        if head.startswith("ROUTE: REPLAN"):
            return planner_node_id
        # head.startswith("ROUTE: REPORT"):
        return reporter_node_id

    evaluator_node = create_agent_node(
        evaluator_node_id,
        evaluator_model,
        evaluator_prompt,
        evaluator_tool_node_id,
        exit_node_id_fn=evaluator_router
    )

    ### Reporter node

    reporter_tool_node = create_tool_node(ReporterAgent.tools)
    reporter_node = create_agent_node(
        reporter_node_id,
        reporter_model,
        reporter_prompt,
        reporter_tool_node_id,
        END
    )

    graph = StateGraph(MessagesState)
    
    graph.add_edge(START, planner_node_id)

    graph.add_node(planner_node_id, planner_node)
    graph.add_node(planner_tool_node_id, planner_tool_node)
    graph.add_edge(planner_tool_node_id, planner_node_id)

    graph.add_node(manager_node_id, manager_node)
    graph.add_node(manager_tool_node_id, manager_tool_node)
    graph.add_edge(manager_tool_node_id, manager_node_id)

    graph.add_node(recruiter_node_id, recruiter_node)
    graph.add_node(recruiter_tool_node_id, recruiter_tool_node)
    graph.add_edge(recruiter_tool_node_id, recruiter_node_id)

    graph.add_node(evaluator_node_id, evaluator_node)
    graph.add_node(evaluator_tool_node_id, evaluator_tool_node)
    graph.add_edge(evaluator_tool_node_id, evaluator_node_id)

    graph.add_node(reporter_node_id, reporter_node)
    graph.add_node(reporter_tool_node_id, reporter_tool_node)
    graph.add_edge(reporter_tool_node_id, reporter_node_id)

    return graph