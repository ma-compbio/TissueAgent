"""Tests for the public CellBench three-arm comparison protocol."""

from pathlib import Path
import sys

import pytest

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from demo.run_cellbench_comparison import (  # noqa: E402
    DEFAULT_DATASET,
    AnalysisProposal,
    CandidateMatch,
    MatchingVerdict,
    ProposalCritique,
    ProposalSet,
    load_dataset,
    run_paper,
    sanitize_matches,
    score_matches,
)


def _proposals(prefix: str) -> ProposalSet:
    return ProposalSet(
        proposals=[
            AnalysisProposal(
                title=f"{prefix} candidate {index}",
                hypothesis=f"Hypothesis {index}",
                analysis_plan=["Prepare the stated data", "Test the comparison"],
                summary=f"Summary {index}",
            )
            for index in range(1, 6)
        ]
    )


class FakeCaller:
    """Record prompts and return schema-valid deterministic responses."""

    def __init__(self) -> None:
        """Initialize an empty call log."""
        self.calls: list[dict] = []

    def __call__(self, stage, system_prompt, user_prompt, schema):
        """Record one call and return a deterministic schema instance."""
        self.calls.append(
            {
                "stage": stage,
                "system": system_prompt,
                "user": user_prompt,
                "schema": schema,
            }
        )
        if schema is ProposalSet:
            return _proposals(stage)
        if schema is ProposalCritique:
            return ProposalCritique(
                overall_assessment=f"Critique for {stage}",
                proposal_feedback=[f"Feedback {index}" for index in range(1, 6)],
                coverage_gaps=[],
                duplication_risks=[],
            )
        if schema is MatchingVerdict:
            return MatchingVerdict(
                matches=[
                    CandidateMatch(
                        candidate_index=1,
                        ground_truth_index=1,
                        confidence=0.9,
                        reason="Same objective and method",
                    )
                ],
                assessment="One match",
            )
        raise AssertionError(f"Unexpected schema: {schema}")


class RefusingRevisionCaller(FakeCaller):
    """Simulate a persistent provider safety refusal on CV revision."""

    def __call__(self, stage, system_prompt, user_prompt, schema):
        """Raise the provider refusal only for the selected revision stage."""
        if stage == "cv_revision":
            self.calls.append(
                {
                    "stage": stage,
                    "system": system_prompt,
                    "user": user_prompt,
                    "schema": schema,
                }
            )
            raise RuntimeError(
                "invalid_prompt: prompt flagged as potentially violating usage policy"
            )
        return super().__call__(stage, system_prompt, user_prompt, schema)


def test_public_cellbench_dataset_is_complete() -> None:
    """The public source contains all 50 contexts and 483 target analyses."""
    papers = load_dataset(DEFAULT_DATASET)
    counts = [len(paper["ground_truth"]) for paper in papers]
    assert len(papers) == 50
    assert sum(counts) == 483
    assert min(counts) == 5
    assert max(counts) == 18


def test_one_to_one_sanitizer_keeps_highest_confidence_edges() -> None:
    """Duplicate or invalid judge edges cannot inflate benchmark recall."""
    verdict = MatchingVerdict(
        matches=[
            CandidateMatch(
                candidate_index=1,
                ground_truth_index=1,
                confidence=0.7,
                reason="lower-confidence candidate duplicate",
            ),
            CandidateMatch(
                candidate_index=1,
                ground_truth_index=2,
                confidence=0.9,
                reason="best candidate edge",
            ),
            CandidateMatch(
                candidate_index=2,
                ground_truth_index=2,
                confidence=0.8,
                reason="ground-truth duplicate",
            ),
            CandidateMatch(
                candidate_index=2,
                ground_truth_index=3,
                confidence=0.6,
                reason="remaining valid edge",
            ),
            CandidateMatch(
                candidate_index=6,
                ground_truth_index=4,
                confidence=1.0,
                reason="invalid candidate index",
            ),
        ],
        assessment="test",
    )
    kept, dropped = sanitize_matches(verdict, candidate_count=5, ground_truth_count=4)
    assert [(edge["candidate_index"], edge["ground_truth_index"]) for edge in kept] == [
        (1, 2),
        (2, 3),
    ]
    assert {edge["drop_reason"] for edge in dropped} == {
        "candidate_index_out_of_range",
        "duplicate_candidate",
        "duplicate_ground_truth",
    }


def test_metric_math_uses_fixed_five_proposal_denominator() -> None:
    """Precision, recall, and F1 use the declared fixed-K protocol."""
    metrics = score_matches([{"candidate_index": 1}, {"candidate_index": 2}], 5, 8)
    assert metrics["proposal_precision_at_5"] == pytest.approx(2 / 5)
    assert metrics["ground_truth_recall_at_5"] == pytest.approx(2 / 8)
    assert metrics["f1_at_5"] == pytest.approx(2 * (2 / 5) * (2 / 8) / (2 / 5 + 2 / 8))
    assert metrics["paper_hit_rate"] == 1.0


def test_protocol_is_blind_paired_equal_budget_and_resumable(tmp_path: Path) -> None:
    """GT stays out of generation and the shared CV draft is not regenerated."""
    secret = "SECRET_HIDDEN_GROUND_TRUTH_METHOD"
    paper = {
        "paper_index": 0,
        "paper_id": "paper-zero",
        "context": "Public paper context with single-cell RNA sequencing.",
        "ground_truth": [{"title": "Hidden", "description": secret}],
    }
    generation = FakeCaller()
    judge = FakeCaller()
    checkpoint_path = tmp_path / "paper.json"

    first = run_paper(paper, "Public method examples", generation, judge, checkpoint_path)
    generation_count = len(generation.calls)
    judge_count = len(judge.calls)
    second = run_paper(paper, "Public method examples", generation, judge, checkpoint_path)

    assert generation_count == 8
    assert judge_count == 3
    assert len(generation.calls) == generation_count
    assert len(judge.calls) == judge_count
    assert first["logical_call_budget"] == {
        "tissueagent": 3,
        "cellvoyager": 3,
        "combined": 3,
    }
    assert second["status"] == "complete"
    assert all(
        secret not in call["system"] and secret not in call["user"]
        for call in generation.calls
    )
    assert all(secret in call["user"] for call in judge.calls)
    combined_prompt = next(
        call["user"] for call in generation.calls if call["stage"] == "combined_critic"
    )
    cv_prompt = next(
        call["user"] for call in generation.calls if call["stage"] == "cv_critic"
    )
    assert "cv_draft candidate 1" in combined_prompt
    assert "cv_draft candidate 1" in cv_prompt


def test_persistent_safety_refusal_reuses_valid_draft(tmp_path: Path) -> None:
    """A persistent provider refusal is explicit and does not drop the paper."""
    paper = {
        "paper_index": 0,
        "paper_id": "public-paper",
        "context": "Benign public biomedical context.",
        "ground_truth": [{"title": "Analysis", "description": "Public method"}],
    }
    generation = RefusingRevisionCaller()
    checkpoint = run_paper(
        paper,
        "Public examples",
        generation,
        FakeCaller(),
        tmp_path / "paper.json",
    )
    stage = checkpoint["stages"]["cv_revision"]
    assert stage["provider_safety_fallback"] == "reused_prior_valid_stage"
    assert stage["output"] == checkpoint["stages"]["cv_draft"]["output"]
    assert checkpoint["status"] == "complete"
