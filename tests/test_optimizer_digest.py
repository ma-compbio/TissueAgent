"""Session digest: deterministic compression of an archived run.

Uses the real archived CCC session (projects/2026-08-27_12-41-27) as a fixture
for the chat-only path, plus a synthetic session exercising metrics folding.
"""

import json
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"
REPO = SRC.parent
for _p in (str(SRC), str(REPO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from optimizer.session_digest import load_session_digest, render_digest  # noqa: E402

REAL_SESSION = REPO / "projects" / "2026-08-27_12-41-27"


@pytest.mark.skipif(not REAL_SESSION.is_dir(), reason="archived fixture session not present")
class TestRealSession:
    def test_digest_fields(self):
        d = load_session_digest(REAL_SESSION)
        assert d.template_names == ["ccc_ensemble"]
        assert len(d.plan_steps) == 8
        assert d.plan_steps[0]["title"].startswith("Subset MERFISH")
        assert all(s["status"] == "done" for s in d.plan_steps)
        assert d.terminal_state == "done"  # no metrics.json → falls back to plan status
        assert d.prompt.startswith("Run a CCC workflow")

    def test_artifact_audit(self):
        d = load_session_digest(REAL_SESSION)
        assert d.artifacts_present, "fixture session has outputs/"
        assert not d.artifacts_missing, "all expected artifacts were produced"

    def test_render_capped(self):
        d = load_session_digest(REAL_SESSION)
        text = render_digest(d, max_chars=5000)
        assert len(text) <= 5000
        assert "ccc_ensemble" in text


@pytest.fixture()
def synthetic_session(tmp_path):
    sd = tmp_path / "2026-01-01_00-00-00"
    (sd / "outputs").mkdir(parents=True)
    (sd / "outputs" / "made_it.csv").write_text("a,b\n1,2\n")
    plan_md = (
        "# Plan\n\n```yaml\nstatus: failed\nuser_request: do the thing\n"
        "provenance:\n  template_names:\n  - my_template\n```\n\n"
        "## Step 1 — First step\n\n```yaml\nstatus: done\nretry_count: 0\n"
        "assigned_agent: coding_agent\nskills: [skill-a]\n"
        "expected_artifacts:\n- project/outputs/made_it.csv\n```\n\n"
        "## Step 2 — Second step\n\n```yaml\nstatus: failed\nretry_count: 2\n"
        "assigned_agent: coding_agent\nskills: []\n"
        "expected_artifacts:\n- project/outputs/never_made.csv\n```\n"
    )
    chat = {
        "messages": [
            {"type": "human", "data": {"content": [{"type": "text", "text": "do the thing"}]}}
        ],
        "replan_count": 1,
        "plan_markdown": plan_md,
        "subagent_states": {
            "tool_1": [
                "coding_agent",
                {
                    "messages": [
                        {
                            "type": "tool",
                            "data": {
                                "content": "x" * 600
                                + "\nTraceback (most recent call last)\nValueError: boom",
                                "status": "success",
                            },
                        }
                    ]
                },
                "inv-1",
            ]
        },
    }
    (sd / ".chat.json").write_text(json.dumps(chat))
    return sd


class TestSyntheticSession:
    def test_chat_only_degrades_gracefully(self, synthetic_session):
        d = load_session_digest(synthetic_session)
        assert d.terminal_state == "failed"
        assert d.template_names == ["my_template"]
        assert d.replan_count == 1
        assert d.artifacts_present == ["made_it.csv"]
        assert d.artifacts_missing == ["project/outputs/never_made.csv"]

    def test_failure_mining_truncates(self, synthetic_session):
        d = load_session_digest(synthetic_session)
        assert len(d.executor_failures) == 1
        f = d.executor_failures[0]
        assert f["agent"] == "coding_agent"
        assert "ValueError: boom" in f["excerpt"]
        assert len(f["excerpt"]) <= 400

    def test_metrics_folding(self, synthetic_session):
        metrics = {
            "outcome": {"terminal_state": "reported"},
            "usage": {
                "input_tokens": 1000,
                "output_tokens": 100,
                "total_tokens": 1100,
                "llm_calls": 7,
                "by_step": [
                    {"step_id": 1, "input_tokens": 600, "output_tokens": 60, "llm_calls": 4}
                ],
            },
            "loops": {
                "replans_triggered": 2,
                "replan_reasons": ["step 2 kept failing"],
                "evaluator_verdicts": {"pass": 1, "fail": 2},
            },
        }
        (synthetic_session / "metrics.json").write_text(json.dumps(metrics))
        d = load_session_digest(synthetic_session)
        assert d.terminal_state == "reported"
        assert d.usage_totals["total_tokens"] == 1100
        assert d.plan_steps[0]["total_tokens"] == 660
        assert "total_tokens" not in d.plan_steps[1]
        assert d.replan_count == 2
        assert d.evaluator_verdicts == ["pass×1", "fail×2"]

    def test_not_a_session_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_session_digest(tmp_path)
