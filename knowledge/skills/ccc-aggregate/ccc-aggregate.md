---
name: ccc-aggregate
description: Step 6 (final) of the ccc_ensemble workflow. Runs the shipped build_ensemble step, combining the four member LR-level score tables (LIANA+, COMMOT, stLearn, decoupler) into the ensemble by the mean of the four members' percentile ranks over the LR pairs scored by ALL members. Writes the final ranked ensemble table ccc_ensemble.csv.
applies_to: [coding_agent]
tags: [ccc, ligand-receptor, ensemble, consensus]
status: enable
---

# CCC — Ensemble (mean-of-percentile-ranks consensus)

## ⚠️ How to run this

This skill **ships a runnable script** — do NOT write your own aggregation and do NOT paste
code from this file. Run the shipped script in the kernel:

```python
%run project/skills/ccc-aggregate/scripts/ccc_aggregate.py
```

It reads the four member score tables plus the shared resource, ranks and combines them, and
writes `ccc_ensemble.csv`. If you need the combiner as a function instead, import it (do not
reimplement it):

```python
import sys; sys.path.insert(0, "project/skills/ccc-aggregate/scripts")
from ccc_aggregate import build_ensemble
```

The script is authoritative. The ensemble score is the **mean of the four members' percentile
ranks** (ranked *after* the inner join); do NOT change the combiner (not `min`, not weighted —
`mean` is the validated 4-member rule), drop or add a member, add p-values/FDR, or add
evaluation. If it fails, fix the inputs.

## When to use

**Step 6 (final) of the `ccc_ensemble` plan**, after [[ccc-liana]], [[ccc-commot]],
[[ccc-stlearn]] and [[ccc-decoupler]] each wrote their LR-level score table. This step ranks
and combines all four. Not a standalone method.

## Why this is simple

All four members ran on **one shared resource**, so they report the same single-gene
`(ligand, receptor)` universe and the combination is a clean inner join. Over the pairs scored
by **all** members, each member's score is converted to a percentile rank (0..1, scale-robust)
*after* the join, and the ensemble score is the **mean** of the four ranks — promoting pairs
strong across the expression (LIANA), spatial (COMMOT, stLearn) and downstream-response
(decoupler) axes. It is a descriptive consensus rank, **not** a calibrated p-value.

**On the combiner:** the earlier 2-member ensemble used a strict `min` (weakest-link). Once
decoupler is added, `min` is dominated — decoupler's lower cross-fold stability makes it the
weakest link on many pairs and `min` throws away its orthogonal signal. `mean` recovers it and
is the validated 4-member rule. Do not switch back to `min`.

## Input (data files from Steps 1–5)

- `project/outputs/liana_scores.csv`, `commot_scores.csv`, `stlearn_scores.csv`,
  `decoupler_scores.csv` — the four `ligand, receptor, <name>_score` tables.
- `project/outputs/ccc_lr_common.csv` — the shared resource universe.

## Output

- `project/outputs/ccc_ensemble.csv` — final ranked table, sorted by `ensemble_score`
  descending. Columns: `ligand, receptor, liana_score, commot_score, stlearn_score,
  decoupler_score, liana_pct, commot_pct, stlearn_pct, decoupler_pct, ensemble_score`. One row
  per LR pair scored by **all** members. `ensemble_score ∈ [0,1]` = mean of the four ranks.

## Success criteria

- `ccc_ensemble.csv` is non-empty with the columns above (empty ⇒ upstream run failure — check
  all four `*_scores.csv` share LR pairs).
- Every row has all four member scores populated (the universe is the intersection by design).
- `ligand`/`receptor` are single genes (guaranteed by the shared monomeric resource).

## What the script does

`build_ensemble(member_dfs, resource)` inner-joins the four member tables onto the shared
universe, percentile-ranks each member score *after* the join, and sets
`ensemble_score = mean` of the four ranks, sorted descending. `main()` loads the four
`*_scores.csv` plus `ccc_lr_common.csv`, aggregates, and writes `ccc_ensemble.csv`.

## Common issues

- **Ensemble empty though each member found pairs.** The members scored non-overlapping pairs
  — check all four `*_scores.csv` share `(ligand, receptor)` from the same `ccc_lr_common.csv`.
  A small intersection is a real ceiling to report, not something to work around.
- **A member contributes nothing.** COMMOT routes only pairs with spatial signal; LIANA scores
  only pairs clearing `expr_prop`. Low overlap is a genuine ceiling — report it; do not drop
  the member from the join.
- **Do not rescore or re-weight.** The mean of the four percentile ranks is the method.

## References

- Related skills: [[ccc-data-prep]], [[ccc-liana]], [[ccc-commot]], [[ccc-stlearn]],
  [[ccc-decoupler]]; parent plan `ccc_ensemble`.
