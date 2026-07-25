"""Native TissueAgent integration for the spatial paper benchmark."""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from queue import Empty, Queue
from typing import Callable

from benchmark.spatial_cellbench.methods import (
    LangChainModelCall,
    register_benchmark_models,
    run_spatial_cv,
)
from benchmark.spatial_cellbench.schemas import PublicContext, validate_proposal_count

TA_ARM = "tissueagent"
TA_CV_ARM = "tissueagent_spatial_cv"
TA_ARMS = (TA_ARM, TA_CV_ARM)
SPATIAL_CV_PROTOCOL = "spatial_cv_dynamic_n_v1"
OUTER_AGENT_ORDER = (
    "planner_agent",
    "recruiter_agent",
    "manager_agent",
    "evaluator_agent",
    "reporter_agent",
)

HYPOTHESIS_SYSTEM = r"""
You are TissueAgent's Hypothesis Agent in a blinded paper-analysis benchmark. The paper's
actual analyses are hidden. Use only the public background and generated artifact snapshots
below; never search for or identify the source paper.

Follow the Manager's current scientific instruction and write exactly one requested proposal
artifact: `hypotheses/draft_proposals.json` for a draft step or
`hypotheses/final_proposals.json` for final synthesis. Never write both in one invocation. Paths
passed to `read_json` and `write_json` are relative to the project output root. The file must be
one JSON object whose only top-level key is `proposals`, with exactly {{proposal_count}} items.
Each item must contain only `title` and `summary`; the summary is a detailed paragraph explaining
the proposed analysis. Recover likely analyses from the hidden paper, not novel follow-ups. Use
only modalities, cohorts, and comparisons stated in the public background.

Every `<execute>...</execute>` block must contain plain Python source. Imports and arbitrary
file access are disabled. `read_text`, `read_json`, and `write_json` are available. Call
`write_json("hypotheses/<requested file>.json", payload)` directly; do not use `import`, `open`,
or `json.dump`. Emit one execute block that writes the artifact. A validated write ends the
invocation.

PUBLIC BACKGROUND:
{{public_context}}

CURRENT GENERATED ARTIFACTS:
{{artifacts}}

{{skill_prompt}}
""".strip()

CRITIC_SYSTEM = r"""
You are TissueAgent's Critic Agent in a blinded paper-analysis benchmark. Use only the public
background and generated artifacts below; never search for or identify the source paper.

Assess whether candidates are supported, spatially meaningful, specific, and likely to be
analyses in the hidden paper. Identify unsupported assumptions, likely omissions, and useful
repairs. Write concise valid JSON to `hypotheses/critique.json` with `write_file_tool`; do not
write a proposal set.

PUBLIC BACKGROUND:
{{public_context}}

CURRENT GENERATED ARTIFACTS:
{{artifacts}}
""".strip()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _semantic_json_sha256(payload: object) -> str:
    return _sha256_text(json.dumps(payload, sort_keys=True, separators=(",", ":")))


def _atomic_write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _validate_public(public: PublicContext) -> None:
    if len(public.context.split()) != public.word_count:
        raise ValueError("Public context word count does not match its frozen record")
    if _sha256_text(public.context) != public.context_sha256:
        raise ValueError("Public context hash does not match its frozen record")


def build_ta_task(
    public: PublicContext,
    proposal_count: int,
    require_spatial_cv: bool = False,
) -> str:
    """Return the native task, including the declared integration treatment when requested."""
    _validate_public(public)
    recruitment = (
        "For this TA+CV treatment, the Recruiter must assign step (1) to the Spatial-CV "
        "Planning Agent (`spatial_cv_agent`). Do not replace it with Hypothesis or merely "
        "list it as available. Assign steps (2) and (3) by their advertised critique and "
        "final-synthesis outputs."
        if require_spatial_cv
        else "Recruit the best available agent whose advertised output matches each step."
    )
    return f"""
PAPER-ANALYSIS BENCHMARK. Use ROUTE: PLAN and the normal TissueAgent workflow. Coordinate the
available domain agents to propose exactly {proposal_count} computational spatial-omics analyses
most likely performed in the hidden paper. This is one proposal-synthesis deliverable, not
{proposal_count} analyses to execute. Use exactly three compact plan steps and no others:
(1) generate the candidate draft at `project/outputs/hypotheses/draft_proposals.json`,
(2) critique that draft at `project/outputs/hypotheses/critique.json`, and
(3) synthesize the final candidates at `project/outputs/hypotheses/final_proposals.json`.
Do not create one step per proposal, merge these three steps, or apply knowledge plan templates
as candidate analyses; do not pre-specify the candidate contents or run the proposed analyses.
{recruitment} Dispatch every step once its predecessor artifact exists. Do not search for or
identify the source paper, request more data, or score against hidden answers.

Creating the requested JSON proposal artifacts is required and is not the same as executing the
proposed analyses. Physically write every listed artifact to its exact path; never describe an
artifact as simulated, in-memory, or append qualifiers to an artifact path.

The only required final artifact is
`project/outputs/hypotheses/final_proposals.json`. Specialist tool descriptions define any
other intermediate artifacts; a preliminary synthesis step may use
`project/outputs/hypotheses/draft_proposals.json`, and an optional critique may use
`project/outputs/hypotheses/critique.json`. Hypothesis advertises draft and final proposal files;
Critic advertises only the critique file. Do not invent other required output paths. The final
proposal file must be a JSON object whose only top-level key is `proposals`, with exactly
{proposal_count} items. Each item contains only `title` and a detailed `summary`. Use only the
information below.

PUBLIC BACKGROUND:
{public.context}
""".strip()


def _artifact_snapshots(outputs: Path, proposal_count: int) -> dict[str, object]:
    snapshots = {}
    for relative in (
        "hypotheses/final_proposals.json",
        "hypotheses/draft_proposals.json",
        "hypotheses/critique.json",
        "hypotheses/spatial_cv_proposals.json",
    ):
        path = outputs / relative
        if not path.is_file():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        snapshots[relative] = payload
    return snapshots


def build_hypothesis_prompt(
    public: PublicContext,
    outputs: Path,
    proposal_count: int,
    audit_path: Path | None = None,
) -> str:
    """Render the dynamic benchmark prompt for the real Hypothesis Agent."""
    snapshots = _artifact_snapshots(outputs, proposal_count)
    cv_path = "hypotheses/spatial_cv_proposals.json"
    if audit_path is not None:
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "at": datetime.now(timezone.utc).isoformat(),
            "artifact_keys": sorted(snapshots),
            "artifact_sha256": {
                path: _semantic_json_sha256(payload)
                for path, payload in sorted(snapshots.items())
            },
        }
        if cv_path in snapshots:
            record["spatial_cv_sha256"] = hashlib.sha256(
                (outputs / cv_path).read_bytes()
            ).hexdigest()
        with audit_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, sort_keys=True) + "\n")
    return (
        HYPOTHESIS_SYSTEM.replace("{{public_context}}", public.context)
        .replace("{{proposal_count}}", str(proposal_count))
        .replace("{{artifacts}}", json.dumps(snapshots, indent=2, ensure_ascii=False))
    )


def build_critic_prompt(
    public: PublicContext,
    outputs: Path,
    proposal_count: int,
) -> str:
    """Render the dynamic benchmark prompt for the Critic Agent."""
    return CRITIC_SYSTEM.replace("{{public_context}}", public.context).replace(
        "{{artifacts}}",
        json.dumps(
            _artifact_snapshots(outputs, proposal_count),
            indent=2,
            ensure_ascii=False,
        ),
    )


def build_critic_tools(outputs: Path) -> list:
    """Return read tools plus one benchmark-scoped critique writer."""
    from langchain.tools import StructuredTool

    from agents.agent_tools import file_read_tools

    def write_critique(file_path: str, content: str) -> str:
        relative = Path(file_path.strip())
        if relative.parts[:2] == ("project", "outputs"):
            relative = Path(*relative.parts[2:])
        elif relative.parts[:1] == ("outputs",):
            relative = Path(*relative.parts[1:])
        if relative.as_posix() != "hypotheses/critique.json":
            return "Error: Critic must write only hypotheses/critique.json"
        try:
            payload = json.loads(content)
        except json.JSONDecodeError as exc:
            return f"Error: critique must be valid JSON: {exc}"
        if not isinstance(payload, (dict, list)):
            return "Error: critique JSON must be an object or array"
        _atomic_write_json(outputs / relative, payload)
        audit_path = outputs / "audit" / "critic_validated_writes.jsonl"
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        with audit_path.open("a", encoding="utf-8") as stream:
            stream.write(
                json.dumps(
                    {
                        "at": datetime.now(timezone.utc).isoformat(),
                        "relative_path": relative.as_posix(),
                        "payload_sha256": _semantic_json_sha256(payload),
                    },
                    sort_keys=True,
                )
                + "\n"
            )
        return "Successfully wrote hypotheses/critique.json"

    return [
        *file_read_tools,
        StructuredTool.from_function(
            func=write_critique,
            name="write_file_tool",
            description="Write valid JSON to hypotheses/critique.json and nowhere else.",
        ),
    ]


def _expected_cv_stages(proposal_count: int) -> list[str]:
    return [
        f"spatial_cv_{index:02d}_{stage}"
        for index in range(1, proposal_count + 1)
        for stage in ("draft", "critic", "revision")
    ]


def _validate_spatial_cv_bundle(
    outputs: Path,
    public: PublicContext,
    overview: str,
    model_id: str,
    proposal_count: int,
) -> tuple[bool, str, dict | None]:
    proposals_path = outputs / "hypotheses" / "spatial_cv_proposals.json"
    trace_path = outputs / "hypotheses" / "spatial_cv_trace.json"
    if not proposals_path.exists() and not trace_path.exists():
        return False, "absent", None
    if not proposals_path.is_file() or not trace_path.is_file():
        if trace_path.is_file():
            try:
                trace = json.loads(trace_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                trace = None
            return False, "partial", trace
        return False, "partial", None
    try:
        proposals = validate_proposal_count(
            json.loads(proposals_path.read_text(encoding="utf-8")),
            proposal_count,
        )
        trace = json.loads(trace_path.read_text(encoding="utf-8"))
    except (ValueError, json.JSONDecodeError) as exc:
        return False, f"parse:{type(exc).__name__}", None
    expected_stages = _expected_cv_stages(proposal_count)
    calls = trace.get("calls")
    checks = {
        "status": trace.get("status") == "success",
        "protocol": trace.get("protocol") == SPATIAL_CV_PROTOCOL,
        "eval_id": trace.get("eval_id") == public.eval_id,
        "model": trace.get("model_id") == model_id,
        "count": trace.get("proposal_count") == proposal_count,
        "context": trace.get("context_sha256") == public.context_sha256,
        "overview": trace.get("overview_sha256") == _sha256_text(overview),
        "stages": isinstance(calls, list)
        and [call.get("stage") for call in calls] == expected_stages,
        "proposal_hash": trace.get("proposal_sha256")
        == hashlib.sha256(proposals_path.read_bytes()).hexdigest(),
    }
    failures = [name for name, passed in checks.items() if not passed]
    if failures:
        return False, "mismatch:" + ",".join(failures), trace
    validate_proposal_count(proposals, proposal_count)
    return True, "valid", trace


def create_spatial_cv_agent(
    state_queue,
    context_resolver=None,
    spatial_cv_public: PublicContext | None = None,
    spatial_cv_overview: str = "",
    spatial_cv_model_id: str | None = None,
    spatial_cv_outputs: Path | None = None,
    spatial_cv_count: int | None = None,
    spatial_cv_caller_factory: Callable[[str], object] = LangChainModelCall,
):
    """Create the naturally recruitable benchmark-local Spatial-CV tool."""
    del state_queue, context_resolver
    from langchain.tools import StructuredTool

    if (
        spatial_cv_public is None
        or spatial_cv_model_id is None
        or spatial_cv_outputs is None
        or spatial_cv_count is None
    ):
        raise ValueError("Spatial-CV benchmark inputs must be supplied explicitly")
    proposals_path = spatial_cv_outputs / "hypotheses" / "spatial_cv_proposals.json"
    draft_path = spatial_cv_outputs / "hypotheses" / "draft_proposals.json"
    trace_path = spatial_cv_outputs / "hypotheses" / "spatial_cv_trace.json"

    def run_agent(prompt: str) -> str:
        del prompt
        valid, reason, _ = _validate_spatial_cv_bundle(
            spatial_cv_outputs,
            spatial_cv_public,
            spatial_cv_overview,
            spatial_cv_model_id,
            spatial_cv_count,
        )
        if valid:
            _atomic_write_json(
                draft_path,
                json.loads(proposals_path.read_text(encoding="utf-8")),
            )
            return f"Spatial-CV already produced {spatial_cv_count} valid proposals."
        if reason != "absent":
            raise RuntimeError(f"Spatial-CV workspace is not fresh: {reason}")
        started = time.perf_counter()
        caller = spatial_cv_caller_factory(spatial_cv_model_id)
        try:
            result = run_spatial_cv(
                spatial_cv_public,
                spatial_cv_overview,
                spatial_cv_count,
                caller,
            )
            _atomic_write_json(proposals_path, result.model_dump())
            _atomic_write_json(draft_path, result.model_dump())
            calls = list(getattr(caller, "traces", []))
            expected = _expected_cv_stages(spatial_cv_count)
            if [call.get("stage") for call in calls] != expected:
                raise RuntimeError(
                    "Spatial-CV call stages do not match the dynamic-N protocol"
                )
        except Exception as exc:
            proposals_path.unlink(missing_ok=True)
            calls = list(getattr(caller, "traces", []))
            failed_attempts = list(getattr(caller, "failed_attempts", []))
            _atomic_write_json(
                trace_path,
                {
                    "status": "failed",
                    "protocol": SPATIAL_CV_PROTOCOL,
                    "eval_id": spatial_cv_public.eval_id,
                    "model_id": spatial_cv_model_id,
                    "proposal_count": spatial_cv_count,
                    "context_sha256": spatial_cv_public.context_sha256,
                    "overview_sha256": _sha256_text(spatial_cv_overview),
                    "logical_model_calls": len(calls),
                    "observable_model_attempts": getattr(
                        caller,
                        "observable_attempt_count",
                        len(calls) + len(failed_attempts),
                    ),
                    "calls": calls,
                    "failed_attempts": failed_attempts,
                    "elapsed_seconds": round(time.perf_counter() - started, 3),
                    "error_type": type(exc).__name__,
                },
            )
            raise
        _atomic_write_json(
            trace_path,
            {
                "status": "success",
                "protocol": SPATIAL_CV_PROTOCOL,
                "eval_id": spatial_cv_public.eval_id,
                "model_id": spatial_cv_model_id,
                "proposal_count": spatial_cv_count,
                "context_sha256": spatial_cv_public.context_sha256,
                "overview_sha256": _sha256_text(spatial_cv_overview),
                "logical_model_calls": len(calls),
                "observable_model_attempts": caller.observable_attempt_count,
                "calls": calls,
                "failed_attempts": caller.failed_attempts,
                "elapsed_seconds": round(time.perf_counter() - started, 3),
                "proposal_sha256": hashlib.sha256(proposals_path.read_bytes()).hexdigest(),
            },
        )
        return f"Spatial-CV produced {spatial_cv_count} independently reviewed proposals."

    return StructuredTool.from_function(
        func=run_agent,
        name="spatial_cv_transfer_tool",
        description=(
            f"Generate exactly {spatial_cv_count} likely spatial analyses through sequential "
            "draft, critic, and revision cycles. Writes "
            "hypotheses/draft_proposals.json plus an audited "
            "hypotheses/spatial_cv_proposals.json copy."
        ),
    )


def build_ta_roster(
    public: PublicContext,
    outputs: Path,
    proposal_count: int,
    include_spatial_cv: bool,
    overview: str,
    model_id: str,
) -> list:
    """Build the native TA roster; TA+CV adds exactly one optional specialist."""
    from agents.agent_defns import CustomAgent, ReActAgent, WorkerModelCtor
    from agents.agent_registry.hypothesis_agent.model import create_hypothesis_agent

    roster = [
        CustomAgent(
            id="hypothesis",
            name="Hypothesis Agent",
            description=(
                f"General-purpose drafting and final synthesis for exactly {proposal_count} "
                "likely spatial paper analyses. Writes hypotheses/draft_proposals.json or "
                "hypotheses/final_proposals.json; does not write critiques."
            ),
            ctor=create_hypothesis_agent,
        ),
        ReActAgent(
            id="critic",
            name="Critic Agent",
            description=(
                "Review-only critic for candidate spatial paper analyses. Writes only "
                "hypotheses/critique.json and never writes draft or final proposals."
            ),
            prompt=lambda _state: build_critic_prompt(public, outputs, proposal_count),
            tools=build_critic_tools(outputs),
            model_ctor=WorkerModelCtor,
        ),
    ]
    if include_spatial_cv:
        roster.append(
            CustomAgent(
                id="spatial_cv",
                name="Spatial-CV Planning Agent",
                description=(
                    f"Specialized spatial-paper drafting for exactly {proposal_count} likely "
                    "analyses using independent draft, critic, and revision cycles. Writes the "
                    "standard "
                    "hypotheses/draft_proposals.json plus an audited "
                    "hypotheses/spatial_cv_proposals.json copy; does not write the final synthesis."
                ),
                ctor=create_spatial_cv_agent,
            )
        )
    return roster


def _patch_workspace(root: Path) -> None:
    """Redirect process-global mutable TissueAgent paths to one worker root."""
    import config

    root = root.resolve()
    data_dir = root / "workspace"
    config.DATA_DIR = data_dir
    config.NOTEBOOK_DIR = data_dir / "notebook"
    config.LIBRARY_DIR = data_dir / "library"
    config.DATASET_DIR = config.LIBRARY_DIR / "datasets"
    config.LIBRARY_FILES_DIR = config.LIBRARY_DIR / "files"
    config.ACTIVE_PROJECT_DIR = data_dir / "project"
    config.UPLOADS_DIR = config.LIBRARY_FILES_DIR
    config.PDF_UPLOADS_DIR = config.LIBRARY_FILES_DIR
    config.PROJECTS_DIR = root / "projects"
    config.PLAN_SCRATCH_DIR = root / "plan_scratch"
    for path in (
        config.NOTEBOOK_DIR,
        config.DATASET_DIR,
        config.LIBRARY_FILES_DIR,
        config.ACTIVE_PROJECT_DIR / "outputs",
        config.ACTIVE_PROJECT_DIR / "uploads",
        config.PLAN_SCRATCH_DIR,
        config.PROJECTS_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)
    (config.ACTIVE_PROJECT_DIR / ".project_id").write_text(
        "spatial-cellbench-worker\n",
        encoding="utf-8",
    )


def _collect_ai_usage(states: list[dict]) -> list[dict]:
    seen = set()
    records = []
    for state in states:
        for message in state.get("messages", []):
            if getattr(message, "type", "") != "ai":
                continue
            key = getattr(message, "id", None) or id(message)
            if key in seen:
                continue
            seen.add(key)
            usage = getattr(message, "usage_metadata", None) or {}
            records.append(
                {
                    "name": getattr(message, "name", None),
                    "input_tokens": usage.get("input_tokens"),
                    "output_tokens": usage.get("output_tokens"),
                    "total_tokens": usage.get("total_tokens"),
                }
            )
    return records


def _read_exposure_records(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _agent_tool_call_records(state: dict, agent_name: str) -> list[dict]:
    records = []
    for message in state.get("messages", []):
        if getattr(message, "name", None) != agent_name:
            continue
        for tool_call in getattr(message, "tool_calls", []) or []:
            name = tool_call.get("name") if isinstance(tool_call, dict) else None
            if name:
                args = tool_call.get("args", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}
                records.append({"name": name, "args": args if isinstance(args, dict) else {}})
    return records


def _agent_tool_calls(state: dict, agent_name: str) -> list[str]:
    return [record["name"] for record in _agent_tool_call_records(state, agent_name)]


def _normalize_output_path(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    parts = Path(value.strip()).parts
    for index in range(len(parts) - 1):
        if parts[index : index + 2] == ("project", "outputs"):
            return Path(*parts[index + 2 :]).as_posix()
    if parts[:1] == ("outputs",):
        return Path(*parts[1:]).as_posix()
    return Path(*parts).as_posix()


def _manager_write_records(state: dict) -> list[dict]:
    records = []
    for tool_call in _agent_tool_call_records(state, "manager_agent"):
        if tool_call["name"] != "write":
            continue
        args = tool_call["args"]
        relative_path = _normalize_output_path(args.get("file_path"))
        contents = args.get("contents", args.get("content"))
        payload_sha256 = None
        if isinstance(contents, str):
            try:
                payload_sha256 = _semantic_json_sha256(json.loads(contents))
            except json.JSONDecodeError:
                pass
        records.append(
            {
                "relative_path": relative_path,
                "payload_sha256": payload_sha256,
            }
        )
    return records


def _matching_write_author_candidates(
    relative_path: str,
    payload: object,
    hypothesis_writes: list[dict],
    critic_writes: list[dict],
    manager_writes: list[dict],
) -> list[str]:
    payload_sha256 = _semantic_json_sha256(payload)
    candidates = []
    for agent_name, records in (
        ("hypothesis_agent", hypothesis_writes),
        ("critic_agent", critic_writes),
        ("manager_agent", manager_writes),
    ):
        if any(
            record.get("relative_path") == relative_path
            and record.get("payload_sha256") == payload_sha256
            for record in records
        ):
            candidates.append(agent_name)
    return candidates


def _outer_agent_trace(state: dict) -> dict:
    messages = state.get("messages", [])
    sequence = [
        name
        for message in messages
        if (name := getattr(message, "name", None)) in OUTER_AGENT_ORDER
    ]
    replan_request_count = int(state.get("replan_count", 0) or 0)
    routed_replan_count = sum(
        getattr(message, "name", None) == "evaluator_agent"
        and isinstance(getattr(message, "content", None), str)
        and getattr(message, "content").strip().upper().startswith("ROUTE: REPLAN")
        for message in messages
    )
    phase_count = 1 + routed_replan_count

    def final_response_count(agent_name: str) -> int:
        return sum(
            getattr(message, "name", None) == agent_name
            and not (getattr(message, "tool_calls", []) or [])
            for message in messages
        )

    return {
        "node_sequence": sequence,
        "planner_format_retry_count": max(
            0, final_response_count("planner_agent") - phase_count
        ),
        "recruiter_format_retry_count": max(
            0, final_response_count("recruiter_agent") - phase_count
        ),
        "evaluator_replan_count": routed_replan_count,
        "evaluator_replan_request_count": replan_request_count,
    }


def _validate_outer_agent_trace(trace: dict) -> None:
    sequence = trace["node_sequence"]
    if not sequence or sequence[0] != OUTER_AGENT_ORDER[0]:
        raise RuntimeError("Native TissueAgent did not start with Planner")
    expected_index = 0
    for name in sequence:
        if name == OUTER_AGENT_ORDER[expected_index]:
            expected_index += 1
            if expected_index == len(OUTER_AGENT_ORDER):
                break
    if expected_index != len(OUTER_AGENT_ORDER) or sequence[-1] != "reporter_agent":
        raise RuntimeError("Native TissueAgent did not complete through Reporter")


def recover_ta_partial_trace(
    public: PublicContext,
    overview: str,
    model_id: str,
    orchestration_model_id: str,
    proposal_count: int,
    workspace_root: Path,
    include_spatial_cv: bool,
) -> dict | None:
    """Recover bounded integration facts from an interrupted native run."""
    from server.plan_store import PlanStore, serialize_plan

    plan_path = workspace_root / "plan_scratch" / "plan.md"
    outputs = workspace_root / "workspace" / "project" / "outputs"
    if not plan_path.is_file() and not outputs.is_dir():
        return None
    plan = PlanStore(workspace_root / "plan_scratch").read()
    assigned = [step.id for step in plan.steps if step.assigned_agent == "spatial_cv_agent"]
    valid, reason, cv_trace = _validate_spatial_cv_bundle(
        outputs,
        public,
        overview,
        model_id,
        proposal_count,
    )
    final_path = outputs / "hypotheses" / "final_proposals.json"
    final_valid = False
    if final_path.is_file():
        try:
            validate_proposal_count(
                json.loads(final_path.read_text(encoding="utf-8")),
                proposal_count,
            )
            final_valid = True
        except ValueError:
            pass
    return {
        "partial_trace": True,
        "plan": serialize_plan(plan),
        "spatial_cv_available": include_spatial_cv,
        "spatial_cv_recruited_steps": assigned,
        "spatial_cv_invoked": cv_trace is not None,
        "spatial_cv_artifact_valid": valid,
        "spatial_cv_bundle_reason": reason,
        "final_artifact_complete": final_valid,
        "worker_model_id": model_id,
        "orchestration_model_id": orchestration_model_id,
    }


def run_tissueagent(
    public: PublicContext,
    overview: str,
    model_id: str,
    orchestration_model_id: str,
    proposal_count: int,
    workspace_root: Path,
    include_spatial_cv: bool,
) -> dict:
    """Run the real outer TissueAgent graph with a restricted domain roster."""
    _validate_public(public)
    if workspace_root.exists() and any(workspace_root.iterdir()):
        raise ValueError("TissueAgent benchmark workspace must be fresh and empty")
    _patch_workspace(workspace_root)
    register_benchmark_models()

    import config
    import models
    from graph.graph import create_tissueagent_graph
    from graph.ui_events import register_ui_event_queue
    from langchain_core.messages import HumanMessage
    from server.plan_store import plan_store, serialize_plan
    from server.rate_limit import with_header_retry
    from server.usage_tracker import usage_tracker

    models.set_selection(orchestration_model_id, model_id)
    plan_store.reset()
    usage_tracker.reset()
    outputs = config.active_project_outputs()
    _atomic_write_json(outputs / "briefs" / "public_context.json", public.model_dump())
    roster = build_ta_roster(
        public,
        outputs,
        proposal_count,
        include_spatial_cv,
        overview,
        model_id,
    )
    audit_path = outputs / "audit" / "hypothesis_prompt_exposure.jsonl"
    write_audit_path = outputs / "audit" / "hypothesis_validated_writes.jsonl"
    hypothesis_prompt = lambda: build_hypothesis_prompt(
        public,
        outputs,
        proposal_count,
        audit_path,
    )
    task = build_ta_task(public, proposal_count, require_spatial_cv=include_spatial_cv)

    from agents.recruiter_agent import prompt as recruiter_prompt

    empty_skills = workspace_root / "empty_skills"
    empty_skills.mkdir(parents=True, exist_ok=True)
    recruiter_prompt._SKILL_REGISTRY = empty_skills
    recruiter_prompt._SKILL_CACHE = None

    def validate_hypothesis_artifact(relative_path: str, payload: object) -> None:
        allowed = {
            "hypotheses/draft_proposals.json",
            "hypotheses/final_proposals.json",
        }
        if relative_path not in allowed:
            raise ValueError("Hypothesis must write the requested draft or final proposal path")
        validate_proposal_count(payload, proposal_count)
        write_audit_path.parent.mkdir(parents=True, exist_ok=True)
        with write_audit_path.open("a", encoding="utf-8") as stream:
            stream.write(
                json.dumps(
                    {
                        "at": datetime.now(timezone.utc).isoformat(),
                        "relative_path": relative_path,
                        "payload_sha256": _semantic_json_sha256(payload),
                    },
                    sort_keys=True,
                )
                + "\n"
            )

    state_queue = Queue()
    register_ui_event_queue(Queue())
    graph = create_tissueagent_graph(
        state_queue,
        lambda model: with_header_retry(model, max_attempts=6),
        domain_agents=roster,
        prompt_override=hypothesis_prompt,
        sandbox_root=outputs,
        artifact_validator=validate_hypothesis_artifact,
        stop_after_write=True,
        spatial_cv_public=public,
        spatial_cv_overview=overview,
        spatial_cv_model_id=model_id,
        spatial_cv_outputs=outputs,
        spatial_cv_count=proposal_count,
    ).compile()
    started = time.perf_counter()
    result = graph.invoke(
        {"messages": [HumanMessage(content=task)]},
        {"recursion_limit": config.RECURSION_LIMIT},
    )
    elapsed = time.perf_counter() - started
    outer_graph_trace = _outer_agent_trace(result)
    _validate_outer_agent_trace(outer_graph_trace)
    manager_tool_calls = _agent_tool_calls(result, "manager_agent")
    manager_writes = _manager_write_records(result)

    final_path = outputs / "hypotheses" / "final_proposals.json"
    if not final_path.is_file():
        raise RuntimeError("TissueAgent did not produce hypotheses/final_proposals.json")
    proposals = validate_proposal_count(
        json.loads(final_path.read_text(encoding="utf-8")),
        proposal_count,
    )
    states = [result]
    while True:
        try:
            queued = state_queue.get_nowait()
        except Empty:
            break
        if isinstance(queued, tuple) and len(queued) >= 2 and isinstance(queued[1], dict):
            states.append(queued[1])

    plan = plan_store.read()
    if any(step.skills for step in plan.steps):
        raise RuntimeError("Benchmark plan unexpectedly assigned external skills")
    unassigned = [step.id for step in plan.steps if not step.assigned_agent]
    allowed_expected = {
        "project/outputs/hypotheses/draft_proposals.json",
        "project/outputs/hypotheses/final_proposals.json",
        "project/outputs/hypotheses/critique.json",
    }
    if include_spatial_cv:
        allowed_expected.add("project/outputs/hypotheses/spatial_cv_proposals.json")
    unexpected_expected = sorted(
        {
            path
            for step in plan.steps
            for path in step.expected_artifacts
            if path not in allowed_expected
        }
    )
    artifact_owners = {
        "project/outputs/hypotheses/draft_proposals.json": {"hypothesis_agent"},
        "project/outputs/hypotheses/final_proposals.json": {"hypothesis_agent"},
        "project/outputs/hypotheses/critique.json": {"critic_agent"},
        "project/outputs/hypotheses/spatial_cv_proposals.json": {"spatial_cv_agent"},
    }
    if include_spatial_cv:
        artifact_owners["project/outputs/hypotheses/draft_proposals.json"].add(
            "spatial_cv_agent"
        )
    wrong_owners = [
        (step.id, path, step.assigned_agent, sorted(artifact_owners[path]))
        for step in plan.steps
        for path in step.expected_artifacts
        if path in artifact_owners and step.assigned_agent not in artifact_owners[path]
    ]
    manager_dispatched_all_steps = bool(plan.steps) and plan.current_step_id > max(
        step.id for step in plan.steps
    )
    manager_nonfinal_steps_complete = all(
        step.status == "done" for step in plan.steps[:-1]
    )
    manager_final_step_started = bool(plan.steps) and plan.steps[-1].status in {
        "running",
        "done",
    }
    assigned = [step.id for step in plan.steps if step.assigned_agent == "spatial_cv_agent"]
    valid_cv, cv_reason, cv_trace = _validate_spatial_cv_bundle(
        outputs,
        public,
        overview,
        model_id,
        proposal_count,
    )
    if not include_spatial_cv and (assigned or cv_reason != "absent"):
        raise RuntimeError("TA workspace was contaminated by Spatial-CV state")
    if include_spatial_cv and assigned != [1]:
        raise RuntimeError("TA+CV must recruit Spatial-CV exactly once for draft step 1")
    if cv_trace is not None and not assigned:
        raise RuntimeError("Spatial-CV executed without a Recruiter assignment")
    if assigned and not valid_cv:
        raise RuntimeError(f"Recruited Spatial-CV did not produce a valid bundle: {cv_reason}")
    exposures = _read_exposure_records(audit_path)
    validated_writes = _read_exposure_records(write_audit_path)
    critique_writes = _read_exposure_records(
        outputs / "audit" / "critic_validated_writes.jsonl"
    )
    final_writes = [
        record
        for record in validated_writes
        if record.get("relative_path") == "hypotheses/final_proposals.json"
    ]
    final_authors = _matching_write_author_candidates(
        "hypotheses/final_proposals.json",
        proposals.model_dump(),
        validated_writes,
        critique_writes,
        manager_writes,
    )
    if not final_authors:
        raise RuntimeError("Final artifact does not match an audited native-agent write")
    draft_path = outputs / "hypotheses" / "draft_proposals.json"
    draft_writes = [
        record
        for record in validated_writes
        if record.get("relative_path") == "hypotheses/draft_proposals.json"
    ]
    artifact_author_candidates = {
        "hypotheses/final_proposals.json": final_authors,
    }
    intermediate_artifact_validity = {}
    if draft_path.is_file():
        draft_payload = json.loads(draft_path.read_text(encoding="utf-8"))
        try:
            validate_proposal_count(draft_payload, proposal_count)
            intermediate_artifact_validity["hypotheses/draft_proposals.json"] = True
        except ValueError:
            intermediate_artifact_validity["hypotheses/draft_proposals.json"] = False
        draft_authors = _matching_write_author_candidates(
            "hypotheses/draft_proposals.json",
            draft_payload,
            validated_writes,
            critique_writes,
            manager_writes,
        )
        artifact_author_candidates["hypotheses/draft_proposals.json"] = draft_authors
    critique_path = outputs / "hypotheses" / "critique.json"
    if critique_path.is_file():
        critique_payload = json.loads(critique_path.read_text(encoding="utf-8"))
        intermediate_artifact_validity["hypotheses/critique.json"] = isinstance(
            critique_payload, (dict, list)
        )
        critique_authors = _matching_write_author_candidates(
            "hypotheses/critique.json",
            critique_payload,
            validated_writes,
            critique_writes,
            manager_writes,
        )
        artifact_author_candidates["hypotheses/critique.json"] = critique_authors
    exposure_sets = [record.get("artifact_keys", []) for record in exposures]
    cv_exposed = any(
        "hypotheses/spatial_cv_proposals.json" in paths for paths in exposure_sets
    )
    if include_spatial_cv and not cv_exposed:
        raise RuntimeError("TA+CV final synthesis did not receive the recruited CV artifact")
    model_spec = models.get_model_spec(model_id)
    orchestration_model_spec = models.get_model_spec(orchestration_model_id)
    return {
        "proposals": proposals.model_dump(),
        "trace": {
            "native_tissueagent_graph": True,
            "outer_graph": outer_graph_trace,
            "task_sha256": _sha256_text(task),
            "context_sha256": public.context_sha256,
            "proposal_count": proposal_count,
            "model": {
                "id": model_spec.id,
                "provider": model_spec.provider,
                "api_model": model_spec.api_model,
                "reasoning_effort": model_spec.reasoning_effort,
            },
            "orchestration_model": {
                "id": orchestration_model_spec.id,
                "provider": orchestration_model_spec.provider,
                "api_model": orchestration_model_spec.api_model,
                "reasoning_effort": orchestration_model_spec.reasoning_effort,
            },
            "roster": [agent.id for agent in roster],
            "plan": serialize_plan(plan),
            "final_artifact_complete": True,
            "plan_template_names": list(plan.provenance.template_names),
            "plan_step_count_compliant": 1 <= len(plan.steps) <= 3,
            "plan_unassigned_steps": unassigned,
            "plan_unexpected_artifacts": unexpected_expected,
            "plan_artifact_assignment_mismatches": wrong_owners,
            "manager_dispatched_all_steps": manager_dispatched_all_steps,
            "manager_nonfinal_steps_complete": manager_nonfinal_steps_complete,
            "manager_final_step_started": manager_final_step_started,
            "manager_acknowledged": all(step.status == "done" for step in plan.steps),
            "manager_tool_calls": manager_tool_calls,
            "manager_write_count": len(manager_writes),
            "manager_write_paths": [
                record["relative_path"] for record in manager_writes
            ],
            "artifact_author_candidates": artifact_author_candidates,
            "intermediate_artifact_validity": intermediate_artifact_validity,
            "hypothesis_invoked": bool(exposures),
            "hypothesis_validated_write_count": len(validated_writes),
            "hypothesis_draft_write_count": len(draft_writes),
            "hypothesis_final_write_count": len(final_writes),
            "critic_validated_write_count": len(critique_writes),
            "spatial_cv_available": include_spatial_cv,
            "spatial_cv_recruited_steps": assigned,
            "spatial_cv_invoked": cv_trace is not None,
            "spatial_cv_execution_success": bool(
                cv_trace and cv_trace.get("status") == "success"
            ),
            "spatial_cv_artifact_valid": valid_cv,
            "spatial_cv_bundle_reason": cv_reason,
            "spatial_cv_exposed_to_hypothesis": cv_exposed,
            "hypothesis_prompt_artifact_sets": exposure_sets,
            "hypothesis_prompt_exposures": [
                {
                    "artifact_keys": record.get("artifact_keys", []),
                    "artifact_sha256": record.get("artifact_sha256", {}),
                }
                for record in exposures
            ],
            "spatial_cv_trace": cv_trace,
            "ta_ai_calls": _collect_ai_usage(states),
            "elapsed_seconds": round(elapsed, 3),
            "final_artifact_sha256": hashlib.sha256(final_path.read_bytes()).hexdigest(),
        },
    }
