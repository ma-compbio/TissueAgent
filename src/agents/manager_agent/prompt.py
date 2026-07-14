"""Prompt templates and description for the manager agent."""

from __future__ import annotations

from pathlib import Path

from agents.agent_utils import substitute_shared_prompts
from server.plan_store import PlanDocument, plan_store

_DIR = Path(__file__).parent
_TEMPLATE = substitute_shared_prompts((_DIR / "prompt.txt").read_text())

ManagerDescription = """
Coordinate the Executor Team composed of expert agents to execute each step in the Plan.
""".strip()


def _format_plan(doc: PlanDocument) -> str:
    """Render the plan for the manager prompt: user request + steps with assignments.

    Deliberately omits per-step status. The manager derives progress from its own
    tool-call history (each ``next_step`` / ``retry_step`` call and its result is
    visible in the message list).
    """
    lines: list[str] = []
    if doc.user_request:
        lines.append(f"User request: {doc.user_request}")
        lines.append("")
    if not doc.steps:
        lines.append("(no steps)")
        return "\n".join(lines).rstrip()
    lines.append("Steps:")
    for step in doc.steps:
        lines.append(f"Step {step.id} — {step.title}")
        if step.description:
            lines.append(f"  description: {step.description}")
        lines.append(f"  assigned_agent: {step.assigned_agent or '(unassigned)'}")
        if step.expected_artifacts:
            lines.append(
                "  expected_artifacts: " + ", ".join(step.expected_artifacts)
            )
    return "\n".join(lines)


def _format_filtered_registry(
    doc: PlanDocument, agent_id_descriptions: dict[str, str]
) -> str:
    """Render descriptions for only the agents the plan actually assigns."""
    used_ids: list[str] = []
    seen: set[str] = set()
    for step in doc.steps:
        aid = step.assigned_agent
        if aid and aid not in seen:
            seen.add(aid)
            used_ids.append(aid)
    if not used_ids:
        return "(no agents assigned)"
    return "\n".join(
        f" - {aid}: {agent_id_descriptions.get(aid, '(no description)')}"
        for aid in used_ids
    )


def ManagerPrompt(agent_id_descriptions: dict[str, str]):
    """Build a state-aware prompt callable for the manager agent.

    Returns a function that, when called with the current LangGraph state, reads
    ``plan_store`` and renders the manager prompt with two placeholders substituted:

    * ``{{formatted_plan}}`` — user request + step list with assigned_agent and
      expected_artifacts (no status; the manager derives progress from its own
      tool-call history).
    * ``{{agent_registry}}`` — descriptions for only the agents assigned in the plan.

    The manager's message filter (:func:`graph.message_filters.filter_for_manager`)
    strips HumanMessages and every other agent's messages, so all situational context
    lives in this system prompt.
    """
    def render(state) -> str:
        doc = plan_store.read()
        return (
            _TEMPLATE
            .replace("{{formatted_plan}}", _format_plan(doc))
            .replace("{{agent_registry}}", _format_filtered_registry(doc, agent_id_descriptions))
        )

    return render
