#!/usr/bin/env python3
"""Score hypothesis-recovery runs against gold_claims.json.

Produces per-fixture scores.json and an aggregate revision table.

Recovery labels: exact | partial | related | miss
Expert scores: use agent-provided quality_scores when present; otherwise leave null.
Testability / execution: inferred from test_plan presence and test_results files.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
BENCHMARK_ROOT = _REPO / "benchmark" / "hypothesis_recovery"

RECOVERY_ORDER = ("exact", "partial", "related", "miss")


def _tokenize(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(t) > 2}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def match_recovery(hypothesis: dict, claim: dict) -> tuple[str, float, list[str]]:
    """Heuristic recovery match (LLM-as-judge can replace later; human audit required)."""
    h_text = " ".join(
        str(hypothesis.get(k) or "")
        for k in ("statement", "mechanism", "narrowing_notes", "header")
    )
    c_text = claim.get("statement") or ""
    h_tok = _tokenize(h_text)
    c_tok = _tokenize(c_text)

    h_lower = h_text.lower()
    kw = [k.lower() for k in (claim.get("keywords") or [])]
    kw_hits = []
    for k in kw:
        if k in h_lower or _tokenize(k) <= h_tok:
            kw_hits.append(k)
            continue
        # partial: majority of keyword tokens appear (ligand-target ≈ ligand-receptor)
        kt = _tokenize(k)
        if kt and len(kt & h_tok) / len(kt) >= 0.5:
            kw_hits.append(k)
    ct = [c.lower() for c in (claim.get("cell_types") or [])]
    ct_hits = [c for c in ct if c.lower() in h_lower]

    jac = _jaccard(h_tok, c_tok)
    kw_frac = (len(kw_hits) / len(kw)) if kw else 0.0
    ct_frac = (len(ct_hits) / len(ct)) if ct else 0.0
    score = 0.45 * jac + 0.35 * kw_frac + 0.20 * ct_frac

    if score >= 0.55 and (kw_frac >= 0.5 or ct_frac >= 0.5):
        label = "exact"
    elif score >= 0.35:
        label = "partial"
    elif score >= 0.18 or kw_hits or ct_hits:
        label = "related"
    else:
        label = "miss"
    evidence = []
    if kw_hits:
        evidence.append(f"keywords={kw_hits}")
    if ct_hits:
        evidence.append(f"cell_types={ct_hits}")
    evidence.append(f"jaccard={jac:.3f}")
    return label, score, evidence


def _load_hypotheses(run_dir: Path) -> list[dict]:
    for rel in (
        "hypotheses/hypotheses.json",
        "hypotheses.json",
    ):
        p = run_dir / rel
        if p.is_file():
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "hypotheses" in data:
                return data["hypotheses"]
    return []


def _latest_run(arm_dir: Path) -> Path | None:
    if not arm_dir.is_dir():
        return None
    runs = [p for p in arm_dir.iterdir() if p.is_dir()]
    if not runs:
        return None
    return sorted(runs, key=lambda p: p.name)[-1]


def _testability(hyp: dict) -> bool:
    plan = hyp.get("test_plan") or hyp.get("code_excerpt") or ""
    return bool(str(plan).strip())


def _execution_success(run_dir: Path, hyp: dict) -> bool | None:
    status = (hyp.get("status") or "").upper()
    # Narrowed statuses imply the test plan was executed (including falsifying DROPPED).
    if status in {"SUPPORTED", "REFINE", "DROPPED"}:
        return True
    for rel in ("hypotheses/test_results_phase3.json", "test_results_phase3.json"):
        if (run_dir / rel).is_file():
            return True
    if hyp.get("code_excerpt"):
        return None  # CellVoyager proposed code; execution not separately tracked here
    return False


def score_arm(run_dir: Path, claims: list[dict], arm: str) -> dict:
    hyps = _load_hypotheses(run_dir)
    per_hyp = []
    claim_best: dict[str, dict] = {}

    for hyp in hyps:
        best_label, best_score, best_claim, best_ev = "miss", -1.0, None, []
        for claim in claims:
            label, score, ev = match_recovery(hyp, claim)
            if score > best_score or (
                score == best_score
                and RECOVERY_ORDER.index(label) < RECOVERY_ORDER.index(best_label)
            ):
                best_label, best_score, best_claim, best_ev = label, score, claim["id"], ev
            prev = claim_best.get(claim["id"])
            if prev is None or score > prev["score"]:
                claim_best[claim["id"]] = {
                    "hypothesis_id": hyp.get("id"),
                    "label": label,
                    "score": score,
                }
        qs = hyp.get("quality_scores") or {}
        per_hyp.append(
            {
                "hypothesis_id": hyp.get("id"),
                "statement": (hyp.get("statement") or hyp.get("header") or "")[:300],
                "best_claim_id": best_claim,
                "recovery": best_label,
                "match_score": round(best_score, 4),
                "evidence": best_ev,
                "quality_scores": qs,
                "testable": _testability(hyp),
                "execution_success": _execution_success(run_dir, hyp),
                "status": hyp.get("status"),
            }
        )

    recovered = [
        c
        for c, v in claim_best.items()
        if v["label"] in {"exact", "partial"}
    ]
    related = [
        c
        for c, v in claim_best.items()
        if v["label"] == "related"
    ]

    def _mean_dim(dim: str) -> float | None:
        vals = [
            h["quality_scores"][dim]
            for h in per_hyp
            if isinstance(h.get("quality_scores"), dict)
            and isinstance(h["quality_scores"].get(dim), (int, float))
        ]
        return round(sum(vals) / len(vals), 3) if vals else None

    dims = ["derivable", "novel", "feasible", "specific", "falsifiable"]
    n = max(len(claims), 1)
    return {
        "arm": arm,
        "run_dir": str(run_dir.relative_to(_REPO)),
        "n_hypotheses": len(hyps),
        "n_gold_claims": len(claims),
        "recovery_rate_exact_or_partial": round(len(recovered) / n, 4),
        "recovery_rate_including_related": round((len(recovered) + len(related)) / n, 4),
        "claims_recovered": recovered,
        "claims_related": related,
        "claims_missed": [
            c["id"] for c in claims if c["id"] not in recovered and c["id"] not in related
        ],
        "mean_quality_scores": {d: _mean_dim(d) for d in dims},
        "testability_rate": round(
            sum(1 for h in per_hyp if h["testable"]) / max(len(per_hyp), 1), 4
        ),
        "execution_success_rate": round(
            sum(1 for h in per_hyp if h["execution_success"]) / max(len(per_hyp), 1), 4
        ),
        "per_hypothesis": per_hyp,
        "per_claim_best": claim_best,
    }


def score_fixture(fixture_id: str) -> dict:
    fixture_dir = BENCHMARK_ROOT / fixture_id
    claims = json.loads((fixture_dir / "gold_claims.json").read_text(encoding="utf-8"))[
        "claims"
    ]
    arms = {}
    for arm in ("tissueagent", "cellvoyager", "tissueagent_cellvoyager"):
        latest = _latest_run(fixture_dir / "runs" / arm)
        if latest is None:
            arms[arm] = {"arm": arm, "status": "missing_run"}
            continue
        arms[arm] = score_arm(latest, claims, arm)

    out = {
        "fixture_id": fixture_id,
        "scored_utc": datetime.now(timezone.utc).isoformat(),
        "scorer": "heuristic_v1",
        "scorer_note": (
            "Automatic keyword/jaccard matching for triage; "
            "expert audit required for manuscript numbers."
        ),
        "arms": arms,
    }
    (fixture_dir / "scores.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return out


def aggregate(results: list[dict]) -> Path:
    rows = []
    for r in results:
        for arm_name, arm in (r.get("arms") or {}).items():
            if arm.get("status") == "missing_run":
                rows.append(
                    {
                        "fixture_id": r["fixture_id"],
                        "system": arm_name,
                        "status": "missing_run",
                    }
                )
                continue
            rows.append(
                {
                    "fixture_id": r["fixture_id"],
                    "system": arm_name,
                    "status": "scored",
                    "n_hypotheses": arm.get("n_hypotheses"),
                    "recovery_rate_exact_or_partial": arm.get(
                        "recovery_rate_exact_or_partial"
                    ),
                    "recovery_rate_including_related": arm.get(
                        "recovery_rate_including_related"
                    ),
                    "testability_rate": arm.get("testability_rate"),
                    "execution_success_rate": arm.get("execution_success_rate"),
                    "mean_quality_scores": arm.get("mean_quality_scores"),
                    "claims_recovered": arm.get("claims_recovered"),
                }
            )

    out_dir = BENCHMARK_ROOT / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "aggregate_scores.json"
    json_path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")

    # Markdown table for revision
    md_lines = [
        "# Hypothesis-recovery benchmark — aggregate scores",
        "",
        f"_Generated {datetime.now(timezone.utc).isoformat()} (heuristic scorer v1; audit before manuscript)._",
        "",
        "| Fixture | System | Recovery (exact/partial) | +related | Testability | Execution | n hyp |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        if row.get("status") != "scored":
            md_lines.append(
                f"| {row['fixture_id']} | {row['system']} | — | — | — | — | — |"
            )
            continue
        md_lines.append(
            "| {fixture_id} | {system} | {r1:.2f} | {r2:.2f} | {t:.2f} | {e:.2f} | {n} |".format(
                fixture_id=row["fixture_id"],
                system=row["system"],
                r1=row["recovery_rate_exact_or_partial"] or 0,
                r2=row["recovery_rate_including_related"] or 0,
                t=row["testability_rate"] or 0,
                e=row["execution_success_rate"] or 0,
                n=row["n_hypotheses"],
            )
        )
    md_path = out_dir / "aggregate_scores.md"
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    return md_path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--fixture", action="append", default=[], help="Fixture id (repeatable)")
    p.add_argument("--all", action="store_true", help="Score all fixtures with gold_claims.json")
    p.add_argument("--aggregate", action="store_true", help="Write aggregate table")
    args = p.parse_args(argv)

    fixtures = list(args.fixture)
    if args.all or not fixtures:
        fixtures = sorted(
            d.name
            for d in BENCHMARK_ROOT.iterdir()
            if d.is_dir() and (d / "gold_claims.json").is_file()
        )

    results = []
    for fid in fixtures:
        print(f"Scoring {fid}...")
        results.append(score_fixture(fid))

    if args.aggregate or len(results) > 1 or args.all:
        path = aggregate(results)
        print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
