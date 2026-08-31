---
name: ccc-liana
description: Step 2 of the ccc_ensemble workflow. Runs the shipped LIANA+ rank_aggregate scorer (non-spatial cell-group expression consensus) on the shared LR resource, and writes one LR-level score table (liana_scores.csv) for the ensemble aggregator.
applies_to: [coding_agent]
tags: [ccc, liana, ligand-receptor, ensemble]
status: enable
---

# CCC — LIANA+ (expression-consensus axis)

## ⚠️ How to run this

This skill **ships a runnable script** — do NOT write your own LIANA step and do NOT
paste code from this file. Run the shipped script in the kernel:

```python
%run project/skills/ccc-liana/scripts/ccc_liana.py
```

It reads the Step 1 artifacts, scores every pair, and writes `liana_scores.csv`. If you
need the scorer as a function instead, import it (do not reimplement it):

```python
import sys; sys.path.insert(0, "project/skills/ccc-liana/scripts")
from ccc_liana import run_liana
```

The script is authoritative for the installed library versions. Do NOT edit it, reimplement
the scoring by hand, swap the scoring axis, add `bivariate`, change `use_raw` (it is `False`
on purpose), or groupby anything other than `_ct`. If it fails, fix the environment/inputs.

## When to use

Step 2 of the `ccc_ensemble` plan, after [[ccc-data-prep]]. LIANA+ `rank_aggregate` is the
**non-spatial expression-consensus** member: per LR pair it aggregates
CellPhoneDB/NATMI/Connectome/logFC ranks across cell groups. It rewards specific, strong LR
co-expression but is blind to location — the spatial axes come from [[ccc-commot]] and
[[ccc-stlearn]], the downstream axis from [[ccc-decoupler]].

It runs on the **shared resource** (`ccc_lr_common.csv`) from [[ccc-data-prep]], not LIANA's
native default, so all four members test the same pairs. `liana` is pre-installed.

## Input (data files from Step 1)

- `project/outputs/ccc_base.h5ad` — copy of the immutable base; `.X` log1p, `obs['_ct']`.
- `project/outputs/ccc_lr_common.csv` — shared monomeric resource (`ligand,receptor`).
- `project/outputs/logs/ccc_data_prep.json` — read `small_panel`.

## Output

- `project/outputs/liana_scores.csv` — columns `ligand, receptor, liana_score` where
  `liana_score = 1 - min magnitude_rank` (higher = stronger). One row per scored LR pair.

## Success criteria

- `liana_scores.csv` has columns `ligand, receptor, liana_score` and is non-empty.

## What the script does

`run_liana(adata, resource, expr_prop=0.1, seed=1337, n_perms=100)` calls
`li.mt.rank_aggregate(..., groupby="_ct", use_raw=False, ...)` on the shared resource, then
per LR pair takes `liana_score = 1 - min magnitude_rank` over all cell-group pairs. `main()`
loads the Step 1 artifacts (dropping `expr_prop` to 0.05 when `small_panel`), scores, and
writes `liana_scores.csv`.

## Common issues

- **`.raw` instead of `.X`.** The script passes `use_raw=False`; do not change it.
- **Empty/dropped pairs.** Usually `expr_prop` too high for a sparse panel (the script already
  drops it to 0.05 when `small_panel`) or a species/resource mismatch in [[ccc-data-prep]].
- **`inspect.signature` on `li.mt.rank_aggregate` raises** — it's a class instance; the call
  in `run_liana` is complete, do not introspect it.

## References

- LIANA+ tutorial (in-repo): `src/agents/agent_registry/coding_agent_cache/tutorials/liana-examples/basic_usage.md`
- Related skills: [[ccc-data-prep]], [[ccc-commot]], [[ccc-stlearn]], [[ccc-decoupler]],
  [[ccc-aggregate]].
