# Methods note — Retrospective hypothesis-recovery benchmark

**Purpose.** Address Reviewer #1 Comment #7 by evaluating whether TissueAgent’s
**full multi-agent graph** (and CellVoyager as baseline / optional recruit)
can recover author-reported spatial biology findings when given only a dataset
and limited background.

## Protocol

1. **Curation.** Select published ST studies with available data and clear
   biological claims. For each study, write:
   - `background.md` — tissue, technology, annotation availability, constraints;
     **author findings withheld**
   - `gold_claims.json` — 1–3 scorer-only gold claims (never staged to agents)
2. **Three-arm execution** on identical inputs (full AnnData; **no subsample**):
   - **TissueAgent alone** — `create_tissueagent_graph` / CLI-equivalent
     `session.agent.invoke` (planner → recruiter → manager → evaluator → reporter);
     recruitable pool **excludes** `cellvoyager_agent`
   - **CellVoyager alone** — `run_cellvoyager_analysis` on the same `.h5ad` + background
   - **TissueAgent + CellVoyager** — same full graph with `cellvoyager_agent` **in**
     the recruitable pool; recruiter decides whether to assign it (not hard-coded)
3. **Scoring** (report all four):
   - **Hypothesis recovery** — exact / partial / related / miss vs gold claims
   - **Expert scores** — derivable, novel, feasible, specific, falsifiable (1–10)
   - **Testability** — presence of an executable test plan supported by the data
   - **Execution success** — whether the test plan was run to statistical results

Automatic keyword/jaccard matching (`demo/score_hypothesis_recovery.py`) is for
triage; manuscript numbers should be expert-audited.

## Invalid prior runs (archived)

Runs under
`benchmark/hypothesis_recovery/_archive_shortcut_3phase_20260711/` used a
**hard-coded coding → hypothesis → coding shortcut** that bypassed planner /
recruiter / manager. Those results are **not** full TissueAgent and must not be
cited as system-level evidence.

## Reproducibility

```bash
PYTHONPATH=src python demo/run_hypothesis_recovery.py \
  --fixture farah_heart_merfish --arm tissueagent --live

PYTHONPATH=src python demo/run_hypothesis_recovery.py \
  --fixture farah_heart_merfish --arm cellvoyager --num-analyses 1 --model gpt-4o

PYTHONPATH=src python demo/run_hypothesis_recovery.py \
  --fixture farah_heart_merfish --arm tissueagent_cellvoyager --live

# Batch (three-arm, full data):
PYTHONPATH=src python demo/run_recovery_batch.py \
  --fixtures 2026_NC_Renoir,2023_NC_SpaCET,2025_NM_Spotiphy,farah_heart_merfish \
  --ta-live --ta-with-cv --cv-repeats 2 --model gpt-4o --no-docker

PYTHONPATH=src python demo/score_hypothesis_recovery.py --all --aggregate
```

**Rebuttal policy:** always use the full AnnData listed in each fixture's
`dataset_manifest.json`. Do **not** subsample cells/spots. CellVoyager timeout
is 4 hours. Full-graph runs must leave `plan.json` / `plan.md` with recruiter
assignments under the run directory.

Artifacts live under
`benchmark/hypothesis_recovery/<fixture>/runs/{tissueagent,cellvoyager,tissueagent_cellvoyager}/`.

## Fixture status (full-graph revision, 2026-07-11)

| Fixture | Dataset (FULL) | TA alone | CV alone | TA+CV (CV recruited) |
|---------|----------------|----------|----------|----------------------|
| `2026_NC_Renoir` | TNBC Visium CID44971 | `ta_20260711_070520` | ×3 | `tacv_20260711_093002` (True) |
| `2023_NC_SpaCET` | 10x Visium breast 3,798 × 36,601 | `ta_20260711_085556` | ×2 | `tacv_20260711_100905` (True) |
| `2025_NM_Spotiphy` | Xenium FAD 104,831 × 247 | `ta_20260711_131129` | ×2 | `tacv_20260711_134547` (True) |
| `farah_heart_merfish` | 228,635 × 238 MERFISH | `ta_20260711_142003` | ×2 | `tacv_20260711_150708` (True) |

All TissueAgent / TA+CV runs have `mode: full_graph` and `plan.json`. Kidney atlas remains stretch-only (KPMP controlled access).

See `results/REVISION_RESULTS.md` and `results/aggregate_scores.md`.
