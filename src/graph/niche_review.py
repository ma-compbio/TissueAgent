"""Prevent a saved prediction file from masking unexecuted niche review steps."""

import re

from server.plan_store import PlanDocument


def guard_niche_review_verdict(content: str, plan: PlanDocument) -> str:
    """Require completion of explicitly planned niche coding/review work before success."""
    if not content.lstrip().upper().startswith("ROUTE: REPORT"):
        return content
    pending = [
        step
        for step in plan.steps
        if "tissue-niche-annotation" in {s.replace("_", "-") for s in step.skills}
        and (
            (step.assigned_agent or "").startswith("coding_agent")
            or re.search(r"\breview\b", f"{step.title} {step.description}", re.IGNORECASE)
        )
        and step.status != "done"
    ]
    if not pending:
        return content
    descriptions = "; ".join(f"Step {s.id}: {s.title} ({s.status})" for s in pending)
    return (
        "ROUTE: REPLAN\n\n"
        "EVALUATION: Niche predictions may be available, but planned spatial analysis/review "
        f"has not been completed: {descriptions}.\n\n"
        "FEEDBACK: Preserve the existing annotated H5AD and completed scientific work. "
        "Recover missing audit files or correct artifact paths without repeating clustering "
        "or labeling, then execute and verify the outstanding spatial review. "
        "Do not report the annotation as reviewed until that work is complete."
    )
