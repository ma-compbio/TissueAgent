"""Regression test for the coding/hypothesis sub-graph state.

The parent graph now has a checkpointer (Milestone 3). When the manager
invokes a coding/hypothesis sub-graph from inside a tool node, LangGraph
propagates the parent's checkpointer config into the sub-invoke. That
means the sub-graph's state is also serialised — anything in the state
schema must be msgpack-friendly.

Both ``CodeActState`` and ``HypothesisState`` used to carry
``repl: PythonREPL`` in their state. ``PythonREPL`` is not
msgpack-serialisable, so a real coding-agent invocation crashed with::

    TypeError: Type is not msgpack serializable: PythonREPL

This test locks in the fix: ``repl`` has been moved out of state into a
closure-local holder.

``CodeActState`` itself no longer exists — the coding agent was refactored onto
the shared ``AgentState`` from ``graph.node_factories``. The invariant still
applies to whatever state the coding agent declares, so this asserts against the
class it actually uses rather than a name that has been deleted.

Run from the repo root::

    OPENAI_API_KEY=dummy .venv/bin/python tests/test_subagent_checkpoint_safety.py
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("OPENAI_API_KEY", "dummy")

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def test_coding_agent_state_is_checkpoint_safe() -> None:
    """The coding agent's state must carry nothing msgpack can't serialise.

    Formerly asserted against ``CodeActState``; that class is gone and the agent
    now builds its graph on the shared ``AgentState``. Read the state class off
    the module the agent imports, so a future rename fails loudly here instead of
    silently stopping the check.
    """
    import agents.agent_registry.coding_agent_cache.model as coding_model

    state_cls = coding_model.AgentState
    annotations = getattr(state_cls, "__annotations__", {})

    assert "repl" not in annotations, (
        f"{state_cls.__name__} must NOT declare 'repl' — that field would carry a "
        "PythonREPL into the parent's checkpointer and crash msgpack. "
        "Keep the REPL in a closure-local holder instead."
    )
    # The original bug was a non-serialisable *object* in state, not the name
    # 'repl' specifically. Pin the whole schema: every field must be a type
    # msgpack can round-trip.
    safe = (str, int, float, bool, list, dict, type(None))
    for field, annotation in annotations.items():
        if field == "messages":
            continue  # LangGraph serialises messages itself
        assert annotation in safe or getattr(annotation, "__origin__", None) in safe, (
            f"{state_cls.__name__}.{field}: {annotation!r} may not be msgpack-"
            "serialisable. Sub-graph state is checkpointed by the parent; keep "
            "non-serialisable objects in a closure instead."
        )
    print("OK: coding_agent_state_is_checkpoint_safe")


def test_hypothesis_state_has_no_repl() -> None:
    """Test that HypothesisState does not declare a repl field that would break msgpack."""
    from agents.agent_registry.hypothesis_agent.model import HypothesisState

    annotations = getattr(HypothesisState, "__annotations__", {})
    assert "repl" not in annotations, (
        "HypothesisState must NOT declare 'repl' for the same reason as "
        "CodeActState. The hypothesis agent persists its REPL across "
        "invocations via the closure-local repl_holder."
    )
    print("OK: hypothesis_state_has_no_repl")


def test_parent_checkpointer_does_not_choke_on_subgraph_state() -> None:
    """Synthetic repro of the original crash, plus the fix.

    Builds the smallest possible failure case: parent graph with a
    checkpointer, a tool node that invokes a sub-graph, and a sub-graph
    whose state schema contains a non-msgpack-serialisable object.

    With the object IN the state (bad) → invoke raises TypeError.
    With the object OUT of state, held in closure (good) → invoke
    succeeds.
    """
    from typing import Any
    from langgraph.graph import StateGraph, MessagesState, START, END
    from langgraph.checkpoint.memory import MemorySaver
    from langchain_core.tools import StructuredTool
    from langchain_core.messages import HumanMessage

    class NotSerialisable:
        pass

    # --- BAD: object in state ------------------------------------------------
    class BadState(MessagesState):
        thing: Any

    bad_sub = StateGraph(BadState)
    bad_sub.add_node(
        "a",
        lambda s: {"messages": [HumanMessage("done")], "thing": NotSerialisable()},
    )
    bad_sub.add_edge(START, "a")
    bad_sub.add_edge("a", END)
    bad_sub_c = bad_sub.compile()

    def bad_tool_fn(prompt: str) -> str:
        bad_sub_c.invoke({"messages": [HumanMessage(prompt)]})
        return "ok"

    bad_tool = StructuredTool.from_function(
        func=bad_tool_fn, name="bad_tool", description="x"
    )

    def bad_parent_node(s):
        bad_tool.invoke({"prompt": "hi"})
        return {"messages": [HumanMessage("ok")]}

    bad_parent = StateGraph(MessagesState)
    bad_parent.add_node("p", bad_parent_node)
    bad_parent.add_edge(START, "p")
    bad_parent.add_edge("p", END)
    bad_parent_c = bad_parent.compile(checkpointer=MemorySaver())

    cfg = {"configurable": {"thread_id": "t_bad"}}
    try:
        bad_parent_c.invoke({"messages": []}, cfg)
    except TypeError as e:
        assert "msgpack" in str(e), e
    else:
        raise AssertionError(
            "Expected the bad case to raise TypeError about msgpack — if it "
            "doesn't, LangGraph's checkpoint propagation may have changed."
        )

    # --- GOOD: object in closure ---------------------------------------------
    holder: dict = {"thing": None}

    good_sub = StateGraph(MessagesState)

    def good_node(s):
        if holder["thing"] is None:
            holder["thing"] = NotSerialisable()
        return {"messages": [HumanMessage("done")]}

    good_sub.add_node("a", good_node)
    good_sub.add_edge(START, "a")
    good_sub.add_edge("a", END)
    good_sub_c = good_sub.compile()

    def good_tool_fn(prompt: str) -> str:
        good_sub_c.invoke({"messages": [HumanMessage(prompt)]})
        return "ok"

    good_tool = StructuredTool.from_function(
        func=good_tool_fn, name="good_tool", description="x"
    )

    def good_parent_node(s):
        good_tool.invoke({"prompt": "hi"})
        return {"messages": [HumanMessage("ok")]}

    good_parent = StateGraph(MessagesState)
    good_parent.add_node("p", good_parent_node)
    good_parent.add_edge(START, "p")
    good_parent.add_edge("p", END)
    good_parent_c = good_parent.compile(checkpointer=MemorySaver())

    cfg = {"configurable": {"thread_id": "t_good"}}
    good_parent_c.invoke({"messages": []}, cfg)
    assert holder["thing"] is not None, "closure should have captured the object"
    print("OK: parent_checkpointer_does_not_choke_on_subgraph_state")


if __name__ == "__main__":
    test_coding_agent_state_is_checkpoint_safe()
    test_hypothesis_state_has_no_repl()
    test_parent_checkpointer_does_not_choke_on_subgraph_state()
    print("\nAll subagent checkpoint safety tests PASS")
