---
name: ccc-aggregate
description: Step 4 (final) of the ccc_ensemble workflow. Combines the LIANA+ and COMMOT LR-level score tables into the ensemble via the verbatim `build_ensemble` helper — a within-method percentile-rank consensus (mean of the two percentile ranks) over the LR pairs scored by BOTH tools. Writes the final ranked ensemble table ccc_ensemble.csv.
applies_to: [coding_agent]
tags: [ccc, ligand-receptor, ensemble, consensus]
status: enable
---

# CCC — Ensemble (percentile-rank consensus)

## ⚠️ Fixed pipeline — do not deviate

This step calls `build_ensemble` from `ensemble_ccc.py` (written verbatim in
[[ccc-data-prep]]). Use the driver below **exactly**. The ensemble score is the mean of the
two tools' percentile ranks — do not change the weighting, do not add a third method, do not
add p-values/FDR, and do not add evaluation metrics. If it fails, fix the inputs, not the code.

## When to use

**Step 4 (final) of the `ccc_ensemble` plan**, after [[ccc-liana]] and [[ccc-commot]] each
wrote their LR-level score table. This step ranks and combines them. Not a standalone method.

## Why this is simple

Both tools ran on **one shared resource** (from [[ccc-data-prep]]), so both report the same
single-gene `(ligand, receptor)` universe and the combination is a clean join. Over the pairs
scored by **both** tools, each tool's score is converted to a percentile rank (0..1, robust to
scale), and the ensemble score is the mean of the two ranks — promoting pairs strong on
**both** the expression axis (LIANA) and the spatial axis (COMMOT). The result is a
descriptive consensus rank, **not** a calibrated p-value.

## Input (project working dir)

- `liana_scores.csv` — `ligand, receptor, liana_score` (from [[ccc-liana]]).
- `commot_scores.csv` — `ligand, receptor, commot_score` (from [[ccc-commot]]).
- `ccc_lr_common.csv` — the shared resource universe (from [[ccc-data-prep]]).
- `ensemble_ccc.py` — the shared library from Step 1 (must already exist).

## Output

- `ccc_ensemble.csv` — the final ranked ensemble table, sorted by `ensemble_score`
  descending. Columns: `ligand, receptor, liana_score, commot_score, liana_pct, commot_pct,
  ensemble_score`. One row per LR pair scored by **both** tools. `ensemble_score ∈ [0,1]` =
  mean of `liana_pct` and `commot_pct`; the top rows are the high-confidence ensemble calls.

## Success criteria

- `ccc_ensemble.csv` is non-empty and has the columns above (empty ⇒ a run failure upstream,
  not a null result — check that both `*_scores.csv` files have overlapping LR pairs).
- Every row has both `liana_score` and `commot_score` populated (the universe is the
  intersection — pairs only one tool scored are dropped by design).
- `ligand`/`receptor` are single genes (guaranteed by the shared monomeric resource).

## Driver — use verbatim

```python
import pandas as pd
from ensemble_ccc import build_ensemble

resource = pd.read_csv("ccc_lr_common.csv")[["ligand", "receptor"]]
liana_df = pd.read_csv("liana_scores.csv")
commot_df = pd.read_csv("commot_scores.csv")

uni = build_ensemble(liana_df, commot_df, resource)
uni = uni.sort_values("ensemble_score", ascending=False).reset_index(drop=True)
uni.to_csv("ccc_ensemble.csv", index=False)
print(f"Ensemble — {len(uni)} LR pairs scored by BOTH tools")
print(uni.head(15).to_string(index=False))
```

## Common issues

- **Ensemble empty though each tool found pairs.** The tools scored non-overlapping pairs —
  check that both `*_scores.csv` share `(ligand, receptor)` rows from the same
  `ccc_lr_common.csv`. This is an intersection by design; a small intersection is a real
  ceiling to report, not something to work around.
- **A tool contributes nothing.** COMMOT routes only pairs with spatial signal; LIANA scores
  only pairs clearing `expr_prop`. Low overlap is a genuine ceiling — report it.
- **Do not rescore or re-weight.** The percentile-rank mean is the method. Reporting should
  read straight off `ensemble_score`.

## References

- Related skills: [[ccc-data-prep]], [[ccc-liana]], [[ccc-commot]]; parent plan `ccc_ensemble`.
</content>
