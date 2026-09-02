# ruff: noqa: D102, D103, D107
"""Tests for the one-query CellVoyager CellBench pilot."""

from __future__ import annotations

from pathlib import Path

from benchmark.cellvoyager_cellbench_pilot.methods import (
    evaluate_bundle,
    expected_generation_stages,
    load_query,
    run_cellvoyager,
)
from benchmark.cellvoyager_cellbench_pilot.run_all import build_aggregate
from benchmark.cellvoyager_cellbench_pilot.schemas import (
    CellVoyagerAnalysis,
    MatchVerdict,
)
from benchmark.cellvoyager_cellbench_pilot.ta import build_task
from benchmark.cellvoyager_cellbench_pilot.ta import create_cellvoyager_agent

ROOT = Path(__file__).resolve().parents[1]
CORPUS = (
    ROOT
    / "src"
    / "agents"
    / "agent_registry"
    / "cellvoyager_agent"
    / "upstream"
    / "CellBench"
    / "data"
    / "cellbench_50.csv"
)


class FakeCaller:
    """Return deterministic proposal and judge responses."""

    def __init__(self, verdicts: list[bool] | None = None) -> None:
        self.verdicts = list(verdicts or [])
        self.stages = []
        self.prompts = []

    def structured(self, stage, system_prompt, user_prompt, schema):
        del system_prompt
        self.stages.append(stage)
        self.prompts.append(user_prompt)
        if schema is MatchVerdict:
            return MatchVerdict(match=self.verdicts.pop(0), reason="pilot decision")
        return CellVoyagerAnalysis(
            hypothesis=f"Hypothesis from {stage}",
            analysis_plan=["Inspect cell states", "Validate the comparison"],
            summary=f"Detailed single-cell analysis summary produced during {stage}.",
        )

    def text(self, stage, system_prompt, user_prompt):
        del system_prompt
        self.stages.append(stage)
        self.prompts.append(user_prompt)
        return "Improve specificity and statistical validation."

    @property
    def traces(self):
        return [{"stage": stage} for stage in self.stages]


def test_query_six_is_the_bounded_five_analysis_pilot() -> None:
    query = load_query(CORPUS, "6")
    assert query["analysis_count"] == 5
    assert len(query["ground_truth"]) == 5
    assert "caries" in query["context"].lower()


def test_cellvoyager_runs_three_stages_per_analysis() -> None:
    caller = FakeCaller()
    bundle = run_cellvoyager("public context", "analysis overview", 2, caller)
    assert len(bundle.analyses) == 2
    assert caller.stages == expected_generation_stages(2)
    assert bundle.analyses[0].summary in caller.prompts[3]


def test_evaluation_uses_independent_candidate_matches() -> None:
    generation = FakeCaller()
    bundle = run_cellvoyager("public context", "analysis overview", 2, generation)
    judge = FakeCaller([True, False])
    result = evaluate_bundle(bundle, [{"title": "Truth", "description": "Details"}], judge)
    assert result["metrics"] == {
        "matched_candidates": 1,
        "candidate_count": 2,
        "candidate_hit_fraction": 0.5,
    }
    assert judge.stages == ["judge_01", "judge_02"]


def test_tissueagent_prompt_explicitly_requires_cellvoyager() -> None:
    task = build_task("public context", 5)
    assert "exactly\none plan step" in task
    assert "must assign" in task
    assert "cellvoyager_agent_agent" in task
    assert "final_proposals.json" in task
    assert "do not request an h5ad file" in task
    assert "JSON list of at least two methodological step strings" in task
    assert "do not reinterpret it as a single string" in task
    assert "do not dispatch it again" in task


def test_benchmark_cellvoyager_agent_writes_scored_artifact(tmp_path: Path) -> None:
    caller = FakeCaller()
    agent = create_cellvoyager_agent(
        None,
        cellbench_context="public context",
        cellbench_overview="analysis overview",
        cellbench_outputs=tmp_path,
        cellbench_count=2,
        cellbench_caller_factory=lambda _model: caller,
    )
    result = agent.invoke({"prompt": "Generate the final proposals."})
    assert "produced 2" in result
    assert (tmp_path / "hypotheses" / "final_proposals.json").is_file()
    assert (tmp_path / "hypotheses" / "cellvoyager_trace.json").is_file()
    repeated = agent.invoke({"prompt": "Retry the same step."})
    assert "already produced 2" in repeated
    assert caller.stages == expected_generation_stages(2)


def test_full_aggregate_preserves_pooled_and_equal_query_metrics() -> None:
    rows = [
        {
            "query_id": "0",
            "candidate_count": 2,
            "direct_hits": 1,
            "recruited_hits": 2,
            "direct_hit_fraction": 0.5,
            "recruited_hit_fraction": 1.0,
            "direct_cellvoyager_calls": 6,
            "recruited_cellvoyager_calls": 6,
            "judge_calls": 4,
            "recruited": True,
            "invoked": True,
        },
        {
            "query_id": "1",
            "candidate_count": 4,
            "direct_hits": 4,
            "recruited_hits": 2,
            "direct_hit_fraction": 1.0,
            "recruited_hit_fraction": 0.5,
            "direct_cellvoyager_calls": 12,
            "recruited_cellvoyager_calls": 12,
            "judge_calls": 8,
            "recruited": True,
            "invoked": True,
        },
    ]
    aggregate = build_aggregate(rows, total_queries=2)
    assert aggregate["status"] == "complete"
    assert aggregate["direct_pooled_hit_fraction"] == 5 / 6
    assert aggregate["recruited_pooled_hit_fraction"] == 4 / 6
    assert aggregate["direct_mean_query_hit_fraction"] == 0.75
    assert aggregate["recruited_mean_query_hit_fraction"] == 0.75
    assert aggregate["recruitment_successes"] == 2


def test_full_aggregate_is_running_until_every_query_completes() -> None:
    aggregate = build_aggregate([], total_queries=50)
    assert aggregate["status"] == "running"
    assert aggregate["completed_queries"] == 0
    assert aggregate["direct_pooled_hit_fraction"] is None
