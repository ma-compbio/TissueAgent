#!/usr/bin/env python3
"""Require complete, traceable refined-native results before reporting an S6 row."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from statistics import mean

from benchmark.spatial_cellbench.refinement import (
    Blueprint,
    CandidateReview,
    REFINED_ARM,
    evidence_ledger,
    validate_blueprint,
)
from benchmark.spatial_cellbench.run import (
    GENERATION_MODEL,
    ORCHESTRATION_MODEL,
    _atomic_write_json,
    _generation_payload,
    _load_corpus,
    _sha256_json,
    _validate_checkpoint_hash,
    _validate_generation_checkpoint,
)
from benchmark.spatial_cellbench.scripts.report_table_s6 import summarize
from benchmark.spatial_cellbench.ta import _semantic_json_sha256, _validate_outer_agent_trace


def audit(run_dir: Path, spec_path: Path) -> dict:
    """Validate models, corpus, attempts, graph, candidates, judgments and arithmetic."""
    contexts, truths, manifest, overview = _load_corpus()
    spec = json.loads(spec_path.read_text())
    identity = json.loads((run_dir / "run_meta.json").read_text())["identity"]
    counts = {p.eval_id: len(truths[p.eval_id].analyses) for p in contexts}
    if (
        set(identity["paper_ids"]) != set(counts)
        or identity["replicates"] != 3
        or identity["arms"] != [REFINED_ARM]
        or len(counts) != 20
    ):
        raise ValueError("Require all 20 papers and three repetitions of the refined arm")
    if identity["source_fingerprint"] != spec["source_fingerprint"]:
        raise ValueError("Source differs from the pre-run specification")
    for key in ("public_contexts_sha256", "ground_truth_sha256", "scope_adjudication_sha256"):
        if identity[key] != manifest["frozen_artifacts"][key]:
            raise ValueError("Frozen corpus drift")
    rows, units, decisions = [], [], Counter()
    for public in contexts:
        count = counts[public.eval_id]
        for replicate in (1, 2, 3):
            relative = Path(public.eval_id) / f"replicate_{replicate:02d}" / f"{REFINED_ARM}.json"
            generation = json.loads((run_dir / "generation" / relative).read_text())
            judged = json.loads((run_dir / "judging" / relative).read_text())
            payload = _generation_payload(
                public,
                count,
                REFINED_ARM,
                replicate,
                GENERATION_MODEL,
                ORCHESTRATION_MODEL,
                overview,
                identity["source_fingerprint"]["sha256"],
            )
            _validate_checkpoint_hash(generation, "Generation")
            _validate_generation_checkpoint(generation, payload)
            _validate_checkpoint_hash(judged, "Judge")
            if generation["status"] != "success" or judged["status"] != "success":
                raise ValueError(f"Incomplete scientific unit: {relative}")
            if (
                judged["generation_proposal_sha256"] != generation["proposal_sha256"]
                or judged["truth_sha256"] != _sha256_json(truths[public.eval_id].model_dump())
                or judged["truth_artifact_sha256"] != identity["ground_truth_sha256"]
            ):
                raise ValueError("Judgment input identity mismatch")
            trace = generation["trace"]
            refinement = trace["refinement_trace"]
            _validate_outer_agent_trace(trace["outer_graph"])
            if (
                trace["model"] != identity["generation_model"]
                or trace["orchestration_model"] != identity["orchestration_model"]
                or judged["trace"]["model"] != identity["judge_model"]
            ):
                raise ValueError("Model drift")
            if (
                not trace["native_tissueagent_graph"]
                or trace["roster"] != ["hypothesis", "critic"]
                or trace["spatial_cv_invoked"]
                or trace["manager_write_count"]
                or trace["plan_unassigned_steps"]
                or trace["plan_artifact_assignment_mismatches"]
                or trace["plan_unexpected_artifacts"]
            ):
                raise ValueError("Native graph or specialist ownership violation")
            if (
                refinement["protocol"] != spec["protocol"]
                or refinement["status"] != "success"
                or refinement["context_sha256"] != public.context_sha256
                or refinement["overview_sha256"] != identity["overview_sha256"]
                or refinement["semantic_retries"] != 0
            ):
                raise ValueError("Refinement protocol drift")
            unit_dir = (
                run_dir / "work" / public.eval_id / f"replicate_{replicate:02d}" / REFINED_ARM
            )
            attempts = sorted(unit_dir.glob("attempt_*"))
            if not 1 <= len(attempts) <= spec["failure_policy"]["max_attempts_per_unit"]:
                raise ValueError("Predeclared attempt limit exceeded")
            outputs = attempts[-1] / "runtime/workspace/project/outputs"
            if (
                hashlib.sha256(
                    (outputs / "hypotheses/final_proposals.json").read_bytes()
                ).hexdigest()
                != trace["final_artifact_sha256"]
            ):
                raise ValueError("Final checkpoint is not from the final attempt")
            failures = sorted(unit_dir.glob("failed_checkpoint_*.json"))
            if len(failures) != len(attempts) - 1:
                raise ValueError("Attempt history is incomplete")
            for path in failures:
                failed = json.loads(path.read_text())
                _validate_checkpoint_hash(failed, "Failed attempt")
                if failed["status"] != "failed":
                    raise ValueError("A successful unit was retried")
            for relative_artifact, expected_hash in refinement["artifact_sha256"].items():
                if (
                    _semantic_json_sha256(json.loads((outputs / relative_artifact).read_text()))
                    != expected_hash
                ):
                    raise ValueError("Rich artifact checksum mismatch")
            ledger = json.loads((outputs / "hypotheses/context_evidence.json").read_text())
            if ledger != evidence_ledger(public):
                raise ValueError("Evidence ledger changed")
            expected_stages = [f"native_C{i:02d}_draft" for i in range(1, count + 1)]
            expected_stages += [f"native_C{i:02d}_critic" for i in range(1, count + 1)]
            unit_decisions = []
            for index in range(1, count + 1):
                cid = f"C{index:02d}"
                directory = outputs / "hypotheses/blueprints"
                draft_path, final_path = (
                    directory / f"draft_{cid}.json",
                    directory / f"final_{cid}.json",
                )
                draft = Blueprint.model_validate(json.loads(draft_path.read_text()))
                final = Blueprint.model_validate(json.loads(final_path.read_text()))
                review = CandidateReview.model_validate(
                    json.loads((directory / f"review_{cid}.json").read_text())
                )
                validate_blueprint(draft, cid, public)
                validate_blueprint(final, cid, public)
                if review.candidate_id != cid:
                    raise ValueError("Reviewer identity mismatch")
                if review.decision == "KEEP":
                    if draft_path.read_bytes() != final_path.read_bytes():
                        raise ValueError("KEEP changed a candidate")
                else:
                    expected_stages.append(f"native_{cid}_revision")
                    if (
                        draft.primary_objective != final.primary_objective
                        and not review.allow_objective_change
                    ):
                        raise ValueError("Unapproved objective change")
                if generation["proposals"]["proposals"][index - 1] != {
                    "title": final.title,
                    "summary": final.summary,
                }:
                    raise ValueError("Export is not deterministic")
                unit_decisions.append(review.decision)
            if (
                [c["stage"] for c in refinement["calls"]] != expected_stages
                or len(expected_stages) > 3 * count
                or refinement["decisions"] != unit_decisions
            ):
                raise ValueError("Specialist stage or decision audit mismatch")
            decisions.update(unit_decisions)
            judge_trace = judged["trace"]
            if judged["trace_sha256"] != _sha256_json(judge_trace):
                raise ValueError("Judge trace checksum mismatch")
            if [c["stage"] for c in judge_trace["calls"]] != [
                f"judge_{i:02d}" for i in range(1, count + 1)
            ]:
                raise ValueError("Judge stage mismatch")
            if [d["candidate_index"] for d in judged["decisions"]] != list(range(count)):
                raise ValueError("Missing or duplicate judgments")
            matched = sum(d["match"] for d in judged["decisions"])
            metrics = {
                "matched_candidates": matched,
                "candidate_count": count,
                "candidate_hit_fraction": matched / count,
            }
            if metrics != judged["metrics"]:
                raise ValueError("Judge arithmetic mismatch")
            rows.append(
                {
                    "eval_id": public.eval_id,
                    "replicate": replicate,
                    "arm": REFINED_ARM,
                    "metrics": metrics,
                }
            )
            calls = trace["ta_ai_calls"] + refinement["calls"]
            units.append(
                {
                    "eval_id": public.eval_id,
                    "replicate": replicate,
                    "generation_attempts": len(attempts),
                    "generation_calls": len(calls),
                    "generation_tokens": sum(c.get("total_tokens") or 0 for c in calls),
                    "missing_token_records": sum(c.get("total_tokens") is None for c in calls),
                    "judge_calls": len(judge_trace["calls"]),
                    "judge_tokens": sum(c.get("total_tokens") or 0 for c in judge_trace["calls"]),
                    "generation_seconds": trace["elapsed_seconds"],
                    "generation_sha256": generation["checkpoint_sha256"],
                    "judging_sha256": judged["checkpoint_sha256"],
                }
            )
    aggregate = json.loads((run_dir / "aggregate.json").read_text())
    _validate_checkpoint_hash(aggregate, "Aggregate")
    key = lambda r: (r["eval_id"], r["replicate"], r["arm"])
    if sorted(rows, key=key) != sorted(aggregate["scored_rows"], key=key):
        raise ValueError("Aggregate differs from independently audited checkpoints")
    return {
        "identity": identity,
        "protocol": spec["protocol"],
        "summary": summarize(rows, REFINED_ARM, counts),
        "decision_counts": dict(decisions),
        "units": units,
        "scored_rows": rows,
        "generation_attempts": sum(u["generation_attempts"] for u in units),
        "successful_generation_cost_mean": {
            k: mean(u[k] for u in units)
            for k in ["generation_calls", "generation_tokens", "generation_seconds"]
        },
        "judge_calls": sum(u["judge_calls"] for u in units),
        "judge_tokens": sum(u["judge_tokens"] for u in units),
    }


def main():
    """Write an independently reconstructed full-run report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    report = audit(args.run_dir, args.output_dir / "run_spec.json")
    _atomic_write_json(args.output_dir / "table_s6_summary.json", report)
    print(
        json.dumps(
            {
                "summary": report["summary"],
                "decisions": report["decision_counts"],
                "attempts": report["generation_attempts"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
