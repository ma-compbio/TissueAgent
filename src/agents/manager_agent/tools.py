"""Tool definitions for the manager agent.

The manager owns two execution-control tools, ``next_step`` and ``retry_step``, plus the
file-inspection toolkit. Both control tools wrap the per-agent transfer tools (one per
sub-agent in the agent registry) and add cursor + status bookkeeping on top:

* ``next_step`` marks the previously-dispatched step ``done`` (manager-as-source-of-truth
  acceptance) and dispatches the cursor's step.
* ``retry_step`` re-dispatches the most recently dispatched step without advancing the
  cursor; the previous attempt is marked ``failed`` for the UI before re-running.

Artifact validation is run after each invocation. Its summary (Found / Missing /
Status / Progress) is both emitted to the UI via the ``artifact_validation`` event
and appended to the tool's return value so the manager sees the verdict inline
alongside the sub-agent's own summary.
"""

from __future__ import annotations

from typing import Optional

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from agents.agent_tools import glob_tool, grep_tool, read_tool, write_tool
from config import MAX_STEP_RETRIES
from graph.node_factories import run_heuristic_validation
from graph.ui_events import emit_message
from langchain_core.messages import AIMessage
from server.plan_store import PlanDocument, PlanStep, plan_store, serialize_plan


class StepArgs(BaseModel):
    """Arguments accepted by ``next_step`` and ``retry_step``."""

    task_instructions: str = Field(
        description=(
            "Free-text instructions delegated to the sub-agent assigned to this step. "
            "Mention any prior-step artifacts that are relevant inputs by their workspace-relative paths."
        ),
    )
    expected_artifacts: Optional[list[str]] = Field(
        default=None,
        description=(
            "Optional override for the artifacts the heuristic validator will look for. "
            "Defaults to the plan's expected_artifacts for this step."
        ),
    )


def _emit_plan_updated(doc: PlanDocument) -> None:
    """Push a ``plan_updated`` UI event with the latest plan snapshot."""
    payload = serialize_plan(doc)
    message = AIMessage(
        content="plan_updated",
        additional_kwargs={"plan_payload": payload},
        name="plan_updated",
    )
    emit_message(message)


def _find_running_step(doc: PlanDocument) -> PlanStep | None:
    return next((s for s in doc.steps if s.status == "running"), None)


def _find_step(doc: PlanDocument, step_id: int) -> PlanStep | None:
    return next((s for s in doc.steps if s.id == step_id), None)


def _set_step_status(step_id: int, status: str) -> PlanDocument:
    doc = plan_store.read()
    step = _find_step(doc, step_id)
    if step is not None:
        step.status = status  # type: ignore[assignment]
        plan_store.write(doc)
        _emit_plan_updated(doc)
    return doc


def _invoke_via_transfer_tool(
    step: PlanStep,
    task_instructions: str,
    invocation_tools_by_agent: dict[str, StructuredTool],
) -> str:
    """Dispatch ``task_instructions`` to the transfer tool for ``step.assigned_agent``.

    Sub-agents can return multimodal content (list of dict parts) when their last
    message carries images; the manager tool signature is ``-> str``, so we coerce
    at the boundary rather than let a list bleed into downstream string handling.
    """
    if not step.assigned_agent:
        return f"Error: step {step.id} has no assigned_agent."
    tool = invocation_tools_by_agent.get(step.assigned_agent)
    if tool is None:
        known = ", ".join(sorted(invocation_tools_by_agent)) or "<none>"
        return (
            f"Error: no transfer tool for assigned_agent '{step.assigned_agent}'. "
            f"Known agents: {known}."
        )
    result = tool.invoke({"prompt": task_instructions})
    if isinstance(result, str):
        return result
    if isinstance(result, list):
        # Flatten multimodal content into a text summary; images are dropped
        # (the UI has already received them via the streaming channel).
        parts: list[str] = []
        for item in result:
            if isinstance(item, dict) and item.get("type") in ("text", "output_text"):
                parts.append(str(item.get("text", "")))
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(parts) if parts else str(result)
    return str(result)


def create_manager_step_tools(
    invocation_tools_by_agent: dict[str, StructuredTool],
) -> list[StructuredTool]:
    """Build the manager's ``next_step`` and ``retry_step`` tools.

    Args:
        invocation_tools_by_agent: Map from ``assigned_agent`` id (as stored in plan_store)
            to the corresponding per-agent transfer tool. Built in :mod:`graph.graph` after
            all sub-agent subgraphs are compiled.
    """

    def _dispatch(step: PlanStep, args: StepArgs) -> str:
        result = _invoke_via_transfer_tool(
            step, args.task_instructions, invocation_tools_by_agent
        )
        expected = (
            list(args.expected_artifacts)
            if args.expected_artifacts is not None
            else list(step.expected_artifacts)
        )
        _, _, validation_summary = run_heuristic_validation(step.id, expected)
        return f"{result}\n\n{validation_summary}"

    def next_step(
        task_instructions: str,
        expected_artifacts: Optional[list[str]] = None,
    ) -> str:
        """Mark the previous step ``done`` (if any) and dispatch the cursor's step."""
        args = StepArgs(task_instructions=task_instructions, expected_artifacts=expected_artifacts)
        doc = plan_store.read()
        prior = _find_running_step(doc)
        if prior is not None:
            prior.status = "done"  # type: ignore[assignment]
            plan_store.write(doc)
            _emit_plan_updated(doc)

        doc = plan_store.read()
        target = _find_step(doc, doc.current_step_id)
        if target is None:
            return (
                "No more steps to dispatch — the plan is complete. "
                "Emit your final response so the evaluator can review."
            )
        target.status = "running"  # type: ignore[assignment]
        plan_store.write(doc)
        _emit_plan_updated(doc)

        result = _dispatch(target, args)

        # Advance the cursor by *index* rather than target.id + 1, so a plan
        # edited mid-run (non-contiguous step ids) still progresses to the
        # actual next step. When target is the last step, park the cursor one
        # past the last id — subsequent next_step calls then hit the "plan
        # complete" branch above.
        doc = plan_store.read()
        try:
            idx = next(i for i, s in enumerate(doc.steps) if s.id == target.id)
        except StopIteration:
            idx = None
        if idx is not None and idx + 1 < len(doc.steps):
            doc.current_step_id = doc.steps[idx + 1].id
        else:
            last_id = doc.steps[-1].id if doc.steps else target.id
            doc.current_step_id = last_id + 1
        plan_store.write(doc)
        _emit_plan_updated(doc)
        return result

    def retry_step(
        task_instructions: str,
        expected_artifacts: Optional[list[str]] = None,
    ) -> str:
        """Re-dispatch the most recently dispatched step without advancing the cursor."""
        args = StepArgs(task_instructions=task_instructions, expected_artifacts=expected_artifacts)
        doc = plan_store.read()
        target = _find_running_step(doc)
        if target is None:
            return (
                "Error: retry_step requires a previously dispatched step. "
                "Call next_step first to begin step 1."
            )
        target_id = target.id

        # Enforce the per-step retry budget. Once exhausted, refuse the retry and
        # leave the step ``failed`` so the manager must advance (``next_step`` to
        # accept the partial result) or let the evaluator trigger a replan,
        # rather than looping ``retry_step`` until the recursion limit.
        if (target.retry_count or 0) >= MAX_STEP_RETRIES:
            _set_step_status(target_id, "failed")
            return (
                f"Error: step {target_id} has reached the retry limit "
                f"(MAX_STEP_RETRIES={MAX_STEP_RETRIES}); it has been retried "
                f"{target.retry_count} time(s) without producing the expected "
                "artifacts. Do NOT call retry_step on it again. Either call "
                "next_step to accept the partial result and continue, or emit "
                "your final response so the evaluator can decide whether to replan."
            )

        # Briefly mark the failing attempt, then re-arm the step for the retry.
        _set_step_status(target_id, "failed")
        doc = plan_store.read()
        target = _find_step(doc, target_id)
        if target is None:
            return f"Error: step {target_id} disappeared between status writes."
        target.status = "running"  # type: ignore[assignment]
        target.retry_count = (target.retry_count or 0) + 1
        plan_store.write(doc)
        _emit_plan_updated(doc)

        return _dispatch(target, args)

    next_step_tool = StructuredTool.from_function(
        func=next_step,
        name="next_step",
        description=(
            "Mark the previously dispatched step as done and dispatch the next step in the plan. "
            "Required as the first manager tool call (to begin step 1). After the final step, "
            "calling next_step returns a 'plan complete' notice — emit your final response then."
        ),
        args_schema=StepArgs,
    )

    retry_step_tool = StructuredTool.from_function(
        func=retry_step,
        name="retry_step",
        description=(
            "Re-dispatch the most recently dispatched step with new task_instructions. "
            "Does not advance the cursor. Errors if called before any next_step."
        ),
        args_schema=StepArgs,
    )

    return [next_step_tool, retry_step_tool]


ManagerTools: list[StructuredTool] = [
    glob_tool,
    grep_tool,
    read_tool,
    write_tool,
]
