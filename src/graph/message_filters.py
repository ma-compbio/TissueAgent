"""Message-history compression and per-agent filtering.

These are pure functions that project or truncate message lists without
mutating graph state — used to keep agent context windows manageable.
"""

from typing import Any, List, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage

from graph.message_utils import content_to_text

# ---------------------------------------------------------------------------
# Manager-history compression (strategy 2F)
# ---------------------------------------------------------------------------
#
# Among the five orchestration agents (planner/recruiter/manager/evaluator/
# reporter) the manager is the only one whose context grows with the
# number of sub-agent invocations: every transfer-tool call leaves a full
# ToolMessage behind, and large coding/hypothesis outputs accumulate
# linearly. For Tier-1 API users this can blow the TPM ceiling or the
# context window long before the recursion limit fires.
#
# We compress on the *transient* message list we pass to the model — we
# never write the compressed view back into the graph state. That way the
# UI trace panel keeps every full message, exports stay faithful, and
# only what the manager re-reads on each hop shrinks.

# Keep at most this many of the most recent sub-agent ToolMessages in full.
_MANAGER_KEEP_RECENT_SUBAGENT_RESULTS = 1

# When truncating older sub-agent ToolMessages, keep this many chars from
# the head and tail and replace the middle with an explicit marker.
_TRUNCATE_HEAD_CHARS = 800
_TRUNCATE_TAIL_CHARS = 400
_TRUNCATE_MIN_CHARS = _TRUNCATE_HEAD_CHARS + _TRUNCATE_TAIL_CHARS + 80


def _truncate_middle(text: str, name: str) -> str:
    """Replace the middle of *text* with a marker if it is long enough to compress."""
    if len(text) <= _TRUNCATE_MIN_CHARS:
        return text
    head = text[:_TRUNCATE_HEAD_CHARS]
    tail = text[-_TRUNCATE_TAIL_CHARS:]
    omitted = len(text) - _TRUNCATE_HEAD_CHARS - _TRUNCATE_TAIL_CHARS
    return (
        f"{head}\n"
        f"...\n"
        f"[{name} output truncated: {omitted} characters omitted "
        f"to stay under the context limit; full output remains visible "
        f"in the trace panel]\n"
        f"...\n"
        f"{tail}"
    )


def compress_for_manager(messages: List[BaseMessage]) -> List[BaseMessage]:
    """Return a copy of *messages* with old sub-agent ToolMessages truncated.

    The most recent ``_MANAGER_KEEP_RECENT_SUBAGENT_RESULTS`` sub-agent transfer ToolMessages are preserved verbatim;
    earlier ones are head-plus-tail truncated. Non-tool messages and main-pipeline tool messages
    (planner/recruiter/manager/evaluator/reporter own tools) are passed through unchanged.
    """
    # Identify which ToolMessages correspond to sub-agent transfers.
    # Convention used elsewhere in the codebase:
    #   sub-agent transfer tools are named "<agent_id>_transfer_tool".
    indices: List[int] = []
    for i, msg in enumerate(messages):
        if not isinstance(msg, ToolMessage):
            continue
        if str(msg.name or "").endswith("_transfer_tool"):
            indices.append(i)

    if len(indices) <= _MANAGER_KEEP_RECENT_SUBAGENT_RESULTS:
        return messages

    to_truncate = set(indices[:-_MANAGER_KEEP_RECENT_SUBAGENT_RESULTS])

    compressed: List[BaseMessage] = []
    for i, msg in enumerate(messages):
        if i not in to_truncate:
            compressed.append(msg)
            continue
        original_text = content_to_text(msg.content)
        new_text = _truncate_middle(original_text, str(msg.name or "sub-agent"))
        if new_text is original_text or new_text == original_text:
            compressed.append(msg)
            continue
        # Re-emit the ToolMessage with shortened content; keep all metadata.
        compressed.append(
            ToolMessage(
                content=new_text,
                tool_call_id=msg.tool_call_id,
                name=msg.name,
                id=msg.id,
                status=getattr(msg, "status", None) or "success",
            )
        )
    return compressed


# ---------------------------------------------------------------------------
# Per-agent message filters
# ---------------------------------------------------------------------------
#
# Each main pipeline agent only needs a subset of the shared message history.
# These filters project the full list down to the relevant slice *before* the
# LLM call, without mutating graph state — identical in spirit to the manager
# compression above but structural rather than size-based.


def _last_index_of_final(messages: List[BaseMessage], agent_name: str) -> Optional[int]:
    """Index of the last AIMessage from *agent_name* that has no tool calls.

    This corresponds to the agent's final output (plan, assignments, etc.)
    after all tool-calling rounds have completed.
    """
    for i in range(len(messages) - 1, -1, -1):
        msg = messages[i]
        if (
            isinstance(msg, AIMessage)
            and getattr(msg, "name", "") == agent_name
            and not getattr(msg, "tool_calls", [])
        ):
            return i
    return None


def filter_for_recruiter(messages: List[BaseMessage]) -> List[BaseMessage]:
    """Recruiter sees: user query + planner's final plan output only.

    Strips the planner's intermediate tool calls (template reads, globs, etc.).
    """
    result = [msg for msg in messages if isinstance(msg, HumanMessage)]
    idx = _last_index_of_final(messages, "planner_agent")
    if idx is not None:
        result.append(messages[idx])
    return result


def filter_for_execution_phase(messages: List[BaseMessage]) -> List[BaseMessage]:
    """Manager / Evaluator / Reporter see: user query, finalized plan
    (planner final + recruiter final), and all post-recruiter messages.

    Strips planner and recruiter intermediate tool-calling turns.  The
    post-recruiter slice naturally grows as the manager executes steps,
    and later includes the evaluator's assessment for the reporter.
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
