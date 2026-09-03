---
name: ccc-commot
description: Step 3 of the ccc_ensemble workflow. Runs the shipped COMMOT (collective optimal transport) spatial_communication scorer on the shared LR resource at a single native-unit distance threshold, scoring each LR pair by total routed OT flow. Writes one LR-level score table (commot_scores.csv) for the ensemble aggregator.
applies_to: [coding_agent]
tags: [ccc, commot, spatial, optimal-transport, ensemble]
status: enable
---

# CCC — COMMOT (spatial optimal-transport axis)

## ⚠️ How to run this

This skill **ships a runnable script**. To save time/tokens, do **not** list/cat/read the script or this SKILL file first; do **not** write your own COMMOT step or paste code. Run the shipped script in the kernel:

```python
%run project/skills/ccc-commot/scripts/ccc_commot.py
```

It installs the `commot` PyPI package if needed, reads the Step 1 artifacts, routes every
pair, and writes `commot_scores.csv`. The script is authoritative. There is **one** distance threshold, `dis_mult × median_nn`
with `dis_mult` read from the JSON log (it is **1.5** — do not raise it). Do NOT add a
second regime, add cluster-level permutation tests, change the score (summed OT flow), or
add evaluation. If it fails, fix the environment/inputs.

## When to use

Step 3 of the `ccc_ensemble` plan, after [[ccc-data-prep]]. COMMOT is the **spatial
optimal-transport** member: an LR pair scores only if ligand can be transported to nearby
receptor within `dis_thr`. Spatially precise but can route weak signal and ignores cell-group
specificity — expression specificity comes from [[ccc-liana]], the complementary spatial
co-expression axis from [[ccc-stlearn]], the downstream axis from [[ccc-decoupler]]. Requires
`obsm['spatial']`. It runs on the **shared resource** (never COMMOT's native CellChatDB).

## Distance threshold (native units)

`dis_thr = dis_mult × median_nn` (`dis_mult = 1.5`), in the units of `obsm['spatial']` —
COMMOT does not convert pixels to µm, so the threshold derives from the calibrated
`median_nn` in the prep log. One short-range radius, by design.

## Memory guard (do NOT randomly subsample)

COMMOT stores an `n×n` sparse matrix per LR pair and the OT solve costs seconds per pair.
[[ccc-data-prep]] already capped the object to a central patch and the resource to
`MAX_PAIRS`. If still too large, crop to a smaller contiguous patch or run per ROI — **never**
global random subsampling (it changes the OT solution).

## Input (data files from Step 1)

- `project/outputs/ccc_base.h5ad` — `.X` log1p, `obsm['spatial']`.
- `project/outputs/ccc_lr_common.csv` — shared monomeric resource.
- `project/outputs/logs/ccc_data_prep.json` — read `median_nn` and `dis_mult`.

## Output

- `project/outputs/commot_scores.csv` — columns `ligand, receptor, commot_score` (total
  routed OT flow; higher = more communication). One row per LR pair COMMOT routed.

## Success criteria

- `commot_scores.csv` has columns `ligand, receptor, commot_score` and is non-empty. If zero
  routed: check gene symbols, `dis_thr` units, and species — do not relax anything else.

## What the script does

`run_commot(adata, resource, dis_thr)` calls `ct.tl.spatial_communication(...)` on the shared
resource, then per pair sums the routed OT flow (`adata.obsp["commot-shared-<lig>-<rec>"]`),
dropping the large per-pair matrices afterward. `main()` installs `commot`, derives
`dis_thr = dis_mult * median_nn` from the prep log, scores, and writes `commot_scores.csv`.

## Common issues

- **`dis_thr=None` → AttributeError.** Always a positive scalar; the script derives it from `median_nn`.
- **Wrong units → all-zero or saturated.** Deriving `dis_thr` from `median_nn` is correct whether
  coords are pixels or µm.
- **`commot.__version__` doesn't exist** — use `importlib.metadata.version('commot')`.

## References

- COMMOT: Cang et al., *Nature Methods* 2023. Docs: <https://commot.readthedocs.io/>
- Related skills: [[ccc-data-prep]], [[ccc-liana]], [[ccc-stlearn]], [[ccc-decoupler]],
  [[ccc-aggregate]].
