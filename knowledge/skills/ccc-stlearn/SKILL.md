---
name: ccc-stlearn
description: Step 4 of the ccc_ensemble workflow. Runs the shipped vectorised stLearn cci.lr spatial LR co-expression scorer on the shared LR resource at the same native-unit radius as COMMOT, scoring each pair by its neighbourhood co-expression strength. Writes one LR-level score table (stlearn_scores.csv) for the ensemble aggregator.
applies_to: [coding_agent]
tags: [ccc, stlearn, spatial, co-expression, ensemble]
status: enable
---

# CCC — stLearn (spatial co-expression axis)

## ⚠️ How to run this

This skill **ships a runnable script**. To save time/tokens, do **not** list/cat/read the script or this SKILL file first; do **not** write your own stLearn step or paste code. Run the shipped script in the kernel:

```python
%run project/skills/ccc-stlearn/scripts/ccc_stlearn.py
```

It reads the Step 1 artifacts, scores every pair, and writes `stlearn_scores.csv`. No
`stlearn` install is needed — the statistic is plain numpy/scipy. The script is authoritative. There is **one** radius (`dis_mult × median_nn` from the JSON
log — the same **1.5** COMMOT uses); do NOT add a second regime, call stLearn's stock
clustering/permutation tail, change the statistic, or add evaluation. If it fails, fix the
environment/inputs.

## When to use

Step 4 of the `ccc_ensemble` plan, after [[ccc-data-prep]]. stLearn is a **spatial
co-expression** member complementary to COMMOT's optimal transport: for each spot and pair
`(L, R)` it rewards a ligand spot whose neighbours express the receptor (and vice versa). A
*local co-presence* statistic on the radius graph vs COMMOT's *global transport* — the two
are ~0.84 correlated but both decorrelated from [[ccc-liana]] and [[ccc-decoupler]].

## Why the vectorised statistic (not `st.tl.cci.lr`'s loop)

The shipped script reproduces stLearn v0.2.5's exact `cci.lr` statistic —

```
s_i = 1[L_i > t] · frac_neighbours_expressing_R
    + 1[R_i > t] · frac_neighbours_expressing_L      (per spot i)
stlearn_score(pair) = sum_i s_i
```

— but with a single row-normalised radius graph instead of stLearn's per-spot Python loop.
The statistic is identical (Spearman ≈ 1.0 vs genuine `st.tl.cci.lr` on full patches), but it
is fast and robust to spots with no radius neighbour (the stock loop crashes there). It needs
no `stlearn` install — it is plain numpy/scipy. Do not swap it for the stock call.

## Input (data files from Step 1)

- `project/outputs/ccc_base.h5ad` — `.X` log1p, `obsm['spatial']`.
- `project/outputs/ccc_lr_common.csv` — shared monomeric resource.
- `project/outputs/logs/ccc_data_prep.json` — read `median_nn` and `dis_mult`.

## Output

- `project/outputs/stlearn_scores.csv` — columns `ligand, receptor, stlearn_score` (summed
  neighbourhood co-expression; higher = more co-expression). One row per LR pair.

## Success criteria

- `stlearn_scores.csv` has columns `ligand, receptor, stlearn_score` and is non-empty.
- Scores are finite and non-negative (a sum of non-negative terms).

## What the script does

`_neighbour_frac_matrix(coords, dis_thr)` builds a row-normalised binary radius graph (giving
each isolated spot its single nearest neighbour), and `run_stlearn(adata, resource, dis_thr)`
computes the summed co-expression statistic per pair. `main()` derives
`dis_thr = dis_mult * median_nn` from the prep log, scores, and writes `stlearn_scores.csv`.

## Common issues

- **All-zero scores.** The panel doesn't co-express the LR genes within the radius, or a
  species/symbol mismatch upstream — check [[ccc-data-prep]]; do not relax the radius.
- **stLearn ≈ COMMOT.** ~0.84 correlated by design; expected, not a bug.

## References

- stLearn: Pham et al., *Nature Communications* 2023. `stlearn.tl.cci.lr` (v0.2.5).
- Related skills: [[ccc-data-prep]], [[ccc-liana]], [[ccc-commot]], [[ccc-decoupler]],
  [[ccc-aggregate]].
