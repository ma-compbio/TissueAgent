"""Parse structured JSON plan output from the planner and recruiter agents.

This module extracts JSON emitted by planner and recruiter agents, validates it, builds/updates the
:class:`~server.plan_store.PlanDocument`, persists it, and emits a ``plan_updated`` UI event.

The two public factories - :func:`create_planner_state_update` and
:func:`create_recruiter_state_update` - are wired as ``state_update_fn``
callbacks on their respective agent nodes in :mod:`graph.graph`.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage

from agents.recruiter_agent.prompt import get_skill_metadata
from graph.ui_events import emit_message
from server.plan_store import (
    PlanDocument,
    PlanProvenance,
    PlanStep,
    plan_store,
    serialize_plan,
)

_JSON_FENCE_RE = re.compile(
    r"```json\s*\n(.*?)\n\s*```",
    re.DOTALL,
)


def _extract_json(text: str) -> dict | None:
    """Extract JSON from *text*, trying fenced blocks first, then raw JSON.

    Returns the parsed dict, or ``None`` if no valid JSON is found.
    """
    match = _JSON_FENCE_RE.search(text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError as exc:
            logging.warning("Failed to parse plan JSON block: %s", exc)
            return None
    text = text.strip()
    for open_ch, close_ch in ("{", "}"), ("[", "]"):
        start = text.find(open_ch)
        if start == -1:
            continue
        end = text.rfind(close_ch)
        if end <= start:
            continue
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            continue

    logging.warning("No valid JSON found in text")
    return None


def _emit_plan_updated(doc: PlanDocument) -> None:
    """Push a plan-updated marker into the UI event stream."""
    payload = serialize_plan(doc)
    message = AIMessage(
        content="plan_updated",
        additional_kwargs={"plan_payload": payload},
        name="plan_updated",
    )
    emit_message(message)


def _build_plan_from_json(data: dict) -> PlanDocument | None:
    """Construct a :class:`PlanDocument` from the planner's JSON output.

    Expected schema::

        {
          "user_request": "...",
          "steps": [
            {
              "title": "...",
              "description": "...",
              "reasoning": "...",
              "expected_artifacts": ["..."]
            }
          ],
          "provenance": {
            "template_names": ["..."],
            "justification": "free-form description of how templates were used"
          }
        }
    """
    steps_raw = data.get("steps")
    if not steps_raw or not isinstance(steps_raw, list):
        return None

    steps: list[PlanStep] = []
    for i, s in enumerate(steps_raw):
        if not isinstance(s, dict):
            continue
        steps.append(
            PlanStep(
                id=i + 1,
                title=(s.get("title") or "").strip(),
                description=(s.get("description") or "").strip(),
                reasoning=(s.get("reasoning") or "").strip(),
                expected_artifacts=[
                    a.strip()
                    for a in (s.get("expected_artifacts") or [])
                    if isinstance(a, str) and a.strip()
                ],
            )
        )

    if not steps:
        return None

    prov_raw = data.get("provenance")
    if isinstance(prov_raw, dict):
        template_names = prov_raw.get("template_names", [])
        if isinstance(template_names, str):
            template_names = [template_names]
        provenance = PlanProvenance(
            template_names=list(template_names) if template_names else [],
            justification=(prov_raw.get("justification") or "").strip(),
        )
    else:
        provenance = PlanProvenance()

    return PlanDocument(
        status="draft",
        user_request=(data.get("user_request") or "").strip(),
        steps=steps,
        provenance=provenance,
    )


def _parse_and_persist_plan(text: str) -> "PlanDocument | None":
    """Extract a plan JSON block from *text*, persist it, and emit the UI event.

    Returns the persisted :class:`PlanDocument` on success or ``None`` when the
    response contains no parseable plan.
    """
    data = _extract_json(text)
    if data is None:
        return None
    doc = _build_plan_from_json(data)
    if doc is None:
        return None
    plan_store.write(doc)
    _emit_plan_updated(doc)
    logging.info(
        "planner_state_update: wrote %d step(s) to %s (status=draft)",
        len(doc.steps),
        plan_store.path,
    )
    return doc


def create_planner_state_update(max_retries: int = 2):
    """Factory that returns a ``state_update_fn`` for the planner node.

    Initial plan: validates the ROUTE first-line header, parses and persists the plan for
    ROUTE: PLAN, signals a retry when the format is invalid.

    Replan (state["replan_count"] > 0): the replan prompt instructs the model to emit only
    a JSON fenced block (no ROUTE header), so we skip the ROUTE check and try to parse the
    JSON directly. Parse failures populate ``planner_validation_errors`` so ``planner_router``
    knows to loop back instead of advancing to the recruiter.

    Raises ``RuntimeError`` if retries are exhausted.
    """

    def planner_state_update(response: AIMessage, state) -> dict[str, Any]:
        # Mid-loop tool-call turns produce no plan content; nothing to validate or persist.
        if getattr(response, "tool_calls", None):
            return {}
        text = (response.content.strip() or "") if isinstance(response.content, str) else ""
        replan_count = int(state.get("replan_count", 0) or 0)
        is_replan = replan_count > 0

        # planner_retry_count is scoped per (initial-plan | replan) phase. Detect
        # a phase transition (replan_count changed since the last recorded phase)
        # and reset the counter so replans don't inherit initial-plan retries.
        prior_phase = state.get("planner_retry_phase")
        current_phase = f"replan:{replan_count}" if is_replan else "initial"
        phase_changed = prior_phase != current_phase
        prior = 0 if phase_changed else int(state.get("planner_retry_count", 0) or 0)

        if is_replan:
            if _parse_and_persist_plan(text) is not None:
                # Success — reset retry counter for the next phase.
                return {
                    "planner_validation_errors": None,
                    "planner_retry_count": 0,
                    "planner_retry_phase": current_phase,
                }
            if prior >= max_retries:
                # Route to reporter with a clean error instead of raising and
                # crashing the graph.
                error_msg = (
                    f"Planner failed to produce a valid JSON plan on replan after "
                    f"{max_retries} retries. Last response started with: {text[:120]!r}"
                )
                logging.error("planner_state_update: %s", error_msg)
                response.content = (
                    "ROUTE: DIRECT\n\n"
                    f"Planner retries exhausted: {error_msg}"
                )
                return {
                    "planner_validation_errors": None,
                    "planner_retry_count": 0,
                    "planner_retry_phase": current_phase,
                }
            feedback = HumanMessage(
                content=(
                    "Your response must contain a single fenced ```json``` code block "
                    "with the plan schema (user_request, steps, provenance). Please try again."
                )
            )
            return {
                "messages": [response, feedback],
                "planner_retry_count": prior + 1,
                "planner_retry_phase": current_phase,
                "planner_validation_errors": "replan_json_parse_failed",
            }

        head = text.splitlines()[0].upper() if text else ""

        # DIRECT / CLARIFY — no plan expected
        if "DIRECT" in head or "CLARIFY" in head:
            return {
                "planner_retry_count": 0,
                "planner_retry_phase": current_phase,
            }

        # Invalid format — retry with feedback
        if "PLAN" not in head:
            if prior >= max_retries:
                error_msg = (
                    f"Planner failed to produce a valid ROUTE after {max_retries} retries. "
                    f"Last response started with: {text[:120]!r}"
                )
                logging.error("planner_state_update: %s", error_msg)
                response.content = (
                    "ROUTE: DIRECT\n\n"
                    f"Planner retries exhausted: {error_msg}"
                )
                return {
                    "planner_retry_count": 0,
                    "planner_retry_phase": current_phase,
                }
            feedback = HumanMessage(
                content=(
                    "Your response must begin with exactly one of: "
                    "ROUTE: DIRECT, ROUTE: CLARIFY, or ROUTE: PLAN. "
                    "Please try again."
                )
            )
            return {
                "messages": [response, feedback],
                "planner_retry_count": prior + 1,
                "planner_retry_phase": current_phase,
            }

        # ROUTE: PLAN — parse and persist the JSON block
        if _parse_and_persist_plan(text) is None:
            if prior >= max_retries:
                error_msg = (
                    "Planner failed to produce a valid JSON plan. "
                    "No fenced JSON block found in the response."
                )
                logging.error("planner_state_update: %s", error_msg)
                response.content = (
                    "ROUTE: DIRECT\n\n"
                    f"Planner retries exhausted: {error_msg}"
                )
                return {
                    "planner_retry_count": 0,
                    "planner_retry_phase": current_phase,
                }
            feedback = HumanMessage(
                content=(
                    "Your ROUTE: PLAN response must contain a fenced ```json``` block "
                    "with the plan schema. Please try again."
                )
            )
            return {
                "messages": [response, feedback],
                "planner_retry_count": prior + 1,
                "planner_retry_phase": current_phase,
            }
        return {
            "planner_retry_count": 0,
            "planner_retry_phase": current_phase,
        }

    return planner_state_update


def _apply_assignments_from_json(data: dict) -> PlanDocument | None:
    """Read assignments from the recruiter's JSON and annotate the on-disk plan.

    Expected schema::

        {
          "assignments": [
            {
              "step_id": 1,
              "assigned_agent": "coding_agent",
              "assignment_rationale": "..."
            }
          ]
        }
    """
    assignments_raw = data.get("assignments")
    if not assignments_raw or not isinstance(assignments_raw, list):
        return None

    doc = plan_store.read()
    if not doc.steps:
        logging.warning("recruiter: no plan on disk to annotate")
        return None

    by_id = {}
    for a in assignments_raw:
        if not isinstance(a, dict):
            continue
        step_id = a.get("step_id")
        if step_id is not None:
            by_id[int(step_id)] = a

    missing: list[int] = []
    for step in doc.steps:
        a = by_id.get(step.id)
        if a is None:
            missing.append(step.id)
            continue
        step.assigned_agent = (a.get("assigned_agent") or "").strip()
        step.assignment_rationale = (a.get("assignment_rationale") or "").strip()
        # Only overwrite skills when the JSON actually carries the key —
        # otherwise a retry response that omits skills would wipe prior
        # assignments on the on-disk plan.
        if "skills" in a:
            step.skills = list(a.get("skills") or [])

    if missing:
        logging.warning("recruiter: missing assignments for step ids %s", missing)

    doc.status = "recruited"
    return doc


def _validate_assignments(doc: PlanDocument, valid_agent_ids: set) -> list[str]:
    """Validate recruiter assignments.

    Returns list of error strings (empty = valid).
    """
    skill_meta = get_skill_metadata()
    valid_skill_names = set(skill_meta.keys())
    errors: list[str] = []
    for step in doc.steps:
        if step.assigned_agent and step.assigned_agent not in valid_agent_ids:
            errors.append(
                f"Step {step.id}: assigned_agent '{step.assigned_agent}' is not a valid "
                f"agent ID. Valid IDs: {sorted(valid_agent_ids)}"
            )
        for skill_name in step.skills:
            if skill_name not in valid_skill_names:
                errors.append(
                    f"Step {step.id}: skill '{skill_name}' not found. "
                    f"Valid skills: {sorted(valid_skill_names)}"
                )
            elif (
                step.assigned_agent and step.assigned_agent not in skill_meta[skill_name].applies_to
            ):
                errors.append(
                    f"Step {step.id}: skill '{skill_name}' does not apply to agent "
                    f"'{step.assigned_agent}'. applies_to: {skill_meta[skill_name].applies_to}"
                )
    return errors


def create_recruiter_state_update(valid_agent_ids: set, max_retries: int = 2):
    """Factory that returns a ``state_update_fn`` for the recruiter node.

    The returned callback parses the recruiter's JSON output, validates agent IDs and skill
    assignments, and either persists the plan or signals a retry by returning validation errors in
    the state.
    """

    def recruiter_state_update(response: AIMessage, state) -> dict[str, Any]:
        # Skip mid-loop tool-call turns; assignments are only parsed from the final text response.
        if getattr(response, "tool_calls", None):
            return {}
        text = (response.content or "") if isinstance(response.content, str) else ""
        prior = int(state.get("recruiter_retry_count", 0) or 0)

        def _retry(error_msg: str) -> dict[str, Any]:
            logging.warning("recruiter_state_update: %s", error_msg)
            if prior >= max_retries:
                # Retry limit reached — surface the error via state instead of
                # raising. The router will treat this as terminal.
                logging.error(
                    "recruiter_state_update: retry limit reached (%d), advancing with error",
                    max_retries,
                )
                return {
                    "recruiter_validation_errors": error_msg,
                    "recruiter_retry_count": prior,
                }
            feedback = HumanMessage(content=error_msg)
            return {
                "messages": [response, feedback],
                "recruiter_validation_errors": error_msg,
                "recruiter_retry_count": prior + 1,
            }

        data = _extract_json(text)
        if data is None:
            return _retry(
                "No parseable JSON found in your response. Emit a single fenced "
                "```json``` block containing the assignments schema."
            )

        doc = _apply_assignments_from_json(data)
        if doc is None:
            return _retry(
                "The recruiter JSON was parsed but no assignments could be applied "
                "(missing 'assignments' array, or no matching plan on disk). Please "
                "re-emit the assignments schema."
            )

        errors = _validate_assignments(doc, valid_agent_ids)

        if errors:
            error_msg = "Validation errors in your assignments:\n" + "\n".join(
                f"- {e}" for e in errors
            )
            return _retry(error_msg)

        plan_store.write(doc)
        _emit_plan_updated(doc)
        logging.info(
            "recruiter_state_update: annotated %d step(s), status=recruited",
            len(doc.steps),
        )
        return {"recruiter_validation_errors": None, "recruiter_retry_count": 0}

    return recruiter_state_update
