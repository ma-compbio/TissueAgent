"""Regression test for the top-level graph's state schema.

The main graph is compiled with a state schema. If a node writes a key via
``Command(update=...)`` that the schema does NOT declare as a channel,
LangGraph silently drops the write — no error, no warning.

That is exactly how every orchestration cap became inert. The main graph was
built as ``StateGraph(MessagesState)``, which declares only ``messages``, while
the evaluator wrote ``replan_count``. The write vanished, so every cycle read
``0``, ``new_count`` was always ``1``, ``MAX_REPLANS`` never tripped, and a run
that kept failing evaluation replanned until it hit the graph recursion limit
and returned nothing. The BMB-Expr run of 2026-08-05 has one such run (hb017
seed 2: five REPLAN verdicts, ``replans_triggered: 0``, terminal state
``recursion-limit``) and six more whose replans went uncounted.

The fix is ``OrchestratorState``, which declares the counters. These tests pin
the *class of bug* rather than the one field: the schema must keep declaring
every key the state-update functions actually write.

Deliberately pytest-free (matching the other tests in this directory). No LLM
and no kernel — the graph here is a stub built on the real schema, because
building the real graph pulls in the sandbox.

Run from the repo root::

    OPENAI_API_KEY=dummy python tests/test_orchestrator_state_channels.py
"""

import ast
import os
import sys
from pathlib import Path

os.environ.setdefault("OPENAI_API_KEY", "dummy")

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# Counters whose loss silently disables a cap. Named explicitly so deleting one
# from the schema fails here instead of at the next benchmark run.
REQUIRED_CHANNELS = {
    "replan_count",
    "replan_history",
    "recruiter_retry_count",
    "planner_retry_count",
}


def _declared_channels() -> set:
    from graph.node_factories import OrchestratorState

    return set(getattr(OrchestratorState, "__annotations__", {}))


def test_schema_declares_the_orchestration_counters() -> None:
    declared = _declared_channels()
    missing = REQUIRED_CHANNELS - declared
    assert not missing, (
        f"OrchestratorState is missing channel(s) {sorted(missing)}. A counter that "
        "is not a declared channel is silently dropped on write, which makes its cap "
        "inert — see this module's docstring."
    )
    print("OK: schema_declares_the_orchestration_counters")


def test_main_graph_is_built_on_the_orchestrator_schema() -> None:
    """``create_tissueagent_graph`` must pass OrchestratorState to StateGraph.

    Checked by reading the source rather than by building the graph: the real
    builder reaches for the sandbox and takes minutes, and the thing under test
    is a single construction argument.
    """
    tree = ast.parse((SRC / "graph" / "graph.py").read_text())
    builder = next(
        (
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name == "create_tissueagent_graph"
        ),
        None,
    )
    assert builder is not None, "create_tissueagent_graph not found in graph/graph.py"

    # Sub-agents get their own StateGraph(AgentState) inside this same function,
    # so target the one whose result the builder returns — the top-level graph.
    returned = next(
        (
            n.value.id
            for n in ast.walk(builder)
            if isinstance(n, ast.Return) and isinstance(n.value, ast.Name)
        ),
        None,
    )
    assert returned, "create_tissueagent_graph does not return a plain name"

    schemas = [
        (n.value.args[0].id if n.value.args and isinstance(n.value.args[0], ast.Name) else None)
        for n in ast.walk(builder)
        if isinstance(n, ast.Assign)
        and isinstance(n.value, ast.Call)
        and isinstance(n.value.func, ast.Name)
        and n.value.func.id == "StateGraph"
        and any(isinstance(t, ast.Name) and t.id == returned for t in n.targets)
    ]
    assert schemas, f"no StateGraph(...) assigned to the returned name '{returned}'"
    assert all(s == "OrchestratorState" for s in schemas), (
        f"main graph built with {schemas} — it must use OrchestratorState. Bare "
        "MessagesState declares only 'messages' and drops every counter write."
    )
    print("OK: main_graph_is_built_on_the_orchestrator_schema")


def test_every_state_update_write_is_a_declared_channel() -> None:
    """No state-update function may write a key the schema doesn't declare.

    This is the guard that would have caught the original bug: ``replan_count``
    was written by the evaluator and declared nowhere.
    """
    declared = _declared_channels() | {"messages"}
    offenders = []
    for path in (SRC / "graph" / "graph.py", SRC / "graph" / "plan_output.py"):
        tree = ast.parse(path.read_text())
        for fn in ast.walk(tree):
            if not isinstance(fn, ast.FunctionDef) or "state_update" not in fn.name:
                continue
            for node in ast.walk(fn):
                if not isinstance(node, ast.Return) or not isinstance(node.value, ast.Dict):
                    continue
                for key in node.value.keys:
                    if isinstance(key, ast.Constant) and key.value not in declared:
                        offenders.append(f"{path.name}:{fn.name} writes '{key.value}'")
    assert not offenders, (
        "state-update function(s) write undeclared channels — LangGraph will drop "
        f"these writes silently: {offenders}. Declare them on OrchestratorState."
    )
    print("OK: every_state_update_write_is_a_declared_channel")


def test_undeclared_writes_are_dropped_declared_ones_persist() -> None:
    """The mechanism itself, both directions.

    The bad case documents *why* the schema matters: it is not an error, it is a
    silent drop. If LangGraph ever starts raising instead, this test says so.
    """
    from langchain_core.messages import AIMessage
    from langgraph.graph import END, START, MessagesState, StateGraph
    from langgraph.types import Command

    from graph.node_factories import OrchestratorState

    def writer(state):
        return Command(
            goto=END,
            update={"messages": [AIMessage("v")], "replan_count": 7, "replan_history": ["t0"]},
        )

    def build(schema):
        g = StateGraph(schema)
        g.add_node("w", writer)
        g.add_edge(START, "w")
        return g.compile()

    dropped = build(MessagesState).invoke({"messages": []})
    assert "replan_count" not in dropped, (
        "bare MessagesState unexpectedly kept 'replan_count' — LangGraph's handling of "
        "undeclared channels changed; re-read this module's docstring before trusting it."
    )

    kept = build(OrchestratorState).invoke({"messages": []})
    assert kept.get("replan_count") == 7, f"declared channel not persisted: {kept!r}"
    assert kept.get("replan_history") == ["t0"], f"declared channel not persisted: {kept!r}"
    print("OK: undeclared_writes_are_dropped_declared_ones_persist")


def test_counter_accumulates_across_visits() -> None:
    """A counter must read back its prior value on the next visit.

    Persisting one write is not enough — the cap compares ``prior + 1`` against
    the limit, so what matters is that the second visit sees ``1`` and not ``0``.
    Under the bug every visit read ``0``, so ``new_count`` was permanently ``1``
    and no limit above 1 could ever trip.
    """
    from langchain_core.messages import AIMessage
    from langgraph.graph import END, START, StateGraph
    from langgraph.types import Command

    from graph.node_factories import OrchestratorState

    LIMIT = 2
    seen = []

    def evaluator(state):
        prior = int(state.get("replan_count", 0) or 0)
        new_count = prior + 1
        seen.append(new_count)
        return Command(
            goto=END if new_count > LIMIT else "evaluator",
            update={"messages": [AIMessage("verdict")], "replan_count": new_count},
        )

    g = StateGraph(OrchestratorState)
    g.add_node("evaluator", evaluator)
    g.add_edge(START, "evaluator")
    # Bounded well under the real RECURSION_LIMIT: if the counter stops
    # accumulating, this raises instead of spinning — the same way the real run
    # died at the graph recursion limit.
    final = g.compile().invoke({"messages": []}, {"recursion_limit": 10})

    assert seen == [1, 2, 3], f"counter did not accumulate across visits: saw {seen}"
    assert final.get("replan_count") == LIMIT + 1, f"final count wrong: {final.get('replan_count')}"
    print("OK: counter_accumulates_across_visits")


def main() -> int:
    test_schema_declares_the_orchestration_counters()
    test_main_graph_is_built_on_the_orchestrator_schema()
    test_every_state_update_write_is_a_declared_channel()
    test_undeclared_writes_are_dropped_declared_ones_persist()
    test_counter_accumulates_across_visits()
    print("\nAll orchestrator state channel tests PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
