"""Experimental native Hypothesis/Critic protocol; never imports hidden answers.

The production discovery prompt is unchanged. This recovery adapter records novelty
as unassessable because the known findings of the source paper are withheld.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Literal

from pydantic import Field, create_model, model_validator

from benchmark.spatial_cellbench.methods import LangChainModelCall
from benchmark.spatial_cellbench.schemas import (
    AnalysisProposal,
    PublicContext,
    StrictModel,
    validate_proposal_count,
)

OVERVIEW_ARM = "tissueagent_overview"
REFINED_ARM = "tissueagent_refined"
REFINEMENT_PROTOCOL = "native_five_dimension_recovery_v4"
OVERVIEW_PROTOCOL = "native_shared_overview_v1"


def overview_guidance(overview: str) -> str:
    """The identical optional guidance supplied to both native specialists."""
    return (
        "\n\nFROZEN SPATIAL ANALYSIS OVERVIEW (optional method guidance):\n"
        "The public background determines which objectives are relevant. This is not a "
        "category checklist or quota; do not add unsupported modalities or comparisons.\n"
        + overview
    )


class DimensionAssessment(StrictModel):
    """Evidence-backed rating, with explicit missingness."""

    assessable: Literal[True]
    score: float = Field(ge=0, le=10)
    reason: str = Field(min_length=10)


class UnassessableNovelty(StrictModel):
    """Recovery cannot assess novelty against findings that were withheld."""

    assessable: Literal[False]
    score: None
    reason: str = Field(min_length=10)


class FiveDimensions(StrictModel):
    """Preserve the production quality dimensions in recovery mode."""

    derivable: DimensionAssessment
    novel: UnassessableNovelty
    feasible: DimensionAssessment
    specific: DimensionAssessment
    falsifiable: DimensionAssessment

    @model_validator(mode="after")
    def recovery_scope(self):
        """Separate unknown scientific novelty from assessable proposal quality."""
        if self.novel.assessable or self.novel.score is not None:
            raise ValueError("Scientific novelty is unassessable against withheld findings")
        for name in ("derivable", "feasible", "specific", "falsifiable"):
            if not getattr(self, name).assessable:
                raise ValueError(f"Recovery requires an explicit assessment of {name}")
        return self


class Blueprint(AnalysisProposal):
    """One traceable hypothesis and analysis blueprint."""

    candidate_id: str = Field(pattern=r"^C[0-9]{2}$")
    primary_objective: str = Field(min_length=10)
    context_evidence: list[str] = Field(
        min_length=1, max_length=5, description="Select E## evidence IDs from PUBLIC BACKGROUND."
    )
    assumptions: list[str] = Field(max_length=6)
    required_inputs: list[str] = Field(min_length=1, max_length=8)
    comparison: str = Field(min_length=5)
    analysis_plan: list[str] = Field(min_length=2, max_length=8)
    validation: str = Field(min_length=20)
    quality_scores: FiveDimensions


class CandidateReview(StrictModel):
    """An independent, actionable per-candidate critique."""

    candidate_id: str = Field(pattern=r"^C[0-9]{2}$")
    decision: Literal["KEEP", "REVISE", "REJECT"]
    quality_scores: FiveDimensions
    nonredundancy: str = Field(min_length=10)
    issues: list[str]
    requested_edits: list[str]
    allow_objective_change: bool
    objective_change_reason: str

    @model_validator(mode="after")
    def actionable(self):
        """Require concrete justification for repairs and replacements."""
        if self.decision == "KEEP":
            if self.issues or self.requested_edits or self.allow_objective_change:
                raise ValueError("KEEP must preserve the complete proposal unchanged")
        elif not self.issues or not self.requested_edits:
            raise ValueError("Revision/rejection requires concrete issues and edits")
        if self.allow_objective_change and len(self.objective_change_reason.strip()) < 10:
            raise ValueError("Objective changes need an explicit evidence-based reason")
        if self.decision == "REJECT" and not self.allow_objective_change:
            raise ValueError("Replacement requires explicit objective-change authorization")
        return self


class CandidateRevision(StrictModel):
    """One targeted revision and its reason."""

    candidate: Blueprint
    change_reason: str = Field(min_length=10)


class KeepReview(CandidateReview):
    """Accept a complete candidate without requesting changes."""

    decision: Literal["KEEP"]
    issues: list[str] = Field(max_length=0)
    requested_edits: list[str] = Field(max_length=0)
    allow_objective_change: Literal[False]
    objective_change_reason: Literal[""]


class RepairReview(CandidateReview):
    """Request concrete repairs while retaining the primary objective."""

    decision: Literal["REVISE"]
    issues: list[str] = Field(min_length=1)
    requested_edits: list[str] = Field(min_length=1)
    allow_objective_change: Literal[False]
    objective_change_reason: Literal[""]


class ReframeReview(CandidateReview):
    """Authorize an evidence-based objective change or replacement."""

    decision: Literal["REVISE", "REJECT"]
    issues: list[str] = Field(min_length=1)
    requested_edits: list[str] = Field(min_length=1)
    allow_objective_change: Literal[True]
    objective_change_reason: str = Field(min_length=10)


class CriticResponse(StrictModel):
    """A mutually consistent critic decision, enforced in the response schema."""

    review: KeepReview | RepairReview | ReframeReview


def review_schema(candidate_id: str):
    """Bind reviewer identity and enforce decision-dependent fields in the API schema."""
    choices = tuple(
        create_model(
            f"{base.__name__}{candidate_id}",
            __base__=base,
            candidate_id=(Literal[candidate_id], ...),
        )
        for base in (KeepReview, RepairReview, ReframeReview)
    )
    return create_model(
        f"CriticResponse{candidate_id}",
        __base__=CriticResponse,
        review=(choices[0] | choices[1] | choices[2], ...),
    )


DIMENSION_INSTRUCTIONS = """
Assess exactly five dimensions, each with evidence and a score from 0 to 10:
derivable (grounded in public context), novel (scientific novelty relative to known
findings), feasible (available inputs and practicable computation), specific (precise
objective/comparison), falsifiable (a test with an outcome that could refute the claim).
This is analysis recovery, not discovery. The source paper's findings are hidden:
novel MUST have assessable=false, score=null, and explain that scientific novelty
cannot be established. The other four dimensions must have assessable=true and scores.
Nonredundancy across candidates is separate from scientific novelty. Never invent
results, cohorts, modalities, time points, or annotations. State necessary assumptions.
""".strip()

HYPOTHESIS_SYSTEM = (
    """You are TissueAgent's Hypothesis Agent using a structured recovery adapter.
Recover a likely computational spatial analysis from the public background. Do not identify
or search for the paper. The overview is method guidance, not evidence that an analysis occurred.
Create a coherent single primary objective, not a grab bag of possible analyses. The title and
detailed summary must stand alone for final export and include the objective, inputs,
comparison, method and validation; do not state invented experimental results.
context_evidence must list the E## sentence identifiers supplied in PUBLIC BACKGROUND.
Select only sentences that support this objective. Their original text is stored deterministically.
Prefer complementary context-supported objectives; different algorithms for the same
biological question alone are not distinct objectives. Do not force overview-category coverage.
"""
    + DIMENSION_INSTRUCTIONS
)

CRITIC_SYSTEM = (
    """You are TissueAgent's independent Critic Agent. Review the candidate against
the public background and overview, without access to hidden answers or the author's scores.
Assess all five dimensions independently. KEEP a supported, specific, feasible, falsifiable
candidate: do not rewrite for style. REVISE only for concrete defects; request minimal repairs.
REJECT only when the objective is unsupported or substantively redundant with a stronger peer,
and specify a context-grounded replacement direction. Compare primary scientific objectives,
not just shared methods. A broad generic survey is not preferable to a well-supported objective.
Do not remove a credible candidate merely because another overview category is absent.
For KEEP, issues and requested_edits must be empty and allow_objective_change=false.
For REVISE, preserve primary_objective unless an explicit evidence-based change is necessary;
authorize any such change using allow_objective_change and objective_change_reason.
For REJECT, explicitly authorize replacement. Explain nonredundancy separately from novelty.
"""
    + DIMENSION_INSTRUCTIONS
)


def evidence_ledger(public: PublicContext) -> dict[str, str]:
    """Index unchanged source sentences so evidence never depends on model transcription."""
    sentences = re.split(r"(?<=[.!?])\s+", public.context.strip())
    return {f"E{i:02d}": sentence for i, sentence in enumerate(sentences, 1)}


def blueprint_schema(public: PublicContext, candidate_id: str, objective: str | None = None):
    """Constrain IDs, evidence references and any immutable objective in the API schema."""
    fields = {
        "candidate_id": (Literal[candidate_id], ...),
        "context_evidence": (
            list[Literal[tuple(evidence_ledger(public))]],
            Field(min_length=1, max_length=5),
        ),
    }
    if objective is not None:
        fields["primary_objective"] = (Literal[objective], ...)
    return create_model(f"GroundedBlueprint{candidate_id}", __base__=Blueprint, **fields)


def validate_blueprint(candidate: Blueprint, candidate_id: str, public: PublicContext) -> None:
    """Verify identity and exact grounding in the public context."""
    if candidate.candidate_id != candidate_id:
        raise ValueError("Candidate identity changed")
    if any(reference not in evidence_ledger(public) for reference in candidate.context_evidence):
        raise ValueError("Candidate evidence must reference a frozen public-context sentence")


def apply_revision(draft: Blueprint, review: CandidateReview, revision: CandidateRevision | None):
    """Apply exactly one authorized edit; KEEP returns the original object."""
    if review.candidate_id != draft.candidate_id:
        raise ValueError("Review identity mismatch")
    if review.decision == "KEEP":
        if revision is not None:
            raise ValueError("KEEP must not invoke revision")
        return draft
    if revision is None or revision.candidate.candidate_id != draft.candidate_id:
        raise ValueError("A revision must retain the original candidate identity")
    if (
        revision.candidate.primary_objective != draft.primary_objective
        and not review.allow_objective_change
    ):
        raise ValueError("Unapproved objective change")
    return revision.candidate


class RefinementSession:
    """Bounded specialist work dispatched by the real native outer graph.

    No hidden reference data, judge feedback, whole-set rewrite or semantic retry.
    A failed invocation seals this session; redispatch cannot spend another budget.
    """

    def __init__(
        self, public, overview, count, outputs, model_id, caller_factory=LangChainModelCall
    ):
        """Bind immutable public inputs and a lazy model client."""
        self.public, self.overview, self.count = public, overview, count
        self.outputs, self.model_id = Path(outputs), model_id
        self.caller_factory, self.caller = caller_factory, None
        self.drafts, self.reviews, self.finals, self.changes = [], [], [], []
        self.written = {}
        self.failure = None

    def _common(self):
        return (
            "PUBLIC BACKGROUND (fixed evidence IDs):\n"
            + json.dumps(evidence_ledger(self.public), ensure_ascii=False)
            + overview_guidance(self.overview)
        )

    def _write(self, relative, payload, author=None):
        from benchmark.spatial_cellbench.ta import _atomic_write_json, _semantic_json_sha256

        _atomic_write_json(self.outputs / relative, payload)
        self.written[relative] = _semantic_json_sha256(payload)
        if author:
            audit = self.outputs / "audit" / f"{author}_validated_writes.jsonl"
            audit.parent.mkdir(parents=True, exist_ok=True)
            with audit.open("a") as stream:
                stream.write(
                    json.dumps(
                        {"relative_path": relative, "payload_sha256": self.written[relative]}
                    )
                    + "\n"
                )

    def verify_artifacts(self):
        """Reject changes to specialist artifacts by other actors."""
        from benchmark.spatial_cellbench.ta import _semantic_json_sha256

        for relative, expected in self.written.items():
            if _semantic_json_sha256(json.loads((self.outputs / relative).read_text())) != expected:
                raise RuntimeError(f"Specialist artifact was modified externally: {relative}")

    def trace(self):
        """Return auditable costs, decisions and artifact identities."""
        from benchmark.spatial_cellbench.ta import _sha256_text

        calls = self.caller.traces if self.caller else []
        return {
            "protocol": REFINEMENT_PROTOCOL,
            "model_id": self.model_id,
            "context_sha256": self.public.context_sha256,
            "overview_sha256": _sha256_text(self.overview),
            "proposal_count": self.count,
            "logical_call_budget": 3 * self.count,
            "logical_model_calls": len(calls),
            "calls": calls,
            "failed_attempts": self.caller.failed_attempts if self.caller else [],
            "observable_model_attempts": self.caller.observable_attempt_count if self.caller else 0,
            "semantic_retries": 0,
            "failure": self.failure,
            "status": "failed" if self.failure else ("success" if self.finals else "partial"),
            "artifact_sha256": dict(self.written),
            "decisions": [review.decision for review in self.reviews],
            "changes": self.changes,
        }

    def invoke(self, role):
        """Execute one idempotent specialist milestone and seal failures."""
        from benchmark.spatial_cellbench.ta import _atomic_write_json

        if self.failure:
            raise RuntimeError("Refinement session is sealed after a failed invocation")
        try:
            self.verify_artifacts()
            if self.caller is None:
                self.caller = self.caller_factory(self.model_id)
            if role == "critic":
                self._review()
            elif role == "hypothesis":
                if not self.drafts:
                    self._draft()
                elif self.reviews:
                    self._finalize()
            else:
                raise ValueError("Unknown specialist")
        except Exception as exc:
            self.failure = f"{type(exc).__name__}: {str(exc)[:400]}"
            raise
        finally:
            _atomic_write_json(self.outputs / "audit" / "refinement_trace.json", self.trace())
        return "Validated specialist artifacts written. " + (
            "Final proposals complete."
            if self.finals
            else "Critique complete; dispatch Hypothesis for targeted revision and export."
            if self.reviews
            else "Draft complete; dispatch Critic next."
        )

    def _draft(self):
        self._write("hypotheses/context_evidence.json", evidence_ledger(self.public))
        for index in range(1, self.count + 1):
            cid = f"C{index:02d}"
            peers = [
                {
                    "candidate_id": d.candidate_id,
                    "primary_objective": d.primary_objective,
                    "summary": d.summary,
                }
                for d in self.drafts
            ]
            candidate = self.caller.structured(
                f"native_{cid}_draft",
                HYPOTHESIS_SYSTEM,
                self._common()
                + f"\nDraft candidate {cid} of {self.count}.\n"
                + "EXISTING CANDIDATES:\n"
                + json.dumps(peers),
                blueprint_schema(self.public, cid),
            )
            validate_blueprint(candidate, cid, self.public)
            self.drafts.append(candidate)
            self._write(f"hypotheses/blueprints/draft_{cid}.json", candidate.model_dump())
        self._write("hypotheses/draft_proposals.json", self._export(self.drafts), "hypothesis")

    def _review(self):
        if len(self.drafts) != self.count:
            raise RuntimeError("Critic requires a complete validated draft")
        if self.reviews:
            return
        for draft in self.drafts:
            peers = [
                {
                    "candidate_id": p.candidate_id,
                    "primary_objective": p.primary_objective,
                    "summary": p.summary,
                }
                for p in self.drafts
                if p != draft
            ]
            response = self.caller.structured(
                f"native_{draft.candidate_id}_critic",
                CRITIC_SYSTEM,
                self._common()
                + "\nCANDIDATE:\n"
                + json.dumps(draft.model_dump(exclude={"quality_scores"}))
                + "\nPEER OBJECTIVES:\n"
                + json.dumps(peers),
                review_schema(draft.candidate_id),
            )
            review = CandidateReview.model_validate(response.review.model_dump())
            if review.candidate_id != draft.candidate_id:
                raise ValueError("Review identity mismatch")
            self.reviews.append(review)
            self._write(
                f"hypotheses/blueprints/review_{draft.candidate_id}.json", review.model_dump()
            )
        self._write(
            "hypotheses/critique.json",
            {"reviews": [r.model_dump() for r in self.reviews]},
            "critic",
        )

    def _finalize(self):
        if self.finals:
            return
        if len(self.reviews) != self.count:
            raise RuntimeError("Final export requires all independent reviews")
        for draft, review in zip(self.drafts, self.reviews, strict=True):
            revision = None
            if review.decision != "KEEP":
                peers = [p.primary_objective for p in self.finals] + [
                    p.primary_objective for p in self.drafts[len(self.finals) + 1 :]
                ]
                revision = self.caller.structured(
                    f"native_{draft.candidate_id}_revision",
                    HYPOTHESIS_SYSTEM,
                    self._common()
                    + "\nRevise this one candidate only. Apply the requested repairs. "
                    "Preserve candidate_id. Copy primary_objective exactly unless the critic "
                    "explicitly "
                    "authorized a change. Explain the edits in change_reason.\nDRAFT:\n"
                    + draft.model_dump_json()
                    + "\nCRITIQUE:\n"
                    + review.model_dump_json()
                    + "\nPEER OBJECTIVES:\n"
                    + json.dumps(peers),
                    create_model(
                        f"TargetedRevision{draft.candidate_id}",
                        __base__=CandidateRevision,
                        candidate=(
                            blueprint_schema(
                                self.public,
                                draft.candidate_id,
                                None if review.allow_objective_change else draft.primary_objective,
                            ),
                            ...,
                        ),
                    ),
                )
            final = apply_revision(draft, review, revision)
            validate_blueprint(final, draft.candidate_id, self.public)
            self.finals.append(final)
            self.changes.append(
                {
                    "candidate_id": draft.candidate_id,
                    "decision": review.decision,
                    "changed": final.model_dump() != draft.model_dump(),
                    "objective_changed": final.primary_objective != draft.primary_objective,
                    "change_reason": revision.change_reason
                    if revision
                    else "KEEP; copied unchanged",
                }
            )
            self._write(
                f"hypotheses/blueprints/final_{draft.candidate_id}.json", final.model_dump()
            )
        expected = [f"native_C{i:02d}_draft" for i in range(1, self.count + 1)]
        expected += [f"native_C{i:02d}_critic" for i in range(1, self.count + 1)]
        expected += [
            f"native_{r.candidate_id}_revision" for r in self.reviews if r.decision != "KEEP"
        ]
        if [call["stage"] for call in self.caller.traces] != expected:
            raise RuntimeError("Native refinement calls violate the fixed budget or stage order")
        self._write("hypotheses/final_proposals.json", self._export(self.finals), "hypothesis")

    def _export(self, candidates):
        payload = {"proposals": [{"title": p.title, "summary": p.summary} for p in candidates]}
        return validate_proposal_count(payload, self.count).model_dump()

    def roster(self):
        """Expose Hypothesis and Critic through native CustomAgent dispatch."""
        from agents.agent_defns import CustomAgent
        from langchain_core.tools import StructuredTool

        def factory(role):
            def constructor(state_queue, context_resolver=None):
                del state_queue, context_resolver

                def run_agent(prompt: str) -> str:
                    del prompt  # Scientific inputs are frozen, never Manager-generated hints.
                    return self.invoke(role)

                return StructuredTool.from_function(
                    func=run_agent,
                    name=f"{role}_refinement_tool",
                    description=(
                        "Draft candidates if no draft exists; after critique, apply only "
                        "authorized per-candidate repairs and deterministically export "
                        "final proposals."
                        if role == "hypothesis"
                        else "Independently assess each drafted candidate "
                        "on five dimensions and write KEEP/REVISE/REJECT decisions."
                    ),
                )

            return constructor

        return [
            CustomAgent(
                id="hypothesis",
                name="Hypothesis Agent",
                description="Structured five-dimension drafting and targeted final revision. "
                "Writes "
                "hypotheses/draft_proposals.json in step 1 and hypotheses/final_proposals.json "
                "after Critic in step 3. Does not write critiques.",
                ctor=factory("hypothesis"),
            ),
            CustomAgent(
                id="critic",
                name="Critic Agent",
                description="Independent five-dimension per-candidate review. Writes only "
                "hypotheses/critique.json in step 2. Never writes proposals.",
                ctor=factory("critic"),
            ),
        ]
