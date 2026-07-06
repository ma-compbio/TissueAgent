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
from queue import Empty


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


def _drain_trace(queue, stop_event: threading.Event, quiet: bool) -> None:
    """Pretty-print UI events as the graph runs, until stop_event is set.

    Mirrors the shape emitted by ``graph.ui_events.emit_message``: each item is
    ``("message", msg)`` or ``("subagent_message", {"agent_name", "message", ...})``.
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
        if quiet:
            continue
        try:
            if isinstance(event, tuple) and len(event) == 2:
                kind, payload = event
                if kind == "subagent_message":
                    agent = payload.get("agent_name", "subagent")
                    _print_msg(payload.get("message"), prefix=f"  ⤷ {agent} ")
                elif kind == "message":
                    _print_msg(payload, prefix="")
        except Exception as e:  # never let trace printing crash the run
            logging.debug("Trace print error: %s", e)


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


def run(prompt: str, args: argparse.Namespace) -> str:
    """Run the pipeline on *prompt* and return the final answer text."""
    from langchain_core.messages import HumanMessage

    from config import RECURSION_LIMIT
    from server.session_manager import session, _new_thread_id
    from server.utils import stringify_chat_content

    session, code_backend = _bootstrap(args)

    try:
        # Mint a project so outputs land under a real project dir (kernel cwd,
        # file tools, and persistence all key off this).
        try:
            from server.utils import write_active_project_id, read_active_project_id
            from datetime import datetime

            if not read_active_project_id():
                project_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                write_active_project_id(project_id)
                session.project_id = project_id
        except Exception as e:
            logging.warning("Could not mint a project id: %s", e)

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
            args=(session.ui_event_queue, stop_event, args.quiet),
            daemon=True,
        )
        tracer.start()

        start = time.perf_counter()
        result = session.agent.invoke(session.agent_state, config)
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

        if not args.quiet:
            print(f"\n--- done in {elapsed:.1f}s ---", flush=True)
        return answer
    finally:
        if code_backend is not None:
            try:
                code_backend.stop()
            except Exception as e:
                logging.warning("Error stopping code backend: %s", e)


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)

    # Keep the default log stream on stderr so stdout carries the answer cleanly.
    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(levelname)s | %(message)s",
        stream=sys.stderr,
    )

    prompt = _read_prompt(args)
    if not prompt:
        print("error: no prompt provided (pass text, '-', or pipe via stdin)", file=sys.stderr)
        return 2

    try:
        answer = run(prompt, args)
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        return 130

    print("\n=== Final Answer ===\n" if not args.quiet else "", end="")
    print(answer.strip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
