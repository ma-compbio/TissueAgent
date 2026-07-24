---
name: ccc-stlearn
description: Run stLearn's spatial CCI on the shared CCC resource — the per-spot LR hotspot permutation test (st.tl.cci.run + adj_pvals) followed by the cell-type-pair CCI test (run_cci). Grids single-cell data from raw counts first. Treats cell-type-pair support as UNDIRECTED. Emits one standardized long CSV for the ensemble aggregator plus its operable LR universe.
applies_to: [coding_agent]
tags: [ccc, stlearn, spatial, ligand-receptor]
status: enable
---

# CCC — stLearn CCI

## When to use

Step 4 of the `ccc_ensemble` plan. stLearn's CCI test is a **per-spot LR-hotspot statistic**
(spots co-expressing ligand and receptor with a significant neighbourhood, permutation-tested)
followed by a cell-type-pair attribution. This is a different lens from LIANA (cluster mean
expression) and COMMOT (OT flow) — three independent views.

Runs on the **shared resource** from [[ccc-data-prep]] (`ccc_lr_common.csv`), formatted as
`"ligand_receptor"` strings. **Do not** call `st.tl.cci.load_lrs()` — that substitutes
stLearn's native connectomeDB and breaks the shared-universe comparison.

Don't run on non-spatial data.

## ⚠️ Version preflight (do this first)

The modern CCI API (`st.tl.cci.run`, `run_cci`, `grid`, `adj_pvals`) exists in **stLearn
≥1.x**. Older 0.2.x only has `st.tl.cci.lr`/`merge` — a different API this skill does **not**
target. Check and, if needed, upgrade before anything else:

```python
import stlearn as st
from importlib.metadata import version
print("stlearn", version("stlearn"))
if not hasattr(st.tl.cci, "run"):
    import subprocess, sys
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-U", "stlearn"], check=True)
    import importlib; importlib.reload(st)          # re-import; then re-check hasattr
    if not hasattr(st.tl.cci, "run"):
        raise RuntimeError("stLearn CCI API unavailable; report API drift, don't guess.")
```

If signatures differ from those below, print `help(st.tl.cci.run)` and adapt — report drift
rather than guessing parameter names.

## Mode branch

| resolution_mode | Path | grid | distance (native units) | spot_mixtures |
|---|---|---|---|---|
| `spot_multicell` (Visium/ST) | direct | no | `None` (spot + immediate neighbours) | `True` iff deconvolution proportions exist, else `False` |
| `single_cell` (Xenium/MERFISH/seqFISH) | **grid first** | `st.tl.cci.grid` on **raw counts** | `1.5 × median_nn` or grid pitch | `True` (gridded pseudo-spots carry cell-type proportions) |

**Grid from counts, not normalized values.** Summing independently per-cell-normalized values
produces bin values driven by cell count, not molecule abundance. Grid raw counts, *then*
normalize the grid (no log1p). Without gridding, single-cell data blows up the neighbour graph
and forces the lossier `spot_mixtures=False` path.

## Input

- `ccc_base.h5ad` (copy it) — swap `.X = layers['norm_no_log']` (normalize_total, **no** log1p:
  stLearn's LR statistic assumes raw-scale relative counts).
- `ccc_lr_common.csv` — shared monomeric resource.
- `logs/ccc_data_prep.json` — read `species`, `resolution_mode`, `median_nn`, `has_deconv`,
  `sample_col`, `stlearn_species`.

## Output

- `stlearn_ccc.csv` — standardized long table for [[ccc-aggregate]] at `level=celltype_pair`,
  `regime=contact`. Schema `engine, mode, regime, level, spatial, ligand, receptor, source,
  target, score, higher_better, pvalue, contrib_dist`. `score` = significant-spot count
  (higher=stronger); `pvalue` = per-LR adjusted permutation p; `contrib_dist` = the neighbour
  scale tested (`distance`, or grid pitch when gridded). **stLearn's cell-type-pair support is
  undirected** — its counter fires for either LR orientation across an edge — so it corroborates
  the pair spatially but direction comes from LIANA/COMMOT.
- `stlearn_lr.csv` — per-LR hotspot summary (`lr_pair, n_spots_sig, adj_pval`), LR-level.
- `stlearn_universe.csv` — operable pairs: shared pairs with both genes on the panel.
- `logs/ccc_stlearn.json` — `{species, gridded, distance, spot_mixtures, n_lr_sig,
  n_permutations, species_mapping}`.

## Success criteria

- After the preflight, `st.tl.cci.run` exists.
- `adata.uns['lr_summary']` has ≥1 row with significant spots after `adj_pvals`.
- `stlearn_ccc.csv` non-empty (empty ⇒ investigate data, not a lower `n_perms`).

## Code template

```python
# --- preflight (see above) then: ---
import json
import numpy as np, pandas as pd, scanpy as sc, stlearn as st

prep = json.load(open("logs/ccc_data_prep.json"))
species, res_mode, median_nn = prep["species"], prep["resolution_mode"], prep["median_nn"]
has_deconv = prep.get("has_deconv", False)
if median_nn is None:
    raise ValueError("median_nn is null — stLearn distance needs calibrated coords")

adata = sc.read_h5ad("ccc_base.h5ad")               # copy of the immutable base
common = pd.read_csv("ccc_lr_common.csv")
lrs = (common.ligand.astype(str) + "_" + common.receptor.astype(str)).to_numpy()

# --- single-cell: grid raw counts first, then normalize (no log1p) ---
gridded = False
if res_mode == "single_cell":
    adata.X = adata.layers["counts"].copy()         # grid COUNTS, not normalized values
    n_obs = adata.n_obs
    N = int(np.clip(round(np.sqrt(max(n_obs // 4, 100))), 50, 200))  # ~4 cells/pseudo-spot
    adata = st.tl.cci.grid(adata, n_row=N, n_col=N, use_label="_ccc_cell_type")
    st.pp.normalize_total(adata)                    # normalize the GRID; still no log1p
    gridded = True
    xr, yr = np.ptp(adata.obsm["spatial"][:, 0]), np.ptp(adata.obsm["spatial"][:, 1])
    distance = max(1.5 * median_nn, min(xr / N, yr / N))
    spot_mixtures = True
else:
    adata.X = adata.layers["norm_no_log"].copy()    # normalize_total, NO log1p
    distance = None                                 # spot + immediate neighbours
    spot_mixtures = bool(has_deconv)

# --- LR hotspot test + BH, then cell-type-pair CCI ---
st.tl.cci.run(adata, lrs, min_spots=20, distance=distance, n_pairs=1000,
              n_cpus=4, random_state=1337)
st.tl.cci.adj_pvals(adata, correct_axis="spot", pval_adj_cutoff=0.05, adj_method="fdr_bh")
st.tl.cci.run_cci(adata, use_label="_ccc_cell_type", min_spots=3,
                  spot_mixtures=spot_mixtures, n_perms=500, n_cpus=4, random_state=1337)

# per-LR hotspot summary (LR-level)
summ = adata.uns["lr_summary"].reset_index().rename(columns={"index": "lr_pair"})
summ.to_csv("stlearn_lr.csv", index=False)
# map lr_pair -> adjusted p for the per-cell-type rows
pcol = next((c for c in ["n_spots_sig_pval", "adj_pval", "pval"] if c in summ.columns), None)
p_by_lr = dict(zip(summ["lr_pair"], summ[pcol])) if pcol else {}

# cell-type-pair CCI (UNDIRECTED support) -> long rows
rows = []
per_lr = adata.uns["per_lr_cci__ccc_cell_type"]     # dict: 'lig_rec' -> DataFrame src×tgt
for lr, mat in per_lr.items():
    lig, rec = lr.split("_", 1)
    for src in mat.index:
        for tgt in mat.columns:
            n_sig = int(mat.loc[src, tgt])
            if n_sig < 3:                            # drop empty cell-type pairs
                continue
            rows.append(dict(engine="stlearn", mode="cci", regime="contact",
                             level="celltype_pair", spatial=True,
                             ligand=lig, receptor=rec, source=src, target=tgt,
                             score=n_sig, higher_better=True,
                             pvalue=p_by_lr.get(lr, np.nan),
                             contrib_dist=float(distance) if distance else float(median_nn)))
pd.DataFrame(rows).to_csv("stlearn_ccc.csv", index=False)

genes = set(adata.var_names)
common[common.ligand.isin(genes) & common.receptor.isin(genes)][["ligand", "receptor"]] \
    .to_csv("stlearn_universe.csv", index=False)

from importlib.metadata import version as _ver
json.dump({"species": species, "stlearn_version": _ver("stlearn"), "gridded": gridded,
           "distance": (float(distance) if distance else None),
           "spot_mixtures": spot_mixtures,
           "n_lr_sig": int((summ.get("n_spots_sig", pd.Series(dtype=int)) > 0).sum()),
           "n_permutations": 500,
           "species_mapping": None if species == "human" else "mouseconsensus_shared"},
          open("logs/ccc_stlearn.json", "w"), indent=2)
print(f"stLearn done — gridded={gridded}, cell-type-pair rows={len(rows)}")
```

## Common issues

- **Old API (0.2.x).** Only `st.tl.cci.lr`/`merge` — the preflight upgrades or reports drift.
- **`.X` is log1p → scores collapse.** stLearn wants normalize_total **without** log1p; the
  base object's `layers['norm_no_log']` is exactly that.
- **`load_lrs` substitutes the native DB.** Pass the shared `lrs` array; don't call `load_lrs`.
- **Grid then normalize (single-cell).** Grid raw counts, normalize the grid. Normalizing per
  cell then summing yields count-driven bins.
- **Direction is unreliable.** The counter fires for either LR orientation across an edge —
  emit the pair but let LIANA/COMMOT set direction; the aggregator treats stLearn as support.
- **`np.ptp(arr)`**, not `arr.ptp()` (removed in NumPy 2).
- **Mouse.** connectomeDB2020 is human-derived; here we bypass it with the shared
  `mouseconsensus` resource, which is safer than stLearn's casing-based mouse conversion. If
  the shared resource can't be mouse-mapped, drop stLearn and run a 2-method consensus.
- **`run_cci` is slow** (O(n_lrs · n_perms · n_celltypes²)); pre-filter `lr_summary` to
  significant LRs for large panels.

## References

- stLearn CCI tutorial (Visium): <https://stlearn.readthedocs.io/en/latest/tutorials/cell_cell_interaction.html>
- Xenium grid path: <https://stlearn.readthedocs.io/en/latest/tutorials/cell_cell_interaction_xenium.html>
- stLearn: Pham et al., *Nature Communications* 2023.
- Related skills: [[ccc-data-prep]], [[ccc-liana]], [[ccc-commot]], [[ccc-aggregate]].
