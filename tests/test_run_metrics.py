"""Tests for the per-run ``metrics.json`` dump emitted by the CLI.

Run from the repo root::

    cd src && python ../tests/test_run_metrics.py

Deliberately pytest-free (matching the other tests in this directory). Pure and
deterministic — no graph, no LLM, no kernel: every helper under test is a reader
over state that already exists at run end.
"""

import json
import sys
import tempfile
import types
from pathlib import Path

import cli
import config
import server.plan_store as plan_store_mod
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from server.plan_store import PlanDocument, PlanStep, PlanStore
from server.usage_tracker import usage_tracker

_failures: list[str] = []


def check(cond: bool, msg: str) -> None:
    if cond:
        print(f"  ok: {msg}")
    else:
        print(f"  FAIL: {msg}")
        _failures.append(msg)


def _args(**overrides):
    """Parse a minimal CLI invocation, then apply overrides."""
    argv = ["--task-id", "hb001", "--seed", "0", "some prompt"]
    ns = cli._build_arg_parser().parse_args(argv)
    for k, v in overrides.items():
        setattr(ns, k, v)
    return ns


def _session(**state):
    base = {
        "messages": ["m1", "m2"],
        "replan_count": 0,
        "replan_history": [],
        "recruiter_retry_count": 0,
        "planner_retry_count": 0,
    }
    base.update(state)
    return types.SimpleNamespace(project_id="2026-01-01_00-00-00", agent_state=base)


def _metrics(session=None, args=None, **overrides):
    kwargs = dict(
        session=session or _session(),
        args=args or _args(),
        prompt="p",
        answer="a",
        started_at="2026-01-01T00:00:00-05:00",
        elapsed=1.5,
        terminal_state="completed",
        error=None,
    )
    kwargs.update(overrides)
    return cli._collect_metrics(**kwargs)


def test_limits_snapshot():
    print("test_limits_snapshot")
    limits = cli._limits_block()
    for name in (
        "MAX_EXECUTOR_RETRIES",
        "EXECUTOR_RECURSION_LIMIT",
        "MAX_STEP_RETRIES",
        "MAX_REPLANS",
        "MAX_PLANNER_RETRIES",
        "MAX_RECRUITER_RETRIES",
        "RECURSION_LIMIT",
        "MAX_OUTPUT_CHARS",
    ):
        check(limits.get(name) == getattr(config, name), f"{name} snapshotted from config")


def test_models_recorded_per_role():
    print("test_models_recorded_per_role")
    block = cli._model_block()
    check(set(block) == {"orchestration", "worker"}, "both model roles recorded separately")
    for role, entry in block.items():
        check(entry["model_id"] is not None, f"{role} has a model id")
        check("provider" in entry and "reasoning_effort" in entry, f"{role} carries provider fields")


def test_usage_totals():
    print("test_usage_totals")
    usage_tracker.reset()
    usage_tracker.record_llm_call("planner_agent", None, {"input_tokens": 100, "output_tokens": 10}, 1.0)
    usage_tracker.record_llm_call("coding_agent", 2, {"input_tokens": 40, "output_tokens": 5}, 2.0)
    usage_tracker.record_llm_call("coding_agent", 2, None, 0.5)  # metadata stripped on a retry path
    u = cli._usage_block()
    check(u["input_tokens"] == 140, "input tokens summed across agents")
    check(u["output_tokens"] == 15, "output tokens summed across agents")
    check(u["total_tokens"] == 155, "total = input + output")
    check(u["llm_calls"] == 3, "calls counted even when usage metadata is missing")
    check(u["llm_time_seconds"] == 3.5, "llm time summed")
    check(set(u["by_agent"]) == {"planner_agent", "coding_agent"}, "per-agent breakdown kept")
    check([s["step_id"] for s in u["by_step"]] == [2], "per-step breakdown kept")
    usage_tracker.reset()


def test_plan_block_counts_retries(tmp_dir: Path):
    print("test_plan_block_counts_retries")
    store = PlanStore(plan_dir=tmp_dir)
    store.write(
        PlanDocument(
            status="running",
            user_request="u",
            steps=[
                PlanStep(id=1, title="a", status="done", retry_count=0),
                PlanStep(id=2, title="b", status="done", retry_count=2),
                PlanStep(id=3, title="c", status="failed", retry_count=config.MAX_STEP_RETRIES),
            ],
        )
    )
    original = plan_store_mod.plan_store
    plan_store_mod.plan_store = store
    try:
        block = cli._plan_block()
    finally:
        plan_store_mod.plan_store = original

    check(block["available"] is True, "plan block reads the store")
    check(block["steps_total"] == 3, "steps counted")
    check(block["step_retries_total"] == 2 + config.MAX_STEP_RETRIES, "retry counts summed")
    check(block["steps_retried"] == 2, "distinct retried steps counted")
    check(block["step_retry_limit_hits"] == 1, "steps at MAX_STEP_RETRIES flagged")
    check(block["step_retry_recovered"] == 1, "retried step ending 'done' counts as recovered")
    check(block["steps_failed"] == 1, "failed steps counted")
    check(len(block["steps"]) == 3, "per-step detail kept for audit")


def test_plan_block_after_reset(tmp_dir: Path):
    print("test_plan_block_after_reset")
    # A DIRECT run never writes a plan. The store lives outside the project
    # dir, so without the reset in run() it still holds the *previous* task's
    # plan and the dump reports those steps as if they were this run's.
    store = PlanStore(plan_dir=tmp_dir)
    store.write(PlanDocument(status="running", user_request="u", steps=[PlanStep(id=1, title="stale")]))
    store.reset()
    original = plan_store_mod.plan_store
    plan_store_mod.plan_store = store
    try:
        block = cli._plan_block()
    finally:
        plan_store_mod.plan_store = original
    check(block.get("steps_total", 0) == 0, "no steps leak from a previous run after reset")


def test_replan_limit_hit_is_derived_from_state():
    print("test_replan_limit_hit_is_derived_from_state")
    # The cap-hit run is the one the trace cannot see: the evaluator's third
    # REPLAN is rewritten to ROUTE: REPORT before it is emitted, so only state
    # knows replan_count == MAX_REPLANS + 1.
    over = _metrics(session=_session(replan_count=config.MAX_REPLANS + 1))
    check(over["loops"]["replans_triggered"] == config.MAX_REPLANS + 1, "replan count taken from state")
    check(over["loops"]["replan_limit_hit"] is True, "limit hit flagged above MAX_REPLANS")

    at_cap = _metrics(session=_session(replan_count=config.MAX_REPLANS))
    check(at_cap["loops"]["replan_limit_hit"] is False, "at-cap run is not a limit hit")


def _verdict(route: str, agent: str = "evaluator_agent") -> AIMessage:
    """An evaluator message shaped the way node_factories leaves it in state."""
    msg = AIMessage(content=f"ROUTE: {route}\n\nEVALUATION: because reasons.")
    msg.name = agent
    return msg


def _retry_call(call_id: str, tool: str = "retry_step") -> AIMessage:
    msg = AIMessage(
        content="",
        tool_calls=[{"name": tool, "args": {"task_instructions": "again"}, "id": call_id}],
    )
    msg.name = "manager_agent"
    return msg


def test_replans_successful():
    print("test_replans_successful")
    # Replan resolved the blocker: REPLAN then a genuine REPORT.
    good = cli._replan_outcomes([_verdict("REPLAN"), _verdict("REPORT")], replan_count=1)
    check(good["replans_successful"] == 1, "REPLAN followed by a genuine REPORT is successful")
    check(good["forced_report_at_cap"] is False, "no forced verdict when under the cap")
    check(good["verdict_state_mismatch"] is None, "verdicts reconcile with replan_count")

    # Thrashed: the first replan led straight to another one.
    thrash = cli._replan_outcomes(
        [_verdict("REPLAN"), _verdict("REPLAN"), _verdict("REPORT")], replan_count=2
    )
    check(thrash["replans_successful"] == 1, "a replan followed by another replan is not successful")

    # Cap hit: the third REPLAN is rewritten to REPORT in state, so the message
    # log shows 2 REPLANs while replan_count says 3. That final REPORT is the
    # loop being cut off — not the second replan succeeding.
    capped = cli._replan_outcomes(
        [_verdict("REPLAN"), _verdict("REPLAN"), _verdict("REPORT")],
        replan_count=config.MAX_REPLANS + 1,
    )
    check(capped["forced_report_at_cap"] is True, "cap-hit run detected from the state/verdict delta")
    check(capped["replans_successful"] == 0, "the forced REPORT at the cap counts no replan as successful")
    check(capped["verdict_state_mismatch"] is None, "the known off-by-one is not flagged as a mismatch")

    # Crashed mid-replan: no verdict follows, so nothing succeeded.
    cut = cli._replan_outcomes([_verdict("REPLAN")], replan_count=1)
    check(cut["replans_successful"] == 0, "a replan with no following verdict is not successful")

    # Reader/state disagreement beyond the known off-by-one must be visible.
    broken = cli._replan_outcomes([_verdict("REPORT")], replan_count=3)
    check(broken["verdict_state_mismatch"] == 3, "an unexplained delta is reported, not swallowed")

    # Only the evaluator's verdicts count — the planner emits ROUTE: too.
    mixed = cli._replan_outcomes(
        [_verdict("PLAN", agent="planner_agent"), _verdict("REPLAN"), _verdict("REPORT")],
        replan_count=1,
    )
    check(mixed["evaluator_verdicts"] == ["REPLAN", "REPORT"], "planner ROUTE lines are excluded")


def test_manager_retries_from_messages():
    print("test_manager_retries_from_messages")
    messages = [
        HumanMessage(content="do it"),
        _retry_call("c0", tool="next_step"),
        ToolMessage(content="Dispatched step 1", tool_call_id="c0"),
        _retry_call("c1"),
        ToolMessage(content="Dispatched step 1 (retry)", tool_call_id="c1"),
        _retry_call("c2"),
        ToolMessage(
            content=f"Error: step 1 has reached the retry limit (MAX_STEP_RETRIES={config.MAX_STEP_RETRIES})",
            tool_call_id="c2",
        ),
    ]
    m = cli._manager_retries_from_messages(messages)
    check(m["retry_step_calls"] == 2, "every retry_step call counted")
    check(m["retry_step_refused"] == 1, "a retry refused at the budget is counted separately")
    check(m["retry_step_dispatched"] == 1, "dispatched retries exclude refusals")
    check(m["next_step_calls"] == 1, "next_step dispatches counted")

    check(
        cli._manager_retries_from_messages([])["retry_step_calls"] == 0,
        "no messages -> no retries",
    )


def _planner(content: str) -> AIMessage:
    msg = AIMessage(content=content)
    msg.name = "planner_agent"
    return msg


def test_planner_route_and_degradation():
    print("test_planner_route_and_degradation")
    p = cli._planner_block([_planner("ROUTE: PLAN\n\n```json\n{}\n```")])
    check(p["route"] == "PLAN", "route read from the planner's first line")
    check(p["degraded_to_direct"] is False, "a normal PLAN run is not degraded")

    # Retries exhausted: the forced content is committed to state, so the dump
    # sees a failed run that would otherwise look like a clean DIRECT.
    forced = cli._planner_block(
        [_planner("ROUTE: DIRECT\n\nPlanner retries exhausted: Planner failed to produce valid JSON")]
    )
    check(forced["route"] == "DIRECT", "forced verdict still reads as DIRECT")
    check(forced["degraded_to_direct"] is True, "forced DIRECT flagged as degraded")

    # Replans re-enter the planner, so every turn's verdict is kept.
    multi = cli._planner_block([_planner("ROUTE: PLAN\n\nx"), _planner("ROUTE: PLAN\n\ny")])
    check(multi["routes"] == ["PLAN", "PLAN"], "one route recorded per planner turn")

    # The evaluator also emits ROUTE: lines — they must not be counted here.
    check(
        cli._planner_block([_verdict("REPORT")])["route"] is None,
        "evaluator verdicts are not planner routes",
    )


def test_planner_format_retries():
    print("test_planner_format_retries")
    messages = [
        HumanMessage(content="do it"),
        _planner("not json at all"),
        HumanMessage(
            content="Your response must contain a single fenced ```json``` code block "
            "with the plan schema (user_request, steps, provenance). Please try again."
        ),
        _planner("still not json"),
        HumanMessage(content="Your ROUTE: PLAN response must contain a fenced ```json``` block with the plan schema. Please try again."),
        _planner("ROUTE: PLAN\n\n```json\n{}\n```"),
    ]
    block = cli._planner_block(messages)
    check(block["format_retries"] == 2, "each retry-feedback message counted")
    check(block["route"] == "PLAN", "the eventual route still resolves")
    check(
        cli._planner_block([HumanMessage(content="Your response is great")])["format_retries"] == 0,
        "unrelated user text is not a retry",
    )


def test_reason_texts():
    print("test_reason_texts")
    retry = AIMessage(
        content="",
        tool_calls=[{"name": "retry_step", "args": {"task_instructions": "step 2 produced no table"}, "id": "r1"}],
    )
    retry.name = "manager_agent"
    reasons = cli._reason_texts([retry, _verdict("REPLAN"), _verdict("REPORT")])
    check(
        reasons["step_retry_reasons"] == ["step 2 produced no table"],
        "retry_step task_instructions captured verbatim",
    )
    check(len(reasons["replan_reasons"]) == 1, "only REPLAN verdicts carry a replan reason")
    check("EVALUATION" in reasons["replan_reasons"][0], "the evaluator's rationale is kept raw")

    long_reason = AIMessage(
        content="", tool_calls=[{"name": "retry_step", "args": {"task_instructions": "x" * 5000}, "id": "r2"}]
    )
    long_reason.name = "manager_agent"
    capped = cli._reason_texts([long_reason], max_chars=100)
    check(len(capped["step_retry_reasons"][0]) == 100, "reason text is capped so metrics.json stays small")


def test_metrics_shape():
    print("test_metrics_shape")
    m = _metrics()
    for key in ("schema_version", "run", "models", "limits", "outcome", "usage", "loops", "plan"):
        check(key in m, f"top-level key '{key}' present")
    check(m["run"]["task_id"] == "hb001", "task id passed through from --task-id")
    check(m["run"]["seed"] == "0", "seed passed through from --seed")
    check(m["run"]["sandbox"] in ("docker", "local-gateway"), "sandbox recorded")
    check(m["run"]["wall_time_s"] == 1.5, "wall time recorded")
    check(m["outcome"]["terminal_state"] == "completed", "terminal state recorded")
    json.dumps(m, default=str)  # must be serializable — it is written verbatim
    check(True, "metrics record is JSON-serializable")


def test_terminal_state_classification():
    print("test_terminal_state_classification")
    check(cli._terminal_state_for(KeyboardInterrupt()) == "interrupted", "KeyboardInterrupt -> interrupted")
    check(
        cli._terminal_state_for(RuntimeError("Recursion limit of 100 reached")) == "recursion-limit",
        "recursion limit detected from the message",
    )
    check(cli._terminal_state_for(ValueError("boom")) == "crashed", "anything else -> crashed")


def test_write_metrics(tmp_dir: Path):
    print("test_write_metrics")
    project = tmp_dir / "project"
    out = tmp_dir / "archive" / "metrics.json"
    original = config.ACTIVE_PROJECT_DIR
    config.ACTIVE_PROJECT_DIR = project
    try:
        path = cli._write_metrics(_metrics(), _args(metrics_out=str(out)))
    finally:
        config.ACTIVE_PROJECT_DIR = original

    check(path == str(project / "metrics.json"), "returns the project-dir path")
    check((project / "metrics.json").is_file(), "written to the project dir")
    check(out.is_file(), "also written to --metrics-out for archiving")
    check(
        json.loads(out.read_text())["run"]["task_id"] == "hb001",
        "archived copy round-trips as JSON",
    )


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        tmp_dir = Path(td)
        test_limits_snapshot()
        test_models_recorded_per_role()
        test_usage_totals()
        test_plan_block_counts_retries(tmp_dir / "plan")
        test_plan_block_after_reset(tmp_dir / "plan-reset")
        test_replan_limit_hit_is_derived_from_state()
        test_replans_successful()
        test_manager_retries_from_messages()
        test_planner_route_and_degradation()
        test_planner_format_retries()
        test_reason_texts()
        test_metrics_shape()
        test_terminal_state_classification()
        test_write_metrics(tmp_dir / "write")

    print()
    if _failures:
        print(f"{len(_failures)} FAILURE(S):")
        for f in _failures:
            print(f"  - {f}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
