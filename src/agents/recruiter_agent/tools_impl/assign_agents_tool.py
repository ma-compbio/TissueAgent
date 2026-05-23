"""``assign_agents`` tool used by the recruiter agent.

The recruiter reads the plan written by the planner and annotates each
step with an ``assigned_agent`` plus an ``assignment_rationale``. It
must NOT delete, reorder, rewrite, or add steps — those are the
planner's authored fields and the user's review territory.

If no specialist agent fits a step, the recruiter falls back to
``coding`` (the general-purpose sub-agent) and records that reasoning
explicitly in the rationale. There is no ``unassignable`` status.
"""

from __future__ import annotations

from typing import List

from langchain.tools import StructuredTool
from langchain_core.messages import AIMessage
from pydantic import BaseModel, Field

from graph.graph_utils import log_message
from server.plan_store import (
    PlanDocument,
    plan_store,
    serialize_plan,
)


class AgentAssignment(BaseModel):
    """One step's agent assignment."""

    step_id: int = Field(
        ...,
        description="The integer id of the step to annotate (matches the plan's `## Step N` heading).",
    )
    assigned_agent: str = Field(
        ...,
        description=(
            "The sub-agent that should execute this step. Use the agent's "
            "registry id (e.g. 'coding', 'gene_agent', 'single_cell', "
            "'hypothesis', 'pdf_reader', 'searcher', 'critic', "
            "'cell_annotater', 'spot'). If no specialist fits, use "
            "'coding' as the general-purpose fallback."
        ),
    )
    assignment_rationale: str = Field(
        ...,
        description=(
            "One- or two-sentence explanation of why this agent is the "
            "right pick for this step. When using 'coding' as a fallback, "
            "explicitly say so."
        ),
    )


class AssignAgentsArgs(BaseModel):
    """Arguments for the ``assign_agents`` tool."""

    assignments: List[AgentAssignment] = Field(
        ...,
        description=(
            "One assignment per step. Every step in the current plan must "
            "be assigned — there is no 'leave blank' option."
        ),
    )


def _emit_plan_updated(doc: PlanDocument) -> None:
    payload = serialize_plan(doc)
    message = AIMessage(
        content="plan_updated",
        additional_kwargs={"plan_payload": payload},
        name="plan_updated",
    )
    try:
        log_message(message)
    except Exception:
        pass


def _assign_agents_impl(assignments: List[AgentAssignment]) -> str:
    """Annotate the current plan with agent assignments."""
    doc = plan_store.read()
    if not doc.steps:
        return (
            "assign_agents: no plan on disk to annotate. The planner must "
            "call write_plan first."
        )

    by_id = {a.step_id: a for a in assignments}
    missing: List[int] = []
    for step in doc.steps:
        a = by_id.get(step.id)
        if a is None:
            missing.append(step.id)
            continue
        step.assigned_agent = a.assigned_agent.strip()
        step.assignment_rationale = a.assignment_rationale.strip()

    if missing:
        return (
            "assign_agents: not all steps were assigned. Missing step ids: "
            f"{missing}. Re-call the tool with every step covered."
        )

    doc.status = "recruited"
    plan_store.write(doc)
    _emit_plan_updated(doc)
    return (
        f"assign_agents: annotated {len(doc.steps)} step(s); plan status "
        f"is now 'recruited'."
    )


def _assign_agents_tool_runner(**kwargs):
    parsed = AssignAgentsArgs(**kwargs)
    return _assign_agents_impl(parsed.assignments)


assign_agents_tool: StructuredTool = StructuredTool.from_function(
    func=_assign_agents_tool_runner,
    name="assign_agents",
    description=(
        "Annotate each step of the current plan with the sub-agent that "
        "should execute it and the rationale for that choice. Every step "
        "must be assigned. If no specialist fits a step, use 'coding' as "
        "the fallback and say so in the rationale. Calling this tool sets "
        "the plan status to 'recruited'."
    ),
    args_schema=AssignAgentsArgs,
)
