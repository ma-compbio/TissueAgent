"""A sub-agent that blows its recursion budget must not kill the whole run.

When an inner coding sub-agent hits ``GraphRecursionError``, that exception used
to propagate out through ``retry_step`` and crash the manager node — no
evaluation, no report, even when partial artifacts were already on disk. The
manager's transfer-tool wrapper now catches it and returns a partial-result
message that names what survived on disk.
"""

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from langgraph.errors import GraphRecursionError  # noqa: E402

from agents.manager_agent import tools as mtools  # noqa: E402
from server.plan_store import PlanStep  # noqa: E402


class _ExplodingTool:
    """Stand-in transfer tool that always exhausts its recursion budget."""

    def invoke(self, _args):
        raise GraphRecursionError("Recursion limit of 160 reached")


def test_recursion_error_is_converted_not_raised(tmp_path, monkeypatch):
    monkeypatch.setattr(mtools, "run_heuristic_validation", lambda *a, **k: (None, None, ""))

    step = PlanStep(
        id=3,
        title="Render figure",
        assigned_agent="coding_agent",
        expected_artifacts=["outputs/panel_A.png"],
    )
    out = mtools._invoke_via_transfer_tool(
        step, "make the figure", {"coding_agent": _ExplodingTool()}
    )
    assert isinstance(out, str)
    assert "BUDGET EXHAUSTED" in out
    assert "step 3" in out


def test_handoff_reports_surviving_artifacts(tmp_path, monkeypatch):
    # Point DATA_DIR at a temp workspace and drop one of the two expected files.
    # ``_recursion_handoff_message`` does ``from config import DATA_DIR`` at call
    # time, so patching the module attribute is picked up.
    import config

    monkeypatch.setattr(config, "DATA_DIR", tmp_path)

    (tmp_path / "outputs").mkdir()
    (tmp_path / "outputs" / "done.png").write_bytes(b"x")

    step = PlanStep(
        id=5,
        title="Two outputs",
        assigned_agent="coding_agent",
        expected_artifacts=["outputs/done.png", "outputs/missing.png"],
    )
    msg = mtools._recursion_handoff_message(step)
    assert "outputs/done.png" in msg
    assert "outputs/missing.png" not in msg


def test_handoff_when_nothing_produced(tmp_path, monkeypatch):
    import config

    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    step = PlanStep(id=7, title="Nothing", assigned_agent="coding_agent",
                    expected_artifacts=["outputs/x.png"])
    msg = mtools._recursion_handoff_message(step)
    assert "None of the expected artifacts were produced" in msg


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-q"]))
