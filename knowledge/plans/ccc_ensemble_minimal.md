---
name: ccc_ensemble
status: disabled
description: >
  Cell-cell communication on spatial transcriptomics via a four-member
  ensemble: LIANA+ (expression consensus), COMMOT (spatial optimal transport),
  stLearn (spatial co-expression) and decoupler+PROGENy (downstream response).
  Combine per-LR results into a single ranked table.
---

<!--
  Deliberately minimal starting template for the knowledge-optimizer benchmark
  (benchmark/optimizer_ccc/). It shares `name: ccc_ensemble` with the full
  template so the planner index key is stable across rounds; the benchmark
  harness guarantees exactly one of the two is enabled at a time. Keep
  status: disabled outside benchmark runs.
-->

## Output
- `ccc_ensemble.csv` — one row per ligand-receptor pair, columns
  `ligand, receptor, liana_score, commot_score, stlearn_score, decoupler_score,
  liana_pct, commot_pct, stlearn_pct, decoupler_pct, ensemble_score`,
  sorted by `ensemble_score` descending.

Run the four members and aggregate their results. Relevant skills exist
(ccc-data-prep, ccc-liana, ccc-commot, ccc-stlearn, ccc-decoupler,
ccc-aggregate).
