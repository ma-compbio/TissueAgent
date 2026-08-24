#!/usr/bin/env python3
"""Behaviour test: does the CODING AGENT follow the ccc-liana skill on the LIANA step?

Drives the REAL coding-agent graph on a single ccc-liana step and classifies what
it actually did — used the skill's `li.mt.rank_aggregate`/`li.mt.bivariate`/
`li.rs.select_resource`, or wandered into introspection (`help`/`dir`/`__doc__`),
OmniPath, or `search_documentation`.

Based on the built-in runner in model.py: it uses the DOCKER sandbox
(`ContainerManager`) — that container is where the kernel + scanpy/liana live
(``/opt/venv``). The container bind-mounts the host workspace to ``/workspace``, so
inputs are staged into the real ``workspace/project/outputs/`` (= ``/workspace/
project/outputs/`` in the kernel). This adds the skill injection the built-in
runner omits (a running ccc-liana plan step + context_resolver).

⚠ SHARED STATE. Uses the same `plan_store` file and the sandbox container the
backend uses. Refuses to run while the backend is up (--force to override). Stop
the server first.

PREREQ: a prepped base (from test_ccc_liana_step.py --fast, in --prepped).

Usage:
    python scripts/test_ccc_liana_agent.py            # after stopping the backend
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path
from queue import Empty, Queue

_ROOT = Path(__file__).resolve().parent.parent
for _p in (str(_ROOT), str(_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _backend_running() -> bool:
    r = subprocess.run(["pgrep", "-af", "uvicorn"], capture_output=True, text=True)
    return "server.main" in r.stdout


SKILL_PATTERNS = [r"li\.mt\.rank_aggregate", r"li\.mt\.bivariate",
                  r"li\.rs\.select_resource", r"li\.ut\.spatial_neighbors"]
INTROSPECT_PATTERNS = [r"\bhelp\(", r"\.__doc__", r"\bdir\(\s*li", r"\binspect\.",
                       r"available_resources", r"getdoc"]
OFFSKILL_PATTERNS = [r"omnipath", r"import_intercell_network", r"decoupler",
                     r"\bop\.interactions"]


def _classify(code: str) -> set[str]:
    tags = set()
    if any(re.search(p, code) for p in SKILL_PATTERNS):
        tags.add("skill")
    if any(re.search(p, code, re.I) for p in INTROSPECT_PATTERNS):
        tags.add("introspect")
    if any(re.search(p, code, re.I) for p in OFFSKILL_PATTERNS):
        tags.add("offskill")
    return tags


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--prepped", default="/tmp/ccc_liana_test",
                   help="dir with prepped ccc_base.h5ad (from test_ccc_liana_step.py)")
    p.add_argument("--force", action="store_true", help="run even if backend is up (unsafe)")
    p.add_argument("--keep-container", action="store_true",
                   help="don't stop the sandbox container at the end")
    args = p.parse_args()

    if _backend_running() and not args.force:
        sys.exit("REFUSING: backend server is running (shares plan_store + the sandbox "
                 "container). Stop it first, then re-run. Use --force to override.")

    prepped = Path(args.prepped).resolve()
    for f in ("ccc_base.h5ad", "ccc_lr_common.csv", "logs/ccc_data_prep.json"):
        if not (prepped / f).exists():
            sys.exit(f"Missing {prepped/f} — run: python scripts/test_ccc_liana_step.py --fast")

    # Stage into the REAL workspace (bind-mounted into the container as /workspace).
    from config import active_project_outputs

    out = active_project_outputs()                       # workspace/project/outputs
    for sub in ("adata", "tables", "logs"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    shutil.copy(prepped / "ccc_base.h5ad", out / "adata" / "ccc_base.h5ad")
    shutil.copy(prepped / "ccc_lr_common.csv", out / "tables" / "ccc_lr_common.csv")
    shutil.copy(prepped / "logs" / "ccc_data_prep.json", out / "logs" / "ccc_data_prep.json")
    for stale in ("tables/liana_ccc.csv", "tables/liana_universe.csv", "logs/ccc_liana.json"):
        (out / stale).unlink(missing_ok=True)
    print(f"staged inputs under {out}")

    from graph.node_factories import StepContext
    from graph.ui_events import register_ui_event_queue
    from agents.agent_registry.coding_agent.model import create_coding_agent
    from agents.agent_registry.coding_agent.sandbox import ContainerManager, KernelClient

    # Inline skill context — no plan_store write, so nothing shared with a live
    # session's plan state. This is exactly what the resolver would return for a
    # running ccc-liana step.
    def resolver(_agent_id: str) -> StepContext:
        return StepContext(step_id=2, skills=["ccc-liana"], expected_artifacts=[])

    print("starting Docker sandbox (ContainerManager)...")
    cm = ContainerManager()
    cm.ensure_running()
    client = KernelClient()
    register_ui_event_queue(Queue())

    state_queue: Queue = Queue()
    tool = create_coding_agent(state_queue, client, context_resolver=resolver)

    task = (
        "Run the LIANA+ cell-cell communication analysis for the CCC ensemble on the "
        "already-prepared base object, following your assigned ccc-liana skill.\n\n"
        "Inputs (workspace-relative):\n"
        "- project/outputs/adata/ccc_base.h5ad\n"
        "- project/outputs/tables/ccc_lr_common.csv\n"
        "- project/outputs/logs/ccc_data_prep.json\n\n"
        "Write outputs to:\n"
        "- project/outputs/tables/liana_ccc.csv\n"
        "- project/outputs/tables/liana_universe.csv\n"
        "- project/outputs/logs/ccc_liana.json\n\n"
        "This is a quick smoke test: use a reduced permutation count (n_perms=50)."
    )
    print("Dispatching one ccc-liana step to the real coding agent...\n")
    try:
        tool.invoke({"prompt": task})
    finally:
        if not args.keep_container:
            cm.stop()

    final_state = None
    while True:
        try:
            _, st, _ = state_queue.get_nowait()
            final_state = st
        except Empty:
            break

    msgs = (final_state or {}).get("messages", []) if isinstance(final_state, dict) else []
    py_calls, doc_tool_calls, tag_counts = [], 0, {"skill": 0, "introspect": 0, "offskill": 0}
    for m in msgs:
        for tc in (getattr(m, "tool_calls", None) or []):
            name = tc.get("name")
            if name == "search_documentation":
                doc_tool_calls += 1
            elif name == "python":
                code = (tc.get("args") or {}).get("code", "")
                py_calls.append(code)
                for t in _classify(code):
                    tag_counts[t] += 1

    produced = (out / "tables" / "liana_ccc.csv").exists()
    print("\n" + "=" * 70)
    print("AGENT BEHAVIOUR REPORT — LIANA step")
    print("=" * 70)
    print(f"python() calls:              {len(py_calls)}")
    print(f"  used skill APIs:           {tag_counts['skill']}")
    print(f"  runtime introspection:     {tag_counts['introspect']}  (help/dir/__doc__/inspect)")
    print(f"  off-skill (OmniPath/etc.): {tag_counts['offskill']}")
    print(f"search_documentation calls:  {doc_tool_calls}")
    print(f"produced liana_ccc.csv:      {produced}")
    verdict = (tag_counts["skill"] > 0 and tag_counts["introspect"] == 0
               and tag_counts["offskill"] == 0 and doc_tool_calls == 0 and produced)
    print("-" * 70)
    print("VERDICT:", "PASS — followed the skill, no doc-hunting."
          if verdict else "FAIL — see the code blocks below.")
    if not verdict:
        for i, code in enumerate(py_calls):
            tags = _classify(code)
            if tags & {"introspect", "offskill"} or i < 3:
                print(f"\n--- python call #{i} {sorted(tags)} ---\n{code[:700]}")
    sys.exit(0 if verdict else 1)


if __name__ == "__main__":
    main()
