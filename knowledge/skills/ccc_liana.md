---
name: ccc-liana
description: Step 2 of the ccc_ensemble workflow. Runs LIANA+ rank_aggregate (non-spatial cell-group expression consensus) on the shared LR resource via the verbatim `run_liana` helper, and writes one LR-level score table (liana_scores.csv) for the ensemble aggregator.
applies_to: [coding_agent]
tags: [ccc, liana, ligand-receptor, ensemble]
status: enable
---

# CCC — LIANA+ (expression-consensus axis)

## ⚠️ Fixed pipeline — do not deviate

This step calls `run_liana` from `ensemble_ccc.py` (written verbatim in [[ccc-data-prep]]).
Use the driver below **exactly**. Do not swap the scoring axis, add `bivariate`, change
`use_raw`, add regimes, or add any evaluation. If it fails, fix the environment/inputs, not
the method code.

## When to use

Step 2 of the `ccc_ensemble` plan, after [[ccc-data-prep]]. LIANA+ `rank_aggregate` is the
**non-spatial expression-consensus** axis of the ensemble: for each ligand-receptor pair it
aggregates CellPhoneDB/NATMI/Connectome/logFC/… ranks across cell groups. It rewards specific,
strong LR co-expression but is blind to physical location — the spatial axis comes from
[[ccc-commot]].

It runs on the **shared resource** (`ccc_lr_common.csv`) from [[ccc-data-prep]], not LIANA's
native default, so both ensemble methods test the same pairs. `liana` is pre-installed.

## Input

- `ccc_base.h5ad` (immutable) — copy it; `.X` is log1p-normalized, `obs['_ct']` are labels.
- `ccc_lr_common.csv` — shared monomeric resource (`ligand,receptor`).
- `ensemble_ccc.py` — the shared library from Step 1 (must already exist).
- `logs/ccc_data_prep.json` — read `small_panel`.

## Output

- `liana_scores.csv` — the LR-level score table for [[ccc-aggregate]]. Columns:
  `ligand, receptor, liana_score` where `liana_score = 1 - min magnitude_rank` (higher =
  stronger). One row per LR pair in the shared resource that LIANA scored.
- `liana_res.csv` — the raw `adata.uns['liana_res']` (full columns) for inspection.

## Success criteria

- `adata.uns['liana_res']` is a non-empty DataFrame; `magnitude_rank ∈ [0,1]`.
- `liana_scores.csv` has columns `ligand, receptor, liana_score` and is non-empty.

## Driver — use verbatim

```python
import json
import pandas as pd, scanpy as sc
from ensemble_ccc import run_liana

prep = json.load(open("logs/ccc_data_prep.json"))
small_panel = prep.get("small_panel", False)

adata = sc.read_h5ad("ccc_base.h5ad")                    # copy of the immutable base
resource = pd.read_csv("ccc_lr_common.csv")[["ligand", "receptor"]]

liana_df, lr = run_liana(adata, resource, expr_prop=0.05 if small_panel else 0.1)
liana_df.to_csv("liana_scores.csv", index=False)         # ligand,receptor,liana_score
lr.to_csv("liana_res.csv", index=False)                  # raw liana_res for inspection
print(f"LIANA done — {len(liana_df)} LR pairs scored")
```

## Common issues

- **`.raw` used instead of `.X`.** `run_liana` passes `use_raw=False`; do not change it or
  LIANA silently uses a stale `.raw`.
- **Empty result / dropped pairs.** Usually `expr_prop` too high for a sparse imaging panel —
  the driver already drops it to 0.05 when `small_panel` is set — or a species/resource
  mismatch upstream in [[ccc-data-prep]].
- **`inspect.signature` on `li.mt.rank_aggregate` raises.** It is a class instance; the call
  inside `run_liana` is complete — do not introspect it.

## References

- LIANA+ tutorial (in-repo): `src/agents/agent_registry/coding_agent/tutorials/liana-examples/basic_usage.md`
- Related skills: [[ccc-data-prep]], [[ccc-commot]], [[ccc-aggregate]].
</content>
