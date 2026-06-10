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


def filter_for_execution_phase(messages: list[BaseMessage]) -> list[BaseMessage]:
    """Filter messages for the execution phase.

    Manager / Evaluator / Reporter see: user query, finalized plan (planner final + recruiter
    final), and all post-recruiter messages. Strips planner and recruiter intermediate tool-calling
    turns.  The post-recruiter slice naturally grows as the manager executes steps, and later
    includes the evaluator's assessment for the reporter.
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
