---
name: ccc-commot
description: Step 3 of the ccc_ensemble workflow. Runs COMMOT (collective optimal transport) spatial_communication on the shared LR resource at a single native-unit distance threshold via the verbatim `run_commot` helper, scoring each LR pair by total routed OT flow. Writes one LR-level score table (commot_scores.csv) for the ensemble aggregator.
applies_to: [coding_agent]
tags: [ccc, commot, spatial, optimal-transport, ensemble]
status: enable
---

# CCC — COMMOT (spatial optimal-transport axis)

## ⚠️ Fixed pipeline — do not deviate

This step calls `run_commot` from `ensemble_ccc.py` (written verbatim in [[ccc-data-prep]]).
Use the driver below **exactly**. There is **one** distance threshold (`1.5 × median_nn`) —
do not add a second regime, do not add cluster-level permutation tests, do not change the
score (it is the summed OT flow), and do not add evaluation. If it fails, fix the
environment/inputs, not the method code.

## When to use

Step 3 of the `ccc_ensemble` plan, after [[ccc-data-prep]]. COMMOT is the **spatial** axis of
the ensemble: it solves a collective optimal-transport problem so an LR pair scores only if
ligand can be transported to nearby receptor within `dis_thr`. It is spatially precise but can
route weak/nonspecific signal and ignores cell-group specificity — the expression-specificity
axis comes from [[ccc-liana]]. Requires `obsm['spatial']`.

It runs on the **shared resource** (`ccc_lr_common.csv`) from [[ccc-data-prep]], passed as
`df_ligrec` — never COMMOT's native CellChatDB. Install is idempotent: `pip install commot`.

## Input

- `ccc_base.h5ad` (immutable) — copy it; `.X` log1p-normalized, `obsm['spatial']`.
- `ccc_lr_common.csv` — shared monomeric resource (`ligand,receptor`).
- `ensemble_ccc.py` — the shared library from Step 1 (must already exist).
- `logs/ccc_data_prep.json` — read `median_nn` (native units) and `dis_mult`.

## Distance threshold (native units)

`dis_thr = dis_mult × median_nn` (`dis_mult = 1.5`), in the units of `obsm['spatial']` —
COMMOT does **not** convert pixels to µm, so the threshold is derived from the calibrated
`median_nn` in the prep log. This is a short-range communication radius. There is one radius,
by design.

## Memory guard (do NOT randomly subsample)

COMMOT stores an `n×n` sparse matrix per LR pair and the OT solve costs seconds per pair.
[[ccc-data-prep]] already caps the object to a contiguous central patch (`crop_central`,
`CROP_N`) and the resource to `MAX_PAIRS`. If a section is still too large, crop to a smaller
contiguous patch or run per section/ROI — **never** global random subsampling (it changes the
OT solution by altering local ligand/receptor supply).

## Output

- `commot_scores.csv` — the LR-level score table for [[ccc-aggregate]]. Columns:
  `ligand, receptor, commot_score` where `commot_score` = total routed OT flow (sum of the
  per-pair spot×spot matrix; higher = more communication). One row per LR pair COMMOT routed.

## Success criteria

- `commot_scores.csv` has columns `ligand, receptor, commot_score` and is non-empty (at least
  some pairs routed). If zero routed: check gene symbols, `dis_thr` units, and species — do
  **not** relax anything else.

## Driver — use verbatim

```python
import subprocess, sys
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "commot"], check=True)
import json
import pandas as pd, scanpy as sc
from ensemble_ccc import run_commot

prep = json.load(open("logs/ccc_data_prep.json"))
median_nn, dis_mult = prep["median_nn"], prep.get("dis_mult", 1.5)
if median_nn is None:
    raise ValueError("median_nn is null — COMMOT needs calibrated coords (see ccc-data-prep)")

adata = sc.read_h5ad("ccc_base.h5ad")                    # copy of the immutable base
resource = pd.read_csv("ccc_lr_common.csv")[["ligand", "receptor"]]

commot_df = run_commot(adata, resource, dis_thr=dis_mult * median_nn)
commot_df.to_csv("commot_scores.csv", index=False)       # ligand,receptor,commot_score
print(f"COMMOT done — {len(commot_df)} LR pairs routed at dis_thr={dis_mult * median_nn:.1f}")
```

## Common issues

- **`dis_thr=None` → `AttributeError`.** Always a positive scalar; the driver derives it from
  `median_nn`.
- **Wrong units → all-zero or saturated.** `dis_thr` is in coordinate units; deriving it from
  `median_nn` is correct whether coords are pixels or µm.
- **Ensembl IDs → 0 pairs silently.** [[ccc-data-prep]] guarantees symbols; if you see 0,
  check the prep step.
- **`commot.__version__` doesn't exist** — use `importlib.metadata.version('commot')`.

## References

- COMMOT: Cang et al., *Nature Methods* 2023. Docs: <https://commot.readthedocs.io/>
- Related skills: [[ccc-data-prep]], [[ccc-liana]], [[ccc-aggregate]].
</content>
