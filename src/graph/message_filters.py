"""Per-agent message filters.

These are pure functions that project message lists without mutating graph state, to keep agent
context windows focused on relevant information.
"""

from collections.abc import Callable

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage


def _last_index_of_final(messages: list[BaseMessage], agent_name: str) -> int | None:
    """Index of the last AIMessage from *agent_name* that has no tool calls.

    This corresponds to the agent's final output (plan, assignments, etc.) after all tool-calling
    rounds have completed.
    """
    for i in range(len(messages) - 1, -1, -1):
        msg = messages[i]
        if isinstance(msg, AIMessage) and getattr(msg, "name", "") == agent_name:
            return i
    return None


def filter_for_recruiter(messages: list[BaseMessage]) -> list[BaseMessage]:
    """Recruiter sees: user query + planner's final plan output only.

    Strips the planner's intermediate tool calls (template reads, globs, etc.).
    """
    result = [msg for msg in messages if isinstance(msg, HumanMessage)]
    idx = _last_index_of_final(messages, "planner_agent")
    if idx is not None:
        result.append(messages[idx])
    return result


def filter_for_planner(messages: list[BaseMessage]) -> list[BaseMessage]:
    """Planner filter, handles both initial planning and replan.

    Initial planning: no recruiter has run yet, so pass through unchanged — the planner
    needs to see its own ReAct tool-call messages from the current round.

    Replan: drop the previous planner final (it's injected into the system prompt via
    {{previous_plan}}) and the recruiter's response (irrelevant for revising the plan).
    The planner sees the user query + everything after the previous recruiter's final,
    which is the execution trace, the evaluator's REPLAN feedback, and any tool messages
    from the planner's own current replan loop.
    """
    recruiter_final_idx = _last_index_of_final(messages, "recruiter_agent")
    if recruiter_final_idx is None:
        return messages
    user_msgs = [m for m in messages if isinstance(m, HumanMessage)]
    return user_msgs + messages[recruiter_final_idx + 1 :]


def find_last_planner_final_content(messages: list[BaseMessage]) -> str:
    """Return the text content of the most recent planner_agent final response.

    Used to inject the previous plan into the replan system prompt via the
    ``{{previous_plan}}`` placeholder. Returns an empty string when no planner final
    exists yet (e.g., the initial planning call).
    """
    idx = _last_index_of_final(messages, "planner_agent")
    if idx is None:
        return ""
    content = messages[idx].content
    return content if isinstance(content, str) else ""


def filter_for_execution_phase(messages: list[BaseMessage]) -> list[BaseMessage]:
    """Filter messages for the execution phase.

    Evaluator / Reporter see: user query, finalized plan (planner final + recruiter
    final), and all post-recruiter messages. Strips planner and recruiter intermediate tool-calling
    turns.  The post-recruiter slice naturally grows as the manager executes steps, and later
    includes the evaluator's assessment for the reporter.

    Note: this filter is NOT used by the manager any more — the manager uses
    :func:`filter_for_manager`, which is much stricter.
    """
    result = [msg for msg in messages if isinstance(msg, HumanMessage)]

    planner_idx = _last_index_of_final(messages, "planner_agent")
    if planner_idx is not None:
        result.append(messages[planner_idx])

    recruiter_idx = _last_index_of_final(messages, "recruiter_agent")
    if recruiter_idx is not None:
        result.append(messages[recruiter_idx])
        result.extend(messages[recruiter_idx + 1 :])

    return result


def filter_for_manager(
    manager_agent_name: str,
) -> Callable[[list[BaseMessage]], list[BaseMessage]]:
    """Build a filter that shows the manager only its own tool-call history.

    The manager's situational context (plan + assignments + user request) is baked
    into its system prompt via :class:`agents.manager_agent.prompt.ManagerPrompt`, so
    the message channel only needs to carry the manager's own dispatch trail: each
    ``next_step`` / ``retry_step`` AIMessage and the ToolMessage it received back.
    From that trail the manager derives which steps have been dispatched and what
    the most recent sub-agent returned.

    The returned filter drops:

    * HumanMessages (the user request is in the system prompt).
    * Planner / recruiter / evaluator AIMessages and their paired ToolMessages.
    * ``plan_updated`` / ``artifact_validation`` UI-only events.

    On turn 1 the manager has no AIMessages yet, so the filter would return an
    empty list — provider APIs reject that. In that case only, a synthetic
    ``HumanMessage("Proceed.")`` is injected. On turn 2+ the real manager
    AIMessages exist, so no synthetic message is added.
    """

    def _filter(messages: list[BaseMessage]) -> list[BaseMessage]:
        kept: list[BaseMessage] = []
        kept_tool_call_ids: set[str] = set()
        for msg in messages:
            if isinstance(msg, AIMessage) and getattr(msg, "name", "") == manager_agent_name:
                kept.append(msg)
                for tc in getattr(msg, "tool_calls", []) or []:
                    tc_id = tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", None)
                    if tc_id:
                        kept_tool_call_ids.add(tc_id)
            elif isinstance(msg, ToolMessage) and msg.tool_call_id in kept_tool_call_ids:
                kept.append(msg)
        if not kept:
            kept.append(HumanMessage(content="Proceed."))
        return kept

    return _filter
