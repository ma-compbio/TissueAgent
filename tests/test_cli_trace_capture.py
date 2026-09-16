"""Tests that a headless CLI run captures sub-agent transcripts.

Run from the repo root::

    cd src && python ../tests/test_cli_trace_capture.py

``subagent_state`` events are pushed onto the UI event queue by the manager's
tool_node. In the web app the websocket route records them; headless, only
``cli._drain_trace`` sees them — and if it drops them, ``save_session`` writes
``subagent_states: {}`` and the coding agent's per-cell history exists nowhere
but the printed stream.

Deliberately pytest-free (matching the other tests in this directory). No graph,
no LLM, no kernel: the drain loop is fed a queue directly.
"""

import sys
import threading
from queue import Queue

import cli
from langchain_core.messages import AIMessage, HumanMessage

_failures: list[str] = []


def check(cond: bool, msg: str) -> None:
    if cond:
        print(f"  ok: {msg}")
    else:
        print(f"  FAIL: {msg}")
        _failures.append(msg)


def _coding_agent_state() -> dict:
    """A coding-agent final state: one executed cell and its output."""
    call = AIMessage(
        content="",
        tool_calls=[{"name": "python", "args": {"code": "adata.shape"}, "id": "py1"}],
    )
    return {"messages": [HumanMessage(content="load the data"), call, HumanMessage(content="Python Output:\n(2700, 32738)")]}


def _drain(events: list, quiet: bool) -> dict:
    """Run the drain loop over *events* to completion; return captured states."""
    queue: Queue = Queue()
    for event in events:
        queue.put(event)
    captured: dict = {}
    stop = threading.Event()
    thread = threading.Thread(
        target=cli._drain_trace, args=(queue, stop, quiet, captured), daemon=True
    )
    thread.start()
    stop.set()
    thread.join(timeout=5)
    check(not thread.is_alive(), f"drain loop terminated (quiet={quiet})")
    return captured


def _state_event(tool_id: str, agent_name: str = "coding") -> tuple:
    return (
        "subagent_state",
        {
            "tool_id": tool_id,
            "agent_name": agent_name,
            "final_state": _coding_agent_state(),
            "invocation_id": f"inv-{tool_id}",
        },
    )


def test_subagent_state_captured():
    print("test_subagent_state_captured")
    captured = _drain([("message", AIMessage(content="hi")), _state_event("tool-1")], quiet=False)
    check(list(captured) == ["tool-1"], "captured under the wrapping ToolMessage id")
    agent_name, final_state, invocation_id = captured["tool-1"]
    check(agent_name == "coding", "agent name recorded")
    check(invocation_id == "inv-tool-1", "invocation id recorded")
    check(len(final_state["messages"]) == 3, "the whole sub-agent transcript is kept")
    check(
        final_state["messages"][1].tool_calls[0]["args"]["code"] == "adata.shape",
        "the executed code survives in the transcript",
    )


def test_capture_is_not_suppressed_by_quiet():
    print("test_capture_is_not_suppressed_by_quiet")
    # --quiet / --json suppress printing, not recording. Before the fix the
    # quiet branch skipped every event, so batch runs saved nothing.
    captured = _drain([_state_event("tool-1")], quiet=True)
    check(list(captured) == ["tool-1"], "sub-agent state captured under --quiet/--json too")


def test_multiple_and_duplicate_invocations():
    print("test_multiple_and_duplicate_invocations")
    captured = _drain(
        [_state_event("tool-1"), _state_event("tool-2", "hypothesis"), _state_event("tool-1")],
        quiet=False,
    )
    check(sorted(captured) == ["tool-1", "tool-2"], "one entry per dispatched step")
    check(captured["tool-2"][0] == "hypothesis", "non-coding sub-agents captured too")


def test_malformed_events_do_not_crash():
    print("test_malformed_events_do_not_crash")
    captured = _drain(
        [
            ("subagent_state", {"agent_name": "coding"}),  # missing tool_id
            "not-a-tuple",
            ("message", None),
            _state_event("tool-1"),
        ],
        quiet=False,
    )
    check(list(captured) == ["tool-1"], "a malformed event is skipped, later ones still land")


def test_states_are_savable():
    print("test_states_are_savable")
    from server.utils import _strip_images_from_subagent_states

    captured = _drain([_state_event("tool-1")], quiet=False)
    cleaned = _strip_images_from_subagent_states(captured)
    messages = cleaned["tool-1"][1]["messages"]
    check(all(isinstance(m, dict) for m in messages), "save_session serializes the captured shape")
    check(len(cleaned["tool-1"]) == 3, "the (agent, state, invocation_id) triple round-trips")


def main() -> int:
    test_subagent_state_captured()
    test_capture_is_not_suppressed_by_quiet()
    test_multiple_and_duplicate_invocations()
    test_malformed_events_do_not_crash()
    test_states_are_savable()

    print()
    if _failures:
        print(f"{len(_failures)} FAILURE(S):")
        for f in _failures:
            print(f"  - {f}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
