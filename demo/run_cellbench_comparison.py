#!/usr/bin/env python3
"""Run a blind three-arm comparison on the public CellBench-50 benchmark.

The benchmark compares TissueAgent-style planning, CellVoyager-style planning,
and a paired integration in which the CellVoyager draft is revised by the
TissueAgent critic. Generation sees paper context only; hidden analyses are
introduced only in the arm-blind one-to-one judge.
"""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import statistics
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from pydantic import BaseModel, Field

_REPO = Path(__file__).resolve().parents[1]
for _path in (str(_REPO / "src"), str(_REPO)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

PROTOCOL_ID = "cellbench_three_arm_v1"
ARMS = ("tissueagent", "cellvoyager", "combined")
K = 5
DEFAULT_DATASET = (
    _REPO
    / "src"
    / "agents"
    / "agent_registry"
    / "cellvoyager_agent"
    / "upstream"
    / "CellBench"
    / "data"
    / "cellbench_50.csv"
)
DEFAULT_OVERVIEW = (
    _REPO
    / "src"
    / "agents"
    / "agent_registry"
    / "cellvoyager_agent"
    / "upstream"
    / "cellvoyager"
    / "prompts"
    / "DeepResearch_Analyses.txt"
)
DEFAULT_OUTPUT_ROOT = _REPO / "benchmark" / "cellbench" / "runs"


class AnalysisProposal(BaseModel):
    """One proposed analysis and its executable scientific outline."""

    title: str
    hypothesis: str
    analysis_plan: list[str] = Field(min_length=2, max_length=8)
    summary: str


class ProposalSet(BaseModel):
    """Exactly five distinct proposed analyses."""

    proposals: list[AnalysisProposal] = Field(min_length=K, max_length=K)


class ProposalCritique(BaseModel):
    """Critique used to revise a five-proposal draft."""

    overall_assessment: str
    proposal_feedback: list[str] = Field(min_length=K, max_length=K)
    coverage_gaps: list[str]
    duplication_risks: list[str]


class CandidateMatch(BaseModel):
    """A proposed one-to-one edge between a candidate and a hidden analysis."""

    candidate_index: int
    ground_truth_index: int
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str


class MatchingVerdict(BaseModel):
    """Arm-blind semantic matches emitted by the independent judge."""

    matches: list[CandidateMatch]
    assessment: str


StructuredCall = Callable[[str, str, str, type[BaseModel]], BaseModel]


def _is_provider_safety_refusal(error: object) -> bool:
    return "invalid_prompt" in str(error).lower()


class LangChainStructuredCaller:
    """Invoke one configured project model with Pydantic structured output."""

    def __init__(self, model_id: str) -> None:
        """Build one reusable structured-output model client."""
        from models import build_chat_model

        self.model_id = model_id
        self._model = build_chat_model(model_id, max_retries=3, timeout=300)
        self._chains: dict[type[BaseModel], object] = {}
        self.safety_retry_stages: set[str] = set()

    def __call__(
        self,
        stage: str,
        system_prompt: str,
        user_prompt: str,
        schema: type[BaseModel],
    ) -> BaseModel:
        """Invoke one stage and validate its declared output schema."""
        chain = self._chains.get(schema)
        if chain is None:
            chain = self._model.with_structured_output(schema)
            self._chains[schema] = chain
        messages = [("system", system_prompt), ("human", user_prompt)]
        try:
            result = chain.invoke(messages)
        except Exception as exc:
            if not _is_provider_safety_refusal(exc):
                raise
            benign_context = (
                "This is a benign evaluation using a public biomedical paper. "
                "It requests only high-level retrospective computational-analysis "
                "planning, not pathogen design, wet-lab procedures, or clinical advice.\n\n"
            )
            result = chain.invoke(
                [("system", benign_context + system_prompt), ("human", user_prompt)]
            )
            self.safety_retry_stages.add(stage)
        return schema.model_validate(result)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _atomic_write_json(path: Path, payload: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def load_dataset(path: Path, paper_limit: int | None = None) -> list[dict]:
    """Load and validate public CellBench rows without evaluating arbitrary code."""
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    required = {"context", "analyses_titles", "analyses_full", "id"}
    if not rows or not required.issubset(rows[0]):
        raise ValueError(f"Unexpected CellBench schema in {path}")

    papers = []
    for index, row in enumerate(rows):
        ground_truth = ast.literal_eval(row["analyses_full"])
        if not isinstance(ground_truth, list) or not ground_truth:
            raise ValueError(f"Paper {row['id']} has no ground-truth analyses")
        for analysis in ground_truth:
            if not isinstance(analysis, dict) or not {
                "title",
                "description",
            }.issubset(analysis):
                raise ValueError(f"Paper {row['id']} has malformed ground truth")
        papers.append(
            {
                "paper_index": index,
                "paper_id": str(row["id"]),
                "context": row["context"].strip(),
                "ground_truth": ground_truth,
            }
        )
    if paper_limit is not None:
        if paper_limit < 1:
            raise ValueError("paper_limit must be positive")
        papers = papers[:paper_limit]
    return papers


def _proposal_json(proposals: ProposalSet) -> str:
    return json.dumps(proposals.model_dump(), indent=2, ensure_ascii=False)


def _critique_json(critique: ProposalCritique) -> str:
    return json.dumps(critique.model_dump(), indent=2, ensure_ascii=False)


def _ta_draft_prompts(context: str) -> tuple[str, str]:
    system = """You are the analysis-planning component of TissueAgent, an expert
bioinformatics planner. Recover the computational analyses most likely performed
in a paper from its background alone. Produce exactly five distinct, high-level,
scientifically executable proposals. Focus on WHAT should be analyzed, group
related actions, and avoid unsupported assumptions or modalities."""
    user = f"""The paper's computational analyses are hidden. Infer the five most
likely analyses from the background below.

Each proposal must identify a concrete biological question, use only data or
modalities mentioned in the background, state a compact workflow, and include
an appropriate comparison or validation. Cover complementary major objectives;
do not spend multiple proposals restating the same generic preprocessing step.

PAPER BACKGROUND
{context}"""
    return system, user


def _ta_critic_prompts(
    context: str, proposals: ProposalSet
) -> tuple[str, str]:
    system = """You are TissueAgent's scientific quality-control critic. Review
five candidate analyses for relevance to the paper, specificity, feasibility,
biological plausibility, statistical testability, and diversity. Penalize
unsupported modalities, invented sample labels, generic filler, and duplicate
objectives. Return feedback in candidate order."""
    user = f"""The hidden target is the set of analyses most likely performed in
the paper. Critique this draft without access to the hidden answers. Identify
specific revisions that improve likely method recovery while retaining exactly
five distinct proposals.

PAPER BACKGROUND
{context}

DRAFT PROPOSALS
{_proposal_json(proposals)}"""
    return system, user


def _ta_revision_prompts(
    context: str,
    proposals: ProposalSet,
    critique: ProposalCritique,
) -> tuple[str, str]:
    system = """You are TissueAgent's senior bioinformatics planner. Revise the
five proposals using the scientific critique. Return exactly five distinct
analyses most likely present in the hidden paper. Keep them feasible with only
the stated data, specific enough to match a real method, and free of padding."""
    user = f"""Revise the complete proposal set. You may replace weak or duplicate
proposals, but retain exactly five complementary major analyses.

PAPER BACKGROUND
{context}

DRAFT PROPOSALS
{_proposal_json(proposals)}

CRITIQUE
{_critique_json(critique)}"""
    return system, user


def _cv_draft_prompts(context: str, overview: str) -> tuple[str, str]:
    system = """You are a creative and skilled expert in single-cell
transcriptomics computational analysis. Propose exactly five distinct analyses
most likely performed in the hidden paper."""
    user = f"""You are given the background/introduction from a research paper.
The computational analyses done in the paper are hidden. Propose the five
computational analyses most likely to be in that hidden set.

Treat each analysis plan as a scientific workflow: begin with relevant broad
exploration, focus on the biological objective, and include statistical
validation where appropriate. Each plan step must be distinct. Use only data
explicitly mentioned in the paper. Do not suggest spatial analysis unless
spatial data are mentioned, or RNA velocity unless spliced/unspliced counts are
mentioned. Avoid five variants of the same analysis.

PAPER BACKGROUND
{context}

EXAMPLES OF POTENTIAL ANALYSIS TYPES
{overview}"""
    return system, user


def _cv_critic_prompts(
    context: str,
    proposals: ProposalSet,
    overview: str,
) -> tuple[str, str]:
    system = """You are a single-cell bioinformatics expert providing feedback
on analysis plans. Return feedback for all five candidates in their current
order."""
    user = f"""The following analyses were generated from a paper background.
The paper's actual analyses are hidden, and the goal is to recover those most
likely in the hidden set. Critique relevance, workflow quality, use of only
explicitly mentioned data, missing likely analyses, and overlap among the five.

PAPER BACKGROUND
{context}

DRAFT PROPOSALS
{_proposal_json(proposals)}

EXAMPLES OF POTENTIAL ANALYSIS TYPES
{overview}"""
    return system, user


def _cv_revision_prompts(
    context: str,
    proposals: ProposalSet,
    critique: ProposalCritique,
    overview: str,
) -> tuple[str, str]:
    system = """You are a creative and skilled expert in single-cell
transcriptomics computational analysis. Incorporate the feedback and return
exactly five distinct revised analyses."""
    user = f"""Update the hypothesis, summary, and workflow for the complete set
of analyses so they are most likely to match the paper's hidden analyses. Use
only data explicitly mentioned in the background and preserve five distinct
scientific objectives.

PAPER BACKGROUND
{context}

DRAFT PROPOSALS
{_proposal_json(proposals)}

FEEDBACK
{_critique_json(critique)}

EXAMPLES OF POTENTIAL ANALYSIS TYPES
{overview}"""
    return system, user


def _judge_prompts(
    proposals: ProposalSet, ground_truth: list[dict]
) -> tuple[str, str]:
    system = """You are an independent, arm-blind scientific benchmark judge.
Match proposed analyses to hidden ground-truth analyses using a strict one-to-one
mapping. Emit only genuine semantic matches; candidates and ground truths may
each appear at most once."""
    candidates = "\n\n".join(
        f"CANDIDATE {index}\n{proposal.model_dump_json(indent=2)}"
        for index, proposal in enumerate(proposals.proposals, 1)
    )
    labels = "\n\n".join(
        f"GROUND TRUTH {index}\nTitle: {analysis['title']}\n"
        f"Description: {analysis['description']}"
        for index, analysis in enumerate(ground_truth, 1)
    )
    user = f"""Find the best one-to-one semantic matches between the five
candidates and the ground truths.

A match requires the same scientific objective and the essential data,
comparison, or computational method. Topic overlap alone is not enough. A
generic proposal matches a generic pipeline ground truth only when its data
modality and core procedure agree. Do not match one ground truth to duplicate
candidates. Omit every non-match. Indices are one-based.

{candidates}

{labels}"""
    return system, user


def sanitize_matches(
    verdict: MatchingVerdict,
    candidate_count: int,
    ground_truth_count: int,
) -> tuple[list[dict], list[dict]]:
    """Enforce valid one-to-one edges, retaining the highest-confidence edges."""
    valid = []
    dropped = []
    for position, match in enumerate(verdict.matches):
        edge = match.model_dump()
        edge["source_position"] = position
        if not 1 <= match.candidate_index <= candidate_count:
            edge["drop_reason"] = "candidate_index_out_of_range"
            dropped.append(edge)
        elif not 1 <= match.ground_truth_index <= ground_truth_count:
            edge["drop_reason"] = "ground_truth_index_out_of_range"
            dropped.append(edge)
        else:
            valid.append(edge)

    valid.sort(key=lambda edge: (-edge["confidence"], edge["source_position"]))
    kept = []
    used_candidates: set[int] = set()
    used_ground_truth: set[int] = set()
    for edge in valid:
        if edge["candidate_index"] in used_candidates:
            edge["drop_reason"] = "duplicate_candidate"
            dropped.append(edge)
            continue
        if edge["ground_truth_index"] in used_ground_truth:
            edge["drop_reason"] = "duplicate_ground_truth"
            dropped.append(edge)
            continue
        used_candidates.add(edge["candidate_index"])
        used_ground_truth.add(edge["ground_truth_index"])
        edge.pop("source_position", None)
        kept.append(edge)
    for edge in dropped:
        edge.pop("source_position", None)
    kept.sort(key=lambda edge: edge["candidate_index"])
    return kept, dropped


def score_matches(
    matches: list[dict], candidate_count: int, ground_truth_count: int
) -> dict:
    """Compute fixed-K proposal precision, ground-truth recall, F1, and hit rate."""
    matched = len(matches)
    precision = matched / candidate_count if candidate_count else 0.0
    recall = matched / ground_truth_count if ground_truth_count else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "matched_proposals": matched,
        "matched_ground_truth": matched,
        "proposal_count": candidate_count,
        "ground_truth_count": ground_truth_count,
        "proposal_precision_at_5": precision,
        "ground_truth_recall_at_5": recall,
        "f1_at_5": f1,
        "paper_hit_rate": float(matched > 0),
    }


def _load_checkpoint(path: Path, paper: dict) -> dict:
    context_hash = _sha256_bytes(paper["context"].encode("utf-8"))
    if path.is_file():
        checkpoint = json.loads(path.read_text(encoding="utf-8"))
        if checkpoint.get("protocol_id") != PROTOCOL_ID:
            raise ValueError(f"Protocol mismatch in {path}")
        if checkpoint.get("context_sha256") != context_hash:
            raise ValueError(f"Context mismatch in {path}")
        return checkpoint
    return {
        "protocol_id": PROTOCOL_ID,
        "paper_index": paper["paper_index"],
        "paper_id": paper["paper_id"],
        "context_sha256": context_hash,
        "ground_truth": paper["ground_truth"],
        "stages": {},
        "arm_scores": {},
        "status": "in_progress",
        "created_at": _utc_now(),
    }


def _stage(
    checkpoint: dict,
    checkpoint_path: Path,
    name: str,
    caller: StructuredCall,
    system_prompt: str,
    user_prompt: str,
    schema: type[BaseModel],
    safety_fallback: BaseModel | None = None,
) -> BaseModel:
    existing = checkpoint["stages"].get(name)
    if existing is not None:
        return schema.model_validate(existing["output"])
    prior_error = checkpoint.get("last_error", {})
    prior_safety_refusal = (
        prior_error.get("stage") == name
        and _is_provider_safety_refusal(prior_error.get("message", ""))
    )
    if prior_safety_refusal and safety_fallback is not None:
        result = schema.model_validate(safety_fallback)
        checkpoint["stages"][name] = {
            "completed_at": _utc_now(),
            "output": result.model_dump(),
            "provider_safety_fallback": "reused_prior_valid_stage",
            "provider_error": prior_error["message"],
        }
        checkpoint.pop("last_error", None)
        _atomic_write_json(checkpoint_path, checkpoint)
        return result
    try:
        result = schema.model_validate(caller(name, system_prompt, user_prompt, schema))
    except Exception as exc:
        is_safety_refusal = _is_provider_safety_refusal(exc)
        if is_safety_refusal and safety_fallback is not None:
            result = schema.model_validate(safety_fallback)
            checkpoint["stages"][name] = {
                "completed_at": _utc_now(),
                "output": result.model_dump(),
                "provider_safety_fallback": "reused_prior_valid_stage",
                "provider_error": str(exc),
            }
            checkpoint.pop("last_error", None)
            _atomic_write_json(checkpoint_path, checkpoint)
            return result
        checkpoint["last_error"] = {
            "stage": name,
            "type": type(exc).__name__,
            "message": str(exc),
            "at": _utc_now(),
        }
        _atomic_write_json(checkpoint_path, checkpoint)
        raise
    checkpoint["stages"][name] = {
        "completed_at": _utc_now(),
        "output": result.model_dump(),
    }
    if name in getattr(caller, "safety_retry_stages", set()):
        checkpoint["stages"][name]["safety_context_retry"] = True
    checkpoint.pop("last_error", None)
    _atomic_write_json(checkpoint_path, checkpoint)
    return result


def _safety_fallback_critique() -> ProposalCritique:
    return ProposalCritique(
        overall_assessment=(
            "The provider declined this public-paper critique; preserve the valid draft."
        ),
        proposal_feedback=[
            "Preserve this proposal without provider-generated revision."
            for _ in range(K)
        ],
        coverage_gaps=[],
        duplication_risks=[],
    )


def run_paper(
    paper: dict,
    overview: str,
    generation_caller: StructuredCall,
    judge_caller: StructuredCall,
    checkpoint_path: Path,
) -> dict:
    """Run or resume all three arms and blind scoring for one paper."""
    checkpoint = _load_checkpoint(checkpoint_path, paper)
    context = paper["context"]

    system, user = _ta_draft_prompts(context)
    ta_draft = _stage(
        checkpoint,
        checkpoint_path,
        "ta_draft",
        generation_caller,
        system,
        user,
        ProposalSet,
    )
    system, user = _ta_critic_prompts(context, ta_draft)
    ta_critique = _stage(
        checkpoint,
        checkpoint_path,
        "ta_critic",
        generation_caller,
        system,
        user,
        ProposalCritique,
        _safety_fallback_critique(),
    )
    system, user = _ta_revision_prompts(context, ta_draft, ta_critique)
    ta_final = _stage(
        checkpoint,
        checkpoint_path,
        "ta_revision",
        generation_caller,
        system,
        user,
        ProposalSet,
        ta_draft,
    )

    system, user = _cv_draft_prompts(context, overview)
    cv_draft = _stage(
        checkpoint,
        checkpoint_path,
        "cv_draft",
        generation_caller,
        system,
        user,
        ProposalSet,
    )
    system, user = _cv_critic_prompts(context, cv_draft, overview)
    cv_critique = _stage(
        checkpoint,
        checkpoint_path,
        "cv_critic",
        generation_caller,
        system,
        user,
        ProposalCritique,
        _safety_fallback_critique(),
    )
    system, user = _cv_revision_prompts(context, cv_draft, cv_critique, overview)
    cv_final = _stage(
        checkpoint,
        checkpoint_path,
        "cv_revision",
        generation_caller,
        system,
        user,
        ProposalSet,
        cv_draft,
    )

    system, user = _ta_critic_prompts(context, cv_draft)
    combined_critique = _stage(
        checkpoint,
        checkpoint_path,
        "combined_critic",
        generation_caller,
        system,
        user,
        ProposalCritique,
        _safety_fallback_critique(),
    )
    system, user = _ta_revision_prompts(context, cv_draft, combined_critique)
    combined_final = _stage(
        checkpoint,
        checkpoint_path,
        "combined_revision",
        generation_caller,
        system,
        user,
        ProposalSet,
        cv_draft,
    )

    final_sets = {
        "tissueagent": ta_final,
        "cellvoyager": cv_final,
        "combined": combined_final,
    }
    for arm, proposals in final_sets.items():
        system, user = _judge_prompts(proposals, paper["ground_truth"])
        verdict = _stage(
            checkpoint,
            checkpoint_path,
            f"judge_{arm}",
            judge_caller,
            system,
            user,
            MatchingVerdict,
        )
        kept, dropped = sanitize_matches(
            verdict, len(proposals.proposals), len(paper["ground_truth"])
        )
        checkpoint["arm_scores"][arm] = {
            "final_proposals": proposals.model_dump()["proposals"],
            "judge_assessment": verdict.assessment,
            "matches": kept,
            "dropped_judge_edges": dropped,
            "metrics": score_matches(
                kept, len(proposals.proposals), len(paper["ground_truth"])
            ),
        }

    checkpoint["logical_call_budget"] = {
        "tissueagent": 3,
        "cellvoyager": 3,
        "combined": 3,
    }
    checkpoint["unique_generation_calls"] = 8
    checkpoint["judge_calls"] = 3
    checkpoint["status"] = "complete"
    checkpoint["completed_at"] = _utc_now()
    _atomic_write_json(checkpoint_path, checkpoint)
    return checkpoint


def aggregate_papers(checkpoints: list[dict]) -> dict:
    """Aggregate complete paper checkpoints into macro and micro metrics."""
    complete = [item for item in checkpoints if item.get("status") == "complete"]
    if not complete:
        raise ValueError("No complete paper checkpoints")
    result = {"paper_count": len(complete), "arms": {}}
    metric_names = (
        "proposal_precision_at_5",
        "ground_truth_recall_at_5",
        "f1_at_5",
        "paper_hit_rate",
    )
    for arm in ARMS:
        rows = [paper["arm_scores"][arm]["metrics"] for paper in complete]
        macro = {
            metric: statistics.fmean(row[metric] for row in rows)
            for metric in metric_names
        }
        matched = sum(row["matched_proposals"] for row in rows)
        proposal_count = sum(row["proposal_count"] for row in rows)
        ground_truth_count = sum(row["ground_truth_count"] for row in rows)
        precision = matched / proposal_count
        recall = matched / ground_truth_count
        result["arms"][arm] = {
            "macro": macro,
            "micro": {
                "matched": matched,
                "proposal_count": proposal_count,
                "ground_truth_count": ground_truth_count,
                "proposal_precision_at_5": precision,
                "ground_truth_recall_at_5": recall,
                "f1_at_5": (
                    2 * precision * recall / (precision + recall)
                    if precision + recall
                    else 0.0
                ),
                "paper_hit_rate": macro["paper_hit_rate"],
            },
        }
    result["paired_macro_deltas"] = {
        "combined_minus_cellvoyager": {
            metric: result["arms"]["combined"]["macro"][metric]
            - result["arms"]["cellvoyager"]["macro"][metric]
            for metric in metric_names
        },
        "combined_minus_tissueagent": {
            metric: result["arms"]["combined"]["macro"][metric]
            - result["arms"]["tissueagent"]["macro"][metric]
            for metric in metric_names
        },
    }
    return result


def _write_per_paper_csv(path: Path, checkpoints: list[dict]) -> None:
    fields = [
        "paper_index",
        "paper_id",
        "arm",
        "matched_proposals",
        "ground_truth_count",
        "proposal_precision_at_5",
        "ground_truth_recall_at_5",
        "f1_at_5",
        "paper_hit_rate",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for paper in sorted(checkpoints, key=lambda item: item["paper_index"]):
            for arm in ARMS:
                metrics = paper["arm_scores"][arm]["metrics"]
                writer.writerow(
                    {
                        "paper_index": paper["paper_index"],
                        "paper_id": paper["paper_id"],
                        "arm": arm,
                        **{field: metrics[field] for field in fields[3:]},
                    }
                )


def _summary_markdown(summary: dict) -> str:
    lines = [
        "# CellBench replicate summary",
        "",
        f"Complete papers: {summary['paper_count']}",
        "",
        "| Arm | Precision@5 | GT recall@5 | F1@5 | Paper hit rate |",
        "|---|---:|---:|---:|---:|",
    ]
    for arm in ARMS:
        metrics = summary["arms"][arm]["macro"]
        lines.append(
            f"| {arm} | {metrics['proposal_precision_at_5']:.4f} | "
            f"{metrics['ground_truth_recall_at_5']:.4f} | "
            f"{metrics['f1_at_5']:.4f} | {metrics['paper_hit_rate']:.4f} |"
        )
    lines.extend(["", "Paired deltas use the same papers and shared CV drafts.", ""])
    for name, values in summary["paired_macro_deltas"].items():
        lines.append(
            f"- {name}: precision {values['proposal_precision_at_5']:+.4f}, "
            f"recall {values['ground_truth_recall_at_5']:+.4f}, "
            f"F1 {values['f1_at_5']:+.4f}"
        )
    return "\n".join(lines) + "\n"


def run_replicate(
    papers: list[dict],
    overview: str,
    replicate_dir: Path,
    generation_model: str,
    judge_model: str,
    workers: int,
) -> dict:
    """Run one stochastic replicate with per-paper resumable checkpoints."""
    papers_dir = replicate_dir / "papers"
    papers_dir.mkdir(parents=True, exist_ok=True)
    thread_state = threading.local()

    def process(paper: dict) -> dict:
        if not hasattr(thread_state, "generation"):
            thread_state.generation = LangChainStructuredCaller(generation_model)
            thread_state.judge = LangChainStructuredCaller(judge_model)
        filename = f"paper_{paper['paper_index']:03d}_{paper['paper_id']}.json"
        return run_paper(
            paper,
            overview,
            thread_state.generation,
            thread_state.judge,
            papers_dir / filename,
        )

    checkpoints = []
    errors = []
    if workers == 1:
        for paper in papers:
            try:
                checkpoints.append(process(paper))
                print(
                    f"replicate={replicate_dir.name} "
                    f"paper={paper['paper_index'] + 1}/{len(papers)} complete",
                    flush=True,
                )
            except Exception as exc:
                errors.append(
                    {
                        "paper_index": paper["paper_index"],
                        "paper_id": paper["paper_id"],
                        "type": type(exc).__name__,
                        "message": str(exc),
                    }
                )
                break
    else:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(process, paper): paper for paper in papers}
            for future in as_completed(futures):
                paper = futures[future]
                try:
                    checkpoints.append(future.result())
                    print(
                        f"replicate={replicate_dir.name} "
                        f"paper={paper['paper_index'] + 1}/{len(papers)} complete",
                        flush=True,
                    )
                except Exception as exc:
                    errors.append(
                        {
                            "paper_index": paper["paper_index"],
                            "paper_id": paper["paper_id"],
                            "type": type(exc).__name__,
                            "message": str(exc),
                        }
                    )

    status = {
        "expected_papers": len(papers),
        "completed_papers": len(checkpoints),
        "errors": errors,
        "updated_at": _utc_now(),
    }
    _atomic_write_json(replicate_dir / "status.json", status)
    if errors or len(checkpoints) != len(papers):
        raise RuntimeError(
            f"Replicate incomplete: {len(checkpoints)}/{len(papers)} papers; "
            f"resume the same run directory"
        )

    checkpoints.sort(key=lambda item: item["paper_index"])
    summary = aggregate_papers(checkpoints)
    summary["replicate"] = replicate_dir.name
    summary["completed_at"] = _utc_now()
    _atomic_write_json(replicate_dir / "summary.json", summary)
    _write_per_paper_csv(replicate_dir / "per_paper.csv", checkpoints)
    (replicate_dir / "summary.md").write_text(
        _summary_markdown(summary), encoding="utf-8"
    )
    return summary


def aggregate_replicates(summaries: list[dict]) -> dict:
    """Summarize stochastic replicate means, spread, and paired arm deltas."""
    if not summaries:
        raise ValueError("No replicate summaries")
    metric_names = (
        "proposal_precision_at_5",
        "ground_truth_recall_at_5",
        "f1_at_5",
        "paper_hit_rate",
    )
    result = {"replicate_count": len(summaries), "arms": {}, "paired_deltas": {}}
    for arm in ARMS:
        result["arms"][arm] = {}
        for metric in metric_names:
            values = [summary["arms"][arm]["macro"][metric] for summary in summaries]
            result["arms"][arm][metric] = {
                "mean": statistics.fmean(values),
                "sample_sd": statistics.stdev(values) if len(values) > 1 else None,
                "min": min(values),
                "max": max(values),
                "replicate_values": values,
            }
    for comparison in (
        "combined_minus_cellvoyager",
        "combined_minus_tissueagent",
    ):
        result["paired_deltas"][comparison] = {}
        for metric in metric_names:
            values = [
                summary["paired_macro_deltas"][comparison][metric]
                for summary in summaries
            ]
            result["paired_deltas"][comparison][metric] = {
                "mean": statistics.fmean(values),
                "sample_sd": statistics.stdev(values) if len(values) > 1 else None,
                "min": min(values),
                "max": max(values),
                "replicate_values": values,
            }
    return result


def _aggregate_markdown(aggregate: dict) -> str:
    lines = [
        "# CellBench three-arm comparison",
        "",
        f"Stochastic replicates: {aggregate['replicate_count']}",
        "",
        "| Arm | Precision@5 | GT recall@5 | F1@5 | Paper hit rate |",
        "|---|---:|---:|---:|---:|",
    ]
    for arm in ARMS:
        metrics = aggregate["arms"][arm]
        values = []
        for metric in (
            "proposal_precision_at_5",
            "ground_truth_recall_at_5",
            "f1_at_5",
            "paper_hit_rate",
        ):
            item = metrics[metric]
            spread = item["sample_sd"]
            values.append(
                f"{item['mean']:.4f}"
                if spread is None
                else f"{item['mean']:.4f} ± {spread:.4f}"
            )
        lines.append(f"| {arm} | " + " | ".join(values) + " |")
    lines.extend(
        [
            "",
            "Values are mean ± sample SD across stochastic replicates.",
            "",
            "## Paired integration deltas",
            "",
        ]
    )
    for name, metrics in aggregate["paired_deltas"].items():
        lines.append(
            f"- {name}: precision {metrics['proposal_precision_at_5']['mean']:+.4f}, "
            f"recall {metrics['ground_truth_recall_at_5']['mean']:+.4f}, "
            f"F1 {metrics['f1_at_5']['mean']:+.4f}"
        )
    return "\n".join(lines) + "\n"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--overview", type=Path, default=DEFAULT_OVERVIEW)
    parser.add_argument("--model", default="gpt-5.1")
    parser.add_argument("--judge-model", default="gpt-5")
    parser.add_argument("--paper-limit", type=int)
    parser.add_argument("--replicates", type=int, default=1)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--run-dir", type=Path)
    return parser.parse_args()


def main() -> int:
    """Run the command-line benchmark and write resumable result artifacts."""
    args = _parse_args()
    from dotenv import load_dotenv

    load_dotenv(_REPO / ".env")
    if args.replicates < 1 or args.workers < 1:
        raise ValueError("replicates and workers must be positive")
    papers = load_dataset(args.dataset.resolve(), args.paper_limit)
    overview = args.overview.resolve().read_text(encoding="utf-8")
    run_dir = (
        args.run_dir.resolve()
        if args.run_dir
        else DEFAULT_OUTPUT_ROOT
        / datetime.now(timezone.utc).strftime("run_%Y%m%dT%H%M%SZ")
    )
    run_dir.mkdir(parents=True, exist_ok=True)

    from models import get_model_spec

    meta = {
        "protocol_id": PROTOCOL_ID,
        "created_at": _utc_now(),
        "dataset": str(args.dataset.resolve()),
        "dataset_sha256": _sha256_file(args.dataset.resolve()),
        "overview": str(args.overview.resolve()),
        "overview_sha256": _sha256_file(args.overview.resolve()),
        "paper_count": len(papers),
        "replicates": args.replicates,
        "generation_model": args.model,
        "generation_reasoning_effort": (
            get_model_spec(args.model).reasoning_effort or "provider_default"
        ),
        "judge_model": args.judge_model,
        "judge_reasoning_effort": (
            get_model_spec(args.judge_model).reasoning_effort or "provider_default"
        ),
        "proposals_per_arm": K,
        "logical_calls_per_arm": 3,
        "unique_generation_calls_per_paper": 8,
        "judge_calls_per_paper": 3,
        "workers": args.workers,
        "generation_blind_to": ["analyses_titles", "analyses_full"],
        "judge_arm_blind": True,
        "one_to_one_matching": True,
    }
    meta_path = run_dir / "run_meta.json"
    if meta_path.is_file():
        existing = json.loads(meta_path.read_text(encoding="utf-8"))
        stable_fields = (
            "protocol_id",
            "dataset_sha256",
            "overview_sha256",
            "paper_count",
            "replicates",
            "generation_model",
            "judge_model",
        )
        mismatches = [
            field for field in stable_fields if existing.get(field) != meta.get(field)
        ]
        if mismatches:
            raise ValueError(f"Run metadata mismatch for: {', '.join(mismatches)}")
        meta = existing
    else:
        _atomic_write_json(meta_path, meta)

    summaries = []
    for replicate in range(1, args.replicates + 1):
        replicate_dir = run_dir / f"replicate_{replicate:02d}"
        summary_path = replicate_dir / "summary.json"
        if summary_path.is_file():
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        else:
            summary = run_replicate(
                papers,
                overview,
                replicate_dir,
                args.model,
                args.judge_model,
                args.workers,
            )
        summaries.append(summary)

    aggregate = aggregate_replicates(summaries)
    aggregate["protocol_id"] = PROTOCOL_ID
    aggregate["paper_count"] = len(papers)
    aggregate["generation_model"] = args.model
    aggregate["judge_model"] = args.judge_model
    aggregate["completed_at"] = _utc_now()
    _atomic_write_json(run_dir / "aggregate.json", aggregate)
    (run_dir / "aggregate.md").write_text(
        _aggregate_markdown(aggregate), encoding="utf-8"
    )
    print(f"CellBench comparison complete: {run_dir}")
    print(_aggregate_markdown(aggregate), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
