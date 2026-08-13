"""Headless command-line entry point for TissueAgent.

Runs the full planner → recruiter → manager → evaluator → reporter pipeline in
**autopilot** on a single prompt, streams the agent trace to the terminal, and
prints the final answer. Copilot pauses are a web-UI concern and never apply
here (see ``graph.create_tissueagent_graph``).

Usage (from the repo root, with ``PYTHONPATH=src``)::

    python -m cli "Summarize the cell types in library/datasets/foo.h5ad"
    python -m cli --no-docker "..."          # use a local Kernel Gateway
    python -m cli --quiet "..."              # only print the final answer
    echo "long prompt" | python -m cli -     # read the prompt from stdin

After ``pip install -e .`` the ``tissueagent`` console script wraps this same
entry point.
"""

from __future__ import annotations

import argparse
import logging
import sys
import threading
import time
from pathlib import Path
from queue import Empty

# Make the app importable regardless of how the CLI was launched. The code
# lives under ``src/`` (imported as top-level modules) and the ``knowledge``
# package sits at the repo root. The server relies on being launched from the
# repo root with ``PYTHONPATH=src``; the installed console script has neither,
# so we add both roots here before importing anything app-level.
_SRC_ROOT = Path(__file__).resolve().parent
_REPO_ROOT = _SRC_ROOT.parent
for _p in (str(_SRC_ROOT), str(_REPO_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="tissueagent",
        description="Run the TissueAgent pipeline on a prompt (autopilot).",
    )
    p.add_argument(
        "prompt",
        nargs="*",
        help="The task prompt. Use '-' (or omit and pipe) to read from stdin.",
    )
    p.add_argument(
        "--no-docker",
        action="store_true",
        help="Skip the Docker sandbox; use a local Jupyter Kernel Gateway instead.",
    )
    p.add_argument(
        "--docker",
        action="store_true",
        help="Force the Docker sandbox even if it's disabled by default.",
    )
    p.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress the streaming trace; print only the final answer.",
    )
    p.add_argument(
        "--model",
        default=None,
        help="Model id to use for both roles (e.g. 'gpt-5.1'). Defaults to the configured selection.",
    )
    p.add_argument(
        "--dataset",
        action="append",
        default=[],
        metavar="PATH",
        help=(
            "Stage a reference dataset into library/datasets/ before the run; "
            "the agent can read it at 'library/datasets/<name>'. Repeatable."
        ),
    )
    p.add_argument(
        "--attach",
        action="append",
        default=[],
        metavar="PATH",
        help=(
            "Stage a per-run file into the project's uploads/ before the run; "
            "the agent can read it at 'uploads/<name>'. Repeatable."
        ),
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Emit a JSON object to stdout (answer, project_id, elapsed, artifacts) instead of plain text.",
    )
    p.add_argument(
        "--task-id",
        default=None,
        help="Benchmark task id, recorded verbatim in metrics.json (harness use).",
    )
    p.add_argument(
        "--seed",
        default=None,
        help="Seed / replicate label, recorded verbatim in metrics.json (harness use).",
    )
    p.add_argument(
        "--attempt",
        default=None,
        help=(
            "Launch counter for this (task, model, seed), recorded verbatim in "
            "metrics.json. >1 means an earlier launch produced no result — a hang, "
            "a crash, a cancelled job — so infra flakiness stays separable from "
            "model failure. The harness owns the count (harness use)."
        ),
    )
    p.add_argument(
        "--metrics-out",
        default=None,
        metavar="PATH",
        help=(
            "Also write the run's metrics.json to PATH. It is always written to "
            "the project dir; this copies it somewhere the harness can archive."
        ),
    )
    return p


def _read_prompt(args: argparse.Namespace) -> str:
    """Resolve the prompt from args or stdin."""
    parts = args.prompt
    if parts == ["-"] or not parts:
        if not sys.stdin.isatty():
            text = sys.stdin.read().strip()
            if text:
                return text
        if parts == ["-"]:
            return ""
    return " ".join(parts).strip()


def _drain_trace(
    queue,
    stop_event: threading.Event,
    quiet: bool,
    subagent_states: dict | None = None,
) -> None:
    """Pretty-print UI events as the graph runs, until stop_event is set.

    Mirrors the shape emitted by ``graph.ui_events.emit_message``: each item is
    ``("message", msg)`` or ``("subagent_message", {"agent_name", "message", ...})``.

    Also captures ``subagent_state`` events into *subagent_states* (keyed by the
    wrapping ToolMessage id, same as ``routes/chat.py:995``), so ``save_session``
    persists sub-agent transcripts — the coding agent's per-cell code and output
    above all. Without this the web UI is the only consumer of those events and
    a headless run saves ``subagent_states: {}``, leaving the executor's whole
    history in the printed stream and nowhere else.

    Capture happens **before** the quiet check: ``--quiet`` / ``--json`` suppress
    printing, not recording.
    """
    from server.utils import stringify_chat_content

    def _print_msg(msg, prefix: str) -> None:
        name = getattr(msg, "name", None) or getattr(msg, "type", "message")
        text = stringify_chat_content(getattr(msg, "content", "")).strip()
        tool_calls = getattr(msg, "tool_calls", None) or []
        header = f"{prefix}[{name}]"
        if text:
            print(f"{header} {text}", flush=True)
        for tc in tool_calls:
            print(f"{prefix}  → {tc.get('name')}({', '.join(tc.get('args', {}) or [])})", flush=True)

    while not (stop_event.is_set() and queue.empty()):
        try:
            event = queue.get(timeout=0.1)
        except Empty:
            continue
        if not (isinstance(event, tuple) and len(event) == 2):
            continue
        kind, payload = event

        if kind == "subagent_state" and subagent_states is not None:
            try:
                tool_id = payload["tool_id"]
                if tool_id not in subagent_states:
                    subagent_states[tool_id] = (
                        payload["agent_name"],
                        payload["final_state"],
                        payload.get("invocation_id"),
                    )
            except Exception as e:  # never let capture crash the run
                logging.warning("Could not capture sub-agent state: %s", e)
            continue

        if quiet:
            continue
        try:
            if kind == "subagent_message":
                agent = payload.get("agent_name", "subagent")
                _print_msg(payload.get("message"), prefix=f"  ⤷ {agent} ")
            elif kind == "message":
                _print_msg(payload, prefix="")
        except Exception as e:  # never let trace printing crash the run
            logging.debug("Trace print error: %s", e)


def _stage_files(datasets: list[str], attachments: list[str]) -> list[str]:
    """Copy --dataset / --attach files into the workspace; return ref paths.

    Datasets go to ``library/datasets/`` (read-only reference), attachments to
    the active project's ``uploads/``. Both live under DATA_DIR so the kernel
    and file tools can reach them. Returns workspace-relative paths (e.g.
    ``library/datasets/foo.h5ad``, ``uploads/bar.csv``) for the prompt.
    """
    import shutil

    from config import DATASET_DIR, ACTIVE_PROJECT_DIR, PROJECT_UPLOADS_DIRNAME

    refs: list[str] = []

    def _copy(src_str: str, dest_dir: Path, rel_prefix: str) -> None:
        src = Path(src_str).expanduser()
        if not src.is_file():
            raise FileNotFoundError(f"file not found: {src}")
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / src.name
        shutil.copy2(src, dest)
        refs.append(f"{rel_prefix}/{src.name}")

    for d in datasets:
        _copy(d, DATASET_DIR, "library/datasets")
    uploads_dir = ACTIVE_PROJECT_DIR / PROJECT_UPLOADS_DIRNAME
    for a in attachments:
        _copy(a, uploads_dir, "uploads")
    return refs


def _bootstrap(args: argparse.Namespace):
    """Set up dirs, code backend, kernel, and the compiled graph.

    Returns ``(session, code_backend)``. The caller is responsible for stopping
    the code backend when done.
    """
    import agent_settings
    from config import KERNEL_GATEWAY_URL
    from agents.agent_registry.coding_agent.sandbox import (
        ContainerManager,
        KernelClient,
        LocalKernelGateway,
    )
    from graph.ui_events import register_ui_event_queue
    from server.main import _compile_graph
    from server.session_manager import session
    from server.utils import reset_data_directories

    if args.model:
        import models as model_registry

        model_registry.set_selection(args.model, args.model)

    # Sandbox selection: --docker forces on, --no-docker forces off, else default.
    if args.docker:
        agent_settings.set_sandbox_enabled(True)
    elif args.no_docker:
        agent_settings.set_sandbox_enabled(False)

    reset_data_directories()

    # Provide a code-execution backend (mirrors server.main's lifespan).
    code_backend = None
    try:
        if agent_settings.get_sandbox_enabled():
            code_backend = ContainerManager()
        else:
            code_backend = LocalKernelGateway()
        code_backend.ensure_running()
    except Exception as e:
        code_backend = None
        logging.warning(
            "Could not start a code backend (%s). Code execution will fail "
            "until a Kernel Gateway is reachable at %s.",
            e,
            KERNEL_GATEWAY_URL,
        )

    kernel_client = KernelClient()
    register_ui_event_queue(session.ui_event_queue)
    _compile_graph(kernel_client)
    return session, code_backend


def _collect_artifacts() -> list[str]:
    """Return workspace-relative paths of files written to the project outputs."""
    from config import ACTIVE_PROJECT_DIR, PROJECT_OUTPUTS_DIRNAME

    out_dir = ACTIVE_PROJECT_DIR / PROJECT_OUTPUTS_DIRNAME
    if not out_dir.is_dir():
        return []
    return sorted(
        f"{PROJECT_OUTPUTS_DIRNAME}/{p.relative_to(out_dir)}"
        for p in out_dir.rglob("*")
        if p.is_file()
    )


def _git_commit() -> str | None:
    """Return the repo HEAD sha, or None if git isn't usable here."""
    import subprocess

    try:
        out = subprocess.run(
            ["git", "-C", str(_REPO_ROOT), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception:
        return None
    return out.stdout.strip() or None


def _model_block() -> dict:
    """Snapshot the active model selection for both roles.

    Roles are distinct knobs (``--model`` happens to set both), so they are
    recorded separately — collapsing them would silently lose the distinction.
    """
    import models as model_registry

    selection = model_registry.get_selection()
    block: dict = {}
    for role in ("orchestration", "worker"):
        model_id = selection.get(role)
        entry = {"model_id": model_id, "provider": None, "api_model": None, "reasoning_effort": None}
        try:
            spec = model_registry.get_model_spec(model_id)
            entry.update(
                provider=spec.provider,
                api_model=spec.api_model,
                reasoning_effort=spec.reasoning_effort,
            )
        except Exception:  # unknown/renamed id — keep the raw selection
            pass
        block[role] = entry
    return block


def _plan_block() -> dict:
    """Per-step status and retry counts from the plan store (Layer 2)."""
    from config import MAX_STEP_RETRIES
    from server.plan_store import plan_store

    try:
        doc = plan_store.read()
        steps = list(doc.steps)
    except Exception as e:
        logging.warning("Could not read the plan store for metrics: %s", e)
        return {"available": False}

    per_step = [
        {
            "id": s.id,
            "title": s.title,
            "assigned_agent": s.assigned_agent,
            "status": s.status,
            "retry_count": s.retry_count,
        }
        for s in steps
    ]
    status_counts: dict[str, int] = {}
    for s in steps:
        status_counts[s.status] = status_counts.get(s.status, 0) + 1
    retried = [s for s in steps if s.retry_count > 0]
    return {
        "available": True,
        "plan_status": doc.status,
        "steps_total": len(steps),
        "status_counts": status_counts,
        "steps_failed": sum(1 for s in steps if s.status == "failed"),
        "step_retries_total": sum(s.retry_count for s in steps),
        "steps_retried": len(retried),
        "step_retry_limit_hits": sum(1 for s in retried if s.retry_count >= MAX_STEP_RETRIES),
        # StepStatus spells success "done" (plan_store.py:65) — not "completed".
        "step_retry_recovered": sum(1 for s in retried if s.status == "done"),
        "steps": per_step,
    }


def _usage_block() -> dict:
    """Token/time/call totals from the live usage tracker, plus its breakdowns.

    ``usage_tracker`` is the **only** source of token data — it is not in the
    trace and is not reconstructable after the process exits.
    """
    from server.usage_tracker import usage_tracker

    data = usage_tracker.to_dict()
    agents = data.get("agents", {})
    return {
        "input_tokens": sum(a["input_tokens"] for a in agents.values()),
        "output_tokens": sum(a["output_tokens"] for a in agents.values()),
        "total_tokens": sum(a["input_tokens"] + a["output_tokens"] for a in agents.values()),
        "llm_calls": sum(a["llm_calls"] for a in agents.values()),
        "llm_time_seconds": round(sum(a["time_seconds"] for a in agents.values()), 2),
        "by_agent": agents,
        "by_step": data.get("steps", []),
    }


def _executor_block() -> dict:
    """Layer 1 — the coding agent's code-execution retries.

    Recorded live by ``executor_tracker`` from ``ExecutionResult.error``; the
    agent's own counter is reset on every success and every step, so this
    history exists nowhere else. Not reconstructable from the transcript either:
    the error flag is consumed before the message is built, leaving only
    traceback text that ``MAX_OUTPUT_CHARS`` may have truncated.
    """
    from server.executor_tracker import executor_tracker

    return executor_tracker.to_dict()


def _troubleshooting_block(executor: dict, manager: dict, plan: dict, replans: int, successful_replans: int) -> dict:
    """The three execution-control loops side by side: attempts vs. successes.

    Same vocabulary for all three so they can be compared and summed, which the
    per-layer blocks can't be — each layer counts in its own native unit
    (executions, tool calls, verdicts). Here:

    * **attempts** — times the layer was invoked to fix something.
    * **successful** — times it actually resolved the problem.
    * **limit_hits** — times the layer spent its budget instead.

    Escalation makes the layers hierarchical, not independent: a Layer-1
    exhaustion is what forces the manager to retry a step, and a Layer-2
    failure is what the evaluator replans around. Reading them together shows
    where a run's trouble actually lived.
    """
    from config import MAX_EXECUTOR_RETRIES, MAX_REPLANS, MAX_STEP_RETRIES

    layer1 = {
        "layer": 1,
        "name": "executor-self-correction",
        # An episode is one unbroken failure run — the comparable unit. The raw
        # failed-execution count is kept separately; five failures fixing one
        # bug is one debugging attempt, not five.
        "attempts": executor.get("episodes", 0),
        "successful": executor.get("recovered", 0),
        "limit_hits": executor.get("limit_hits", 0),
        "limit": MAX_EXECUTOR_RETRIES,
        "failed_executions": executor.get("failures", 0),
        "executions": executor.get("executions", 0),
        "max_consecutive": executor.get("max_consecutive", 0),
    }
    layer2 = {
        "layer": 2,
        "name": "manager-retry-step",
        # Refused calls hit the budget and re-dispatched nothing, so they are
        # not attempts to fix anything — they are the budget saying no.
        "attempts": manager.get("retry_step_dispatched", 0),
        "successful": plan.get("step_retry_recovered", 0),
        "limit_hits": plan.get("step_retry_limit_hits", 0),
        "limit": MAX_STEP_RETRIES,
        "refused": manager.get("retry_step_refused", 0),
        "steps_dispatched": manager.get("next_step_calls", 0),
        # plan.md is rewritten on a replan, zeroing per-step retry counts, so
        # `successful` is a lower bound on any run that replanned.
        "successful_is_lower_bound": bool(replans),
    }
    layer3 = {
        "layer": 3,
        "name": "evaluator-replan",
        "attempts": replans,
        "successful": successful_replans,
        "limit_hits": 1 if replans > MAX_REPLANS else 0,
        "limit": MAX_REPLANS,
    }
    layers = [layer1, layer2, layer3]
    return {
        "layers": layers,
        "totals": {
            "attempts": sum(x["attempts"] for x in layers),
            "successful": sum(x["successful"] for x in layers),
            "limit_hits": sum(x["limit_hits"] for x in layers),
            # None rather than 0.0 when nothing ever went wrong — a run that
            # never needed troubleshooting has no recovery rate, and scoring it
            # as 0% would drag every aggregate down.
            "recovery_rate": (
                round(sum(x["successful"] for x in layers) / sum(x["attempts"] for x in layers), 3)
                if sum(x["attempts"] for x in layers)
                else None
            ),
        },
    }


def _limits_block() -> dict:
    """The execution-control constants in force for this run (tuning knobs)."""
    import config as cfg

    return {
        name: getattr(cfg, name)
        for name in (
            "MAX_EXECUTOR_RETRIES",
            "EXECUTOR_RECURSION_LIMIT",
            "MAX_STEP_RETRIES",
            "MAX_REPLANS",
            "MAX_PLANNER_RETRIES",
            "MAX_RECRUITER_RETRIES",
            "RECURSION_LIMIT",
            "MAX_OUTPUT_CHARS",
        )
    }


def _msg_attr(msg, attr, default=None):
    """Read *attr* off a message that may be a BaseMessage or a plain dict."""
    if isinstance(msg, dict):
        return msg.get(attr, msg.get("data", {}).get(attr, default) if isinstance(msg.get("data"), dict) else default)
    return getattr(msg, attr, default)


def _first_line_route(msg) -> str | None:
    """Return the ROUTE verdict on a message's first line, if it has one."""
    from server.utils import stringify_chat_content

    content = stringify_chat_content(_msg_attr(msg, "content", "") or "").strip()
    if not content:
        return None
    head = content.splitlines()[0].strip().upper()
    if not head.startswith("ROUTE:"):
        return None
    return head.split(":", 1)[1].strip().split()[0] if head.split(":", 1)[1].strip() else None


# The planner's format-retry feedback is a fixed HumanMessage built in three
# branches of ``plan_output.py`` (:221, :256, :282). Code literals, not prompt
# copy, so they are stable anchors — and counting them survives the reset-to-0
# that makes ``planner_retry_count`` a lower bound.
_PLANNER_RETRY_FEEDBACK = ("Your response must", "Your ROUTE: PLAN response must")

# Written into ``response.content`` when planner retries are exhausted
# (``plan_output.py:214``) — the run is forced to DIRECT wearing a successful
# route's clothes. The message *is* committed to state, so this is dumpable.
_PLANNER_EXHAUSTED = "Planner retries exhausted:"


def _planner_block(messages: list) -> dict:
    """Route, forced-DIRECT degradation, and the true planner format-retry count."""
    from server.utils import stringify_chat_content

    routes: list[str] = []
    degraded = False
    for msg in messages:
        if _msg_attr(msg, "name", None) != "planner_agent":
            continue
        route = _first_line_route(msg)
        if route:
            routes.append(route)
        if _PLANNER_EXHAUSTED in (stringify_chat_content(_msg_attr(msg, "content", "") or "")):
            degraded = True

    retries = 0
    for msg in messages:
        if _msg_attr(msg, "name", None) is not None:
            continue  # agent messages carry a name; the feedback is a bare HumanMessage
        text = stringify_chat_content(_msg_attr(msg, "content", "") or "").lstrip()
        if text.startswith(_PLANNER_RETRY_FEEDBACK):
            retries += 1

    return {
        "route": routes[0] if routes else None,
        "routes": routes,  # one per planner turn — replans re-enter the planner
        "degraded_to_direct": degraded,
        "format_retries": retries,
    }


def _reason_texts(messages: list, max_chars: int = 2000) -> dict:
    """Raw retry / replan justifications, for the §6 post-hoc classifier.

    Free text does not aggregate — an LLM assigns the categorical code later.
    Stored raw so the enum can be revised without re-running anything.
    """
    from server.utils import stringify_chat_content

    step_retry_reasons: list[str] = []
    for msg in messages:
        for call in _msg_attr(msg, "tool_calls", None) or []:
            name = call.get("name") if isinstance(call, dict) else getattr(call, "name", None)
            if name != "retry_step":
                continue
            call_args = call.get("args") if isinstance(call, dict) else getattr(call, "args", None)
            reason = (call_args or {}).get("task_instructions", "")
            step_retry_reasons.append(str(reason)[:max_chars])

    replan_reasons = [
        stringify_chat_content(_msg_attr(msg, "content", "") or "")[:max_chars]
        for msg in messages
        if _msg_attr(msg, "name", None) == "evaluator_agent"
        and _first_line_route(msg) == "REPLAN"
    ]
    return {"step_retry_reasons": step_retry_reasons, "replan_reasons": replan_reasons}


def _manager_retries_from_messages(messages: list) -> dict:
    """Count manager ``retry_step`` / ``next_step`` dispatches from the message log.

    **Not** derivable from the plan store, which undercounts twice over: a
    replan rewrites plan.md and zeroes every ``retry_count``, and a retry
    refused at the ``MAX_STEP_RETRIES`` budget returns an error without
    incrementing anything (``manager_agent/tools.py:203-212``). The message
    history survives both, so it is the authoritative run-level count.
    """
    retry_call_ids: set[str] = set()
    next_step_calls = 0
    for msg in messages:
        for call in _msg_attr(msg, "tool_calls", None) or []:
            name = call.get("name") if isinstance(call, dict) else getattr(call, "name", None)
            call_id = call.get("id") if isinstance(call, dict) else getattr(call, "id", None)
            if name == "retry_step":
                retry_call_ids.add(call_id)
            elif name == "next_step":
                next_step_calls += 1

    # A refused retry answers with an "Error: ..." ToolMessage (budget spent, or
    # no step dispatched yet) — it consumed a manager turn but retried nothing.
    from server.utils import stringify_chat_content

    refused = 0
    for msg in messages:
        call_id = _msg_attr(msg, "tool_call_id", None)
        if call_id is None or call_id not in retry_call_ids:
            continue
        text = stringify_chat_content(_msg_attr(msg, "content", "") or "").lstrip()
        if text.startswith("Error:"):
            refused += 1

    return {
        "retry_step_calls": len(retry_call_ids),
        "retry_step_refused": refused,
        "retry_step_dispatched": len(retry_call_ids) - refused,
        "next_step_calls": next_step_calls,
    }


def _replan_outcomes(messages: list, replan_count: int) -> dict:
    """Ordered evaluator verdicts, and how many replans actually resolved things.

    A replan is **successful** iff the next evaluator verdict is a *genuine*
    ``ROUTE: REPORT`` — the blocker was cleared. Another REPLAN means it
    thrashed; the forced REPORT at the cap means it was cut off, not fixed.

    The verdict sequence undercounts by exactly one when the cap is hit: the
    evaluator's over-limit REPLAN is rewritten to REPORT in place
    (``graph.py:372-382``) *before* the message reaches state. ``replan_count``
    is authoritative, so the difference identifies that forced verdict. Any
    other mismatch means this reader is broken — flag it rather than shrug.
    """
    verdicts = [
        route
        for msg in messages
        if _msg_attr(msg, "name", None) == "evaluator_agent"
        and (route := _first_line_route(msg)) is not None
    ]
    mined_replans = sum(1 for v in verdicts if v == "REPLAN")
    # The cap-hit run: state counted a REPLAN the message log now spells REPORT.
    forced_final_report = replan_count == mined_replans + 1 and bool(verdicts) and verdicts[-1] == "REPORT"

    successful = 0
    for i, verdict in enumerate(verdicts):
        if verdict != "REPLAN":
            continue
        following = verdicts[i + 1] if i + 1 < len(verdicts) else None
        if following != "REPORT":
            continue  # thrashed into another replan, or the run ended here
        if forced_final_report and i + 1 == len(verdicts) - 1:
            continue  # cut off at the cap, not resolved
        successful += 1

    return {
        "replans_successful": successful,
        "evaluator_verdicts": verdicts,
        "forced_report_at_cap": forced_final_report,
        # 0 normally, 1 on a cap-hit run; anything else means the reader and
        # the state counter disagree and the numbers should not be trusted.
        "verdict_state_mismatch": (
            None if replan_count - mined_replans in (0, 1) else replan_count - mined_replans
        ),
    }


def _hydrate_state_from_checkpoint(session, config: dict) -> None:
    """Best-effort: refresh ``session.agent_state`` from the graph checkpointer.

    Only needed on the failure path — a successful ``invoke`` returns the final
    state directly. The graph compiles with a ``MemorySaver``
    (``server/main.py:96``), so the last committed superstep is still readable
    after a crash. A mid-node failure loses that node's own updates; the
    alternative is reporting the pre-run state, which is strictly worse.
    """
    try:
        snapshot = session.agent.get_state(config)
        values = getattr(snapshot, "values", None)
        if isinstance(values, dict) and values:
            session.agent_state = values
    except Exception as e:
        logging.warning("Could not read graph state from the checkpointer: %s", e)


def _terminal_state_for(exc: BaseException) -> str:
    """Classify how a run died: ``recursion-limit`` | ``interrupted`` | ``crashed``."""
    if isinstance(exc, KeyboardInterrupt):
        return "interrupted"
    name = type(exc).__name__
    if name == "GraphRecursionError" or "recursion limit" in str(exc).lower():
        return "recursion-limit"
    return "crashed"


def _collect_metrics(
    *,
    session,
    args: argparse.Namespace,
    prompt: str,
    answer: str,
    started_at: str,
    elapsed: float,
    terminal_state: str,
    error: str | None,
) -> dict:
    """Assemble the per-run metrics record.

    Purely a reader: everything here already exists in state, config, or the
    plan store at run end. Whatever cannot be read from state (route,
    executor-level retries, degraded-to-DIRECT) is mined from
    ``full_stdout.log`` post-hoc — see docs/benchmark-metrics-spec.md.
    """
    from datetime import datetime

    import agent_settings
    from config import MAX_REPLANS

    state = session.agent_state if isinstance(session.agent_state, dict) else {}
    replan_count = int(state.get("replan_count", 0) or 0)
    messages = list(state.get("messages", []) or [])
    planner = _planner_block(messages)
    reasons = _reason_texts(messages)
    # Computed once — the troubleshooting summary and the per-layer blocks
    # below are two views of the same numbers and must not diverge.
    executor_block = _executor_block()
    manager_block = _manager_retries_from_messages(messages)
    plan_block = _plan_block()
    replan_outcomes = _replan_outcomes(messages, replan_count)

    return {
        "schema_version": 1,
        "run": {
            "project_id": session.project_id,
            "task_id": args.task_id,
            "seed": args.seed,
            "attempt": args.attempt,
            "git_commit": _git_commit(),
            "sandbox": "docker" if agent_settings.get_sandbox_enabled() else "local-gateway",
            "started_at": started_at,
            "ended_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "wall_time_s": round(elapsed, 2),
            "prompt": prompt,
        },
        "models": _model_block(),
        "limits": _limits_block(),
        "outcome": {
            "final_answer": answer,
            "terminal_state": terminal_state,
            "error": error,
            "message_count": len(messages),
            "artifacts": _collect_artifacts(),
            # Read from the planner's own messages, not the log: `ROUTE:`
            # appears verbatim in the agents' system prompts, which the trace
            # echoes (spec §8.2). A degraded run is a failed run wearing a
            # successful route's clothes — count it as such.
            "route": planner["route"],
            "routes": planner["routes"],
            "degraded_to_direct": planner["degraded_to_direct"],
        },
        "usage": _usage_block(),
        # The three execution-control loops in one comparable shape; the
        # per-layer detail follows under "loops".
        "troubleshooting": _troubleshooting_block(
            executor_block, manager_block, plan_block, replan_count, replan_outcomes["replans_successful"]
        ),
        "loops": {
            # Layer 3 — authoritative here and *only* here: when the cap is hit
            # the evaluator's verdict is rewritten to ROUTE: REPORT before the
            # trace sees it, so the log undercounts by one on exactly the runs
            # that failed hardest (spec §5).
            "replans_triggered": replan_count,
            "replan_limit_hit": replan_count > MAX_REPLANS,
            "replan_history": list(state.get("replan_history", []) or []),
            **replan_outcomes,
            "replan_reasons": reasons["replan_reasons"],
            # Layer 1 — executor self-correction inside the coding agent.
            "executor": executor_block,
            # Layer 2 — run-level manager retries, counted from the message log
            # because the plan store's per-step counters are zeroed by a replan.
            "manager": {
                **manager_block,
                "step_retry_reasons": reasons["step_retry_reasons"],
            },
            # Validation retries — output-format failures, not task failures.
            # planner_format_retries counts the planner's retry-feedback
            # messages, which survive the reset-to-0 that leaves the state
            # counter a lower bound.
            "planner_format_retries": planner["format_retries"],
            "planner_retries_state_counter": int(state.get("planner_retry_count", 0) or 0),
            "recruiter_retries": int(state.get("recruiter_retry_count", 0) or 0),
        },
        "plan": plan_block,
    }


def _write_metrics(metrics: dict, args: argparse.Namespace) -> str | None:
    """Write metrics.json to the project dir (and --metrics-out); return its path."""
    import json

    from config import ACTIVE_PROJECT_DIR

    target = ACTIVE_PROJECT_DIR / "metrics.json"
    payload = json.dumps(metrics, ensure_ascii=False, indent=2, default=str)
    written: str | None = None
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(payload, encoding="utf-8")
        written = str(target)
    except Exception as e:
        logging.warning("Could not write metrics.json: %s", e)
    if args.metrics_out:
        try:
            extra = Path(args.metrics_out).expanduser()
            extra.parent.mkdir(parents=True, exist_ok=True)
            extra.write_text(payload, encoding="utf-8")
            written = written or str(extra)
        except Exception as e:
            logging.warning("Could not write metrics to %s: %s", args.metrics_out, e)
    return written


def run(prompt: str, args: argparse.Namespace) -> dict:
    """Run the pipeline on *prompt*; return a result dict.

    Keys: ``answer`` (str), ``project_id`` (str|None), ``elapsed`` (float),
    ``artifacts`` (list[str]), ``staged`` (list[str] of input refs).
    """
    from langchain_core.messages import HumanMessage

    from config import RECURSION_LIMIT
    from server.session_manager import session, _new_thread_id
    from server.utils import stringify_chat_content

    session, code_backend = _bootstrap(args)

    try:
        # Each CLI invocation is a fresh project: wipe the active shell (so a
        # prior run's outputs don't leak into this run's artifact list) and
        # mint a new id. Outputs land under this project dir — kernel cwd, file
        # tools, and persistence all key off it.
        try:
            from server.utils import write_active_project_id, clear_active_project_dir
            from datetime import datetime

            clear_active_project_dir()
            project_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            write_active_project_id(project_id)
            session.project_id = project_id
        except Exception as e:
            logging.warning("Could not mint a project id: %s", e)

        # The plan store lives in PLAN_SCRATCH_DIR — *outside* the project dir,
        # so clear_active_project_dir() above doesn't touch it. Without this a
        # run that never writes a plan (DIRECT / CLARIFY) inherits the previous
        # run's plan.md, and metrics.json reports another task's steps.
        try:
            from server.plan_store import plan_store

            plan_store.reset()
        except Exception as e:
            logging.warning("Could not reset the plan store: %s", e)

        # Stage --dataset / --attach files (after the project exists) and tell
        # the agent where to find them by appending a reference line.
        staged: list[str] = []
        if args.dataset or args.attach:
            try:
                staged = _stage_files(args.dataset, args.attach)
            except FileNotFoundError as e:
                raise SystemExit(f"error: {e}")
            if staged:
                listing = ", ".join(staged)
                prompt = f"{prompt}\n\n[Staged input files (readable via the read tool / code): {listing}]"

        session.thread_id = _new_thread_id()
        user_message = HumanMessage(content=prompt)
        session.agent_state["messages"] = [user_message]

        config = {
            "recursion_limit": RECURSION_LIMIT,
            "configurable": {"thread_id": session.thread_id},
        }

        # Drain the trace on a helper thread while the graph runs.
        stop_event = threading.Event()
        tracer = threading.Thread(
            target=_drain_trace,
            args=(
                session.ui_event_queue,
                stop_event,
                args.quiet or args.json,
                session.subagent_states,
            ),
            daemon=True,
        )
        tracer.start()

        # Token/time accounting starts clean for this run. The tracker is a
        # process-wide singleton, so a second run() in the same process would
        # otherwise inherit the first run's totals.
        from datetime import datetime

        from server.executor_tracker import executor_tracker
        from server.usage_tracker import usage_tracker

        usage_tracker.reset()
        executor_tracker.reset()
        started_at = datetime.now().astimezone().isoformat(timespec="seconds")

        start = time.perf_counter()
        try:
            result = session.agent.invoke(session.agent_state, config)
        except BaseException as e:
            # A crashed / recursion-limited run is exactly the kind the metrics
            # exist to find, so dump before propagating. ``invoke`` returned
            # nothing, so recover what the graph committed from the checkpointer
            # — otherwise the dump would report zero replans for a run that
            # replanned itself to death.
            elapsed = time.perf_counter() - start
            stop_event.set()
            tracer.join(timeout=2)
            _hydrate_state_from_checkpoint(session, config)
            _write_metrics(
                _collect_metrics(
                    session=session,
                    args=args,
                    prompt=prompt,
                    answer="",
                    started_at=started_at,
                    elapsed=elapsed,
                    terminal_state=_terminal_state_for(e),
                    error=f"{type(e).__name__}: {e}",
                ),
                args,
            )
            raise
        elapsed = time.perf_counter() - start

        stop_event.set()
        tracer.join(timeout=2)

        if isinstance(result, dict) and "messages" in result:
            session.agent_state = result
            final = result["messages"][-1] if result["messages"] else None
            answer = stringify_chat_content(getattr(final, "content", "")) if final else ""
        else:
            answer = ""

        # Best-effort: persist so the run shows up in the web UI's project list.
        try:
            from server.utils import save_session
            from server.plan_store import plan_store

            if session.project_id:
                save_session(
                    messages=session.agent_state.get("messages", []),
                    subagent_states=session.subagent_states,
                    uploaded_pdfs=session.uploaded_pdfs,
                    replan_count=session.agent_state.get("replan_count", 0),
                    replan_history=session.agent_state.get("replan_history", []),
                    mode="autopilot",
                    plan_markdown=plan_store.read_markdown(),
                    project_id=session.project_id,
                )
        except Exception as e:
            logging.warning("Could not persist session: %s", e)

        metrics_path = _write_metrics(
            _collect_metrics(
                session=session,
                args=args,
                prompt=prompt,
                answer=answer.strip(),
                started_at=started_at,
                elapsed=elapsed,
                terminal_state="completed",
                error=None,
            ),
            args,
        )

        if not (args.quiet or args.json):
            print(f"\n--- done in {elapsed:.1f}s ---", flush=True)

        return {
            "answer": answer.strip(),
            "project_id": session.project_id,
            "elapsed": round(elapsed, 2),
            "artifacts": _collect_artifacts(),
            "staged": staged,
            "metrics_path": metrics_path,
        }
    finally:
        if code_backend is not None:
            try:
                code_backend.stop()
            except Exception as e:
                logging.warning("Error stopping code backend: %s", e)


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)

    # Keep the default log stream on stderr so stdout carries the answer cleanly.
    # --json implies quiet logging so stdout stays pure JSON.
    logging.basicConfig(
        level=logging.WARNING if (args.quiet or args.json) else logging.INFO,
        format="%(levelname)s | %(message)s",
        stream=sys.stderr,
    )

    prompt = _read_prompt(args)
    if not prompt:
        print("error: no prompt provided (pass text, '-', or pipe via stdin)", file=sys.stderr)
        return 2

    try:
        result = run(prompt, args)
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        return 130
    except SystemExit as e:  # staging/validation errors carry a message
        print(str(e), file=sys.stderr)
        return 2

    if args.json:
        import json

        print(json.dumps(result, indent=2))
    else:
        if not args.quiet:
            print("\n=== Final Answer ===\n", end="")
        print(result["answer"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
