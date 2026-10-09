"""Safety and scientific-protocol contracts for native refinement."""

import hashlib
import json

import pytest
from pydantic import ValidationError

from benchmark.spatial_cellbench.refinement import (
    Blueprint,
    CandidateReview,
    CandidateRevision,
    CriticResponse,
    FiveDimensions,
    RefinementSession,
    apply_revision,
    validate_blueprint,
)
from benchmark.spatial_cellbench.schemas import PublicContext


def public():
    """Build a synthetic context without source-paper information."""
    context = "Spatial expression measures tissue organization. " * 30
    return PublicContext(
        eval_id="spcb_0123456789",
        context=context,
        word_count=len(context.split()),
        context_rule_version="test",
        context_sha256=hashlib.sha256(context.encode()).hexdigest(),
    )


def dimensions():
    """Build valid quality assessments with unknown novelty."""
    return {
        name: {
            "assessable": name != "novel",
            "score": None if name == "novel" else 8,
            "reason": "Known findings are withheld"
            if name == "novel"
            else "Supported by spatial expression context",
        }
        for name in ("derivable", "novel", "feasible", "specific", "falsifiable")
    }


def blueprint(cid="C01"):
    """Build a traceable candidate fixture."""
    return Blueprint(
        candidate_id=cid,
        title="Map spatial expression domains",
        summary="Infer spatial domains from expression and test their spatial stability.",
        primary_objective="Identify expression-defined tissue domains",
        context_evidence=["E01"],
        assumptions=["Coordinates accompany expression measurements"],
        required_inputs=["Expression matrix", "Coordinates"],
        comparison="Expression similarity within versus between spatial domains",
        analysis_plan=["Construct a spatial expression graph", "Compare domain stability"],
        validation="Refute stable domains if coordinate permutation retains equal coherence.",
        quality_scores=dimensions(),
    )


def review(cid="C01", decision="KEEP"):
    """Build an actionable review fixture."""
    return CandidateReview(
        candidate_id=cid,
        decision=decision,
        quality_scores=dimensions(),
        nonredundancy="Distinct primary objective from peer candidates",
        issues=[] if decision == "KEEP" else ["Validation requires a null control"],
        requested_edits=[] if decision == "KEEP" else ["Specify permutation control"],
        allow_objective_change=decision == "REJECT",
        objective_change_reason="Unsupported objective requires replacement"
        if decision == "REJECT"
        else "",
    )


class Caller:
    """Deterministic specialist model for protocol tests."""

    def __init__(self):
        """Initialize observable call accounting."""
        self.traces, self.failed_attempts, self.prompts = [], [], []
        self.observable_attempt_count = 0

    def structured(self, stage, system_prompt, user_prompt, schema):
        """Return stage-appropriate deterministic responses."""
        self.traces.append({"stage": stage, "total_tokens": 10})
        self.prompts.append((stage, system_prompt, user_prompt))
        self.observable_attempt_count += 1
        cid = stage.split("_")[1]
        if issubclass(schema, Blueprint):
            return blueprint(cid)
        if issubclass(schema, CriticResponse):
            return schema.model_validate(
                {
                    "review": review(cid, "KEEP" if cid == "C01" else "REVISE").model_dump(),
                }
            )
        candidate = blueprint(cid).model_copy(
            update={"validation": "Permutation control refutes stability."}
        )
        return CandidateRevision(
            candidate=candidate, change_reason="Added the requested null control"
        )


def test_novelty_is_retained_but_not_fabricated():
    """Verify novelty is retained but not fabricated."""
    values = dimensions()
    assert set(FiveDimensions.model_validate(values).model_dump()) == {
        "derivable",
        "novel",
        "feasible",
        "specific",
        "falsifiable",
    }
    values["novel"].update(assessable=True, score=9)
    with pytest.raises(ValidationError, match="novel"):
        FiveDimensions.model_validate(values)


def test_critic_schema_requires_consistent_actions_and_candidate_identity():
    """Reject the pilot failure at the schema boundary and permit each valid action."""
    from benchmark.spatial_cellbench.refinement import review_schema

    schema = review_schema("C01")
    for decision in ("KEEP", "REVISE", "REJECT"):
        value = review(decision=decision).model_dump()
        assert schema.model_validate({"review": value}).review.decision == decision
    invalid = review(decision="REVISE").model_dump()
    invalid["requested_edits"] = []
    with pytest.raises(ValidationError):
        schema.model_validate({"review": invalid})
    invalid = review().model_dump()
    invalid["candidate_id"] = "C02"
    with pytest.raises(ValidationError):
        schema.model_validate({"review": invalid})
    invalid = review(decision="REJECT").model_dump()
    invalid["allow_objective_change"] = False
    with pytest.raises(ValidationError):
        schema.model_validate({"review": invalid})


def test_evidence_ids_and_locked_objectives_are_constrained_in_schema():
    """Reject fabricated references and objective drift at the structured-output boundary."""
    from benchmark.spatial_cellbench.refinement import blueprint_schema, evidence_ledger

    candidate = blueprint()
    schema = blueprint_schema(public(), "C01", candidate.primary_objective)
    assert schema.model_validate(candidate.model_dump()).context_evidence == ["E01"]
    assert all(sentence in public().context for sentence in evidence_ledger(public()).values())
    for field, value in [
        ("context_evidence", ["E99"]),
        ("candidate_id", "C02"),
        ("primary_objective", "An unrelated objective"),
    ]:
        with pytest.raises(ValidationError):
            schema.model_validate({**candidate.model_dump(), field: value})


def test_evidence_must_exist_and_candidate_identity_must_survive():
    """Verify evidence must exist and candidate identity must survive."""
    candidate = blueprint()
    validate_blueprint(candidate, "C01", public())
    with pytest.raises(ValueError, match="identity"):
        validate_blueprint(candidate, "C02", public())
    with pytest.raises(ValueError, match="reference"):
        validate_blueprint(
            candidate.model_copy(update={"context_evidence": ["Invented modality"]}),
            "C01",
            public(),
        )


def test_keep_is_identity_and_revisions_require_objective_authorization():
    """Verify keep is identity and revisions require objective authorization."""
    draft = blueprint()
    assert apply_revision(draft, review(), None) is draft
    revision = CandidateRevision(
        candidate=draft.model_copy(
            update={"primary_objective": "An unrelated scientific objective"}
        ),
        change_reason="Changed scientific objective",
    )
    with pytest.raises(ValueError, match="KEEP"):
        apply_revision(draft, review(), revision)
    with pytest.raises(ValueError, match="Unapproved"):
        apply_revision(draft, review(decision="REVISE"), revision)
    assert apply_revision(draft, review(decision="REJECT"), revision) == revision.candidate


def test_native_three_milestones_budget_and_exact_keep_bytes(tmp_path):
    """Verify native three milestones budget and exact keep bytes."""
    caller = Caller()
    session = RefinementSession(
        public(), "Frozen overview sentinel", 2, tmp_path, "o3-mini", lambda _: caller
    )
    session.invoke("hypothesis")
    session.invoke("critic")
    session.invoke("hypothesis")
    assert session.trace()["logical_model_calls"] == 5
    assert session.trace()["status"] == "success"
    draft = tmp_path / "hypotheses/blueprints/draft_C01.json"
    final = tmp_path / "hypotheses/blueprints/final_C01.json"
    assert draft.read_bytes() == final.read_bytes()
    assert all("Frozen overview sentinel" in prompt for _, _, prompt in caller.prompts)
    critic_prompts = [prompt for stage, _, prompt in caller.prompts if stage.endswith("critic")]
    assert all('"quality_scores"' not in prompt for prompt in critic_prompts)
    exported = json.loads((tmp_path / "hypotheses/final_proposals.json").read_text())
    assert all(set(p) == {"title", "summary"} for p in exported["proposals"])
    session.invoke("hypothesis")
    session.invoke("critic")
    assert session.trace()["logical_model_calls"] == 5
    session.verify_artifacts()


def test_failed_invocation_seals_budget_and_preserves_partial_trace(tmp_path):
    """Verify failed invocation seals budget and preserves partial trace."""
    caller = Caller()
    session = RefinementSession(public(), "Overview", 2, tmp_path, "o3-mini", lambda _: caller)
    with pytest.raises(RuntimeError, match="complete validated draft"):
        session.invoke("critic")
    with pytest.raises(RuntimeError, match="sealed"):
        session.invoke("hypothesis")
    assert caller.observable_attempt_count == 0
    assert json.loads((tmp_path / "audit/refinement_trace.json").read_text())["status"] == "failed"


def test_external_artifact_rewrite_is_rejected(tmp_path):
    """Verify external artifact rewrite is rejected."""
    session = RefinementSession(public(), "Overview", 2, tmp_path, "o3-mini", lambda _: Caller())
    session.invoke("hypothesis")
    (tmp_path / "hypotheses/draft_proposals.json").write_text("{}")
    with pytest.raises(RuntimeError, match="modified externally"):
        session.invoke("critic")


def test_experimental_worker_dispatch_preserves_native_graph(monkeypatch, tmp_path):
    """Verify experimental worker dispatch preserves native graph."""
    from benchmark.spatial_cellbench import run
    from benchmark.spatial_cellbench.refinement import OVERVIEW_ARM, REFINED_ARM
    from benchmark.spatial_cellbench.schemas import validate_proposal_count

    calls = []

    def native(*args, **kwargs):
        """Verify native."""
        calls.append(kwargs)
        return {
            "proposals": validate_proposal_count(
                {"proposals": [{"title": blueprint().title, "summary": blueprint().summary}]}, 1
            ).model_dump(),
            "trace": {"native_tissueagent_graph": True},
        }

    monkeypatch.setattr(run, "run_tissueagent", native)
    monkeypatch.setattr(run, "_source_fingerprint", lambda: {"sha256": "test-source"})
    for arm in (OVERVIEW_ARM, REFINED_ARM):
        payload = run._generation_payload(
            public(), 1, arm, 1, "o3-mini", "gpt-5.1", "Overview", "test-source"
        )
        result = run.run_generation_worker(payload, tmp_path)
        assert result["trace"]["native_tissueagent_graph"]
        assert calls[-1] == {"include_spatial_cv": False, "experimental_arm": arm}
        assert "truth" not in payload


def test_overview_ablation_does_not_modify_original_critic(tmp_path, monkeypatch):
    """Verify overview ablation does not modify original critic."""
    from benchmark.spatial_cellbench.ta import build_ta_roster
    import sys
    from types import SimpleNamespace

    monkeypatch.setitem(
        sys.modules,
        "agents.agent_defns",
        SimpleNamespace(
            CustomAgent=SimpleNamespace, ReActAgent=SimpleNamespace, WorkerModelCtor=object()
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "agents.agent_registry.hypothesis_agent.model",
        SimpleNamespace(create_hypothesis_agent=object()),
    )
    monkeypatch.setattr("benchmark.spatial_cellbench.ta.build_critic_tools", lambda _: [])

    kwargs = dict(
        public=public(),
        outputs=tmp_path,
        proposal_count=2,
        include_spatial_cv=False,
        overview="Frozen overview sentinel",
        model_id="o3-mini",
    )
    original = build_ta_roster(**kwargs)[1].prompt({})
    treated = build_ta_roster(**kwargs, shared_overview=True)[1].prompt({})
    assert "Frozen overview sentinel" not in original
    assert treated.startswith(original)
    assert "Frozen overview sentinel" in treated


def test_paired_audit_reuses_identical_verdicts_and_resumes_without_calls(tmp_path, monkeypatch):
    """Prevent judge noise and repeat charges for identical or cached proposals."""
    from benchmark.spatial_cellbench import run
    from benchmark.spatial_cellbench.evaluation import build_blind_judge_problem
    from benchmark.spatial_cellbench.schemas import MatchVerdict, validate_proposal_count
    from benchmark.spatial_cellbench.scripts import audit_native_refinement as audit

    contexts, truths, _, _ = run._load_corpus()
    context = contexts[0]
    paper = context.eval_id
    payload = {"proposals": [{"title": blueprint().title, "summary": blueprint().summary}] * 2}
    drafts = validate_proposal_count(payload, 2)
    final_payload = json.loads(json.dumps(payload))
    final_payload["proposals"][1]["summary"] += " A revised final detail."
    finals = validate_proposal_count(final_payload, 2)
    generation = run._seal_checkpoint(
        {
            "status": "success",
            "eval_id": paper,
            "replicate": 1,
            "proposal_count": 2,
            "proposals": final_payload,
            "proposal_sha256": run._sha256_json(final_payload),
        }
    )
    gen_path = tmp_path / "generation" / paper / "replicate_01/tissueagent_refined.json"
    run._atomic_write_json(gen_path, generation)
    hashes = [
        hashlib.sha256(
            build_blind_judge_problem(context, truths[paper], finals, 1, i).prompt.encode()
        ).hexdigest()
        for i in range(2)
    ]
    run._atomic_write_json(
        tmp_path / "judging" / paper / "replicate_01/tissueagent_refined.json",
        run._seal_checkpoint(
            {
                "status": "success",
                "generation_proposal_sha256": generation["proposal_sha256"],
                "truth_sha256": run._sha256_json(truths[paper].model_dump()),
                "decisions": [{"match": True, "reason": "Matched objective"}] * 2,
                "judge_prompt_sha256": hashes,
            }
        ),
    )
    outputs = (
        tmp_path
        / "work"
        / paper
        / ("replicate_01/tissueagent_refined/attempt_01/runtime/workspace/project/outputs")
    )
    run._atomic_write_json(outputs / "hypotheses/draft_proposals.json", drafts.model_dump())

    class Judge:
        def __init__(self):
            self.traces = []

        def structured(self, *args):
            self.traces.append({"stage": args[0], "total_tokens": 10})
            return MatchVerdict(match=False, reason="Different objective")

    judge = Judge()
    monkeypatch.setattr(audit, "LangChainModelCall", lambda _: judge)
    result = audit.audit_unit(tmp_path, gen_path, {paper: context}, truths, tmp_path / "audit")
    assert result["reused_verdicts"] == 1
    assert result["draft_matched"] == 1 and result["final_matched"] == 2
    assert len(judge.traces) == 1
    assert (
        audit.audit_unit(tmp_path, gen_path, {paper: context}, truths, tmp_path / "audit") == result
    )
    assert len(judge.traces) == 1
