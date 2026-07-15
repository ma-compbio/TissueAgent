r"""Tests for the Milestone 4 copilot resume protocol in chat.py.

The graph itself is not exercised — these tests patch ``_launch_run`` and
focus on the dispatcher logic: gate validation, plan edits being
persisted, feedback messages being appended, and cancel cleaning up.

Patch ``_launch_run``, not ``_run_graph``: every handler calls the former,
which detaches the latter via ``asyncio.create_task`` and passes its args
positionally. Patching ``_run_graph`` means nothing is ever awaited and
``call_args.kwargs`` is always empty — so ``kwargs.get("graph_input") is None``
passes whether or not the handler ran at all.

Run from the repo root::

    cd /Users/wenduoc/TissueAgent && OPENAI_API_KEY=dummy \\
        .venv/bin/python tests/test_resume_protocol.py
"""

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import patch


# Make sure OPENAI_API_KEY exists so the import chain (searcher agent
# constructs an OpenAI client at import time) succeeds.
os.environ.setdefault("OPENAI_API_KEY", "dummy")

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


from server.session_manager import session  # noqa: E402
from server.plan_store import (  # noqa: E402
    PlanDocument,
    PlanStep,
    plan_store,
)
from server.routes import chat as chat_module  # noqa: E402


def _reset_session_to_paused(label: str) -> None:
    """Put the session into the state a copilot pause would leave it in."""
    session.reset()
    session.mode = "copilot"
    session.paused_at = label
    session.is_running = True


def _seed_plan(status: str) -> None:
    plan_store.reset()
    plan_store.write(PlanDocument(
        status=status,  # type: ignore[arg-type]
        user_request="Test plan",
        steps=[PlanStep(id=1, title="A", description="d", reasoning="r")],
    ))


class FakeWS:
    """Captures messages send_json would deliver to the client."""

    def __init__(self) -> None:
        """Initialise with an empty sent-messages list."""
        self.sent: list[dict] = []

    async def send_json(self, payload: dict) -> None:
        """Capture a JSON payload as if sent to the client."""
        self.sent.append(payload)


def _types_sent(ws: FakeWS) -> list[str]:
    return [m.get("type") for m in ws.sent]


def run(coro):
    """Run a coroutine synchronously using asyncio.run."""
    return asyncio.run(coro)


# ---------------------------------------------------------------------------


def test_plan_approved_validates_gate_and_calls_run_graph():
    """Test that plan approval validates the pause gate and calls _run_graph."""
    _reset_session_to_paused("before_recruiter")
    _seed_plan("awaiting_plan_review")
    ws = FakeWS()
    with patch.object(chat_module, "_launch_run") as mock_launch:
        run(chat_module._handle_resume(ws, expected_pause="before_recruiter"))
        mock_launch.assert_called_once()
        # graph_input=None means "resume from the checkpoint", as opposed to the
        # feedback paths which re-invoke from the top with the full state.
        assert "graph_input" in mock_launch.call_args.kwargs, (
            "assert the kwarg is actually present — kwargs.get() returning None "
            "would pass whether or not the handler ever called through."
        )
        assert mock_launch.call_args.kwargs["graph_input"] is None
    assert session.paused_at is None
    print("OK: plan_approved_validates_gate_and_calls_run_graph")


def test_wrong_gate_for_assignments_approved():
    """Test that providing the wrong pause gate rejects the resume and sends an error."""
    _reset_session_to_paused("before_recruiter")
    ws = FakeWS()
    with patch.object(chat_module, "_launch_run") as mock_run:
        run(chat_module._handle_resume(ws, expected_pause="before_manager"))
        mock_run.assert_not_called()
    assert "run_error" in _types_sent(ws)
    assert any(m.get("error_type") == "WrongPauseGate" for m in ws.sent)
    assert session.paused_at == "before_recruiter"  # untouched
    print("OK: wrong_gate_for_assignments_approved")


def test_not_paused_rejects():
    """Test that a resume attempt when not paused is rejected with a NotPaused error."""
    session.reset()
    session.paused_at = None
    ws = FakeWS()
    with patch.object(chat_module, "_launch_run") as mock_run:
        run(chat_module._handle_resume(ws, expected_pause="before_recruiter"))
        mock_run.assert_not_called()
    assert any(m.get("error_type") == "NotPaused" for m in ws.sent)
    print("OK: not_paused_rejects")


def test_plan_edited_persists_markdown_and_resumes():
    """Test that a valid plan edit is persisted and the graph is resumed."""
    _reset_session_to_paused("before_recruiter")
    _seed_plan("awaiting_plan_review")
    ws = FakeWS()

    edited = """# Plan

```yaml
status: awaiting_plan_review
user_request: edited request
```

## Step 1 — Renamed step

```yaml
status: pending
assigned_agent: null
assigned_rationale: null
expected_artifacts: []
actual_outputs: []
```

**Description:** new desc
"""
    with patch.object(chat_module, "_launch_run") as mock_run:
        run(chat_module._handle_plan_edited(ws, {"markdown": edited}))
        mock_run.assert_called_once()

    # The new markdown should be on disk with user stamp.
    doc = plan_store.read()
    assert doc.steps[0].title == "Renamed step"
    assert doc.last_edited_by == "user"
    assert doc.last_edited_at is not None
    # plan_updated event was sent before resume.
    assert "plan_updated" in _types_sent(ws)
    assert session.paused_at is None
    print("OK: plan_edited_persists_markdown_and_resumes")


def test_plan_edited_rejects_malformed_without_resuming():
    """Test that a malformed plan edit is rejected without resuming or altering state."""
    _reset_session_to_paused("before_recruiter")
    _seed_plan("awaiting_plan_review")
    before = plan_store.read_markdown()
    ws = FakeWS()
    with patch.object(chat_module, "_launch_run") as mock_run:
        run(chat_module._handle_plan_edited(ws, {"markdown": "not a real plan"}))
        mock_run.assert_not_called()
    after = plan_store.read_markdown()
    assert before == after, "plan file was clobbered by a malformed edit"
    assert any(m.get("error_type") == "PlanEditError" for m in ws.sent)
    # Pause stays open so the user can try again.
    assert session.paused_at == "before_recruiter"
    print("OK: plan_edited_rejects_malformed_without_resuming")


def test_assignments_edited_uses_before_manager_gate():
    """Same shape as plan_edited but a different pause gate."""
    _reset_session_to_paused("before_manager")
    _seed_plan("awaiting_assignment_review")
    edited = """# Plan

```yaml
status: awaiting_assignment_review
user_request: x
```

## Step 1 — Step A

```yaml
status: pending
assigned_agent: coding_agent
assigned_rationale: changed by user
expected_artifacts: []
actual_outputs: []
```

**Description:** d
"""
    ws = FakeWS()
    with patch.object(chat_module, "_launch_run") as mock_run:
        run(chat_module._handle_assignments_edited(ws, {"markdown": edited}))
        mock_run.assert_called_once()
    doc = plan_store.read()
    assert doc.steps[0].assigned_agent == "coding_agent"
    print("OK: assignments_edited_uses_before_manager_gate")


def test_assignments_edited_rejects_wrong_gate():
    """Test that editing assignments at the wrong pause gate sends a WrongPauseGate error."""
    _reset_session_to_paused("before_recruiter")  # wrong gate for assignments
    _seed_plan("awaiting_plan_review")
    ws = FakeWS()
    with patch.object(chat_module, "_launch_run") as mock_run:
        run(chat_module._handle_assignments_edited(ws, {"markdown": "anything"}))
        mock_run.assert_not_called()
    assert any(m.get("error_type") == "WrongPauseGate" for m in ws.sent)
    print("OK: assignments_edited_rejects_wrong_gate")


def test_plan_feedback_appends_message_cycles_thread_resets_plan():
    """Test that plan feedback appends a message, cycles the thread, and resets the plan."""
    _reset_session_to_paused("before_recruiter")
    _seed_plan("awaiting_plan_review")
    original_thread = session.thread_id
    ws = FakeWS()
    with patch.object(chat_module, "_launch_run") as mock_launch:
        run(chat_module._handle_plan_feedback(ws, {"text": "narrow to T cells"}))
        mock_launch.assert_called_once()
        # Re-invoked from the top (graph_input=session.agent_state, not None)
        assert mock_launch.call_args.kwargs["graph_input"] is session.agent_state

    # A new HumanMessage was appended with the feedback content.
    last_msg = session.agent_state["messages"][-1]
    assert "narrow to T cells" in str(last_msg.content)
    # Thread cycled.
    assert session.thread_id != original_thread
    # Plan was reset (no plan.md on disk anymore).
    assert not plan_store.path.is_file()
    # Pause cleared.
    assert session.paused_at is None
    print("OK: plan_feedback_appends_message_cycles_thread_resets_plan")


def test_feedback_rejects_empty_text():
    """Test that empty or whitespace-only feedback is rejected with an EmptyFeedback error."""
    _reset_session_to_paused("before_recruiter")
    _seed_plan("awaiting_plan_review")
    ws = FakeWS()
    with patch.object(chat_module, "_launch_run") as mock_run:
        run(chat_module._handle_plan_feedback(ws, {"text": "   "}))
        mock_run.assert_not_called()
    assert any(m.get("error_type") == "EmptyFeedback" for m in ws.sent)
    # Pause untouched so user can retry.
    assert session.paused_at == "before_recruiter"
    print("OK: feedback_rejects_empty_text")


def test_assignments_feedback_also_rewinds_to_planner():
    """Per Milestone 4 design both feedback paths re-enter at the planner."""
    _reset_session_to_paused("before_manager")
    _seed_plan("awaiting_assignment_review")
    ws = FakeWS()
    with patch.object(chat_module, "_launch_run") as mock_launch:
        run(chat_module._handle_assignments_feedback(ws, {"text": "use spot agent"}))
        mock_launch.assert_called_once()
        assert mock_launch.call_args.kwargs["graph_input"] is session.agent_state
    last_msg = session.agent_state["messages"][-1]
    assert "use spot agent" in str(last_msg.content)
    print("OK: assignments_feedback_also_rewinds_to_planner")


def test_run_cancelled_clears_state_and_acks():
    """Test that cancelling a run clears session state and sends a run_cancelled ack."""
    _reset_session_to_paused("before_recruiter")
    _seed_plan("awaiting_plan_review")
    original_thread = session.thread_id
    ws = FakeWS()
    run(chat_module._handle_run_cancelled(ws))
    assert session.paused_at is None
    assert session.is_running is False
    assert session.thread_id != original_thread
    assert not plan_store.path.is_file()
    assert "run_cancelled" in _types_sent(ws)
    print("OK: run_cancelled_clears_state_and_acks")


def test_run_cancelled_with_nothing_to_cancel_still_acks():
    """Test that cancelling when nothing is running still sends a run_cancelled ack."""
    session.reset()
    session.paused_at = None
    session.is_running = False
    ws = FakeWS()
    run(chat_module._handle_run_cancelled(ws))
    assert "run_cancelled" in _types_sent(ws)
    print("OK: run_cancelled_with_nothing_to_cancel_still_acks")


if __name__ == "__main__":
    test_plan_approved_validates_gate_and_calls_run_graph()
    test_wrong_gate_for_assignments_approved()
    test_not_paused_rejects()
    test_plan_edited_persists_markdown_and_resumes()
    test_plan_edited_rejects_malformed_without_resuming()
    test_assignments_edited_uses_before_manager_gate()
    test_assignments_edited_rejects_wrong_gate()
    test_plan_feedback_appends_message_cycles_thread_resets_plan()
    test_feedback_rejects_empty_text()
    test_assignments_feedback_also_rewinds_to_planner()
    test_run_cancelled_clears_state_and_acks()
    test_run_cancelled_with_nothing_to_cancel_still_acks()
    print("\nAll resume protocol tests PASS")
