# Hypothesis-Recovery Benchmark (TissueAgent vs CellVoyager)

Retrospective hypothesis-recovery evaluation for **Reviewer #1 Comment #7**.

## Protocol

For each fixture:

1. Provide the agent with `dataset.h5ad` (or linked path) + **withheld** `background.md`.
2. **Do not** provide `gold_claims.json`, the paper PDF findings, or author claims.
3. Run **three arms** on the **same** inputs (full data, no subsample):
   - **TissueAgent alone** — full graph (planner → recruiter → manager); CV excluded from pool
   - **CellVoyager alone** — via `cellvoyager_agent` adapter
   - **TissueAgent + CellVoyager** — full graph with CV in recruitable pool (recruiter decides)
4. Score generated hypotheses against `gold_claims.json` (scorer-only).

## Layout

```
benchmark/hypothesis_recovery/<paper_id>/
  background.md
  gold_claims.json
  dataset_manifest.json
  dataset.h5ad          # or symlink; see manifest
  runs/tissueagent/<run_id>/          # must include plan.json (full graph)
  runs/cellvoyager/<run_id>/
  runs/tissueagent_cellvoyager/<run_id>/
  scores.json

_archive_shortcut_3phase_20260711/   # INVALID prior coding+hypothesis shortcut
```

## Run

```bash
# TissueAgent full graph (no CV in pool)
PYTHONPATH=src python demo/run_hypothesis_recovery.py \
  --fixture farah_heart_merfish --arm tissueagent --live

# CellVoyager arm
PYTHONPATH=src python demo/run_hypothesis_recovery.py \
  --fixture farah_heart_merfish --arm cellvoyager --num-analyses 1 --model gpt-4o

# TissueAgent + CellVoyager pool
PYTHONPATH=src python demo/run_hypothesis_recovery.py \
  --fixture farah_heart_merfish --arm tissueagent_cellvoyager --live

# Score / aggregate
PYTHONPATH=src python demo/score_hypothesis_recovery.py --all --aggregate
```

## Fixtures

| ID | Status | Notes |
|----|--------|-------|
| `farah_heart_merfish` | **done** (FULL 228,635 cells) | TA `ta_20260711_142003`; TACV `tacv_20260711_150708` (CV recruited) |
| `2026_NC_Renoir` | **done** (TNBC Visium CID44971) | TA `ta_20260711_070520`; TACV `tacv_20260711_093002` (CV recruited) |
| `2025_NM_Spotiphy` | **done** (FULL Xenium FAD 104,831 cells) | TA `ta_20260711_131129`; TACV `tacv_20260711_134547` (CV recruited) |
| `2023_NC_SpaCET` | **done** (FULL 10x Visium breast 3,798 spots) | TA `ta_20260711_085556`; TACV `tacv_20260711_100905` (CV recruited) |
| `2023_Nature_KidneyCellStateAtlas` | awaiting (stretch) | KPMP controlled access |

Scores: `results/aggregate_scores.md`. Narrative: `results/REVISION_RESULTS.md`.

## Batch (three-arm)

```bash
conda run -n tissueagent --no-capture-output env PYTHONPATH=src \
  python demo/run_recovery_batch.py \
  --fixtures 2026_NC_Renoir,2023_NC_SpaCET,2025_NM_Spotiphy,farah_heart_merfish \
  --ta-live --ta-with-cv --cv-repeats 2 --model gpt-4o --no-docker
```

**Policy:** always use the full `h5ad` listed in `dataset_manifest.json`. Do not subsample for rebuttal runs.
