"""LangGraph state-graph construction for the TissueAgent pipeline.

Assembles the hierarchical multi-agent workflow:

    Planner → Recruiter → Manager → Evaluator → Reporter

Each main agent is wired as an agent-node / tool-node pair.  Specialized
sub-agents from :data:`AgentDefns` are compiled into independent sub-graphs
and exposed to the Manager as invocation tools.
"""

import json
import logging
from datetime import datetime, timezone
from queue import Queue
from typing import Callable

from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.graph import END, MessagesState, START, StateGraph

from agents.agent_defns import (
    AgentDefns,
    CustomAgent,
    PlannerAgent,
    ManagerAgent,
    ReActAgent,
    RecruiterAgent,
    EvaluatorAgent,
    ReporterAgent,
)
from graph.graph_utils import (
    create_agent_node,
    create_tool_node,
    create_agent_invocation_tool,
)
from memori_integration import initialize_memori_context

MAX_REPLANS = 2


def create_tissueagent_graph(
    state_queue: Queue, model_proc_fn: Callable[..., BaseChatModel]
) -> StateGraph:
    """Build the full TissueAgent state graph (uncompiled).

    Constructs sub-agent graphs for each entry in :data:`AgentDefns`, then
    wires the five main pipeline agents with conditional routing edges.
    The caller is responsible for compiling the returned graph.

    Args:
        state_queue: Thread-safe queue where completed sub-agent states are
            placed so the UI can render them.
        model_proc_fn: Callable applied to every bound model (typically
            adds retry logic for rate-limit errors).

    Returns:
        An uncompiled :class:`~langgraph.graph.StateGraph` ready to be
        compiled via ``.compile()``.
    """
    initialize_memori_context()
    assign_agent_node_id = lambda id: f"{id}_agent"
    assign_tool_node_id = lambda id: f"{id}_tools"

    agent_id_descriptions = {assign_agent_node_id(a.id): a.description for a in AgentDefns}

    logging.info(f"Agent ID Descriptions: {json.dumps(agent_id_descriptions, indent=4)}")

    ## Build Subagents

    agent_invocation_tools = []
    for agent in AgentDefns:
        if isinstance(agent, ReActAgent):
            agent_subgraph = StateGraph(MessagesState)
            agent_model = model_proc_fn(agent.model_ctor().bind_tools(agent.tools))

            agent_node_id = assign_agent_node_id(agent.id)
            tool_node_id = assign_tool_node_id(agent.id)
            tool_node = create_tool_node(agent.tools)

            assert isinstance(agent.prompt, str)
            agent_node = create_agent_node(
                agent_node_id, agent_model, agent.prompt, tool_node_id, END
            )

            agent_subgraph.add_node(agent_node_id, agent_node)
            agent_subgraph.add_node(tool_node_id, tool_node)
            agent_subgraph.add_edge(START, agent_node_id)
            agent_subgraph.add_edge(tool_node_id, agent_node_id)
            subagent = agent_subgraph.compile()

            # Enable PDF support for PDF Reader Agent
            supports_pdf = agent.id == "pdf_reader"

            forward_user_images = agent.id == "coding"
            agent_invocation_tool = create_agent_invocation_tool(
                agent_node_id,
                agent.name,
                subagent,
                state_queue,
                supports_pdf=supports_pdf,
                forward_user_images=forward_user_images,
            )
            agent_invocation_tools.append(agent_invocation_tool)

            logging.info(
                "\n\n".join(
                    [
                        "ReAct Agent Info",
                        f"ID:          {agent.id}",
                        f"Name:        {agent.name}",
                        f"Description: {agent.description}",
                        f"Prompt:      {agent.prompt}",
                        f"Tools:       {[tool.name for tool in agent.tools]}",
                    ]
                )
            )

        elif isinstance(agent, CustomAgent):
            agent_invocation_tool = agent.ctor(state_queue)
            agent_invocation_tools.append(agent_invocation_tool)

            logging.info(
                "\n\n".join(
                    [
                        "Custom Agent Info",
                        f"ID:          {agent.id}",
                        f"Name:        {agent.name}",
                        f"Description: {agent.description}",
                    ]
                )
            )

    ## Build Main Agents

    for main_agent in [
        PlannerAgent,
        RecruiterAgent,
        ManagerAgent,
        EvaluatorAgent,
        ReporterAgent,
    ]:
        if isinstance(main_agent.prompt, str):
            prompt_preview = (
                main_agent.prompt
                if len(main_agent.prompt) < 600
                else main_agent.prompt[:600] + "...[truncated]"
            )
        else:
            try:
                prompt_preview = main_agent.prompt(agent_id_descriptions)
                if len(prompt_preview) > 600:
                    prompt_preview = prompt_preview[:600] + "...[truncated]"
            except Exception as e:
                prompt_preview = f"<Prompt callable: {e}>"
        tool_names = [tool.name for tool in main_agent.tools]
        if main_agent == ManagerAgent:
            tool_names += [tool.name for tool in agent_invocation_tools]
        logging.info(
            "\n".join(
                [
                    f"Main Agent: {main_agent.name} (ID: {main_agent.id})",
                    "Prompt:",
                    prompt_preview,
                    f"Available tools: {tool_names}",
                ]
            )
        )

    ### Planner agent

    planner_model = model_proc_fn(PlannerAgent.model_ctor().bind_tools(PlannerAgent.tools))
    assert isinstance(PlannerAgent.prompt, str)
    planner_node_id = assign_agent_node_id(PlannerAgent.id)
    planner_tool_node_id = assign_tool_node_id(PlannerAgent.id)

    ### Recruiter agent

    recruiter_model = model_proc_fn(RecruiterAgent.model_ctor().bind_tools(RecruiterAgent.tools))
    if isinstance(RecruiterAgent.prompt, str):
        recruiter_prompt = RecruiterAgent.prompt
    else:
        recruiter_prompt = RecruiterAgent.prompt(agent_id_descriptions)
    recruiter_node_id = assign_agent_node_id(RecruiterAgent.id)
    recruiter_tool_node_id = assign_tool_node_id(RecruiterAgent.id)

    ### Manager agent

    manager_tools = ManagerAgent.tools + agent_invocation_tools
    manager_model = model_proc_fn(ManagerAgent.model_ctor().bind_tools(manager_tools))
    if isinstance(ManagerAgent.prompt, str):
        manager_prompt = ManagerAgent.prompt
    else:
        manager_prompt = ManagerAgent.prompt(agent_id_descriptions)
    manager_node_id = assign_agent_node_id(ManagerAgent.id)
    manager_tool_node_id = assign_tool_node_id(ManagerAgent.id)

    ### Evaluator agent

    evaluator_model = model_proc_fn(EvaluatorAgent.model_ctor().bind_tools(EvaluatorAgent.tools))
    assert isinstance(EvaluatorAgent.prompt, str)
    evaluator_prompt = EvaluatorAgent.prompt
    evaluator_node_id = assign_agent_node_id(EvaluatorAgent.id)
    evaluator_tool_node_id = assign_tool_node_id(EvaluatorAgent.id)

    ### Reporter agent

    reporter_model = model_proc_fn(ReporterAgent.model_ctor().bind_tools(ReporterAgent.tools))
    assert isinstance(ReporterAgent.prompt, str)
    reporter_node_id = assign_agent_node_id(ReporterAgent.id)
    reporter_tool_node_id = assign_tool_node_id(ReporterAgent.id)

    # Create graph nodes

    ### Planner Node

    planner_tool_node = create_tool_node(PlannerAgent.tools)

    def planner_router(response, state) -> str:
        """PlannerAgent transition fn."""
        text = (response.content or "").strip()
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
        exit_node_id_fn=planner_router,
    )

    ### Recruiter Node

    recruiter_tool_node = create_tool_node(RecruiterAgent.tools)

    recruiter_node = create_agent_node(
        recruiter_node_id,
        recruiter_model,
        recruiter_prompt,
        recruiter_tool_node_id,
        manager_node_id,
    )

    ### Manager Node

    manager_tool_node = create_tool_node(manager_tools)

    manager_node = create_agent_node(
        manager_node_id,
        manager_model,
        manager_prompt,
        manager_tool_node_id,
        evaluator_node_id,
    )

    ### Evaluator node

    evaluator_tool_node = create_tool_node(EvaluatorAgent.tools)

    def evaluator_state_update(response, state):
        content = (response.content or "").strip()
        head = content.splitlines()[0].upper() if content else ""
        if head.startswith("ROUTE: REPLAN"):
            prior = int(state.get("replan_count", 0) or 0)
            new_count = prior + 1
            history = list(state.get("replan_history", []))
            history.append(datetime.now(timezone.utc).isoformat())
            if new_count > MAX_REPLANS:
                response.content = (
                    "ROUTE: REPORT\n\n"
                    "EVALUATION: Replan limit reached (maximum 2). Returning latest evaluator assessment.\n\n"
                    "NOTE: The evaluator attempted to trigger replanning more than twice; "
                    "please review earlier feedback for unresolved blockers."
                )
            return {"replan_count": new_count, "replan_history": history}
        return {}

    def evaluator_router(response, state) -> str:
        """EvaluatorAgent transition function."""
        text = (response.content or "").strip()
        head = text.splitlines()[0].upper() if text else ""
        if head.startswith("ROUTE: REPLAN"):
            prior = int(state.get("replan_count", 0) or 0)
            next_attempt = prior + 1
            if next_attempt > MAX_REPLANS:
                return reporter_node_id
            return planner_node_id
        # head.startswith("ROUTE: REPORT"):
        return reporter_node_id

    evaluator_node = create_agent_node(
        evaluator_node_id,
        evaluator_model,
        evaluator_prompt,
        evaluator_tool_node_id,
        exit_node_id_fn=evaluator_router,
        state_update_fn=evaluator_state_update,
    )

    ### Reporter node

    reporter_tool_node = create_tool_node(ReporterAgent.tools)
    reporter_node = create_agent_node(
        reporter_node_id,
        reporter_model,
        ReporterAgent.prompt,
        reporter_tool_node_id,
        END,
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
