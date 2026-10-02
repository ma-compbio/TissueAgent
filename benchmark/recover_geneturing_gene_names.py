#!/usr/bin/env python3
"""Reevaluate saved GeneGPT conversion traces without model or network calls.

Write a separate post-hoc analysis; never modify original answers or scores.
All predictions are frozen before reference answers are used for scoring.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agents.agent_registry.genegpt_agent.answer_recovery import (  # noqa: E402
    RULE_VERSION,
    recover_gene_symbol,
)
from run_genegpt_paired_pilot import _score  # noqa: E402

TASK = "Gene name conversion"
ARMS = ("direct", "tissueagent", "no_registry")
HISTORICAL = ROOT / "benchmark/geneturing_full_benchmark/records.json"
COMPARISON = ROOT / "benchmark/geneturing_no_registry_all_20260929/historical_matched_comparison.json"
DEFAULT_OUT = ROOT / "benchmark/geneturing_gene_name_recovery_20260930"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    historical = json.loads(HISTORICAL.read_text())
    original = json.loads(COMPARISON.read_text())
    selected = [row for row in historical if row["task"] == TASK]
    assert len(selected) == 50
    hashes = {str(p.relative_to(ROOT)): sha(p) for p in (HISTORICAL, COMPARISON)}

    # Prediction phase: references/scores are never inputs to recovery.
    predictions = []
    for row in selected:
        for arm in ARMS[:2]:
            path = Path(row[arm]["raw_artifact"])
            hashes[str(path.relative_to(ROOT))] = sha(path)
            raw = json.loads(path.read_text())
            # Recruitment sometimes adds execution instructions or paraphrases
            # the question. Verify the identifier, then use the benchmark's
            # canonical task wording identically for both arms.
            assert set(re.findall(r"\bENSG\d{11}\b", raw["question"])) == set(re.findall(r"\bENSG\d{11}\b", row["question"]))
            recovery = recover_gene_symbol(row["question"], raw["api_trace"])
            predictions.append({
                "question": row["question"], "agent_question": raw["question"],
                "arm": arm, "historical_index": row["index"],
                "original_answer": raw["answer"], "raw_completion": raw["raw_completion"],
                "prediction": recovery["answer"] if recovery["answer"] is not None else raw["answer"],
                "recovery": recovery, "raw_artifact": str(path), "source_sha256": sha(path),
            })
    prediction_path = out / "predictions.json"
    prediction_path.write_text(json.dumps(predictions, indent=2) + "\n")
    prediction_hash = sha(prediction_path)

    # Evaluation phase: immutable predictions are now compared with references.
    lookup = {(row["question"], row["arm"]): row for row in predictions}
    scored = copy.deepcopy(original["records"])
    counts = {arm: Counter() for arm in ARMS[:2]}
    unresolved = []
    for row in scored:
        if row["task"] != TASK:
            continue
        for arm in ARMS[:2]:
            pred = lookup[(row["question"], arm)]
            old = copy.deepcopy(row[arm])
            norm, score = _score(pred["prediction"], row["gold"], TASK)
            assert _score(pred["raw_completion"], row["gold"], TASK)[1] == old["benchmark_score"]
            recovery = pred["recovery"]
            row[arm].update(prediction=norm, benchmark_score=score, original=old,
                            recovery=recovery, raw_artifact_sha256=pred["source_sha256"])
            counts[arm]["trace_extractions"] += recovery["answer"] is not None
            counts[arm]["changed_answers"] += norm != old["prediction"]
            counts[arm]["wrong_to_correct"] += old["benchmark_score"] == 0 and score == 1
            counts[arm]["correct_to_wrong"] += old["benchmark_score"] == 1 and score == 0
            if recovery["answer"] is None:
                unresolved.append({"question": row["question"], "arm": arm,
                                   "reason": recovery["reason"], "retained_prediction": norm,
                                   "retained_score": score})
    assert all(row["no_registry"] == old["no_registry"] for row, old in zip(scored, original["records"]))
    assert all(row == old for row, old in zip(scored, original["records"]) if row["task"] != TASK)

    def aggregate(rows):
        conversion = [row for row in rows if row["task"] == TASK]
        clean = [row for row in rows if not row["demonstration"]]
        return {
            "conversion": {arm: mean(row[arm]["benchmark_score"] for row in conversion) for arm in ARMS},
            "overall": {arm: mean(row[arm]["benchmark_score"] for row in rows) for arm in ARMS},
            "excluding_demonstrations_overall": {arm: mean(row[arm]["benchmark_score"] for row in clean) for arm in ARMS},
        }

    summary = {"analysis": "post_hoc_gene_name_output_recovery", "rule": RULE_VERSION,
               "questions": 50, "paired_traces": 100, "new_model_calls": 0, "new_ncbi_calls": 0,
               "original": aggregate(original["records"]), "postprocessed": aggregate(scored),
               "changes": counts, "abstentions": unresolved,
               "interpretation": "Only gene-name conversion outputs were postprocessed. Other categories and the no-registry baseline are unchanged. These are not new end-to-end runs or published GeneGPT scores."}
    for path, expected in hashes.items():
        assert sha(ROOT / path) == expected, path
    assert sha(prediction_path) == prediction_hash
    source_paths = [Path(__file__), ROOT / "src/agents/agent_registry/genegpt_agent/answer_recovery.py",
                    ROOT / "benchmark/run_genegpt_paired_pilot.py",
                    ROOT / "src/agents/agent_registry/genegpt_agent/upstream/evaluate.py"]
    for path in source_paths:
        frozen = out / "source_snapshot" / path.relative_to(ROOT)
        frozen.parent.mkdir(parents=True, exist_ok=True)
        frozen.write_bytes(path.read_bytes())
    audit = {"original_artifacts_unchanged": True, "sources": hashes,
             "predictions_sha256": prediction_hash, "predictions_frozen_before_scoring": True,
             "implementation": {str(p.relative_to(ROOT)): sha(p) for p in source_paths},
             "other_categories_unchanged": True, "no_registry_unchanged": True}
    for name, data in (("summary.json", summary), ("audit.json", audit), ("scored_records.json", scored)):
        (out / name).write_text(json.dumps(data, indent=2) + "\n")

    lines = ["# GeneGPT gene-name output recovery", "",
             "Post-hoc analysis of saved API traces; no new model or NCBI calls. Original answers and scores are preserved.", "",
             "| Metric | Direct GeneGPT | TissueAgent + GeneGPT | No registry |",
             "| --- | ---: | ---: | ---: |"]
    for title, state, key in (
        ("Original conversion score (50 questions)", "original", "conversion"),
        ("After offline conversion recovery (50 questions)", "postprocessed", "conversion"),
        ("Original overall mean (450 questions)", "original", "overall"),
        ("Overall mean after conversion-only recovery", "postprocessed", "overall"),
    ):
        lines.append("| " + title + " | " + " | ".join(f"{summary[state][key][arm]:.1%}" for arm in ARMS) + " |")
    lines += ["", "## Rule and provenance", "",
              "The same rule runs on every conversion trace in both GeneGPT arms, regardless of the original score. Its only inputs are the question and API trace. It requires an exact Ensembl-ID search with one complete NCBI Gene hit, followed by a fetch or summary for that same ID containing one official symbol. Conflicting, ambiguous or incomplete evidence causes abstention; the original answer is then retained. No first-hit selection, reference-based choice, new lookup or LLM judging is used.", "",
              "The no-registry answers and all other categories are unchanged. Predictions were saved and hashed before scoring with the existing scorer. `predictions.json` records evidence URLs and trace indices; `audit.json` hashes all historical inputs.", "",
              "## Recovery counts", ""]
    for arm in ARMS[:2]:
        lines.append(f"- {arm}: {counts[arm]['trace_extractions']}/50 trace extractions; {counts[arm]['wrong_to_correct']} wrong-to-correct answers; {counts[arm]['correct_to_wrong']} correct-to-wrong answers.")
    lines += ["", "## Cases retained without extraction", ""]
    for row in unresolved:
        lines.append(f"- {row['arm']}: {row['question']} Reason: {row['reason']}; original prediction retained: `{row['retained_prediction']}` (score {row['retained_score']:g}).")
    lines += ["", "## Interpretation", "",
              "The low raw conversion scores largely reflect final-answer protocol failures despite successful retrieval. This analysis estimates performance after an explicit deterministic output-processing change. It does not retroactively turn the old model completions into valid answers or validate the modified runner end to end. One direct case remains ambiguous because its lookup returned both ZNF404 and CATED. The original recruited answer already selected ZNF404; recovery does not use that other arm to resolve the direct case.", "",
              "Overall values after recovery replace only conversion scores and are descriptive sensitivity results, not a re-audit of every category. Historical model/execution/resource differences and forced specialist recruitment remain limitations; these numbers do not isolate the causal benefit of the Agent Registry.", ""]
    (out / "REPORT.md").write_text("\n".join(lines))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
