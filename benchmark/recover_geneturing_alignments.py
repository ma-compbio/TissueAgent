#!/usr/bin/env python3
"""Audit/recover both alignment categories offline, retaining earlier gene recovery."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from agents.agent_registry.genegpt_agent.alignment_recovery import RULE_VERSION, recover_alignment  # noqa: E402
from run_genegpt_paired_pilot import _score  # noqa: E402

OUT = ROOT / "benchmark/geneturing_alignment_recovery_20260930"
PRIOR = ROOT / "benchmark/geneturing_gene_name_recovery_20260930"
HISTORY = ROOT / "benchmark/geneturing_full_benchmark/records.json"
COMPARISON = ROOT / "benchmark/geneturing_no_registry_all_20260929/historical_matched_comparison.json"
TASKS = ("Human genome DNA aligment", "Multi-species DNA aligment")
ARMS = ("direct", "tissueagent", "no_registry")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def aggregate(rows):
    groups = {task: [r for r in rows if r["task"] == task] for task in (*TASKS, "Gene name conversion")}
    groups["overall"] = rows
    groups["excluding_demonstrations_overall"] = [r for r in rows if not r["demonstration"]]
    return {name: {arm: mean(r[arm]["benchmark_score"] for r in group) for arm in ARMS}
            for name, group in groups.items()}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    source_paths = [HISTORY, COMPARISON, PRIOR / "scored_records.json", PRIOR / "audit.json", OUT / "protocol.json"]
    hashes = {str(p.relative_to(ROOT)): sha(p) for p in source_paths}
    history = json.loads(HISTORY.read_text())
    original = json.loads(COMPARISON.read_text())["records"]
    prior = json.loads((PRIOR / "scored_records.json").read_text())
    selected = [r for r in history if r["task"] in TASKS]
    assert len(selected) == 100
    predictions = []
    # No reference answer or original score is passed to prediction recovery.
    for row in selected:
        for arm in ARMS[:2]:
            path = Path(row[arm]["raw_artifact"])
            hashes[str(path.relative_to(ROOT))] = sha(path)
            raw = json.loads(path.read_text())
            recovered = recover_alignment(row["question"], raw["api_trace"])
            predictions.append({"task": row["task"], "question": row["question"], "arm": arm,
                                "historical_index": row["index"], "agent_question": raw["question"],
                                "original_completion": raw.get("raw_completion") or "",
                                "prediction": recovered["answer"] if recovered["answer"] is not None else raw.get("raw_completion") or "",
                                "recovery": recovered, "raw_artifact": str(path), "source_sha256": sha(path),
                                "full_responses_available": any("response" in t for t in raw["api_trace"]),
                                "has_blast_report": any("BLASTN" in t.get("response", t.get("response_excerpt", "")) for t in raw["api_trace"])})
    prediction_path = OUT / "predictions.json"
    prediction_path.write_text(json.dumps(predictions, indent=2) + "\n")
    prediction_hash = sha(prediction_path)
    lookup = {(r["question"], r["arm"]): r for r in predictions}
    scored = copy.deepcopy(prior)
    changes = {task: {arm: Counter() for arm in ARMS[:2]} for task in TASKS}
    reasons = {task: {arm: Counter() for arm in ARMS[:2]} for task in TASKS}
    for row, old in zip(scored, prior):
        if row["task"] not in TASKS:
            continue
        for arm in ARMS[:2]:
            pred = lookup[(row["question"], arm)]
            normalized, score = _score(pred["prediction"], row["gold"], row["task"])
            assert _score(pred["original_completion"], row["gold"], row["task"])[1] == old[arm]["benchmark_score"]
            row[arm].update(original=copy.deepcopy(old[arm]), prediction=normalized, benchmark_score=score,
                            recovery=pred["recovery"], raw_artifact_sha256=pred["source_sha256"])
            counts = changes[row["task"]][arm]
            counts["trace_extractions"] += pred["recovery"]["answer"] is not None
            counts["changed_predictions"] += normalized != old[arm]["prediction"]
            counts["improved_scores"] += score > old[arm]["benchmark_score"]
            counts["worsened_scores"] += score < old[arm]["benchmark_score"]
            counts["exact_matches"] += score == 1
            counts["chromosome_only_credit"] += score == 0.5
            reasons[row["task"]][arm][pred["recovery"]["reason"]] += 1
    assert all(r["no_registry"] == old["no_registry"] for r, old in zip(scored, prior))
    assert all(r == old for r, old in zip(scored, prior) if r["task"] not in TASKS)
    for rel, expected in hashes.items():
        assert sha(ROOT / rel) == expected, rel
    assert sha(prediction_path) == prediction_hash
    implementations = [Path(__file__), ROOT / "src/agents/agent_registry/genegpt_agent/alignment_recovery.py",
                       ROOT / "src/agents/agent_registry/genegpt_agent/runner.py",
                       ROOT / "benchmark/run_genegpt_paired_pilot.py",
                       ROOT / "src/agents/agent_registry/genegpt_agent/upstream/evaluate.py"]
    for path in implementations:
        snapshot = OUT / "source_snapshot" / path.relative_to(ROOT)
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        snapshot.write_bytes(path.read_bytes())
    summary = {"analysis": "post_hoc_alignment_output_recovery", "rule": RULE_VERSION,
               "questions": 100, "paired_traces": 200, "new_model_calls": 0, "new_ncbi_calls": 0,
               "original": aggregate(original), "after_gene_name_recovery": aggregate(prior),
               "after_gene_name_and_alignment_recovery": aggregate(scored), "changes": changes,
               "recovery_reasons": reasons, "full_responses_available": sum(p["full_responses_available"] for p in predictions),
               "interpretation": "Offline postprocessing, not new end-to-end evaluations. Human scores retain chromosome-only half credit. Prior gene-name recovery, native baseline and other categories are unchanged."}
    audit = {"source_hashes": hashes, "original_artifacts_unchanged": True, "predictions_frozen_before_scoring": True,
             "predictions_sha256": prediction_hash, "implementation": {str(p.relative_to(ROOT)): sha(p) for p in implementations},
             "prior_gene_name_recovery_unchanged": True, "other_categories_and_native_baseline_unchanged": True}
    for name, value in (("scored_records.json", scored), ("summary.json", summary), ("audit.json", audit)):
        (OUT / name).write_text(json.dumps(value, indent=2) + "\n")
    lines = ["# GeneGPT alignment recovery", "",
             "Offline reevaluation of all 50 human and 50 multi-species alignment questions in both GeneGPT conditions (200 traces). No new model or NCBI calls. Prior gene-name recovery is retained.", "",
             "| Metric | Direct GeneGPT | TissueAgent + GeneGPT | No registry |", "| --- | ---: | ---: | ---: |"]
    for title, stage, task in (
        ("Human alignment: original", "original", TASKS[0]),
        ("Human alignment: after recovery", "after_gene_name_and_alignment_recovery", TASKS[0]),
        ("Multi-species: original", "original", TASKS[1]),
        ("Multi-species: after recovery", "after_gene_name_and_alignment_recovery", TASKS[1]),
        ("Gene-name conversion: prior recovery retained", "after_gene_name_and_alignment_recovery", "Gene name conversion"),
        ("Overall: original outputs", "original", "overall"),
        ("Overall: gene-name plus alignment recovery", "after_gene_name_and_alignment_recovery", "overall"),
    ):
        lines.append("| " + title + " | " + " | ".join(f"{summary[stage][task][arm]:.1%}" for arm in ARMS) + " |")
    lines += ["", "## Human-coordinate limitation", "",
              "Both human-alignment arms still have 44 chromosome-only answers out of 50 and zero exact reference-coordinate matches under the original scorer: 44/50 × 0.5 = 44%. This is a mean benchmark score, not 44% exact coordinate accuracy. The strict evidence rule cannot recover additional benchmark-correct coordinates from the saved traces.", "",
              "The archive stores only 2,000-character response excerpts. Many hits refer to clones, transcripts, RefSeqGene loci or synthetic records rather than a human reference chromosome. Their subject offsets and genomic intervals embedded in titles are not the queried sequence's chromosome coordinates. Recovering exact reference-assembly coordinates for unresolved cases requires additional reference mapping or a new alignment against an explicitly matched assembly; that was not performed.", "",
              "## Recovery rule", "",
              "The rule uses only the question and trace. It links the exact submitted sequence to its returned RID and the retrieved report, verifies query length, and requires a complete displayed hit table plus a co-best perfect full-query alignment. For species, all co-best natural-species titles must agree; explicit synthetic constructs do not establish a natural species. Conflicting taxa are retained as unresolved, including taxa outside the benchmark choices.", "",
              "For human alignment, co-best human-hit titles must agree on chromosome. Exact coordinates require complete alignments on concordant human RefSeq chromosome records; clone/transcript/synthetic offsets are never relabeled as genomic positions. Abstentions retain the original answer. The same rule is applied to every question in both arms without gold-based selection.", "",
              "## Changes and unresolved evidence", ""]
    for task in TASKS:
        for arm in ARMS[:2]:
            c = changes[task][arm]
            lines.append(f"- {task.replace('aligment', 'alignment')}, {arm}: {c['trace_extractions']}/50 evidence extractions, {c['improved_scores']} improved scores, {c['worsened_scores']} worsened scores. Reasons: {dict(reasons[task][arm])}.")
    lines += ["", "## Runner repair and validation scope", "",
              "The runner canonicalizes the BLAST endpoint, requires a Get RID produced by a prior Put, polls the same job no more than once per minute, retains full submission/result bodies, and extracts supported answers before the model drifts into unrelated examples. RID-only completions are rejected. These changes are covered by offline regression tests; the modified runner was not benchmarked with new model/search calls.", "",
              "Text retrieval, request IDs and result-format parameters follow the [NCBI Common URL API documentation](https://blast.ncbi.nlm.nih.gov/doc/blast-help/urlapi.html). Original search parameters are retained; only endpoint/result presentation is normalized.", "",
              "Predictions were saved and hashed before existing benchmark scoring. `predictions.json` includes complete recovery provenance and abstention reasons; `audit.json` records input and implementation hashes. Original artifacts, previous gene-name recovery, all other categories and native baseline scores are unchanged. Historical resource/model differences and forced GeneGPT recruitment still limit causal interpretation of registry benefits.", ""]
    (OUT / "REPORT.md").write_text("\n".join(lines))
    print(json.dumps({k: summary[k] for k in ("after_gene_name_and_alignment_recovery", "changes", "full_responses_available")}, indent=2))


if __name__ == "__main__":
    main()
