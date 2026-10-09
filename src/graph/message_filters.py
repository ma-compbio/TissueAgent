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
        if (isinstance(msg, AIMessage) and getattr(msg, "name", "") == agent_name
                and not msg.tool_calls):
            return i
    return None


def filter_for_recruiter(messages: list[BaseMessage]) -> list[BaseMessage]:
    """Keep the task, latest failure assessment, and planner's revised plan.

    Strips the planner's intermediate tool calls, retaining the recruiter's
    own paired tool exchanges for the current plan.
    """
    result = [msg for msg in messages if isinstance(msg, HumanMessage)]
    feedback = _last_index_of_final(messages, "evaluator_agent")
    if feedback is not None:
        result.append(messages[feedback])
    idx = _last_index_of_final(messages, "planner_agent")
    if idx is not None:
        result.append(messages[idx])
    kept_ids = set()
    for msg in messages[idx + 1 if idx is not None else 0:]:
        if isinstance(msg, AIMessage) and getattr(msg, 'name', '') == 'recruiter_agent':
            result.append(msg)
            kept_ids.update(call['id'] for call in msg.tool_calls)
        elif isinstance(msg, ToolMessage) and msg.tool_call_id in kept_ids:
            result.append(msg)
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
    elif planner_idx is not None:
        # Orchestration-only ablations bypass recruitment. Preserve the Manager's
        # execution and tool evidence for evaluation/reporting in that case.
        result.extend(messages[planner_idx + 1 :])

    return result


def filter_for_manager(
    manager_agent_name: str,
) -> Callable[[list[BaseMessage]], list[BaseMessage]]:
    """Build a filter that shows the manager its current plan's tool-call history.

    The manager's situational context (plan + assignments + user request) is baked
    into its system prompt via :class:`agents.manager_agent.prompt.ManagerPrompt`, so
    the message channel only needs to carry the manager's own dispatch trail: each
    ``next_step`` / ``retry_step`` AIMessage and the ToolMessage it received back.
    From that trail the manager derives which steps have been dispatched and what
    the most recent sub-agent returned.

    A replan produces a new recruiter final. Manager history from before that final
    belongs to the failed plan and must not influence dispatch of the replacement
    plan. The returned filter therefore drops:

    * HumanMessages (the user request is in the system prompt).
    * Planner / recruiter / evaluator AIMessages and their paired ToolMessages.
    * ``plan_updated`` / ``artifact_validation`` UI-only events.

    A synthetic ``HumanMessage("Proceed.")`` anchors every filtered history.
    Some providers require a user turn even when assistant/tool exchanges exist.
    The task and current plan remain in the system prompt.
    """

    def _filter(messages: list[BaseMessage]) -> list[BaseMessage]:
        kept: list[BaseMessage] = []
        kept_tool_call_ids: set[str] = set()
        recruiter_idx = _last_index_of_final(messages, "recruiter_agent")
        current_plan_messages = (
            messages[recruiter_idx + 1 :] if recruiter_idx is not None else messages
        )
        for msg in current_plan_messages:
            if isinstance(msg, AIMessage) and getattr(msg, "name", "") == manager_agent_name:
                kept.append(msg)
                for tc in getattr(msg, "tool_calls", []) or []:
                    tc_id = tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", None)
                    if tc_id:
                        kept_tool_call_ids.add(tc_id)
            elif isinstance(msg, ToolMessage) and msg.tool_call_id in kept_tool_call_ids:
                kept.append(msg)
        return [HumanMessage(content="Proceed."), *kept]

    return _filter
