"""Arm-blind independent candidate judging, matching upstream CellBench."""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass

from benchmark.spatial_cellbench.methods import ModelCall
from benchmark.spatial_cellbench.schemas import (
    GroundTruthPaper,
    MatchVerdict,
    ProposalSet,
    PublicContext,
)

JUDGE_SYSTEM = """
You are an independent, arm-blind scientific benchmark judge. Decide whether the proposed
spatial-omics analysis matches at least one analysis in the ground-truth set. Compare scientific
objectives rather than exact wording or software names. Return the requested structured verdict.
""".strip()
JUDGE_PROTOCOL = "cellbench_independent_candidate_match_v1"


@dataclass(frozen=True)
class BlindJudgeProblem:
    """One candidate-versus-shuffled-truth prompt."""

    prompt: str
    truth_order: tuple[int, ...]


def _seed(value: str) -> int:
    return int(hashlib.sha256(value.encode()).hexdigest()[:16], 16)


def build_blind_judge_problem(
    public: PublicContext,
    truth: GroundTruthPaper,
    proposals: ProposalSet,
    replicate: int,
    candidate_index: int,
) -> BlindJudgeProblem:
    """Build one arm-free problem for an independently scored candidate."""
    if public.eval_id != truth.eval_id:
        raise ValueError("Public context and hidden truth IDs do not match")
    if replicate < 1:
        raise ValueError("Replicate must be positive")
    if not 0 <= candidate_index < len(proposals.proposals):
        raise ValueError("Candidate index is out of range")
    order = list(range(len(truth.analyses)))
    random.Random(
        _seed(f"{JUDGE_PROTOCOL}:{public.eval_id}:{replicate}:{candidate_index}")
    ).shuffle(order)
    candidate = proposals.proposals[candidate_index]
    truth_payload = [
        {
            "ground_truth_id": f"G{position:02d}",
            "title": truth.analyses[index].title,
            "description": truth.analyses[index].description,
        }
        for position, index in enumerate(order, 1)
    ]
    prompt = f"""
Determine whether the proposed spatial-omics analysis matches at least one analysis from the
ground-truth set. A match requires the same main scientific objective; do not require the same
method name. Related topics, generic preprocessing, unsupported follow-ups, and partial mentions
of an input modality are not matches. Judge this candidate independently: another candidate may
match the same ground-truth analysis.

PROPOSED ANALYSIS:
{json.dumps(candidate.model_dump(), indent=2, ensure_ascii=False)}

GROUND-TRUTH ANALYSES:
{json.dumps(truth_payload, indent=2, ensure_ascii=False)}
""".strip()
    return BlindJudgeProblem(prompt=prompt, truth_order=tuple(order))


def evaluate_proposals(
    public: PublicContext,
    truth: GroundTruthPaper,
    proposals: ProposalSet,
    caller: ModelCall,
    replicate: int,
) -> dict:
    """Judge every candidate independently and compute CellBench hit rates."""
    decisions = []
    prompt_hashes = []
    for candidate_index in range(len(proposals.proposals)):
        problem = build_blind_judge_problem(
            public,
            truth,
            proposals,
            replicate,
            candidate_index,
        )
        verdict = MatchVerdict.model_validate(
            caller.structured(
                f"judge_{candidate_index + 1:02d}",
                JUDGE_SYSTEM,
                problem.prompt,
                MatchVerdict,
            )
        )
        decisions.append(
            {
                "candidate_index": candidate_index,
                "match": verdict.match,
                "reason": verdict.reason,
            }
        )
        prompt_hashes.append(hashlib.sha256(problem.prompt.encode()).hexdigest())
    matched = sum(decision["match"] for decision in decisions)
    candidate_count = len(decisions)
    return {
        "judge_protocol": JUDGE_PROTOCOL,
        "judge_prompt_sha256": prompt_hashes,
        "decisions": decisions,
        "metrics": {
            "matched_candidates": matched,
            "candidate_count": candidate_count,
            "candidate_hit_fraction": matched / candidate_count,
        },
    }
