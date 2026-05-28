"""Verify LangGraph interrupt + resume mechanics behave as we depend on.

This is a pure-LangGraph test — it does NOT exercise TissueAgent's
production graph (which requires API keys). The goal is to lock in our
assumption that:

  1. Compiling with a checkpointer + invoking with ``interrupt_before``
     stops the graph before the named node.
  2. ``compiled.get_state(config).next`` reports the pending node so the
     server can map it to a pause label.
  3. ``compiled.invoke(None, config)`` resumes from the checkpoint and
     runs to completion.
  4. Without ``interrupt_before`` (autopilot), the same graph runs
     straight through.

Run from the repo root::

    cd src && python ../tests/test_interrupt_mechanics.py
"""

import sys
from pathlib import Path
from typing import Annotated, TypedDict

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from langgraph.checkpoint.memory import MemorySaver  # noqa: E402
from langgraph.graph import END, START, StateGraph  # noqa: E402


class S(TypedDict, total=False):
    log: Annotated[list, lambda a, b: (a or []) + (b or [])]


def _build_graph():
    g = StateGraph(S)
    g.add_node("planner_agent", lambda s: {"log": ["planner"]})
    g.add_node("recruiter_agent", lambda s: {"log": ["recruiter"]})
    g.add_node("manager_agent", lambda s: {"log": ["manager"]})
    g.add_edge(START, "planner_agent")
    g.add_edge("planner_agent", "recruiter_agent")
    g.add_edge("recruiter_agent", "manager_agent")
    g.add_edge("manager_agent", END)
    return g.compile(checkpointer=MemorySaver())


def test_autopilot_runs_through():
    g = _build_graph()
    cfg = {"configurable": {"thread_id": "t1"}}
    result = g.invoke({"log": []}, cfg)
    assert result["log"] == ["planner", "recruiter", "manager"], result
    snap = g.get_state(cfg)
    assert snap.next == (), snap.next
    print("OK: autopilot_runs_through")


def test_copilot_pauses_before_recruiter():
    g = _build_graph()
    cfg = {"configurable": {"thread_id": "t2"}}
    g.invoke({"log": []}, cfg, interrupt_before=["recruiter_agent", "manager_agent"])
    snap = g.get_state(cfg)
    assert snap.next == ("recruiter_agent",), snap.next
    assert snap.values["log"] == ["planner"], snap.values
    print("OK: copilot_pauses_before_recruiter")


def test_resume_advances_to_next_pause():
    """First resume (None input) runs recruiter, pauses before manager."""
    g = _build_graph()
    cfg = {"configurable": {"thread_id": "t3"}}
    g.invoke({"log": []}, cfg, interrupt_before=["recruiter_agent", "manager_agent"])
    g.invoke(None, cfg, interrupt_before=["recruiter_agent", "manager_agent"])
    snap = g.get_state(cfg)
    assert snap.next == ("manager_agent",), snap.next
    assert snap.values["log"] == ["planner", "recruiter"], snap.values
    print("OK: resume_advances_to_next_pause")


def test_second_resume_completes():
    g = _build_graph()
    cfg = {"configurable": {"thread_id": "t4"}}
    g.invoke({"log": []}, cfg, interrupt_before=["recruiter_agent", "manager_agent"])
    g.invoke(None, cfg, interrupt_before=["recruiter_agent", "manager_agent"])
    g.invoke(None, cfg, interrupt_before=["recruiter_agent", "manager_agent"])
    snap = g.get_state(cfg)
    assert snap.next == (), snap.next
    assert snap.values["log"] == ["planner", "recruiter", "manager"], snap.values
    print("OK: second_resume_completes")


def test_fresh_thread_id_is_isolated():
    g = _build_graph()
    cfg_a = {"configurable": {"thread_id": "tA"}}
    cfg_b = {"configurable": {"thread_id": "tB"}}
    g.invoke({"log": []}, cfg_a, interrupt_before=["recruiter_agent", "manager_agent"])
    g.invoke({"log": []}, cfg_b)  # autopilot on B
    snap_a = g.get_state(cfg_a)
    snap_b = g.get_state(cfg_b)
    assert snap_a.next == ("recruiter_agent",)
    assert snap_b.next == ()
    print("OK: fresh_thread_id_is_isolated")


if __name__ == "__main__":
    test_autopilot_runs_through()
    test_copilot_pauses_before_recruiter()
    test_resume_advances_to_next_pause()
    test_second_resume_completes()
    test_fresh_thread_id_is_isolated()
    print("\nAll interrupt mechanics tests PASS")
