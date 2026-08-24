"""LangGraph state-graph construction for the TissueAgent pipeline.

Assembles the hierarchical multi-agent workflow:

    Planner → Recruiter → Manager → Evaluator → Reporter

Each main agent is wired as an agent-node / tool-node pair.  Specialized sub-agents from
:data:`AgentDefns` are compiled into independent sub-graphs and exposed to the Manager as invocation
tools.
"""

import inspect
import json
import logging
from collections.abc import Callable
from datetime import datetime, timezone
from queue import Queue

from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.graph import END, START, MessagesState, StateGraph

from agents.agent_defns import (
    AgentDefns,
    CustomAgent,
    EvaluatorAgent,
    ManagerAgent,
    PlannerAgent,
    ReActAgent,
    RecruiterAgent,
    ReporterAgent,
)
from agents.agent_utils import substitute_shared_prompts, truncate_output
from agents.planner_agent.prompt import PlannerReplanPrompt
from config import MAX_PLANNER_RETRIES, MAX_RECRUITER_RETRIES, MAX_REPLANS
from agents.manager_agent.tools import create_manager_step_tools
from graph.message_filters import (
    filter_for_execution_phase,
    filter_for_manager,
    filter_for_planner,
    filter_for_recruiter,
    find_last_planner_final_content,
)
from graph.node_factories import (
    AgentState,
    OrchestratorState,
    create_agent_invocation_tool,
    create_agent_node,
    create_step_context_resolver,
    create_tool_node,
)
from graph.plan_output import create_planner_state_update, create_recruiter_state_update


def create_tissueagent_graph(
    state_queue: Queue,
    model_proc_fn: Callable[..., BaseChatModel],
    domain_agents: list | None = None,
    **custom_agent_kwargs,
) -> StateGraph:
    """Build the full TissueAgent state graph (uncompiled).

    Constructs sub-agent graphs for each entry in :data:`AgentDefns` (or *domain_agents*),
    then wires the five main pipeline agents with conditional routing edges. The caller is
    responsible for compiling the returned graph.

    Execution mode (autopilot vs copilot) is an **app-layer** concern. It lives on
    :class:`server.session_manager.SessionState` and is honored by the server's WebSocket handlers
    when they invoke the compiled graph. Direct callers (notebook / CLI) never set up that session
    and therefore always run autopilot; copilot pauses are server-side wiring only.

    Args:
        state_queue: Thread-safe queue where completed sub-agent states are placed so the UI can
            render them.
        model_proc_fn: Callable applied to every bound model (typically adds retry logic for
            rate-limit errors).
        domain_agents: Optional override of the recruitable domain-agent list. Defaults to
            :data:`AgentDefns`. Benchmark ablations may pass a filtered copy (e.g. without
            ``cellvoyager_agent``).
        **custom_agent_kwargs: Extra keyword arguments forwarded to :class:`CustomAgent`
            constructors. Each ctor receives only the kwargs it declares in its signature (filtered
            via ``inspect.signature``). For example, ``kernel_client=...`` is consumed by the coding
            agent's constructor.

    Returns:
        An uncompiled :class:`~langgraph.graph.StateGraph` ready to be compiled via ``.compile()``.
    """
    agents = list(domain_agents) if domain_agents is not None else list(AgentDefns)
    assign_agent_node_id = lambda id: f"{id}_agent"
    assign_tool_node_id = lambda id: f"{id}_tools"

    agent_id_descriptions = {assign_agent_node_id(a.id): a.description for a in agents}
    logging.info(f"Agent ID Descriptions: {json.dumps(agent_id_descriptions, indent=4)}")

    ## Build Subagents

    context_resolver = create_step_context_resolver(assign_agent_node_id)
    agent_invocation_tools = []
    invocation_tools_by_agent: dict[str, "StructuredTool"] = {}
    for agent in agents:
        if isinstance(agent, ReActAgent):
            agent_subgraph = StateGraph(AgentState)
            agent_model = model_proc_fn(agent.model_ctor().bind_tools(agent.tools))

            agent_node_id = assign_agent_node_id(agent.id)
            tool_node_id = assign_tool_node_id(agent.id)
            tool_node = create_tool_node(agent.tools)

            base_prompt = agent.prompt
            if isinstance(base_prompt, str):
                # Substitute shared prompts once at build time, then wrap in a callable that
                # injects the per-step skill_prompt at invocation time. The default-arg binding
                # captures the current loop iteration's prompt instead of the last one.
                substituted = substitute_shared_prompts(base_prompt)

                def prompt_fn(state: AgentState, _prompt: str = substituted) -> str:
                    skill_text = state.get("skill_prompt", "")
                    return _prompt.replace("{{skill_prompt}}", skill_text)
            else:
                # Callable prompts handle their own substitution; just wrap to also apply the
                # shared-prompt pass on whatever the callable returns.
                def prompt_fn(state: AgentState, _base: Callable = base_prompt) -> str:
                    return substitute_shared_prompts(_base(state))

            agent_node = create_agent_node(agent_node_id, agent_model, prompt_fn, tool_node_id, END)

            agent_subgraph.add_node(agent_node_id, agent_node)
            agent_subgraph.add_node(tool_node_id, tool_node)
            agent_subgraph.add_edge(START, agent_node_id)
            agent_subgraph.add_edge(tool_node_id, agent_node_id)
            subagent = agent_subgraph.compile()

            agent_invocation_tool = create_agent_invocation_tool(
                agent_node_id,
                agent.name,
                subagent,
                state_queue,
                context_resolver,
            )
            agent_invocation_tools.append(agent_invocation_tool)
            invocation_tools_by_agent[assign_agent_node_id(agent.id)] = agent_invocation_tool

            logging.info(
                "\n\n".join(
                    [
                        "ReAct Agent Info",
                        f"ID:          {agent.id}",
                        f"Name:        {agent.name}",
                        f"Description: {agent.description}",
                        f"Prompt:      {agent.prompt[:200] if isinstance(agent.prompt, str) else '<callable>'}",
                        f"Tools:       {[tool.name for tool in agent.tools]}",
                    ]
                )
            )

        elif isinstance(agent, CustomAgent):
            sig = inspect.signature(agent.ctor)
            filtered = {k: v for k, v in custom_agent_kwargs.items() if k in sig.parameters}
            agent_invocation_tool = agent.ctor(
                state_queue, context_resolver=context_resolver, **filtered
            )
            agent_invocation_tools.append(agent_invocation_tool)
            invocation_tools_by_agent[assign_agent_node_id(agent.id)] = agent_invocation_tool

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
            prompt_preview = truncate_output(main_agent.prompt, 600)
        else:
            try:
                prompt_obj = main_agent.prompt(agent_id_descriptions)
                # Some prompts (e.g., the manager's) return a state-aware callable
                # rather than a string. Render once with an empty state for preview.
                if callable(prompt_obj):
                    prompt_obj = prompt_obj({"messages": []})
                prompt_preview = truncate_output(prompt_obj, 600)
            except Exception as e:
                prompt_preview = f"<Prompt callable: {e}>"
        tool_names = [tool.name for tool in main_agent.tools]
        if main_agent == ManagerAgent:
            # Manager's transfer-tool surface is wrapped by next_step/retry_step;
            # the per-agent transfer tools are no longer bound directly.
            tool_names += ["next_step", "retry_step"]
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
    initial_planner_prompt = substitute_shared_prompts(PlannerAgent.prompt)
    replan_prompt = substitute_shared_prompts(PlannerReplanPrompt)

    def planner_prompt_fn(state) -> str:
        """Swap to the replan prompt once the evaluator has bounced us back at least once.

        On replan, substitute the previous planner_agent final's content into the
        {{previous_plan}} placeholder. The previous plan is pulled directly from the
        prior planner response (not the recruiter-annotated plan_store), and the
        message filter strips the same response so it isn't shown twice.
        """
        if int(state.get("replan_count", 0) or 0) > 0:
            previous_plan = find_last_planner_final_content(state.get("messages", []))
            return replan_prompt.replace("{{previous_plan}}", previous_plan)
        return initial_planner_prompt

    planner_node_id = assign_agent_node_id(PlannerAgent.id)
    planner_tool_node_id = assign_tool_node_id(PlannerAgent.id)

    ### Recruiter agent

    recruiter_model = model_proc_fn(RecruiterAgent.model_ctor().bind_tools(RecruiterAgent.tools))
    recruiter_prompt = substitute_shared_prompts(RecruiterAgent.prompt(agent_id_descriptions))
    recruiter_node_id = assign_agent_node_id(RecruiterAgent.id)
    recruiter_tool_node_id = assign_tool_node_id(RecruiterAgent.id)

    ### Manager agent

    manager_step_tools = create_manager_step_tools(invocation_tools_by_agent)
    manager_tools = ManagerAgent.tools + manager_step_tools
    manager_model = model_proc_fn(ManagerAgent.model_ctor().bind_tools(manager_tools))

    # ManagerPrompt returns a state-aware callable. Wrap it so shared-prompt substitution
    # is applied to each per-turn render (matches how prompts are wrapped elsewhere).
    _manager_prompt_render = ManagerAgent.prompt(agent_id_descriptions)

    def manager_prompt(state) -> str:
        return substitute_shared_prompts(_manager_prompt_render(state))

    manager_node_id = assign_agent_node_id(ManagerAgent.id)
    manager_tool_node_id = assign_tool_node_id(ManagerAgent.id)

    ### Evaluator agent

    evaluator_model = model_proc_fn(EvaluatorAgent.model_ctor().bind_tools(EvaluatorAgent.tools))
    assert isinstance(EvaluatorAgent.prompt, str)
    evaluator_prompt = substitute_shared_prompts(EvaluatorAgent.prompt)
    evaluator_node_id = assign_agent_node_id(EvaluatorAgent.id)
    evaluator_tool_node_id = assign_tool_node_id(EvaluatorAgent.id)

    ### Reporter agent

    reporter_model = model_proc_fn(ReporterAgent.model_ctor().bind_tools(ReporterAgent.tools))
    assert isinstance(ReporterAgent.prompt, str)
    reporter_prompt = substitute_shared_prompts(ReporterAgent.prompt)
    reporter_node_id = assign_agent_node_id(ReporterAgent.id)
    reporter_tool_node_id = assign_tool_node_id(ReporterAgent.id)

    # Create graph nodes

    ### Planner Node

    planner_tool_node = create_tool_node(PlannerAgent.tools)

    def planner_router(response, state) -> str:
        """PlannerAgent transition fn.

        On replan the planner emits a bare JSON plan with no ROUTE header, so route
        straight to the recruiter unless state_update_fn flagged a parse failure
        (in which case it added retry feedback and we loop back).

        When retries are exhausted, state_update_fn rewrites response.content to
        ``ROUTE: DIRECT`` and clears planner_validation_errors — so an exhausted
        replan short-circuits to END the same way an intentional DIRECT does.
        """
        text = (response.content or "").strip()
        head = text.splitlines()[0].upper() if text else ""
        if head.startswith("ROUTE: DIRECT") or head.startswith("ROUTE: CLARIFY"):
            return END
        if int(state.get("replan_count", 0) or 0) > 0:
            if state.get("planner_validation_errors"):
                return planner_node_id
            return recruiter_node_id
        if head.startswith("ROUTE: PLAN"):
            return recruiter_node_id
        # Invalid format — loop back (state_update_fn already injected feedback)
        return planner_node_id

    planner_state_update_fn = create_planner_state_update(
        max_retries=MAX_PLANNER_RETRIES,
    )

    planner_node = create_agent_node(
        planner_node_id,
        planner_model,
        planner_prompt_fn,
        planner_tool_node_id,
        exit_node=planner_router,
        state_update_fn=planner_state_update_fn,
        message_filter_fn=filter_for_planner,
    )

    ### Recruiter Node

    recruiter_tool_node = create_tool_node(RecruiterAgent.tools)

    valid_agent_ids = {assign_agent_node_id(a.id) for a in agents}
    recruiter_state_update_fn = create_recruiter_state_update(
        valid_agent_ids,
        max_retries=MAX_RECRUITER_RETRIES,
    )

    def recruiter_router(_, state) -> str:
        """Route recruiter output: retry on validation errors, else proceed."""
        errors = state.get("recruiter_validation_errors")
        if errors:
            prior = int(state.get("recruiter_retry_count", 0) or 0)
            if prior >= MAX_RECRUITER_RETRIES:
                return manager_node_id
            return recruiter_node_id
        return manager_node_id

    recruiter_node = create_agent_node(
        recruiter_node_id,
        recruiter_model,
        recruiter_prompt,
        recruiter_tool_node_id,
        exit_node=recruiter_router,
        state_update_fn=recruiter_state_update_fn,
        message_filter_fn=filter_for_recruiter,
    )

    ### Manager Node

    manager_tool_node = create_tool_node(manager_tools)

    manager_node = create_agent_node(
        manager_node_id,
        manager_model,
        manager_prompt,
        manager_tool_node_id,
        evaluator_node_id,
        message_filter_fn=filter_for_manager(manager_node_id),
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
                # Rewrite the verdict in place so the UI and the router agree.
                # The router now decides purely from replan_count, but keeping
                # the content in sync avoids stale REPLAN text bleeding into
                # the reporter's context.
                response.content = (
                    "ROUTE: REPORT\n\n"
                    f"EVALUATION: Replan limit reached (maximum {MAX_REPLANS}). Returning latest evaluator assessment.\n\n"
                    "NOTE: The evaluator attempted to trigger replanning beyond the limit; "
                    "please review earlier feedback for unresolved blockers."
                )
            return {"replan_count": new_count, "replan_history": history}
        return {}

    def evaluator_router(response, state) -> str:
        """EvaluatorAgent transition function.

        state_update_fn runs first (see create_agent_node) and rewrites the
        response content to "ROUTE: REPORT" when the replan limit is hit,
        so routing off the current content is the single source of truth.
        """
        text = (response.content or "").strip()
        head = text.splitlines()[0].upper() if text else ""
        if head.startswith("ROUTE: REPLAN"):
            return planner_node_id
        return reporter_node_id

    evaluator_node = create_agent_node(
        evaluator_node_id,
        evaluator_model,
        evaluator_prompt,
        evaluator_tool_node_id,
        exit_node=evaluator_router,
        state_update_fn=evaluator_state_update,
        message_filter_fn=filter_for_execution_phase,
    )

    ### Reporter node

    reporter_tool_node = create_tool_node(ReporterAgent.tools)
    reporter_node = create_agent_node(
        reporter_node_id,
        reporter_model,
        reporter_prompt,
        reporter_tool_node_id,
        END,
        message_filter_fn=filter_for_execution_phase,
    )

    # OrchestratorState (not bare MessagesState): declares replan_count and the
    # retry counters as channels so their Command(update=...) writes persist.
    # With bare MessagesState those writes were dropped and every replan/retry
    # cap was inert -- see OrchestratorState docstring.
    graph = StateGraph(OrchestratorState)

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
