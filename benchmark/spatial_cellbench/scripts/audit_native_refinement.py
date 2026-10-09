#!/usr/bin/env python3
"""Audit a completed native pilot, with cached same-draft before/after judgments."""

from __future__ import annotations

import argparse
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from statistics import mean, pstdev

from benchmark.spatial_cellbench.evaluation import JUDGE_SYSTEM, build_blind_judge_problem
from benchmark.spatial_cellbench.methods import LangChainModelCall, register_benchmark_models
from benchmark.spatial_cellbench.refinement import REFINED_ARM
from benchmark.spatial_cellbench.run import (
    _atomic_write_json,
    _load_corpus,
    _seal_checkpoint,
    _sha256_json,
    _validate_checkpoint_hash,
)
from benchmark.spatial_cellbench.schemas import MatchVerdict, validate_proposal_count


def audit_unit(run_dir, gen_path, contexts, truths, out_dir):
    """Judge changed drafts only, reusing final verdicts for identical judge inputs."""
    generation = json.loads(gen_path.read_text())
    _validate_checkpoint_hash(generation, "Generation")
    if generation["status"] != "success":
        return None
    paper, replicate = generation["eval_id"], generation["replicate"]
    judge_path = run_dir / "judging" / paper / f"replicate_{replicate:02d}" / gen_path.name
    judging = json.loads(judge_path.read_text())
    _validate_checkpoint_hash(judging, "Judge")
    if judging["status"] != "success":
        return None
    if judging["generation_proposal_sha256"] != generation["proposal_sha256"]:
        raise ValueError("Final judgment belongs to a different generation")
    attempts = list(
        (run_dir / "work" / paper / f"replicate_{replicate:02d}" / REFINED_ARM).glob(
            "attempt_*/runtime/workspace/project/outputs"
        )
    )
    if len(attempts) != 1:
        expected_final = generation.get("trace", {}).get("final_artifact_sha256")
        attempts = [
            outputs
            for outputs in attempts
            if (outputs / "hypotheses/final_proposals.json").is_file()
            and hashlib.sha256(
                (outputs / "hypotheses/final_proposals.json").read_bytes()
            ).hexdigest()
            == expected_final
        ]
        if len(attempts) != 1:
            raise ValueError("Audit cannot identify the uniquely checkpointed final artifact")
    outputs = attempts[0]
    draft_payload = json.loads((outputs / "hypotheses/draft_proposals.json").read_text())
    drafts = validate_proposal_count(draft_payload, generation["proposal_count"])
    finals = validate_proposal_count(generation["proposals"], generation["proposal_count"])
    expected_truth = _sha256_json(truths[paper].model_dump())
    if expected_truth != judging["truth_sha256"]:
        raise ValueError("Hidden truth has changed since final judging")
    fingerprint = _sha256_json(
        {
            "generation": generation["checkpoint_sha256"],
            "judge": judging["checkpoint_sha256"],
            "draft": _sha256_json(draft_payload),
            "protocol": "paired_draft_final_audit_v1",
        }
    )
    destination = out_dir / paper / f"replicate_{replicate:02d}.json"
    if destination.exists():
        previous = json.loads(destination.read_text())
        _validate_checkpoint_hash(previous, "Draft audit")
        if previous["unit_fingerprint"] != fingerprint:
            raise ValueError("Audit resume identity mismatch")
        return previous
    caller, decisions = None, []
    for index, (draft, final) in enumerate(zip(drafts.proposals, finals.proposals, strict=True)):
        problem = build_blind_judge_problem(
            contexts[paper], truths[paper], drafts, replicate, index
        )
        prompt_sha = hashlib.sha256(problem.prompt.encode()).hexdigest()
        final_decision = judging["decisions"][index]
        reused = draft.model_dump() == final.model_dump()
        candidate_path = destination.with_suffix("") / f"C{index + 1:02d}.json"
        candidate_fingerprint = _sha256_json({"unit": fingerprint, "prompt": prompt_sha})
        if candidate_path.exists():
            decision = json.loads(candidate_path.read_text())
            _validate_checkpoint_hash(decision, "Draft candidate")
            if decision["unit_fingerprint"] != candidate_fingerprint:
                raise ValueError("Draft candidate cache identity mismatch")
        else:
            if reused:
                if prompt_sha != judging["judge_prompt_sha256"][index]:
                    raise ValueError("Identical candidate produced a different judge prompt")
                verdict = MatchVerdict(
                    match=final_decision["match"], reason=final_decision["reason"]
                )
                calls = []
            else:
                if caller is None:
                    caller = LangChainModelCall("gpt-4o")
                before = len(caller.traces)
                verdict = caller.structured(
                    f"draft_judge_{index + 1:02d}", JUDGE_SYSTEM, problem.prompt, MatchVerdict
                )
                calls = caller.traces[before:]
            decision = _seal_checkpoint(
                {
                    "unit_fingerprint": candidate_fingerprint,
                    "candidate_id": f"C{index + 1:02d}",
                    "reused_final_verdict": reused,
                    "draft_match": verdict.match,
                    "draft_reason": verdict.reason,
                    "final_match": final_decision["match"],
                    "judge_prompt_sha256": prompt_sha,
                    "calls": calls,
                }
            )
            _atomic_write_json(candidate_path, decision)
        decisions.append(decision)
    result = _seal_checkpoint(
        {
            "unit_fingerprint": fingerprint,
            "paper": paper,
            "replicate": replicate,
            "candidate_count": len(decisions),
            "draft_matched": sum(d["draft_match"] for d in decisions),
            "final_matched": sum(d["final_match"] for d in decisions),
            "reused_verdicts": sum(d["reused_final_verdict"] for d in decisions),
            "gained": sum(not d["draft_match"] and d["final_match"] for d in decisions),
            "lost": sum(d["draft_match"] and not d["final_match"] for d in decisions),
            "decisions": decisions,
        }
    )
    _atomic_write_json(destination, result)
    return result


def summarize(run_dir, drafts):
    """Report complete-run rates and costs without concealing failed units."""
    meta = json.loads((run_dir / "run_meta.json").read_text())
    aggregate = json.loads((run_dir / "aggregate.json").read_text())
    rows, summaries = aggregate["scored_rows"], {}
    for arm, completion in aggregate["completion"].items():
        scored = [r for r in rows if r["arm"] == arm]
        by_rep = []
        for replicate in (1, 2, 3):
            selected = [r for r in scored if r["replicate"] == replicate]
            if len(selected) == completion["scheduled"] // 3:
                by_rep.append(
                    {
                        "replicate": replicate,
                        "micro": mean(r["metrics"]["candidate_hit_fraction"] for r in selected),
                        "macro": sum(r["metrics"]["matched_candidates"] for r in selected)
                        / sum(r["metrics"]["candidate_count"] for r in selected),
                    }
                )
        successful_costs, errors = [], []
        for path in (run_dir / "generation").glob(f"*/replicate_*/{arm}.json"):
            gen = json.loads(path.read_text())
            _validate_checkpoint_hash(gen, "Generation")
            trace = gen.get("trace", {})
            if gen["status"] != "success":
                errors.append(
                    {
                        "paper": gen.get("eval_id"),
                        "replicate": gen.get("replicate"),
                        "error": gen.get("error"),
                        "trace": trace,
                    }
                )
                continue
            calls = trace.get("ta_ai_calls", []) + (trace.get("refinement_trace") or {}).get(
                "calls", []
            )
            successful_costs.append(
                {
                    "paper": gen["eval_id"],
                    "replicate": gen["replicate"],
                    "calls": len(calls),
                    "tokens": sum(c.get("total_tokens") or 0 for c in calls),
                    "token_records_missing": sum(c.get("total_tokens") is None for c in calls),
                    "seconds": trace["elapsed_seconds"],
                }
            )
        summaries[arm] = {
            "completion": completion,
            "replicates": by_rep,
            "errors": errors,
            "micro_mean": mean(r["micro"] for r in by_rep) if len(by_rep) == 3 else None,
            "micro_sd": pstdev(r["micro"] for r in by_rep) if len(by_rep) == 3 else None,
            "macro_mean": mean(r["macro"] for r in by_rep) if len(by_rep) == 3 else None,
            "macro_sd": pstdev(r["macro"] for r in by_rep) if len(by_rep) == 3 else None,
            "successful_generation_costs": successful_costs,
        }
    return {"identity": meta["identity"], "arms": summaries, "paired_draft_final": drafts}


def main():
    """Run or resume the predeclared diagnostic audit."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()
    register_benchmark_models()
    contexts, truths, _, _ = _load_corpus()
    contexts = {p.eval_id: p for p in contexts}
    paths = sorted((args.run_dir / "generation").glob(f"*/replicate_*/{REFINED_ARM}.json"))
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        drafts = list(
            executor.map(
                lambda path: audit_unit(
                    args.run_dir, path, contexts, truths, args.output_dir / "draft_judging"
                ),
                paths,
            )
        )
    result = summarize(args.run_dir, [d for d in drafts if d is not None])
    _atomic_write_json(args.output_dir / "pilot_audit.json", result)
    print(json.dumps({a: s["completion"] for a, s in result["arms"].items()}))


if __name__ == "__main__":
    main()
