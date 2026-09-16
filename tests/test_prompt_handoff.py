"""Regression tests for verbatim user-request delivery to execution workers."""

from __future__ import annotations

import json

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import StructuredTool

import agents.manager_agent.tools as manager_tools
import graph.plan_output as plan_output
from server.plan_store import PlanDocument, PlanStep, PlanStore


def _plan_response(user_request: str = "short paraphrase") -> AIMessage:
    payload = {
        "user_request": user_request,
        "steps": [
            {
                "step_number": 1,
                "title": "Run analysis",
                "description": "Produce the requested analysis and figure.",
                "reasoning": "The task requires an executable analysis.",
                "expected_artifacts": ["figures/result.png"],
            }
        ],
        "provenance": {"template_names": [], "justification": "No template."},
    }
    return AIMessage(content=f"ROUTE: PLAN\n\n```json\n{json.dumps(payload)}\n```")


def test_planner_persists_original_request_instead_of_paraphrase(
    tmp_path, monkeypatch
) -> None:
    """Planner summaries must not replace exact requirements from the user turn."""
    store = PlanStore(tmp_path)
    monkeypatch.setattr(plan_output, "plan_store", store)
    monkeypatch.setattr(plan_output, "_emit_plan_updated", lambda doc: None)
    original = (
        "Run the fixed method exactly.\n"
        "Use 200 permutations and score=max(z,0)*-log10(p)."
    )

    update = plan_output.create_planner_state_update()(
        _plan_response(),
        {"messages": [HumanMessage(content=original)]},
    )

    assert store.read().user_request == original
    assert update["original_user_request"] == original


def test_replan_keeps_captured_request_despite_internal_feedback(tmp_path, monkeypatch) -> None:
    """Internal retry feedback must not become the request persisted by a replan."""
    store = PlanStore(tmp_path)
    monkeypatch.setattr(plan_output, "plan_store", store)
    monkeypatch.setattr(plan_output, "_emit_plan_updated", lambda doc: None)
    original = "Original exact request with fixed parameters."
    response = _plan_response("replacement paraphrase")
    response.content = response.content.split("\n", 2)[2]

    plan_output.create_planner_state_update()(
        response,
        {
            "messages": [
                HumanMessage(content=original),
                HumanMessage(content="Internal planner retry feedback."),
            ],
            "original_user_request": original,
            "replan_count": 1,
        },
    )

    assert store.read().user_request == original


def test_manager_dispatch_prepends_original_request_and_step(tmp_path, monkeypatch) -> None:
    """The transfer boundary must include exact requirements without manager cooperation."""
    store = PlanStore(tmp_path)
    original = "Use the supplied algorithm exactly; score=max(z,0)*-log10(p)."
    store.write(
        PlanDocument(
            status="recruited",
            user_request=original,
            steps=[
                PlanStep(
                    id=1,
                    title="Run analysis",
                    description="Create the scientific results.",
                    expected_artifacts=["figures/result.png"],
                    assigned_agent="coding_agent",
                )
            ],
        )
    )
    monkeypatch.setattr(manager_tools, "plan_store", store)
    monkeypatch.setattr(manager_tools, "_emit_plan_updated", lambda doc: None)
    monkeypatch.setattr(
        manager_tools,
        "run_heuristic_validation",
        lambda step_id, expected: ([], [], "Status: PASSED"),
    )
    captured: dict[str, str] = {}

    def transfer(prompt: str) -> str:
        """Capture the prompt sent across the worker boundary."""
        captured["prompt"] = prompt
        return "done"

    transfer_tool = StructuredTool.from_function(
        transfer,
        name="coding_agent_transfer_tool",
        description="Test transfer.",
    )
    next_step = next(
        tool
        for tool in manager_tools.create_manager_step_tools(
            {"coding_agent": transfer_tool}
        )
        if tool.name == "next_step"
    )

    next_step.invoke({"task_instructions": "Use the uploaded files in project/uploads."})

    prompt = captured["prompt"]
    assert original in prompt
    assert "CURRENT ASSIGNED STEP" in prompt
    assert "Step 1 — Run analysis" in prompt
    assert "Expected artifacts: figures/result.png" in prompt
    assert "Use the uploaded files in project/uploads." in prompt
