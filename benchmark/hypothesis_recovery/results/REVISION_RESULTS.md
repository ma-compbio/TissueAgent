# Hypothesis-recovery benchmark — revision results (Comment #7)

**Nature Methods rebuttal policy:** full AnnData only; **no subsample**.
TissueAgent arms must be **full graph** (`mode: full_graph` + `plan.json`).

Prior invalid 3-phase shortcut runs are archived under
`_archive_shortcut_3phase_20260711/` and must not be cited.

## Protocol

| Arm | Runner |
|-----|--------|
| TissueAgent alone | Full graph; pool **excludes** CellVoyager |
| CellVoyager alone | `run_cellvoyager_analysis` (`gpt-4o`), ≥2 repeats |
| TissueAgent + CellVoyager | Full graph; CellVoyager **in** pool; recruiter decides |

## Completeness (2026-07-11)

| Fixture | TA alone | CV alone | TA+CV |
|---------|----------|----------|-------|
| 2026_NC_Renoir | `ta_20260711_070520` (coding, critic, hypothesis; cv_recruited=False) | ×3 | `tacv_20260711_093002` (cv_recruited=True) |
| 2023_NC_SpaCET | `ta_20260711_085556` (coding, critic, hypothesis; cv_recruited=False) | ×2 | `tacv_20260711_100905` (cv_recruited=True) |
| 2025_NM_Spotiphy | `ta_20260711_131129` (coding, critic, hypothesis; cv_recruited=False) | ×2 | `tacv_20260711_134547` (cv_recruited=True) |
| farah_heart_merfish | `ta_20260711_142003` (coding, critic, hypothesis; cv_recruited=False) | ×2 | `tacv_20260711_150708` (cv_recruited=True) |

**Recruitment evidence:** on all four fixtures, the TA+CV arm authentically recruited
`cellvoyager_agent` via planner/recruiter (not hard-coded). TA-alone runs never
include CV in the pool (`allow_cellvoyager=False`).

## Aggregate (heuristic v1 — expert audit required)

From `aggregate_scores.md` (generated 2026-07-11T15:44Z):

| Fixture | System | Recovery (exact/partial) | +related | Testability | Execution | n hyp |
|---|---|---:|---:|---:|---:|---:|
| 2026_NC_Renoir | tissueagent | 0.00 | 1.00 | 1.00 | 1.00 | 4 |
| 2026_NC_Renoir | cellvoyager | 0.00 | 1.00 | 1.00 | 0.00 | 3 |
| 2026_NC_Renoir | tissueagent_cellvoyager | 0.00 | 1.00 | 1.00 | 1.00 | 3 |
| 2023_NC_SpaCET | tissueagent | 0.00 | 1.00 | 1.00 | 1.00 | 3 |
| 2023_NC_SpaCET | cellvoyager | 0.00 | 0.67 | 1.00 | 0.00 | 2 |
| 2023_NC_SpaCET | tissueagent_cellvoyager | 0.00 | 1.00 | 1.00 | 1.00 | 3 |
| 2025_NM_Spotiphy | tissueagent | 0.00 | 0.00 | 1.00 | 1.00 | 3 |
| 2025_NM_Spotiphy | cellvoyager | 0.00 | 1.00 | 1.00 | 0.00 | 2 |
| 2025_NM_Spotiphy | tissueagent_cellvoyager | 0.33 | 1.00 | 1.00 | 1.00 | 3 |
| farah_heart_merfish | tissueagent | 0.00 | 0.00 | 1.00 | 1.00 | 3 |
| farah_heart_merfish | cellvoyager | 0.00 | 0.33 | 1.00 | 0.00 | 2 |
| farah_heart_merfish | tissueagent_cellvoyager | 0.00 | 0.33 | 1.00 | 1.00 | 3 |

### Triage reading (not manuscript-ready)

- **Execution:** TA alone and TA+CV consistently `execution_success_rate=1.0` (hypotheses
  reach SUPPORTED/REFINE/DROPPED after coding tests). CV alone stays at `0.00`
  (proposals without the same status/test harness).
- **Recovery:** heuristic exact/partial is sparse; +related is often high for TA/TACV
  on Renoir/SpaCET. Spotiphy is the only fixture where TACV shows non-zero
  exact/partial (0.33) under the auto-scorer.
- **Do not quote these numbers in Response without expert audit** of recovery labels
  against `gold_claims.json`.

## Fixes applied for full-graph runs

- `create_tissueagent_graph(domain_agents=...)` ablation pool
- CellVoyager path remapping + gpt-4o fallback without Anthropic
- CV stages `hypotheses/cellvoyager_suggestions.json` + `OBSERVATION_CV`
- Full-graph `recursion_limit` ≥ 250
- Prompt: matplotlib Agg; never `plt.show()`; viz-only subsample if n_obs>20k

## Reproduce

```bash
PYTHONPATH=src python demo/run_recovery_batch.py \
  --fixtures 2026_NC_Renoir,2023_NC_SpaCET,2025_NM_Spotiphy,farah_heart_merfish \
  --ta-live --ta-with-cv --cv-repeats 2 --model gpt-4o --no-docker

PYTHONPATH=src python demo/score_hypothesis_recovery.py --all --aggregate
```
