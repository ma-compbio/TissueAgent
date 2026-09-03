---
name: ccc_ensemble
status: enabled
description: >
  Fixed four-member spatial CCC ensemble: prep shared LR resource/base, run
  LIANA+, COMMOT, stLearn and decoupler, then aggregate to ccc_ensemble.csv.
---

## Output
- `project/outputs/ccc_ensemble.csv` with columns `ligand, receptor, liana_score, commot_score, stlearn_score, decoupler_score, liana_pct, commot_pct, stlearn_pct, decoupler_pct, ensemble_score`, sorted descending.

Draft exactly these six steps and no extra validation/reporting steps. Cross-step state is only `project/outputs/` files. Executors must run each skill's shipped script directly; do not inspect, paste, or reimplement scripts, and do not create extra verification scripts/logs.

1. **Prepare CCC inputs** — skill `ccc-data-prep`; `%run project/skills/ccc-data-prep/scripts/ccc_data_prep.py --adata <input> --cell-type <obs column> --species <human|mouse>`. Expected: `ccc_base.h5ad`, `ccc_lr_common.csv`, `logs/ccc_data_prep.json`.
2. **Run LIANA scoring** — skill `ccc-liana`. Expected: `liana_scores.csv`.
3. **Run COMMOT scoring** — skill `ccc-commot`. Expected: `commot_scores.csv`.
4. **Run stLearn scoring** — skill `ccc-stlearn`. Expected: `stlearn_scores.csv`.
5. **Run decoupler scoring** — skill `ccc-decoupler`; uses `obs['_dact']` from Step 1. Expected: `decoupler_scores.csv`.
6. **Build ensemble ranking** — skill `ccc-aggregate`; inner-join the four member outputs and use mean-of-percentile-ranks. Expected: `ccc_ensemble.csv`.

Fixed guards: all members use shared monomeric `ccc_lr_common.csv`; COMMOT/stLearn radius and decoupler k come from `logs/ccc_data_prep.json`; do not drop/add members, add p-values/evaluation metrics, reweight, or change the combiner.
