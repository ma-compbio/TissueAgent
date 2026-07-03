"""Prompt templates and description for the manager agent."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from agents.agent_utils import format_agent_id_descriptions
from server.plan_store import PlanDocument, PlanStep, plan_store

_DIR = Path(__file__).parent
_TEMPLATE = (_DIR / "prompt.txt").read_text()

ManagerDescription = """
Coordinate the Executor Team composed of expert agents to execute each step in the Plan.
""".strip()


def _format_cursor_state(doc: PlanDocument) -> str:
    """Describe the current cursor: which step is next, and whether one is in-flight."""
    in_flight = next((s for s in doc.steps if s.status == "running"), None)
    target = next((s for s in doc.steps if s.id == doc.current_step_id), None)

    lines: list[str] = []
    if in_flight is not None:
        lines.append(
            f"Most recently dispatched step (in flight): id={in_flight.id} — "
            f"\"{in_flight.title}\" (assigned_agent: {in_flight.assigned_agent})."
        )
        lines.append(
            "Inspect its artifacts below, then call next_step to accept or "
            "retry_step to re-run."
        )
    elif not any(s.status in ("done", "failed", "skipped") for s in doc.steps):
        lines.append(
            "No step has been dispatched yet. Call next_step to begin step 1. "
            "retry_step is not valid as a first call."
        )
    else:
        lines.append("No step is currently in flight.")

    if target is not None and target.status != "running":
        lines.append("")
        lines.append("Next step to dispatch on next_step:")
        lines.append(f"  id: {target.id}")
        lines.append(f"  title: {target.title}")
        if target.description:
            lines.append(f"  description: {target.description}")
        lines.append(f"  assigned_agent: {target.assigned_agent}")
        if target.expected_artifacts:
            lines.append(
                "  expected_artifacts: " + ", ".join(target.expected_artifacts)
            )
    elif target is None and in_flight is None:
        lines.append("")
        lines.append(
            "All plan steps have been dispatched. Emit your final response so "
            "the evaluator can review."
        )

    return "\n".join(lines)


def _format_completed_steps(doc: PlanDocument) -> str:
    """Render accepted-step outputs (status=done) for inclusion in the manager prompt.

    Steps with status != 'done' are excluded — failed-and-not-yet-retried, skipped,
    and pending steps are not "successful outputs" from the manager's perspective.
    The in-flight step's sub-agent output is shown separately under
    "Most Recent Sub-agent Output."
    """
    done_steps = [s for s in doc.steps if s.status == "done"]
    if not done_steps:
        return "(no steps completed yet)"

    lines: list[str] = []
    for step in done_steps:
        lines.append(f"- Step {step.id}: {step.title}")
        if step.actual_outputs:
            for path in step.actual_outputs:
                lines.append(f"    - {path}")
        else:
            lines.append("    - (no artifacts recorded)")
    return "\n".join(lines)


def _format_last_subagent_output(state: dict[str, Any]) -> str:
    """Pull the most recent ToolMessage content from state if available.

    The manager's message filter strips this from the messages list before the LLM
    call, so we surface it here in the system prompt instead — keeping decision
    context in one place while preserving the strict isolation contract.
    """
    from langchain_core.messages import ToolMessage  # local import to avoid cycles

    messages = state.get("messages", []) if isinstance(state, dict) else []
    for msg in reversed(messages):
        if isinstance(msg, ToolMessage):
            content = msg.content
            if isinstance(content, list):
                # Multimodal content: stringify text parts only.
                parts: list[str] = []
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        parts.append(str(part.get("text", "")))
                    elif isinstance(part, str):
                        parts.append(part)
                content = "\n".join(parts)
            tool_name = getattr(msg, "name", None) or "<unknown>"
            return f"(from tool: {tool_name})\n{content}"
    return "(no sub-agent has been dispatched yet)"


def ManagerPrompt(
    agent_id_descriptions: dict[str, str],
) -> Callable[[dict[str, Any]], str]:
    """Build a state-aware prompt callable for the manager agent.

    Returns a function that, when called with the current LangGraph state, reads
    ``plan_store`` and renders the manager prompt with placeholders substituted:

    * ``{agent_registry}`` — fixed at construction time from the agent registry.
    * ``{cursor_state}`` — describes the in-flight step (if any) and the next step to
      dispatch.
    * ``{completed_steps}`` — bulleted list of accepted prior-step outputs.
    * ``{last_subagent_output}`` — content of the most recent ToolMessage, surfaced
      here because :func:`graph.message_filters.filter_for_manager` removes it from
      the messages list.
    """
    registry_text = format_agent_id_descriptions(agent_id_descriptions)
    base = _TEMPLATE.replace("{agent_registry}", registry_text)

    def render(state: dict[str, Any]) -> str:
        doc = plan_store.read()
        return (
            base
            .replace("{cursor_state}", _format_cursor_state(doc))
            .replace("{completed_steps}", _format_completed_steps(doc))
            .replace("{last_subagent_output}", _format_last_subagent_output(state))
        )

    return render
