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

from typing import List, Literal, Optional, Type

from langchain.tools import StructuredTool
from langchain_core.messages import AIMessage
from pydantic import BaseModel, Field

from graph.graph_utils import log_message
from server.plan_store import (
    PlanDocument,
    PlanProvenance,
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
    provenance_source: Literal["template", "denovo"] = Field(
        "denovo",
        description=(
            "Where this plan came from. Set to 'template' when you "
            "adapted a registry template (run ``template_selector_tool`` "
            "first and copy the relevant fields into the other "
            "``provenance_*`` arguments). Set to 'denovo' when you "
            "wrote the plan from scratch with no template."
        ),
    )
    provenance_template_id: Optional[str] = Field(
        None,
        description=(
            "Template id (e.g. 'CELL_ANNOTATION') when "
            "provenance_source == 'template'. Use the exact id returned "
            "by ``template_selector_tool``."
        ),
    )
    provenance_version: Optional[str] = Field(
        None,
        description=(
            "Template version string (e.g. '1.0') when "
            "provenance_source == 'template'."
        ),
    )
    provenance_decision: Optional[Literal["USE", "ADAPT", "NEW"]] = Field(
        None,
        description=(
            "Decision verbatim from ``template_selector_tool``: 'USE' "
            "(strong match), 'ADAPT' (partial match), or 'NEW' (no fit). "
            "Required when provenance_source == 'template'."
        ),
    )
    provenance_score: Optional[float] = Field(
        None,
        description=(
            "Match score (0–1) reported by ``template_selector_tool``. "
            "Optional but useful for later audits."
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


def _write_plan_impl(
    user_request: str,
    steps: List[PlanStepInput],
    provenance: Optional[PlanProvenance] = None,
) -> str:
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
        provenance=provenance,
    )
    plan_store.write(doc)
    _emit_plan_updated(doc)
    prov_note = ""
    if provenance is not None and provenance.source == "template":
        prov_note = (
            f" (provenance: template {provenance.template_id} "
            f"v{provenance.version}, decision {provenance.decision})"
        )
    elif provenance is not None and provenance.source == "denovo":
        prov_note = " (provenance: de novo)"
    return (
        f"write_plan: wrote {len(doc.steps)} step(s) to "
        f"{plan_store.path}. Plan status is now 'draft'.{prov_note}"
    )


def _write_plan_tool_runner(**kwargs):
    """Adapter so StructuredTool.args_schema=WritePlanArgs flows through."""
    parsed = WritePlanArgs(**kwargs)
    # Always attach provenance; default is "denovo" so an LLM that doesn't
    # set anything still ends up with a clearly-marked plan.
    prov = PlanProvenance(
        source=parsed.provenance_source,
        template_id=parsed.provenance_template_id,
        version=parsed.provenance_version,
        decision=parsed.provenance_decision,
        score=parsed.provenance_score,
    )
    return _write_plan_impl(parsed.user_request, parsed.steps, provenance=prov)


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
