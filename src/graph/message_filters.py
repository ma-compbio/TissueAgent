"""Per-agent message filters.

These are pure functions that project message lists without mutating graph state, to keep agent
context windows focused on relevant information.
"""

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage


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


def filter_for_manager(messages: list[BaseMessage]) -> list[BaseMessage]:
    """Strict manager filter: keep only the user's original HumanMessages.

    Under the manager-judgment model, the manager's *entire* context is rebuilt each turn
    from the (state-aware) system prompt: agent registry, current cursor, the assigned
    agent for the current step, and the final outputs of all accepted prior steps. Nothing
    else in the message history is load-bearing for the next decision.

    This filter therefore drops:

    * Planner / recruiter / evaluator AIMessages (already encoded in plan_store + prompt).
    * Prior manager tool-call AIMessages and their paired ToolMessages (the cursor state
      and the new step output are already injected into the next prompt).
    * ``plan_updated`` and ``artifact_validation`` UI-only events (not for the LLM).

    Keeping at least one HumanMessage satisfies provider APIs that require a non-empty
    user turn and gives the LLM the original user ask as additional grounding.
    """
    return [msg for msg in messages if isinstance(msg, HumanMessage)]
