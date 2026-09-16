"""Data contracts for the spatial paper benchmark."""

from __future__ import annotations

from functools import lru_cache

from pydantic import BaseModel, ConfigDict, Field, create_model

MAX_ANALYSES = 30


class StrictModel(BaseModel):
    """Base model that rejects undeclared benchmark fields."""

    model_config = ConfigDict(extra="forbid")


class AnalysisProposal(StrictModel):
    """One final analysis candidate shared by all three arms."""

    title: str = Field(min_length=3)
    summary: str = Field(min_length=20)


class CVAnalysis(StrictModel):
    """Internal rich representation used by the Spatial-CV review loop."""

    title: str = Field(min_length=3)
    hypothesis: str = Field(min_length=3)
    analysis_plan: list[str] = Field(min_length=2, max_length=12)
    summary: str = Field(min_length=20)


class ProposalSet(StrictModel):
    """A paper-specific number of final analysis candidates."""

    proposals: list[AnalysisProposal] = Field(min_length=1, max_length=MAX_ANALYSES)


@lru_cache(maxsize=MAX_ANALYSES)
def proposal_set_schema(count: int) -> type[ProposalSet]:
    """Return a structured-output schema that requires exactly ``count`` proposals."""
    if not 1 <= count <= MAX_ANALYSES:
        raise ValueError(f"Proposal count must be between 1 and {MAX_ANALYSES}")
    return create_model(
        f"ProposalSet{count}",
        __base__=ProposalSet,
        proposals=(
            list[AnalysisProposal],
            Field(min_length=count, max_length=count),
        ),
    )


def validate_proposal_count(value: object, count: int) -> ProposalSet:
    """Validate a proposal object and its paper-specific oracle count."""
    parsed = ProposalSet.model_validate(value)
    if len(parsed.proposals) != count:
        raise ValueError(f"Expected {count} proposals, received {len(parsed.proposals)}")
    return parsed


class PublicContext(StrictModel):
    """The only paper text visible to generation workers."""

    eval_id: str = Field(pattern=r"^spcb_[0-9a-f]{10}$")
    context: str = Field(min_length=100)
    word_count: int = Field(ge=150, le=700)
    context_rule_version: str
    context_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class Evidence(StrictModel):
    """One source-paper location supporting a hidden analysis."""

    page: int = Field(ge=1)
    section: str = Field(min_length=3)
    anchor: str = Field(min_length=8, max_length=300)


class GroundTruthAnalysis(StrictModel):
    """One independently reported, spatial-core analysis."""

    analysis_id: str = Field(pattern=r"^A[0-9]{2}$")
    title: str = Field(min_length=3)
    description: str = Field(min_length=20)
    analysis_type: str = Field(min_length=3)
    evidence: list[Evidence] = Field(min_length=1)


class CurationRecord(StrictModel):
    """Paper-level independent annotation and adjudication record."""

    protocol: str
    curator_a_count: int = Field(ge=1)
    curator_b_count: int = Field(ge=1)
    matched_count: int = Field(ge=0)
    set_f1: float = Field(ge=0.0, le=1.0)
    adjudication_status: str
    notes: str = ""


class GroundTruthPaper(StrictModel):
    """Hidden analysis set for one evaluated paper."""

    eval_id: str = Field(pattern=r"^spcb_[0-9a-f]{10}$")
    schema_version: int = Field(ge=1)
    analyses: list[GroundTruthAnalysis] = Field(min_length=1, max_length=MAX_ANALYSES)
    curation: CurationRecord


class MatchVerdict(StrictModel):
    """One independent candidate-versus-truth-set judge decision."""

    match: bool
    reason: str = Field(min_length=3)
