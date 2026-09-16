"""Regression tests for durable targeted-replan bookkeeping."""

from langchain_core.messages import AIMessage, HumanMessage

from graph.replan_state import effective_replan_count


def _verdict(route: str) -> AIMessage:
    message = AIMessage(content=f"ROUTE: {route}\n\nassessment")
    message.name = "evaluator_agent"
    return message


def test_effective_replan_count_uses_persisted_channel() -> None:
    """The declared counter remains the primary source when present."""
    state = {"messages": [HumanMessage(content="task")], "replan_count": 2}
    assert effective_replan_count(state) == 2


def test_effective_replan_count_recovers_from_message_history() -> None:
    """Prior evaluator verdicts recover a missing or dropped counter."""
    state = {
        "messages": [_verdict("REPLAN"), _verdict("REPORT"), _verdict("REPLAN")],
        "replan_count": 0,
    }
    assert effective_replan_count(state) == 2


def test_effective_replan_count_does_not_double_count_sources() -> None:
    """The counter and history describe the same events, so take their maximum."""
    state = {"messages": [_verdict("REPLAN")], "replan_count": 1}
    assert effective_replan_count(state) == 1
