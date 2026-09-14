"""Helpers for deriving replan state from durable orchestration history."""

from typing import Any


def effective_replan_count(state: dict[str, Any]) -> int:
    """Return the strongest available count of completed replan verdicts.

    ``replan_count`` is the primary bookkeeping channel. The evaluator verdicts in
    ``messages`` are an independent, durable record, so use them as a fallback when a
    caller or checkpoint omits the counter. This keeps the replan prompt and cap
    correct even while resuming older state that predates the counter channel.
    """
    persisted = int(state.get("replan_count", 0) or 0)
    observed = 0
    for message in state.get("messages", []):
        if getattr(message, "name", None) != "evaluator_agent":
            continue
        content = getattr(message, "content", "")
        if not isinstance(content, str):
            continue
        head = content.strip().splitlines()[0].upper() if content.strip() else ""
        if head.startswith("ROUTE: REPLAN"):
            observed += 1
    return max(persisted, observed)
