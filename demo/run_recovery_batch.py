#!/usr/bin/env python3
"""Batch runner for multi-paper hypothesis-recovery three-arm evaluation.

Per fixture (serial):
  1. TissueAgent full graph (CV excluded from pool) — optional
  2. CellVoyager alone × N — skip if enough existing
  3. TissueAgent full graph with CV in pool — optional

Failures are logged; the batch continues.

Usage::

    conda run -n tissueagent --no-capture-output env PYTHONPATH=src \\
      python demo/run_recovery_batch.py \\
      --fixtures 2026_NC_Renoir,2023_NC_SpaCET,2025_NM_Spotiphy,farah_heart_merfish \\
      --ta-live --ta-with-cv --cv-repeats 2 --model gpt-4o --no-docker
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_SRC = _REPO / "src"
_DEMO = Path(__file__).resolve().parent
for _p in (str(_SRC), str(_REPO), str(_DEMO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from run_hypothesis_recovery import (  # noqa: E402
    BENCHMARK_ROOT,
    _load_dotenv,
    run_cellvoyager_arm,
    run_tissueagent_live,
    run_tissueagent_with_cv,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("recovery_batch")


DEFAULT_FIXTURES = [
    "2026_NC_Renoir",
    "2023_NC_SpaCET",
    "2025_NM_Spotiphy",
    "farah_heart_merfish",
]


def _count_runs(fixture_id: str, arm: str) -> int:
    d = BENCHMARK_ROOT / fixture_id / "runs" / arm
    if not d.is_dir():
        return 0
    return sum(1 for p in d.iterdir() if p.is_dir())


def _has_full_graph_ta(fixture_id: str, arm: str = "tissueagent") -> bool:
    d = BENCHMARK_ROOT / fixture_id / "runs" / arm
    if not d.is_dir():
        return False
    for p in d.iterdir():
        if not p.is_dir():
            continue
        meta = p / "run_meta.json"
        if meta.is_file():
            try:
                m = json.loads(meta.read_text(encoding="utf-8"))
                if m.get("mode") == "full_graph":
                    return True
            except json.JSONDecodeError:
                pass
        if (p / "plan.json").is_file() and (p / "hypotheses" / "hypotheses.json").is_file():
            return True
    return False


def _score_fixture(fixture_id: str) -> None:
    from score_hypothesis_recovery import score_fixture

    score_fixture(fixture_id)
    log.info("Scored %s", fixture_id)


def run_batch(
    fixtures: list[str],
    ta_live: bool,
    ta_with_cv: bool,
    cv_repeats: int,
    model: str | None,
    num_analyses: int,
    max_iterations: int,
    no_docker: bool,
    skip_existing: bool,
) -> dict:
    batch_id = datetime.now(timezone.utc).strftime("batch_%Y%m%d_%H%M%S")
    results_dir = BENCHMARK_ROOT / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    log_path = results_dir / f"{batch_id}.jsonl"
    summary: dict = {"batch_id": batch_id, "fixtures": {}}

    for fid in fixtures:
        entry: dict = {"fixture_id": fid, "steps": []}
        log.info("==== Fixture %s ====", fid)
        try:
            manifest = json.loads(
                (BENCHMARK_ROOT / fid / "dataset_manifest.json").read_text(encoding="utf-8")
            )
            if manifest.get("status") != "ready":
                raise RuntimeError(f"dataset not ready: status={manifest.get('status')}")
        except Exception as e:
            entry["error"] = f"manifest: {e}"
            summary["fixtures"][fid] = entry
            _append_log(log_path, entry)
            log.error("Skip %s: %s", fid, e)
            continue

        # TissueAgent full graph (no CV in pool)
        if ta_live:
            if skip_existing and _has_full_graph_ta(fid, "tissueagent"):
                entry["steps"].append({"arm": "tissueagent", "status": "skipped_existing"})
                log.info("Skip TA full-graph for %s (existing)", fid)
            else:
                try:
                    run_dir = run_tissueagent_live(
                        fid, no_docker=no_docker, allow_cellvoyager=False
                    )
                    entry["steps"].append(
                        {"arm": "tissueagent", "status": "ok", "run_dir": str(run_dir)}
                    )
                except Exception as e:
                    entry["steps"].append(
                        {
                            "arm": "tissueagent",
                            "status": "failed",
                            "error": str(e),
                            "traceback": traceback.format_exc()[-2000:],
                        }
                    )
                    log.exception("TA full-graph failed for %s", fid)

        # CellVoyager alone
        existing_cv = _count_runs(fid, "cellvoyager")
        need = max(0, cv_repeats - (existing_cv if skip_existing else 0))
        if skip_existing and existing_cv >= cv_repeats:
            entry["steps"].append(
                {
                    "arm": "cellvoyager",
                    "status": "skipped_existing",
                    "n_existing": existing_cv,
                }
            )
            log.info("Skip CV for %s (%d existing >= %d)", fid, existing_cv, cv_repeats)
            need = 0
        for i in range(need):
            try:
                run_dir = run_cellvoyager_arm(
                    fid,
                    num_analyses=num_analyses,
                    max_iterations=max_iterations,
                    model_name=model,
                )
                entry["steps"].append(
                    {
                        "arm": "cellvoyager",
                        "status": "ok",
                        "repeat": i + 1,
                        "run_dir": str(run_dir),
                    }
                )
            except Exception as e:
                entry["steps"].append(
                    {
                        "arm": "cellvoyager",
                        "status": "failed",
                        "repeat": i + 1,
                        "error": str(e),
                        "traceback": traceback.format_exc()[-2000:],
                    }
                )
                log.exception("CV failed for %s repeat %d", fid, i + 1)

        # TissueAgent + CellVoyager pool
        if ta_with_cv:
            if skip_existing and _has_full_graph_ta(fid, "tissueagent_cellvoyager"):
                entry["steps"].append(
                    {"arm": "tissueagent_cellvoyager", "status": "skipped_existing"}
                )
                log.info("Skip TA+CV full-graph for %s (existing)", fid)
            else:
                try:
                    run_dir = run_tissueagent_with_cv(fid, no_docker=no_docker)
                    meta_path = run_dir / "run_meta.json"
                    cv_recruited = False
                    if meta_path.is_file():
                        cv_recruited = bool(
                            json.loads(meta_path.read_text(encoding="utf-8")).get(
                                "cellvoyager_recruited"
                            )
                        )
                    # One retry if CV was available but not recruited
                    if not cv_recruited:
                        log.warning(
                            "TA+CV run for %s did not recruit CellVoyager; retrying once",
                            fid,
                        )
                        run_dir = run_tissueagent_with_cv(fid, no_docker=no_docker)
                        if (run_dir / "run_meta.json").is_file():
                            cv_recruited = bool(
                                json.loads(
                                    (run_dir / "run_meta.json").read_text(encoding="utf-8")
                                ).get("cellvoyager_recruited")
                            )
                    entry["steps"].append(
                        {
                            "arm": "tissueagent_cellvoyager",
                            "status": "ok",
                            "run_dir": str(run_dir),
                            "cellvoyager_recruited": cv_recruited,
                        }
                    )
                except Exception as e:
                    entry["steps"].append(
                        {
                            "arm": "tissueagent_cellvoyager",
                            "status": "failed",
                            "error": str(e),
                            "traceback": traceback.format_exc()[-2000:],
                        }
                    )
                    log.exception("TA+CV full-graph failed for %s", fid)

        try:
            _score_fixture(fid)
            entry["scored"] = True
        except Exception as e:
            entry["scored"] = False
            entry["score_error"] = str(e)
            log.exception("Score failed for %s", fid)

        summary["fixtures"][fid] = entry
        _append_log(log_path, entry)

    summary_path = results_dir / f"{batch_id}_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    log.info("Batch summary → %s", summary_path)

    try:
        from score_hypothesis_recovery import aggregate, score_fixture

        results = []
        for fid in fixtures:
            try:
                results.append(score_fixture(fid))
            except Exception:
                pass
        if results:
            aggregate(results)
    except Exception:
        log.exception("Aggregate failed")

    return summary


def _append_log(path: Path, entry: dict) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def main(argv: list[str] | None = None) -> int:
    _load_dotenv()
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--fixtures",
        default=",".join(DEFAULT_FIXTURES),
        help="Comma-separated fixture ids",
    )
    p.add_argument(
        "--ta-live",
        action="store_true",
        help="Run TissueAgent full graph (CV excluded from pool)",
    )
    p.add_argument(
        "--ta-with-cv",
        action="store_true",
        help="Run TissueAgent full graph with CellVoyager in recruitable pool",
    )
    p.add_argument("--cv-repeats", type=int, default=2)
    p.add_argument("--model", default="gpt-4o")
    p.add_argument("--num-analyses", type=int, default=1)
    p.add_argument("--max-iterations", type=int, default=4)
    p.add_argument(
        "--no-docker",
        action="store_true",
        default=True,
        help="Use LocalKernelGateway for TA (default True)",
    )
    p.add_argument(
        "--docker",
        action="store_true",
        help="Force Docker sandbox for TA live",
    )
    p.add_argument(
        "--skip-existing",
        action="store_true",
        default=True,
        help="Skip arms that already meet quotas (default True)",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="Re-run even if existing runs satisfy quotas",
    )
    args = p.parse_args(argv)
    fixtures = [x.strip() for x in args.fixtures.split(",") if x.strip()]
    no_docker = not args.docker
    skip_existing = args.skip_existing and not args.force

    run_batch(
        fixtures=fixtures,
        ta_live=args.ta_live,
        ta_with_cv=args.ta_with_cv,
        cv_repeats=args.cv_repeats,
        model=args.model,
        num_analyses=args.num_analyses,
        max_iterations=args.max_iterations,
        no_docker=no_docker,
        skip_existing=skip_existing,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
