"""End-to-end smoke test of the optimizer loop with a scripted stub model.

No network, no real model: the stub emits a fixed tool-call sequence
(list_sessions → read_knowledge_file → edit_knowledge_file → finish) so the
test exercises tool dispatch, the guardrailed edit path, the ledger, and
propose-only revert semantics.
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

from langchain_core.messages import AIMessage  # noqa: E402

from optimizer import guardrails  # noqa: E402
from optimizer.loop import run_optimizer  # noqa: E402


class ScriptedModel:
    """Minimal stand-in for a bound chat model: replays a fixed AIMessage list."""

    def __init__(self, script: list[AIMessage]):
        self._script = list(script)

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        return self._script.pop(0)


def _tool_call(name: str, args: dict, call_id: str) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id}])


@pytest.fixture()
def workspace(tmp_path, monkeypatch):
    """A tmp session + tmp knowledge tree, with guardrail roots repointed."""
    session = tmp_path / "sess"
    (session / "outputs").mkdir(parents=True)
    (session / ".chat.json").write_text(
        json.dumps(
            {
                "messages": [{"type": "human", "data": {"content": "run the thing"}}],
                "replan_count": 0,
                "plan_markdown": "",
                "subagent_states": {},
            }
        )
    )
    skills = tmp_path / "knowledge" / "skills"
    plans = tmp_path / "knowledge" / "plans"
    skills.mkdir(parents=True)
    plans.mkdir()
    plan_file = plans / "my_plan.md"
    plan_file.write_text(
        "---\nname: my_plan\nstatus: enabled\ndescription: a plan\n---\n\n## Steps\nDo the thing.\n"
    )
    monkeypatch.setattr(guardrails, "ALLOWED_ROOTS", (skills.resolve(), plans.resolve()))
    # validate_knowledge defaults to the real repo dirs; repoint them too.
    import optimizer.guardrails as g

    orig_validate = g.validate_knowledge
    monkeypatch.setattr(
        g, "validate_knowledge", lambda **kw: orig_validate(skills_dir=skills, plans_dir=plans)
    )
    return session, plan_file


def _script(plan_file: Path) -> list[AIMessage]:
    return [
        _tool_call("list_sessions", {}, "c1"),
        _tool_call("read_knowledge_file", {"relpath": str(plan_file)}, "c2"),
        _tool_call(
            "edit_knowledge_file",
            {
                "relpath": str(plan_file),
                "old_str": "Do the thing.",
                "new_str": "Do the thing.\nAlways write project/outputs/result.csv.",
            },
            "c3",
        ),
        _tool_call("finish", {"report_markdown": "Added the missing artifact contract."}, "c4"),
    ]


def test_loop_applies_edit_and_finishes(workspace):
    session, plan_file = workspace
    result = run_optimizer(
        [session], "make it better", propose_only=False, model=ScriptedModel(_script(plan_file))
    )
    assert result.finished
    assert result.final_report == "Added the missing artifact contract."
    assert len(result.edits) == 1
    assert "Always write project/outputs/result.csv" in plan_file.read_text()
    assert "+Always write project/outputs/result.csv." in result.edits[0].diff
    assert result.usage["llm_calls"] == 4


def test_propose_only_reverts_but_records(workspace):
    session, plan_file = workspace
    before = plan_file.read_text()
    result = run_optimizer(
        [session], "make it better", propose_only=True, model=ScriptedModel(_script(plan_file))
    )
    assert result.finished
    assert len(result.edits) == 1  # diff recorded...
    assert plan_file.read_text() == before  # ...but file restored


def test_breaking_edit_is_reverted_and_reported(workspace):
    session, plan_file = workspace
    script = [
        _tool_call(
            "edit_knowledge_file",
            {"relpath": str(plan_file), "old_str": "---\nname: my_plan", "new_str": "name: my_plan"},
            "c1",
        ),
        _tool_call("finish", {"report_markdown": "tried and failed"}, "c2"),
    ]
    before = plan_file.read_text()
    result = run_optimizer(
        [session], "focus", propose_only=False, model=ScriptedModel(script)
    )
    assert result.edits == []  # rejected edit never enters the ledger
    assert plan_file.read_text() == before


def test_loop_stops_without_tool_calls(workspace):
    session, _ = workspace
    scripted = ScriptedModel([AIMessage(content="nothing to do")])
    result = run_optimizer([session], "focus", propose_only=False, model=scripted)
    assert not result.finished
    assert result.final_report == "nothing to do"
    assert result.iterations == 1
