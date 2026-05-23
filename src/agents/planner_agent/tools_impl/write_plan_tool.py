"""``write_plan`` tool used by the planner agent.

Replaces the previous free-text plan emission. Calling this tool
persists a structured plan to ``sessions/active/plan.md`` (via
:mod:`server.plan_store`) and emits a ``plan_updated`` UI event so the
front-end refreshes.

The planner is responsible for authoring ``title``, ``description``,
``reasoning``, and ``expected_artifacts`` for every step. The planner
does NOT assign agents — that is the recruiter's job
(:mod:`agents.recruiter_agent.tools_impl.assign_agents_tool`).
"""

from __future__ import annotations

from typing import List, Type

from langchain.tools import StructuredTool
from langchain_core.messages import AIMessage
from pydantic import BaseModel, Field

from graph.graph_utils import log_message
from server.plan_store import (
    PlanDocument,
    PlanStep,
    plan_store,
    serialize_plan,
)


class PlanStepInput(BaseModel):
    """One step authored by the planner.

    Used as the per-element schema inside ``WritePlanArgs.steps``.
    """

    title: str = Field(..., description="Short imperative title for the step.")
    description: str = Field(
        ...,
        description=(
            "One- to three-sentence concrete description of what this step "
            "does, written for the recruiter and the user to read."
        ),
    )
    reasoning: str = Field(
        ...,
        description=(
            "Why this step is needed in service of the user's request. "
            "Make this an explanation, not a restatement of the description."
        ),
    )
    expected_artifacts: List[str] = Field(
        default_factory=list,
        description=(
            "File paths (relative to the repository root) that this step is "
            "expected to produce when it succeeds. Be specific — these are "
            "later checked against the manager's actual outputs."
        ),
    )


class WritePlanArgs(BaseModel):
    """Arguments for the ``write_plan`` tool."""

    user_request: str = Field(
        ...,
        description=(
            "The user's original request, paraphrased into one or two "
            "sentences. Recorded at the top of the plan."
        ),
    )
    steps: List[PlanStepInput] = Field(
        ...,
        description=(
            "Ordered list of plan steps. Must contain at least one step."
        ),
    )


def _emit_plan_updated(doc: PlanDocument) -> None:
    """Push a plan-updated marker into the UI event stream."""
    payload = serialize_plan(doc)
    message = AIMessage(
        content="plan_updated",
        additional_kwargs={"plan_payload": payload},
        name="plan_updated",
    )
    try:
        log_message(message)
    except Exception:
        # Logging failure must never break the tool call.
        pass


def _write_plan_impl(user_request: str, steps: List[PlanStepInput]) -> str:
    """Persist a fresh plan document; returns a short confirmation message."""
    if not steps:
        return "write_plan: no steps provided; nothing written."

    doc = PlanDocument(
        status="draft",
        user_request=user_request.strip(),
        steps=[
            PlanStep(
                id=i + 1,
                title=s.title.strip(),
                description=s.description.strip(),
                reasoning=s.reasoning.strip(),
                expected_artifacts=[a.strip() for a in s.expected_artifacts if a.strip()],
            )
            for i, s in enumerate(steps)
        ],
    )
    plan_store.write(doc)
    _emit_plan_updated(doc)
    return (
        f"write_plan: wrote {len(doc.steps)} step(s) to "
        f"{plan_store.path}. Plan status is now 'draft'."
    )


def _write_plan_tool_runner(**kwargs):
    """Adapter so StructuredTool.args_schema=WritePlanArgs flows through."""
    parsed = WritePlanArgs(**kwargs)
    return _write_plan_impl(parsed.user_request, parsed.steps)


write_plan_tool: StructuredTool = StructuredTool.from_function(
    func=_write_plan_tool_runner,
    name="write_plan",
    description=(
        "Write the evolving plan to disk. Call this once per planning "
        "turn after you have decided on the step list. Each step must "
        "carry a title, description, reasoning, and expected_artifacts; "
        "do NOT assign agents (that is the recruiter's job). Calling "
        "this tool overwrites any prior plan."
    ),
    args_schema=WritePlanArgs,
)
