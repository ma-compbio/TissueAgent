# ruff: noqa: D102, D103, D107
"""Focused tests for the frozen spatial paper benchmark."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

import benchmark.spatial_cellbench.run as run_module
from benchmark.spatial_cellbench.evaluation import (
    JUDGE_PROTOCOL,
    build_blind_judge_problem,
    evaluate_proposals,
)
from benchmark.spatial_cellbench.methods import run_direct, run_spatial_cv
from benchmark.spatial_cellbench.prompts import cv_draft_prompt, direct_prompt
from benchmark.spatial_cellbench.run import (
    ARMS,
    GENERATION_MODEL,
    JUDGE_MODEL,
    ORCHESTRATION_MODEL,
    PROTOCOL,
    _aggregate,
    _completion_exit_code,
    _generation_payload,
    _judge_checkpoint,
    _validate_checkpoint_hash,
)
from benchmark.spatial_cellbench.schemas import (
    AnalysisProposal,
    CVAnalysis,
    GroundTruthPaper,
    MatchVerdict,
    ProposalSet,
    PublicContext,
    proposal_set_schema,
    validate_proposal_count,
)
from benchmark.spatial_cellbench.statistics import paired_summary, paper_arm_means
from benchmark.spatial_cellbench.ta import (
    TA_ARM,
    TA_CV_ARM,
    _agent_tool_calls,
    _expected_cv_stages,
    _manager_write_records,
    _matching_write_author_candidates,
    _outer_agent_trace,
    _validate_spatial_cv_bundle,
    _validate_outer_agent_trace,
    build_hypothesis_prompt,
    build_ta_roster,
    build_ta_task,
    create_spatial_cv_agent,
)
from benchmark.spatial_cellbench.validate_data import validate_archives, validate_data

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "benchmark" / "spatial_cellbench"


def public_context(eval_id: str = "spcb_0123456789") -> PublicContext:
    """Return a valid synthetic public context."""
    context = " ".join(["spatial"] * 160)
    return PublicContext(
        eval_id=eval_id,
        context=context,
        word_count=160,
        context_rule_version="test",
        context_sha256=hashlib.sha256(context.encode()).hexdigest(),
    )


def proposals(count: int) -> ProposalSet:
    """Return ``count`` valid candidates."""
    return ProposalSet(
        proposals=[
            AnalysisProposal(
                title=f"Analysis {index}",
                summary=f"Detailed spatial analysis summary for candidate number {index}.",
            )
            for index in range(1, count + 1)
        ]
    )


def truth(count: int, eval_id: str = "spcb_0123456789") -> GroundTruthPaper:
    """Return a valid synthetic truth set."""
    return GroundTruthPaper.model_validate(
        {
            "eval_id": eval_id,
            "schema_version": 2,
            "analyses": [
                {
                    "analysis_id": f"A{index:02d}",
                    "title": f"Truth {index}",
                    "description": f"Detailed hidden spatial analysis number {index}.",
                    "analysis_type": "test_analysis",
                    "evidence": [
                        {
                            "page": 1,
                            "section": "Results",
                            "anchor": f"hidden analysis evidence {index}",
                        }
                    ],
                }
                for index in range(1, count + 1)
            ],
            "curation": {
                "protocol": "cellbench_fig12_spatial_v2",
                "curator_a_count": count,
                "curator_b_count": count,
                "matched_count": count,
                "set_f1": 1.0,
                "adjudication_status": "complete",
                "notes": "test",
            },
        }
    )


class FakeCaller:
    """Deterministic caller covering generation and judge schemas."""

    def __init__(self, direct_count: int = 1, verdicts: list[bool] | None = None) -> None:
        self.direct_count = direct_count
        self.verdicts = list(verdicts or [])
        self.stages = []
        self.prompts = []

    def structured(self, stage, system_prompt, user_prompt, schema):
        del system_prompt
        self.stages.append(stage)
        self.prompts.append(user_prompt)
        if schema is CVAnalysis:
            return CVAnalysis(
                title=f"Title {stage}",
                hypothesis="A supported spatial hypothesis",
                analysis_plan=["Inspect spatial structure", "Validate the result"],
                summary=f"Detailed reviewed spatial analysis generated during {stage}.",
            )
        if schema is MatchVerdict:
            return MatchVerdict(match=self.verdicts.pop(0), reason="independent decision")
        return schema.model_validate(proposals(self.direct_count).model_dump())

    def text(self, stage, system_prompt, user_prompt):
        del system_prompt
        self.stages.append(stage)
        self.prompts.append(user_prompt)
        return "The analysis is supported; improve its statistical validation."

    @property
    def call_count(self):
        return len(self.stages)

    @property
    def traces(self):
        return [{"stage": stage} for stage in self.stages]

    @property
    def observable_attempt_count(self):
        return len(self.stages)

    @property
    def failed_attempts(self):
        return []


def test_dynamic_proposal_schema_enforces_oracle_count() -> None:
    schema = proposal_set_schema(9)
    assert len(schema.model_validate(proposals(9).model_dump()).proposals) == 9
    with pytest.raises(ValueError):
        schema.model_validate(proposals(8).model_dump())
    with pytest.raises(ValueError):
        validate_proposal_count(proposals(8), 9)


def test_direct_uses_one_call_and_paper_specific_count() -> None:
    caller = FakeCaller(direct_count=12)
    result = run_direct(public_context(), 12, caller)
    assert len(result.proposals) == 12
    assert caller.stages == ["direct"]
    assert "propose 12 spatial" in caller.prompts[0]
    assert "exactly 12 analyses" in direct_prompt("background", 12)


def test_spatial_cv_runs_upstream_three_stage_loop_for_each_analysis() -> None:
    caller = FakeCaller()
    result = run_spatial_cv(public_context(), "overview", 3, caller)
    assert len(result.proposals) == 3
    assert caller.stages == _expected_cv_stages(3)
    assert "Detailed reviewed spatial analysis" in caller.prompts[3]
    assert "different major scientific objective" not in cv_draft_prompt(
        "background", "prior", "overview"
    )
    assert "cohort, tissue" not in cv_draft_prompt("background", "prior", "overview")


def test_judge_scores_candidates_independently_with_duplicate_credit() -> None:
    caller = FakeCaller(verdicts=[True, True, False])
    evaluated = evaluate_proposals(
        public_context(),
        truth(4),
        proposals(3),
        caller,
        replicate=1,
    )
    assert evaluated["judge_protocol"] == JUDGE_PROTOCOL
    assert evaluated["metrics"] == {
        "matched_candidates": 2,
        "candidate_count": 3,
        "candidate_hit_fraction": pytest.approx(2 / 3),
    }
    assert caller.stages == ["judge_01", "judge_02", "judge_03"]
    assert all("independently" in prompt for prompt in caller.prompts)


def test_blind_judge_prompt_uses_only_title_and_summary_for_candidate() -> None:
    problem = build_blind_judge_problem(
        public_context(),
        truth(2),
        proposals(1),
        replicate=2,
        candidate_index=0,
    )
    assert "Analysis 1" in problem.prompt
    assert "Detailed spatial analysis summary" in problem.prompt
    assert "spcb_" not in problem.prompt
    assert "tissueagent" not in problem.prompt


def test_paper_statistics_average_replicates_before_contrast() -> None:
    rows = []
    for eval_id, values in {
        "paper_a": {"direct": [0.1, 0.2, 0.3], TA_ARM: [0.4, 0.5, 0.6]},
        "paper_b": {"direct": [0.5, 0.5, 0.5], TA_ARM: [0.4, 0.4, 0.4]},
    }.items():
        for arm, arm_values in values.items():
            for replicate, value in enumerate(arm_values, 1):
                rows.append(
                    {
                        "eval_id": eval_id,
                        "arm": arm,
                        "replicate": replicate,
                        "metrics": {"candidate_hit_fraction": value},
                    }
                )
    means = paper_arm_means(rows, "candidate_hit_fraction")
    assert means["paper_a"]["direct"] == pytest.approx(0.2)
    summary = paired_summary(
        rows,
        "candidate_hit_fraction",
        TA_ARM,
        "direct",
        bootstrap_samples=100,
    )
    assert summary["paper_count"] == 2
    assert summary["estimate"] == pytest.approx(0.1)


def test_generation_payload_exposes_count_but_not_truth() -> None:
    public = public_context()
    payload = _generation_payload(
        public,
        12,
        "direct",
        1,
        GENERATION_MODEL,
        ORCHESTRATION_MODEL,
        "overview",
        "source",
    )
    assert payload["proposal_count"] == 12
    assert payload["public"] == public.model_dump()
    assert payload["orchestration_model_id"] == ORCHESTRATION_MODEL
    serialized = json.dumps(payload)
    assert "ground_truth" not in serialized
    assert "evidence" not in serialized


def test_retry_replaces_skipped_judge_after_generation_recovers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    public = public_context()
    hidden = truth(3)
    failed = {"status": "failed", "proposal_count": 3}
    skipped = _judge_checkpoint(
        tmp_path,
        public,
        hidden,
        "direct",
        1,
        failed,
        JUDGE_MODEL,
        "truth-artifact",
        retry_failed=False,
    )
    assert skipped["status"] == "skipped"
    monkeypatch.setattr(
        run_module,
        "LangChainModelCall",
        lambda _model: FakeCaller(verdicts=[True, False, True]),
    )
    recovered = {
        "status": "success",
        "proposal_count": 3,
        "proposal_sha256": "recovered-proposals",
        "proposals": proposals(3).model_dump(),
    }
    judged = _judge_checkpoint(
        tmp_path,
        public,
        hidden,
        "direct",
        1,
        recovered,
        JUDGE_MODEL,
        "truth-artifact",
        retry_failed=True,
    )
    assert judged["status"] == "success"
    assert judged["metrics"]["matched_candidates"] == 2
    failures = tmp_path / "judging" / public.eval_id / "replicate_01" / "failed"
    assert len(list(failures.glob("*.json"))) == 1


def test_frozen_arms_and_models_have_no_forced_treatment() -> None:
    assert ARMS == ("direct", TA_ARM, TA_CV_ARM)
    assert GENERATION_MODEL == "o3-mini"
    assert ORCHESTRATION_MODEL == "gpt-5.1"
    assert JUDGE_MODEL == "gpt-4o"
    assert "forced" not in " ".join(ARMS)


def test_ta_plus_cv_task_differs_only_by_declared_agent_treatment() -> None:
    public = public_context()
    task = build_ta_task(public, 9, require_spatial_cv=False)
    integration_task = build_ta_task(public, 9, require_spatial_cv=True)
    assert "exactly\nthree phases" not in task
    assert "must assign" not in task
    assert "final_proposals.json" in task
    assert "Spatial-CV" not in task
    assert "spatial_cv" not in task
    assert "exactly three compact plan steps and no others" in task
    assert "(1) generate the candidate draft" in task
    assert "(2) critique that draft" in task
    assert "(3) synthesize the final candidates" in task
    assert "Do not create one step per proposal" in task
    assert "Physically write every listed artifact to its exact path" in task
    assert "Hypothesis advertises draft and final proposal files" in task
    assert "Critic advertises only the critique file" in task
    assert "Manager must not" not in task
    assert "must assign step (1)" in integration_task
    assert "spatial_cv_agent" in integration_task
    assert public.context in task and public.context in integration_task
    assert "hidden answers" in task and "hidden answers" in integration_task


def test_ta_plus_cv_only_adds_an_eligible_specialist_roster_entry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeAgent(SimpleNamespace):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)

    agent_defns = ModuleType("agents.agent_defns")
    agent_defns.CustomAgent = FakeAgent
    agent_defns.ReActAgent = FakeAgent
    agent_defns.WorkerModelCtor = object()
    hypothesis_module = ModuleType("agents.agent_registry.hypothesis_agent.model")
    hypothesis_module.create_hypothesis_agent = object()
    monkeypatch.setitem(sys.modules, "agents.agent_defns", agent_defns)
    monkeypatch.setitem(
        sys.modules,
        "agents.agent_registry.hypothesis_agent.model",
        hypothesis_module,
    )
    monkeypatch.setattr(run_module, "ROOT", ROOT)
    monkeypatch.setattr(
        "benchmark.spatial_cellbench.ta.build_critic_tools",
        lambda _outputs: [],
    )
    args = (public_context(), tmp_path, 3)
    ta_roster = build_ta_roster(*args, False, "overview", GENERATION_MODEL)
    integration_roster = build_ta_roster(*args, True, "overview", GENERATION_MODEL)
    assert [agent.id for agent in ta_roster] == ["hypothesis", "critic"]
    assert [agent.id for agent in integration_roster] == [
        "hypothesis",
        "critic",
        "spatial_cv",
    ]
    assert ta_roster[0].description == integration_roster[0].description
    assert "only agent" not in integration_roster[0].description
    assert "draft_proposals.json" in integration_roster[2].description


def test_recruited_spatial_cv_writes_standard_draft_and_audit_copy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tools_module = ModuleType("langchain.tools")

    class FakeStructuredTool:
        @classmethod
        def from_function(cls, func, **_kwargs):
            return SimpleNamespace(invoke=lambda args: func(**args))

    tools_module.StructuredTool = FakeStructuredTool
    monkeypatch.setitem(sys.modules, "langchain", ModuleType("langchain"))
    monkeypatch.setitem(sys.modules, "langchain.tools", tools_module)
    agent = create_spatial_cv_agent(
        None,
        spatial_cv_public=public_context(),
        spatial_cv_overview="overview",
        spatial_cv_model_id=GENERATION_MODEL,
        spatial_cv_outputs=tmp_path,
        spatial_cv_count=3,
        spatial_cv_caller_factory=lambda _model: FakeCaller(),
    )
    result = agent.invoke({"prompt": "Generate the recruited candidate draft."})
    assert "produced 3" in result
    draft = json.loads((tmp_path / "hypotheses" / "draft_proposals.json").read_text())
    audited = json.loads(
        (tmp_path / "hypotheses" / "spatial_cv_proposals.json").read_text()
    )
    assert draft == audited
    assert len(draft["proposals"]) == 3


def test_hypothesis_prompt_exposes_valid_cv_artifact(tmp_path: Path) -> None:
    output = tmp_path / "outputs"
    cv_path = output / "hypotheses" / "spatial_cv_proposals.json"
    cv_path.parent.mkdir(parents=True)
    cv_path.write_text(json.dumps(proposals(3).model_dump()), encoding="utf-8")
    audit = output / "audit" / "exposure.jsonl"
    prompt = build_hypothesis_prompt(public_context(), output, 3, audit)
    assert "exactly 3 items" in prompt
    assert "spatial_cv_proposals.json" in prompt
    record = json.loads(audit.read_text(encoding="utf-8"))
    assert record["spatial_cv_sha256"] == hashlib.sha256(cv_path.read_bytes()).hexdigest()
    assert record["artifact_sha256"]["hypotheses/spatial_cv_proposals.json"]


def test_hypothesis_prompt_accepts_one_neutral_draft_artifact(tmp_path: Path) -> None:
    output = tmp_path / "outputs"
    draft_path = output / "hypotheses" / "draft_proposals.json"
    draft_path.parent.mkdir(parents=True)
    draft_path.write_text(json.dumps(proposals(3).model_dump()), encoding="utf-8")
    prompt = build_hypothesis_prompt(public_context(), output, 3)
    assert "hypotheses/draft_proposals.json" in prompt


def test_hypothesis_prompt_can_repair_nonfinal_draft_shape(tmp_path: Path) -> None:
    output = tmp_path / "outputs"
    draft_path = output / "hypotheses" / "draft_proposals.json"
    draft_path.parent.mkdir(parents=True)
    draft_path.write_text(
        json.dumps(proposals(3).model_dump()["proposals"]),
        encoding="utf-8",
    )
    prompt = build_hypothesis_prompt(public_context(), output, 3)
    assert "hypotheses/draft_proposals.json" in prompt
    assert '"title": "Analysis 1"' in prompt


def test_failed_spatial_cv_trace_seals_partial_workspace(tmp_path: Path) -> None:
    public = public_context()
    trace_path = tmp_path / "hypotheses" / "spatial_cv_trace.json"
    trace_path.parent.mkdir(parents=True)
    trace_path.write_text(
        json.dumps({"status": "failed", "calls": [{"stage": "spatial_cv_01_draft"}]}),
        encoding="utf-8",
    )
    valid, reason, trace = _validate_spatial_cv_bundle(
        tmp_path,
        public,
        "overview",
        GENERATION_MODEL,
        3,
    )
    assert not valid
    assert reason == "partial"
    assert trace["status"] == "failed"


def test_aggregate_reports_named_hit_rates_and_two_contrasts(tmp_path: Path) -> None:
    rows = []
    units = []
    for arm in ARMS:
        for replicate in (1, 2, 3):
            rows.append(
                {
                    "eval_id": "paper",
                    "arm": arm,
                    "replicate": replicate,
                    "metrics": {
                        "matched_candidates": 5,
                        "candidate_count": 10,
                        "candidate_hit_fraction": 0.5,
                    },
                }
            )
            units.append(
                {
                    "eval_id": "paper",
                    "arm": arm,
                    "replicate": replicate,
                    "generation_status": "success",
                    "judge_status": "success",
                    "generation_trace": (
                        {
                            "spatial_cv_available": True,
                            "spatial_cv_recruited_steps": [],
                            "spatial_cv_invoked": False,
                            "spatial_cv_artifact_valid": False,
                            "spatial_cv_exposed_to_hypothesis": False,
                        }
                        if arm == TA_CV_ARM
                        else {}
                    ),
                }
            )
    aggregate = _aggregate(tmp_path, rows, units, ["paper"], list(ARMS), 3)
    _validate_checkpoint_hash(aggregate, "test aggregate")
    assert aggregate["arm_summaries"]["direct"]["mean_paper_hit"] == 0.5
    assert aggregate["arm_summaries"]["direct"]["pooled_candidate_hit"] == 0.5
    assert set(aggregate["contrasts"]) == {
        "tissueagent_minus_direct",
        "tissueagent_spatial_cv_minus_tissueagent",
    }


def test_failed_units_produce_nonzero_stage_exit_codes() -> None:
    success = {"generation_status": "success", "judge_status": "success"}
    generation_failure = {"generation_status": "failed", "judge_status": "not_run"}
    judge_failure = {"generation_status": "success", "judge_status": "failed"}
    assert _completion_exit_code([success], skip_judge=False) == 0
    assert _completion_exit_code([generation_failure], skip_judge=True) == 1
    assert _completion_exit_code([judge_failure], skip_judge=False) == 1


def test_manager_writes_are_audited_without_exposing_contents() -> None:
    payload = proposals(3).model_dump()
    state = {
        "messages": [
            SimpleNamespace(
                name="manager_agent",
                tool_calls=[
                    {"name": "next_step"},
                    {
                        "name": "write",
                        "args": {
                            "file_path": "project/outputs/hypotheses/final_proposals.json",
                            "contents": json.dumps(payload),
                        },
                    },
                ],
            )
        ]
    }
    assert _agent_tool_calls(state, "manager_agent") == ["next_step", "write"]
    writes = _manager_write_records(state)
    assert writes == [
        {
            "relative_path": "hypotheses/final_proposals.json",
            "payload_sha256": hashlib.sha256(
                json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
        }
    ]
    assert _matching_write_author_candidates(
        "hypotheses/final_proposals.json", payload, [], [], writes
    ) == ["manager_agent"]


def test_native_outer_trace_must_finish_through_reporter() -> None:
    messages = [
        SimpleNamespace(name=name, tool_calls=[])
        for name in (
            "planner_agent",
            "recruiter_agent",
            "manager_agent",
            "evaluator_agent",
            "reporter_agent",
        )
    ]
    trace = _outer_agent_trace({"messages": messages})
    _validate_outer_agent_trace(trace)
    assert trace["planner_format_retry_count"] == 0
    assert trace["recruiter_format_retry_count"] == 0
    with pytest.raises(RuntimeError, match="Reporter"):
        _validate_outer_agent_trace(_outer_agent_trace({"messages": messages[:-1]}))


def test_outer_trace_counts_only_replans_that_reenter_planner() -> None:
    def message(name: str, content: str = "") -> SimpleNamespace:
        return SimpleNamespace(name=name, content=content, tool_calls=[])

    messages = [
        message("planner_agent", "invalid"),
        message("planner_agent", "ROUTE: PLAN"),
        message("recruiter_agent"),
        message("manager_agent"),
        message("evaluator_agent", "ROUTE: REPLAN"),
        message("planner_agent"),
        message("recruiter_agent"),
        message("manager_agent"),
        message("evaluator_agent", "ROUTE: REPLAN"),
        message("planner_agent"),
        message("recruiter_agent"),
        message("manager_agent"),
        message("evaluator_agent", "ROUTE: REPORT"),
        message("reporter_agent"),
    ]
    trace = _outer_agent_trace({"messages": messages, "replan_count": 3})
    assert trace["planner_format_retry_count"] == 1
    assert trace["recruiter_format_retry_count"] == 0
    assert trace["evaluator_replan_count"] == 2
    assert trace["evaluator_replan_request_count"] == 3


def test_frozen_corpus_and_archive_validate() -> None:
    result = validate_data(
        BENCHMARK / "data" / "corpus_manifest.json",
        BENCHMARK / "data" / "public_contexts.json",
        BENCHMARK / "data" / "ground_truth.json",
    )
    assert result["paper_count"] == 11
    assert result["analysis_count"] == 112
    assert sorted(result["analysis_counts"].values()) == [
        5,
        9,
        9,
        9,
        11,
        11,
        11,
        11,
        12,
        12,
        12,
    ]
    archives = [
        ROOT / "papers-20260711T025044Z-2-001.zip",
        ROOT / "papers-20260721T071755Z-1-001.zip",
    ]
    if all(archive.is_file() for archive in archives):
        assert validate_archives(
            BENCHMARK / "data" / "corpus_manifest.json", archives
        )["verified_pdfs"] == 11


def test_contexts_are_title_free_and_have_no_legacy_appendix() -> None:
    manifest = json.loads((BENCHMARK / "data" / "corpus_manifest.json").read_text())
    contexts = json.loads((BENCHMARK / "data" / "public_contexts.json").read_text())
    by_id = {row["eval_id"]: row for row in contexts}
    for paper in manifest["papers"]:
        record = by_id[paper["opaque_id"]]
        context = record["context"]
        assert record["context_rule_version"] == "cellbench_intro_only_v2"
        assert context.count("\n\n") == 1
        assert "AVAILABLE STUDY INPUTS" not in context
        assert paper["title"].casefold() not in context.casefold()
        for term in paper.get("redaction_terms", []):
            assert term.casefold() not in context.casefold()


def test_protocol_identity_is_frozen() -> None:
    assert PROTOCOL == "spatial_cellbench_dynamic_n_v2"
