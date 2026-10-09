#!/usr/bin/env python3
"""Audit standalone CV checkpoints and reproduce the CellBench-Spatial table."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from statistics import mean, pstdev

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from benchmark.spatial_cellbench.run import (  # noqa: E402
    CV_ARM,
    DEFAULT_ARMS,
    GENERATION_MODEL,
    ORCHESTRATION_MODEL,
    _generation_payload,
    _load_corpus,
    _sha256_json,
    _validate_checkpoint_hash,
    _validate_generation_checkpoint,
)
from benchmark.spatial_cellbench.ta import _expected_cv_stages  # noqa: E402

LABELS = {
    "direct": "Direct o3-mini",
    CV_ARM: "Direct CellVoyager",
    "tissueagent": r"\methodname{}",
    "tissueagent_spatial_cv": r"\methodname{} + CellVoyager",
}


def summarize(rows: list[dict], arm: str, counts: dict[str, int]) -> dict:
    """Calculate three complete run-level scores and their population SDs."""
    selected = [row for row in rows if row["arm"] == arm]
    expected = {(paper, replicate) for paper in counts for replicate in (1, 2, 3)}
    actual = [(row["eval_id"], row["replicate"]) for row in selected]
    if len(actual) != len(expected) or set(actual) != expected:
        raise ValueError(f"Incomplete or duplicated scored rows for {arm}")
    runs = []
    for replicate in (1, 2, 3):
        entries = [row for row in selected if row["replicate"] == replicate]
        for row in entries:
            metrics = row["metrics"]
            count = counts[row["eval_id"]]
            if metrics["candidate_count"] != count:
                raise ValueError("Candidate denominator differs from frozen oracle N")
            if metrics["candidate_hit_fraction"] != metrics["matched_candidates"] / count:
                raise ValueError("Inconsistent candidate hit fraction")
        matched = sum(row["metrics"]["matched_candidates"] for row in entries)
        candidates = sum(row["metrics"]["candidate_count"] for row in entries)
        runs.append(
            {
                "replicate": replicate,
                "paper_count": len(entries),
                "matched_candidates": matched,
                "candidate_count": candidates,
                "micro_avg_percent": 100
                * mean(row["metrics"]["candidate_hit_fraction"] for row in entries),
                "macro_avg_percent": 100 * matched / candidates,
            }
        )
    summary = {"runs": runs, "sd_ddof": 0}
    for metric in ("micro_avg", "macro_avg"):
        values = [run[f"{metric}_percent"] for run in runs]
        summary[f"{metric}_mean_percent"] = mean(values)
        summary[f"{metric}_sd_percent"] = pstdev(values)
    return summary


def latex_row(arm: str, summary: dict) -> str:
    """Format one row using the manuscript's existing two-decimal convention."""
    values = [
        f"${summary[f'{metric}_mean_percent']:.2f}\\% "
        f"\\pm {summary[f'{metric}_sd_percent']:.2f}\\%$"
        for metric in ("micro_avg", "macro_avg")
    ]
    return LABELS[arm] + " & " + " & ".join(values) + r" \\"


def audit(run_dir: Path) -> tuple[list[dict], dict, dict]:
    """Require every expected generation and judge checkpoint to pass integrity checks."""
    contexts, truths, manifest, overview = _load_corpus()
    identity = json.loads((run_dir / "run_meta.json").read_text())["identity"]
    counts = {public.eval_id: len(truths[public.eval_id].analyses) for public in contexts}
    if (
        set(identity["paper_ids"]) != set(counts)
        or identity["replicates"] != 3
        or identity["arms"] != [CV_ARM]
    ):
        raise ValueError("Expected the complete 20-paper standalone CV run")
    for key in ("public_contexts_sha256", "ground_truth_sha256", "scope_adjudication_sha256"):
        if identity[key] != manifest["frozen_artifacts"][key]:
            raise ValueError(f"Run uses a different corpus: {key}")
    rows, ledger = [], []
    total_generation_calls = total_judge_calls = total_tokens = 0
    for public in contexts:
        count = counts[public.eval_id]
        for replicate in (1, 2, 3):
            relative = Path(public.eval_id) / f"replicate_{replicate:02d}" / f"{CV_ARM}.json"
            generation = json.loads((run_dir / "generation" / relative).read_text())
            judged = json.loads((run_dir / "judging" / relative).read_text())
            payload = _generation_payload(
                public,
                count,
                CV_ARM,
                replicate,
                GENERATION_MODEL,
                ORCHESTRATION_MODEL,
                overview,
                identity["source_fingerprint"]["sha256"],
            )
            _validate_generation_checkpoint(generation, payload)
            _validate_checkpoint_hash(judged, "Judge")
            if generation["status"] != "success" or judged["status"] != "success":
                raise ValueError(f"Unsuccessful unit: {relative}")
            if judged["generation_proposal_sha256"] != generation["proposal_sha256"]:
                raise ValueError("Judge scored a different proposal set")
            if judged["truth_sha256"] != _sha256_json(truths[public.eval_id].model_dump()):
                raise ValueError("Judge used a different truth set")
            generation_trace, judge_trace = generation["trace"], judged["trace"]
            if generation_trace["model"] != identity["generation_model"]:
                raise ValueError("Generation model differs from frozen run identity")
            if judge_trace["model"] != identity["judge_model"]:
                raise ValueError("Judge model differs from frozen run identity")
            if generation_trace["context_sha256"] != public.context_sha256:
                raise ValueError("Generation used a different public context")
            if generation_trace["overview_sha256"] != identity["overview_sha256"]:
                raise ValueError("Generation used a different spatial overview")
            if judged["truth_artifact_sha256"] != identity["ground_truth_sha256"]:
                raise ValueError("Judge used a different frozen truth artifact")
            for checkpoint, trace in ((generation, generation_trace), (judged, judge_trace)):
                if checkpoint["trace_sha256"] != _sha256_json(trace):
                    raise ValueError("Trace checksum mismatch")
                if trace["semantic_retries"] != 0 or trace["fallback_model"] is not None:
                    raise ValueError("Semantic retry or fallback detected")
            if [call["stage"] for call in generation_trace["calls"]] != _expected_cv_stages(count):
                raise ValueError("CV did not execute exactly the frozen 3N stages")
            if [call["stage"] for call in judge_trace["calls"]] != [
                f"judge_{index:02d}" for index in range(1, count + 1)
            ]:
                raise ValueError("Judge did not independently score every candidate")
            if generation_trace["logical_model_calls"] != 3 * count:
                raise ValueError("Incorrect CV call count")
            if judge_trace["logical_model_calls"] != count:
                raise ValueError("Incorrect judge call count")
            decisions = judged["decisions"]
            if len(decisions) != count or [d["candidate_index"] for d in decisions] != list(
                range(count)
            ):
                raise ValueError("Missing or repeated candidate judgment")
            matched = sum(d["match"] for d in decisions)
            expected_metrics = {
                "matched_candidates": matched,
                "candidate_count": count,
                "candidate_hit_fraction": matched / count,
            }
            if judged["metrics"] != expected_metrics:
                raise ValueError("Metrics differ from raw judge decisions")
            rows.append(
                {
                    "eval_id": public.eval_id,
                    "replicate": replicate,
                    "arm": CV_ARM,
                    "metrics": expected_metrics,
                }
            )
            ledger.append(
                {
                    "eval_id": public.eval_id,
                    "replicate": replicate,
                    "generation_sha256": generation["checkpoint_sha256"],
                    "judge_sha256": judged["checkpoint_sha256"],
                }
            )
            total_generation_calls += generation_trace["logical_model_calls"]
            total_judge_calls += judge_trace["logical_model_calls"]
            total_tokens += sum(
                call.get("total_tokens") or 0
                for trace in (generation_trace, judge_trace)
                for call in trace["calls"]
            )
    aggregate = json.loads((run_dir / "aggregate.json").read_text())
    _validate_checkpoint_hash(aggregate, "Aggregate")
    key = lambda row: (row["eval_id"], row["replicate"], row["arm"])
    if sorted(aggregate["scored_rows"], key=key) != sorted(rows, key=key):
        raise ValueError("Aggregate differs from audited checkpoints")
    if aggregate["completion"][CV_ARM] != {
        "scheduled": len(rows),
        "generation_success": len(rows),
        "judge_success": len(rows),
    }:
        raise ValueError("Aggregate does not report complete generation and judging")
    return (
        rows,
        counts,
        {
            "identity": identity,
            "generation_units": len(rows),
            "judge_units": len(rows),
            "generation_calls": total_generation_calls,
            "judge_calls": total_judge_calls,
            "recorded_total_tokens": total_tokens,
            "checkpoint_ledger": ledger,
            "aggregate_sha256": aggregate["checkpoint_sha256"],
        },
    )


def update_table(path: Path, summaries: dict) -> None:
    """Add the measured row and its method description without changing older scores."""
    text = path.read_text()
    label = text.index(r"\label{tab:cellbench_spatial}")
    start = text.rfind(r"\begin{table}", 0, label)
    end = text.index(r"\end{table}", label) + len(r"\end{table}")
    block = text[start:end]
    for arm in DEFAULT_ARMS:
        if latex_row(arm, summaries[arm]) not in block:
            raise ValueError(f"Historical manuscript row differs from source aggregate: {arm}")
    new_row = latex_row(CV_ARM, summaries[CV_ARM])
    if "Direct CellVoyager &" in block:
        block = re.sub(r"Direct CellVoyager &[^\n]*", lambda _: new_row, block)
    else:
        anchor = latex_row("direct", summaries["direct"])
        block = block.replace(anchor, anchor + "\n" + new_row, 1)
    block = block.replace(
        "Performance of direct o3-mini, native",
        "Performance of direct o3-mini, direct CellVoyager, native",
        1,
    )
    description = (
        "Direct CellVoyager uses the same spatially adapted draft--critique--revision "
        "cycle as the recruited CellVoyager component, with one cycle per proposal; "
        "its revised proposals are scored directly by the judge.\n"
    )
    if description not in block:
        block = block.replace(r"In native \methodname", description + r"In native \methodname", 1)
    path.write_text(text[:start] + block + text[end:])


def main() -> int:
    """Write an audited numeric report, optionally updating the manuscript table."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument(
        "--historical-aggregate",
        type=Path,
        default=(ROOT / "benchmark/spatial_cellbench/results/combined_20paper_aggregate.json"),
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--update-manuscript", type=Path)
    args = parser.parse_args()
    rows, counts, audit_record = audit(args.run_dir)
    historical = json.loads(args.historical_aggregate.read_text())
    _validate_checkpoint_hash(historical, "Historical aggregate")
    summaries = {
        arm: summarize(rows if arm == CV_ARM else historical["scored_rows"], arm, counts)
        for arm in ("direct", CV_ARM, "tissueagent", "tissueagent_spatial_cv")
    }
    report = {
        "table_label": "tab:cellbench_spatial",
        "paper_count": len(counts),
        "analyses_per_replicate": sum(counts.values()),
        "summaries": summaries,
        "standalone_cv_audit": audit_record,
        "historical_aggregate_sha256": historical["checkpoint_sha256"],
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "table_s6_summary.json").write_text(json.dumps(report, indent=2) + "\n")
    (args.output_dir / "table_s6_rows.tex").write_text(
        "\n".join(latex_row(arm, summary) for arm, summary in summaries.items()) + "\n"
    )
    if args.update_manuscript:
        update_table(args.update_manuscript, summaries)
    print(json.dumps(summaries[CV_ARM], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
