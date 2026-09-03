"""CLI for the knowledge optimizer: ``tissueagent optimize ...``.

Dispatched from :func:`cli.main` on the literal first token ``optimize`` so
the main entry point's bare-prompt interface stays untouched.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="tissueagent optimize",
        description=(
            "Mine past TissueAgent sessions for failure modes and make small, "
            "guardrailed edits to knowledge/skills/ and knowledge/plans/."
        ),
    )
    p.add_argument(
        "--sessions",
        nargs="+",
        required=True,
        metavar="PATH",
        help="One or more session directories (projects/<id>/ or harness copies).",
    )
    p.add_argument(
        "--focus",
        required=True,
        help="Context + areas to focus on (what to optimize for, known symptoms).",
    )
    p.add_argument(
        "--propose-only",
        action="store_true",
        help="Record proposed edits as diffs in the report but leave all files untouched.",
    )
    p.add_argument(
        "--model",
        default=None,
        help="Model id override (same semantics as the main CLI's --model).",
    )
    p.add_argument(
        "--max-iterations",
        type=int,
        default=40,
        help="Hard cap on tool-loop iterations (default 40).",
    )
    p.add_argument(
        "--no-commit",
        action="store_true",
        help="Apply edits but skip the git commit (harness debugging).",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s", stream=sys.stderr)

    sessions = [Path(s).resolve() for s in args.sessions]
    missing = [s for s in sessions if not (s / ".chat.json").is_file()]
    if missing:
        for s in missing:
            print(f"error: {s} has no .chat.json — not a session directory", file=sys.stderr)
        return 2

    if args.model:
        import models as model_registry

        model_registry.set_selection(args.model, args.model)

    from optimizer.loop import run_optimizer
    from optimizer.report import commit_round, knowledge_is_dirty, write_report

    if not args.propose_only and knowledge_is_dirty():
        logging.warning(
            "knowledge/ has uncommitted changes; this round's commit will only stage "
            "the files it edits, but consider committing or stashing first."
        )

    result = run_optimizer(
        sessions,
        args.focus,
        propose_only=args.propose_only,
        max_iterations=args.max_iterations,
    )

    report_path = write_report(result, args.focus, propose_only=args.propose_only)
    print(f"report: {report_path}", file=sys.stderr)

    if result.edits and not args.propose_only and not args.no_commit:
        edited = [rec.path for rec in result.edits]
        summary = f"{len(set(edited))} knowledge file(s) updated from {len(sessions)} session(s)"
        head = commit_round(edited, report_path, summary)
        if head is None:
            print("error: edits applied but git commit failed (see log).", file=sys.stderr)
            return 1
        print(f"committed: {head}", file=sys.stderr)

    if not result.finished:
        logging.warning("loop ended without finish() — hit max iterations or model stopped.")

    n_files = len({rec.path for rec in result.edits})
    print(
        f"{'proposed' if args.propose_only else 'applied'} {len(result.edits)} edit(s) "
        f"across {n_files} file(s); optimizer cost "
        f"{result.usage['input_tokens']}+{result.usage['output_tokens']} tokens "
        f"({result.usage['llm_calls']} calls)"
    )
    return 0
