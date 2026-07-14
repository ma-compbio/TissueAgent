#!/usr/bin/env python3
"""Hypothesis-recovery benchmark runner (TissueAgent full graph vs CellVoyager).

Arms:
  - tissueagent: FULL planner→recruiter→manager graph (CellVoyager excluded from pool)
  - cellvoyager: CellVoyager alone (upstream CLI)
  - tissueagent_cellvoyager: FULL graph with CellVoyager in recruitable pool

Withheld-background protocol for Reviewer #1 Comment #7:
  - Agents see dataset + background.md only
  - gold_claims.json is never staged into the agent workspace

Usage (from repo root)::

    PYTHONPATH=src python demo/run_hypothesis_recovery.py \\
      --fixture farah_heart_merfish --arm tissueagent --live

    PYTHONPATH=src python demo/run_hypothesis_recovery.py \\
      --fixture farah_heart_merfish --arm cellvoyager --num-analyses 1 --model gpt-4o

    PYTHONPATH=src python demo/run_hypothesis_recovery.py \\
      --fixture farah_heart_merfish --arm tissueagent_cellvoyager --live
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_SRC = _REPO / "src"
for _p in (str(_SRC), str(_REPO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

BENCHMARK_ROOT = _REPO / "benchmark" / "hypothesis_recovery"
EXISTING_TA = {
    "farah_heart_merfish": {
        "exploration_log.md": _REPO / "data" / "hypotheses" / "exploration_log.md",
        "hypotheses_draft.json": _REPO / "data" / "hypotheses" / "hypotheses_draft.json",
        "hypotheses.json": _REPO / "data" / "hypotheses" / "hypotheses.json",
        "hypothesis_brief.md": _REPO / "data" / "hypotheses" / "hypothesis_brief.md",
        "test_results_phase3.json": _REPO / "data" / "hypotheses" / "test_results_phase3.json",
        "background.md": _REPO / "data" / "briefs" / "background.md",
    }
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("hypothesis_recovery")


def _load_dotenv() -> None:
    env_path = _REPO / ".env"
    if not env_path.is_file():
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(env_path)
    except ImportError:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _fixture_dir(fixture_id: str) -> Path:
    d = BENCHMARK_ROOT / fixture_id
    if not d.is_dir():
        raise FileNotFoundError(f"Unknown fixture: {fixture_id} ({d})")
    return d


def _resolve_h5ad(fixture_dir: Path) -> Path:
    manifest = json.loads((fixture_dir / "dataset_manifest.json").read_text(encoding="utf-8"))
    candidates: list[Path] = []
    if manifest.get("h5ad_path"):
        candidates.append(_REPO / manifest["h5ad_path"])
    for alt in manifest.get("alternate_paths") or []:
        candidates.append(_REPO / alt)
    local = fixture_dir / "dataset.h5ad"
    if local.is_file() or local.is_symlink():
        candidates.insert(0, local)
    for c in candidates:
        if c.is_file():
            return c.resolve()
    status = manifest.get("status", "unknown")
    raise FileNotFoundError(
        f"No h5ad for {fixture_dir.name} (status={status}). "
        f"Tried: {[str(c) for c in candidates]}. See dataset_manifest.json download_hints."
    )


def _new_run_id(prefix: str) -> str:
    return f"{prefix}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"


def _write_run_meta(run_dir: Path, **meta) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        **meta,
    }
    (run_dir / "run_meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")


def seed_tissueagent(fixture_id: str) -> Path:
    """Copy prior Farah-style TissueAgent artifacts into a benchmark run folder."""
    mapping = EXISTING_TA.get(fixture_id)
    if not mapping:
        raise ValueError(
            f"--seed-existing is only available for fixtures with prior artifacts; "
            f"got {fixture_id}. Known: {sorted(EXISTING_TA)}"
        )
    fixture_dir = _fixture_dir(fixture_id)
    run_id = _new_run_id("seed")
    run_dir = fixture_dir / "runs" / "tissueagent" / run_id
    hyp_dir = run_dir / "hypotheses"
    hyp_dir.mkdir(parents=True, exist_ok=True)
    briefs = run_dir / "briefs"
    briefs.mkdir(parents=True, exist_ok=True)

    copied = []
    for name, src in mapping.items():
        if not src.is_file():
            log.warning("Missing seed file: %s", src)
            continue
        if name == "background.md":
            dest = briefs / "paper_summary.txt"
            shutil.copy2(src, dest)
            # Prefer fixture background if present
            fb = fixture_dir / "background.md"
            if fb.is_file():
                shutil.copy2(fb, dest)
        else:
            dest = hyp_dir / name
            shutil.copy2(src, dest)
        copied.append(str(dest.relative_to(run_dir)))

    _write_run_meta(
        run_dir,
        arm="tissueagent",
        mode="seed_existing",
        fixture_id=fixture_id,
        artifacts=copied,
    )
    log.info("Seeded TissueAgent run at %s", run_dir)
    return run_dir


def run_cellvoyager_arm(
    fixture_id: str,
    num_analyses: int = 1,
    max_iterations: int = 6,
    model_name: str | None = None,
) -> Path:
    from agents.agent_registry.cellvoyager_agent.runner import run_cellvoyager_analysis

    fixture_dir = _fixture_dir(fixture_id)
    h5ad = _resolve_h5ad(fixture_dir)
    background = (fixture_dir / "background.md").read_text(encoding="utf-8")
    run_id = _new_run_id("cv")
    run_dir = fixture_dir / "runs" / "cellvoyager" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    log.info("Starting CellVoyager on %s (%s)", fixture_id, h5ad)
    result = run_cellvoyager_analysis(
        h5ad_path=str(h5ad),
        background_text=background,
        analysis_name=f"recovery_{fixture_id}",
        num_analyses=num_analyses,
        max_iterations=max_iterations,
        model_name=model_name,
        request_id=run_id,
    )

    # Normalize hypotheses into a stable schema for scoring
    hypotheses = []
    for i, h in enumerate(result.get("hypotheses") or [], start=1):
        hypotheses.append(
            {
                "id": f"CV{i}",
                "statement": (h.get("header") or "").strip(),
                "code_excerpt": h.get("code_excerpt"),
                "source_notebook": h.get("source_notebook"),
                "quality_scores": {},
                "status": "PROPOSED",
            }
        )
    (run_dir / "hypotheses.json").write_text(
        json.dumps(hypotheses, indent=2) + "\n", encoding="utf-8"
    )
    (run_dir / "cellvoyager_result.json").write_text(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "request_id",
                    "run_directory",
                    "model_used",
                    "notebook_path",
                    "returncode",
                    "stdout_tail",
                    "stderr_tail",
                )
                if k in result
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    # Soft-link / copy notebook pointer
    if result.get("notebook_path"):
        nb_src = Path(result["notebook_path"])
        if nb_src.is_file():
            shutil.copy2(nb_src, run_dir / nb_src.name)

    _write_run_meta(
        run_dir,
        arm="cellvoyager",
        mode="live",
        fixture_id=fixture_id,
        h5ad=str(h5ad),
        returncode=result.get("returncode"),
        n_hypotheses=len(hypotheses),
        upstream_run_directory=result.get("run_directory"),
    )
    log.info(
        "CellVoyager finished returncode=%s n_hypotheses=%d → %s",
        result.get("returncode"),
        len(hypotheses),
        run_dir,
    )
    return run_dir


def run_tissueagent_live(
    fixture_id: str,
    no_docker: bool = True,
    *,
    allow_cellvoyager: bool = False,
) -> Path:
    """Run FULL TissueAgent graph (planner→recruiter→manager→…) on a fixture.

    Unlike the archived 3-phase shortcut, this invokes ``session.agent`` from
    ``create_tissueagent_graph``. When *allow_cellvoyager* is False, the
    recruitable pool excludes ``cellvoyager_agent`` (TA-alone ablation).
    """
    import argparse
    from dataclasses import asdict

    import agent_settings
    from agents.agent_defns import AgentDefns
    from cli import _bootstrap, _stage_files
    from config import active_project_outputs
    from langchain_core.messages import HumanMessage
    from config import RECURSION_LIMIT
    from server.plan_store import plan_store
    from server.session_manager import session, _new_thread_id
    from server.utils import (
        clear_active_project_dir,
        write_active_project_id,
        stringify_chat_content,
    )

    fixture_dir = _fixture_dir(fixture_id)
    h5ad = _resolve_h5ad(fixture_dir)
    background = (fixture_dir / "background.md").read_text(encoding="utf-8")
    arm = "tissueagent_cellvoyager" if allow_cellvoyager else "tissueagent"
    prefix = "tacv" if allow_cellvoyager else "ta"
    run_id = _new_run_id(prefix)
    run_dir = fixture_dir / "runs" / arm / run_id

    # Build recruitable pool
    if allow_cellvoyager:
        domain_agents = list(AgentDefns)
    else:
        domain_agents = [a for a in AgentDefns if a.id != "cellvoyager_agent"]

    args = argparse.Namespace(
        model=None,
        docker=not no_docker,
        no_docker=no_docker,
        quiet=False,
        json=False,
        dataset=[],
        attach=[],
    )

    # Bootstrap compiles with default AgentDefns; recompile with filtered pool.
    session_obj, code_backend = _bootstrap(args)
    from agents.agent_registry.coding_agent.sandbox import KernelClient
    from server.main import _compile_graph

    kernel_client = KernelClient()
    _compile_graph(kernel_client, domain_agents=domain_agents)

    try:
        clear_active_project_dir()
        project_id = f"recovery_{fixture_id}_{run_id}"
        write_active_project_id(project_id)
        session.project_id = project_id

        staged = _stage_files([str(h5ad)], [])
        out = active_project_outputs()
        (out / "briefs").mkdir(parents=True, exist_ok=True)
        (out / "hypotheses").mkdir(parents=True, exist_ok=True)
        (out / "tables").mkdir(parents=True, exist_ok=True)
        (out / "briefs" / "paper_summary.txt").write_text(background, encoding="utf-8")

        ds_ref = staged[0] if staged else f"library/datasets/{h5ad.name}"
        cv_clause = ""
        if allow_cellvoyager:
            cv_clause = (
                "\n- CellVoyager Agent is available in the recruitable pool. "
                "The recruiter SHOULD consider recruiting cellvoyager_agent for "
                "autonomous exploratory analysis on the same .h5ad + background, "
                "then synthesize its proposals with TissueAgent hypotheses. "
                "Do not hard-require it if another assignment is clearly better; "
                "record the rationale either way.\n"
            )
        else:
            cv_clause = (
                "\n- CellVoyager is NOT available in this run. Do not attempt to "
                "call or recruit cellvoyager_agent.\n"
            )

        prompt = f"""
WITHHELD-BACKGROUND hypothesis-recovery benchmark (Nature Methods Comment #7).

Protocol (strict):
- Author findings / gold claims / PDF paper results are WITHHELD.
- Read ONLY outputs/briefs/paper_summary.txt for tissue/technology/annotation constraints.
- Do NOT invoke PDF Reader. Do NOT search for or load gold_claims.
- Dataset path: {ds_ref} (full AnnData; do NOT subsample cells/spots for analysis/tests).

Required plan template:
- Use read_template / adapt from `hypothesis_recovery_withheld`.
- Produce exploration_log, data_inventory, hypotheses.json with quality_scores,
  test_results_phase3.json, and hypothesis_brief.md under project outputs.
{cv_clause}
Coding / plot constraints (critical for large ST):
- Prefer scanpy/numpy/pandas/scipy; do NOT pip-install.
- Use matplotlib Agg backend; NEVER call plt.show() (headless kernel will hang).
- For visualization only when n_obs > 20000, you may plot a random subset;
  all statistical tests must still use the full object.
- Keep exploration compact: inventory + a few OBSERVATIONs; avoid endless plot loops.

Goal: recover biologically grounded spatial hypotheses testable on this dataset,
then execute test plans and narrow statuses (SUPPORTED / REFINE / DROPPED).
""".strip()

        plan_store.reset()
        session.thread_id = _new_thread_id()
        session.mode = "autopilot"
        user_message = HumanMessage(content=prompt)
        session.agent_state["messages"] = [user_message]

        config = {
            "recursion_limit": max(RECURSION_LIMIT, 250),
            "configurable": {"thread_id": session.thread_id},
        }

        log.info(
            "Starting FULL TissueAgent graph arm=%s fixture=%s allow_cv=%s agents=%s",
            arm,
            fixture_id,
            allow_cellvoyager,
            [a.id for a in domain_agents],
        )
        result = session.agent.invoke(session.agent_state, config)
        if isinstance(result, dict) and "messages" in result:
            session.agent_state = result
            final = result["messages"][-1] if result["messages"] else None
            answer = (
                stringify_chat_content(getattr(final, "content", "")) if final else ""
            )
        else:
            answer = ""

        # Harvest plan + outputs
        run_dir.mkdir(parents=True, exist_ok=True)
        plan_doc = plan_store.read()
        plan_payload = {
            "status": plan_doc.status,
            "user_request": plan_doc.user_request,
            "provenance": asdict(plan_doc.provenance),
            "steps": [asdict(s) for s in plan_doc.steps],
        }
        (run_dir / "plan.json").write_text(
            json.dumps(plan_payload, indent=2) + "\n", encoding="utf-8"
        )
        (run_dir / "plan.md").write_text(plan_doc.to_markdown(), encoding="utf-8")

        recruited = sorted(
            {
                s.assigned_agent
                for s in plan_doc.steps
                if s.assigned_agent
            }
        )
        cv_recruited = any(
            (s.assigned_agent or "").startswith("cellvoyager") for s in plan_doc.steps
        )

        for sub in ("hypotheses", "briefs", "tables", "reports"):
            src = out / sub
            if src.is_dir():
                shutil.copytree(src, run_dir / sub, dirs_exist_ok=True)

        (run_dir / "final_answer.txt").write_text(answer or "", encoding="utf-8")

        _write_run_meta(
            run_dir,
            arm=arm,
            mode="full_graph",
            fixture_id=fixture_id,
            h5ad=str(h5ad),
            no_docker=no_docker,
            allow_cellvoyager=allow_cellvoyager,
            recruited_agents=recruited,
            cellvoyager_recruited=cv_recruited,
            plan_status=plan_doc.status,
            project_id=project_id,
            domain_agent_ids=[a.id for a in domain_agents],
        )
        log.info(
            "FULL TissueAgent run saved → %s (recruited=%s cv_recruited=%s)",
            run_dir,
            recruited,
            cv_recruited,
        )
        return run_dir
    finally:
        if code_backend is not None:
            try:
                code_backend.stop()
            except Exception:
                pass


def run_tissueagent_with_cv(fixture_id: str, no_docker: bool = True) -> Path:
    """Full-graph TissueAgent with CellVoyager in the recruitable pool."""
    return run_tissueagent_live(
        fixture_id, no_docker=no_docker, allow_cellvoyager=True
    )


def main(argv: list[str] | None = None) -> int:
    _load_dotenv()
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--fixture",
        required=True,
        help="Fixture id under benchmark/hypothesis_recovery/",
    )
    p.add_argument(
        "--arm",
        choices=(
            "tissueagent",
            "cellvoyager",
            "tissueagent_cellvoyager",
            "both",
            "all",
        ),
        default="both",
        help="both=TA+CV alone; all=three-arm (TA, CV, TA+CV full graph)",
    )
    p.add_argument(
        "--seed-existing",
        action="store_true",
        help="DEPRECATED archive path: copy prior prototype artifacts (Farah).",
    )
    p.add_argument(
        "--live",
        action="store_true",
        help="Run full TissueAgent graph (planner→recruiter→manager).",
    )
    p.add_argument("--num-analyses", type=int, default=1)
    p.add_argument("--max-iterations", type=int, default=6)
    p.add_argument("--model", default=None, help="Override CellVoyager model")
    p.add_argument(
        "--docker",
        action="store_true",
        help="Use Docker sandbox for TissueAgent coding agent",
    )
    args = p.parse_args(argv)

    if args.arm in ("tissueagent", "both", "all"):
        if args.seed_existing:
            log.warning(
                "--seed-existing is archived shortcut mode; prefer --live full graph"
            )
            seed_tissueagent(args.fixture)
        elif args.live:
            run_tissueagent_live(
                args.fixture, no_docker=not args.docker, allow_cellvoyager=False
            )
        else:
            log.error(
                "TissueAgent arm requires --live "
                "(full graph) or --seed-existing (archived)."
            )
            return 2

    if args.arm in ("cellvoyager", "both", "all"):
        run_cellvoyager_arm(
            args.fixture,
            num_analyses=args.num_analyses,
            max_iterations=args.max_iterations,
            model_name=args.model,
        )

    if args.arm in ("tissueagent_cellvoyager", "all"):
        run_tissueagent_with_cv(args.fixture, no_docker=not args.docker)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
