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

Draft exactly these six scripted steps; cross-step state is only the files in `project/outputs/`. Executors should run each skill's shipped script directly (do not inspect, paste, or reimplement it).

1. **Prepare CCC inputs** — skill `ccc-data-prep`; run `ccc_data_prep.py` with dataset-specific `--adata`, `--cell-type`, `--species`. Expected: `ccc_base.h5ad`, `ccc_lr_common.csv`, `logs/ccc_data_prep.json`.
2. **Run LIANA scoring** — skill `ccc-liana`. Expected: `liana_scores.csv`.
3. **Run COMMOT scoring** — skill `ccc-commot`. Expected: `commot_scores.csv`.
4. **Run stLearn scoring** — skill `ccc-stlearn`. Expected: `stlearn_scores.csv`.
5. **Run decoupler scoring** — skill `ccc-decoupler`; uses `obs['_dact']` from Step 1, not recomputed activity. Expected: `decoupler_scores.csv`.
6. **Build ensemble ranking** — skill `ccc-aggregate`; inner-join the four member outputs and use the shipped mean-of-percentile-ranks combiner. Expected: `ccc_ensemble.csv`.

Fixed-method guards: use the shared monomeric `ccc_lr_common.csv` for all members; keep native-unit spatial thresholds from the prep log (`dis_mult * median_nn`) and `knn_k`; do not drop/add members, add evaluation/p-values, reweight, or change the combiner.
