"""Parse structured JSON plan output from the planner and recruiter agents.

Instead of using proxy tool calls (``write_plan`` / ``assign_agents``), the
planner and recruiter now emit a fenced JSON block in their text response.
This module extracts that JSON, validates it, builds/updates the
:class:`~server.plan_store.PlanDocument`, persists it, and emits a
``plan_updated`` UI event.

The two public helpers — :func:`planner_state_update` and
:func:`recruiter_state_update` — are wired as ``state_update_fn`` callbacks
on their respective agent nodes in :mod:`graph.graph`.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage

from graph.graph_utils import log_message
from server.plan_store import (
    PlanDocument,
    PlanProvenance,
    PlanStep,
    plan_store,
    serialize_plan,
)


# ---------------------------------------------------------------------------
# JSON extraction
# ---------------------------------------------------------------------------

_JSON_FENCE_RE = re.compile(
    r"```json\s*\n(.*?)\n\s*```",
    re.DOTALL,
)


def _extract_json(text: str) -> Optional[dict]:
    """Extract the first fenced JSON block from *text*.

    Returns the parsed dict, or ``None`` if no valid block is found.
    """
    match = _JSON_FENCE_RE.search(text)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        logging.warning("Failed to parse plan JSON block: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Plan-updated event helper
# ---------------------------------------------------------------------------

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
        pass


# ---------------------------------------------------------------------------
# Planner output parsing
# ---------------------------------------------------------------------------

def _build_plan_from_json(data: dict) -> Optional[PlanDocument]:
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
          "provenance": {                 // optional
            "template_names": ["..."],
            "decision": "USE"|"ADAPT"|"NEW"
          }
        }
    """
    steps_raw = data.get("steps")
    if not steps_raw or not isinstance(steps_raw, list):
        return None

    steps: List[PlanStep] = []
    for i, s in enumerate(steps_raw):
        if not isinstance(s, dict):
            continue
        steps.append(PlanStep(
            id=i + 1,
            title=(s.get("title") or "").strip(),
            description=(s.get("description") or "").strip(),
            reasoning=(s.get("reasoning") or "").strip(),
            expected_artifacts=[
                a.strip()
                for a in (s.get("expected_artifacts") or [])
                if isinstance(a, str) and a.strip()
            ],
        ))

    if not steps:
        return None

    provenance: Optional[PlanProvenance] = None
    prov_raw = data.get("provenance")
    if isinstance(prov_raw, dict):
        template_names = prov_raw.get("template_names", [])
        if isinstance(template_names, str):
            template_names = [template_names]
        provenance = PlanProvenance(
            template_names=list(template_names) if template_names else [],
            decision=prov_raw.get("decision"),
        )
    else:
        provenance = PlanProvenance()

    return PlanDocument(
        status="draft",
        user_request=(data.get("user_request") or "").strip(),
        steps=steps,
        provenance=provenance,
    )


def planner_state_update(response: AIMessage, state) -> Dict[str, Any]:
    """``state_update_fn`` for the planner agent node.

    If the response contains a fenced JSON plan block, persists the plan
    and emits a ``plan_updated`` event.  Returns an empty dict (no extra
    state keys needed).
    """
    text = (response.content or "") if isinstance(response.content, str) else ""
    data = _extract_json(text)
    if data is None:
        return {}

    doc = _build_plan_from_json(data)
    if doc is None:
        logging.warning("planner_state_update: JSON found but could not build plan")
        return {}

    plan_store.write(doc)
    _emit_plan_updated(doc)
    logging.info(
        "planner_state_update: wrote %d step(s) to %s (status=draft)",
        len(doc.steps),
        plan_store.path,
    )
    return {}


# ---------------------------------------------------------------------------
# Recruiter output parsing
# ---------------------------------------------------------------------------

def _apply_assignments_from_json(data: dict) -> Optional[PlanDocument]:
    """Read assignments from the recruiter's JSON and annotate the on-disk plan.

    Expected schema::

        {
          "assignments": [
            {
              "step_id": 1,
              "assigned_agent": "coding",
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

    missing: List[int] = []
    for step in doc.steps:
        a = by_id.get(step.id)
        if a is None:
            missing.append(step.id)
            continue
        step.assigned_agent = (a.get("assigned_agent") or "").strip()
        step.assignment_rationale = (a.get("assignment_rationale") or "").strip()

    if missing:
        logging.warning("recruiter: missing assignments for step ids %s", missing)

    doc.status = "recruited"
    return doc


def recruiter_state_update(response: AIMessage, state) -> Dict[str, Any]:
    """``state_update_fn`` for the recruiter agent node.

    If the response contains a fenced JSON assignments block, annotates
    the on-disk plan and emits a ``plan_updated`` event.
    """
    text = (response.content or "") if isinstance(response.content, str) else ""
    data = _extract_json(text)
    if data is None:
        return {}

    doc = _apply_assignments_from_json(data)
    if doc is None:
        logging.warning("recruiter_state_update: JSON found but could not apply assignments")
        return {}

    plan_store.write(doc)
    _emit_plan_updated(doc)
    logging.info(
        "recruiter_state_update: annotated %d step(s), status=recruited",
        len(doc.steps),
    )
    return {}
