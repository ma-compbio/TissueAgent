---
name: ccc-stlearn
description: Run stLearn's spatial cell-cell interaction pipeline on preprocessed AnnData — installs stlearn if needed, loads connectomeDB2020 LR pairs, runs st.tl.cci.run (LR hotspot test with adj_pvals) followed by st.tl.cci.run_cci (cell-type-pair CCI permutation), exposing per-LR significance in adata.uns['lr_summary'] and per-(LR, sender, receiver) results in adata.uns['per_lr_cci_*']. Designed to slot into the ccc_ensemble plan.
applies_to: [coding_agent]
tags: [ccc, stlearn, spatial, ligand-receptor]
status: enable
---

# CCC — stLearn CCI

## When to use

Step 4 of the `ccc_ensemble` plan. stLearn's CCI test is a **spot-level hotspot statistic** for each LR pair (spots with both ligand and receptor expression, neighbour-corrected, permutation-tested) followed by a cell-type-pair attribution step. This is a fundamentally different signal from LIANA+ (mean-expression test on clusters) and from COMMOT (OT-routed spatial flow). Including it gives the ensemble three independent lenses.

Do not use on non-spatial data.

## Mode branching (Visium vs imaging platforms)

The skill has **two execution paths** picked from `logs/ccc_data_prep.json`'s `resolution_mode`. This matches stLearn's own tutorials — the CCI page assumes Visium; the Xenium page grids first.

| `resolution_mode` | Path | `st.tl.cci.grid` | `distance` | `spot_mixtures` |
|---|---|---|---|---|
| `spot_multicell` (Visium / ST / Slide-seq) | direct | not called | `None` (spot + immediate neighbours) | `True` if deconvolution proportions are in `adata.uns[label]`, else `False` |
| `single_cell` (Xenium / MERFISH / seqFISH) | **grid first** | `n_row=125, n_col=125, use_label='_ccc_cell_type'` | `≈ 3 × median_nn_um` (or the grid pitch) | `True` — the gridded object carries per-grid cell-type proportions |

Without gridding, single-cell-resolution data (a) blows up the neighbour graph (`19 spots with no neighbours` was the seqFISH failure mode), and (b) forces `spot_mixtures=False`, which the paper's decision tree calls the "stLearn\*" variant — a lossier fallback. Grid first.

## Input

- `ccc_prepped.h5ad` from [[ccc-data-prep]] — note we will use `layers['norm_no_log']` (normalize_total **without** log1p) because stLearn's LR statistic assumes raw-scale relative counts.
- `logs/ccc_data_prep.json` — READ `species`, `resolution_mode`, `median_nn_um` (drives `distance`). Refuse if `median_nn_um` is null.
- Cell-type column `_ccc_cell_type`.

## Output

- `ccc_prepped.h5ad` re-written with stLearn keys.
- `stlearn_lr_summary.csv` — `adata.uns['lr_summary']` flattened. Columns: `lr_pair, n_spots, n_spots_sig, n_spots_sig_pval` (after `adj_pvals`).
- `stlearn_per_lr_cci.csv` — long-form `(ligand, receptor, source, target, n_sig_spots)` aggregated from `adata.uns['per_lr_cci__ccc_cell_type']`.
- `logs/ccc_stlearn.json` — `{n_lr_pairs_loaded, n_lr_pairs_significant, n_permutations, distance, min_spots}`.

Stored on the AnnData (per the tutorial):

| Location | Key | Content |
|---|---|---|
| `adata.obsm` | `lr_scores` | spot × LR-pair raw score matrix |
| `adata.obsm` | `p_vals`, `p_adjs`, `-log10(p_adjs)` | per-spot per-LR significance |
| `adata.obsm` | `lr_sig_scores` | scores zeroed at non-significant spots |
| `adata.uns` | `lr_summary` | per-LR rank table (key columns above) |
| `adata.uns` | `lr_cci__ccc_cell_type` | matrix of significant CCI counts across all LRs |
| `adata.uns` | `per_lr_cci__ccc_cell_type` | dict: LR pair → cell-type × cell-type CCI dataframe |

## Success Criteria

- `stlearn` import succeeds after install.
- `adata.uns['lr_summary']` has ≥1 row with `n_spots_sig_pval > 0` after `adj_pvals`.
- `stlearn_per_lr_cci.csv` non-empty (will be empty only if no LR had any significant cluster-pair CCI; in that case lowering `n_perms` is **not** a fix — investigate the data).

## Workflow

1. `pip install stlearn`.
2. Load `ccc_prepped.h5ad` and `logs/ccc_data_prep.json`. **Swap `.X` to the no-log1p layer**: `adata.X = adata.layers['norm_no_log'].copy()`.
3. `lrs = st.tl.cci.load_lrs(['connectomeDB2020_lit'], species=species)` — `'connectomeDB2020_put'` is the larger, lower-confidence set; `lit` is literature-supported only.
4. **Branch on `resolution_mode`**:
   - `spot_multicell`: proceed directly on `adata`. `distance = None` (spot + immediate neighbours). `spot_mixtures = True` if `adata.uns[label]` contains deconvolution proportions, else `False`.
   - `single_cell`: **grid first** — `adata = st.tl.cci.grid(adata, n_row=125, n_col=125, use_label='_ccc_cell_type')`. This matches stLearn's Xenium tutorial exactly. Then set `distance = max(3 × median_nn_um, grid_pitch_um)` and `spot_mixtures = True` (the gridded pseudo-spots carry the cell-type proportions).
5. `st.tl.cci.run(adata, lrs, min_spots=20, distance=<see above>, n_pairs=500, n_cpus=4, random_state=1337)`.
6. `st.tl.cci.adj_pvals(adata, correct_axis='spot', pval_adj_cutoff=0.05, adj_method='fdr_bh')`.
7. `st.tl.cci.run_cci(adata, use_label='_ccc_cell_type', min_spots=3, spot_mixtures=<see above>, n_perms=500, n_cpus=4, random_state=1337)`.
8. Flatten `adata.uns['lr_summary']` → `stlearn_lr_summary.csv`. Flatten `adata.uns['per_lr_cci__ccc_cell_type']` → long-form `stlearn_per_lr_cci.csv` for the aggregation step. When run on a gridded object, record `gridded=True` in `logs/ccc_stlearn.json` so aggregation knows source/target are grid-derived proportions rather than raw cell labels.

## Code Template

```python
import subprocess, sys
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "stlearn"], check=True)

import json, os
import pandas as pd
import scanpy as sc
import stlearn as st

with open("logs/ccc_data_prep.json") as f:
    prep = json.load(f)

species         = prep["species"]
resolution_mode = prep["resolution_mode"]
median_nn_um    = prep["median_nn_um"]
if median_nn_um is None:
    raise ValueError("median_nn_um is null — ccc-data-prep needs physical coords")

adata = sc.read_h5ad("ccc_prepped.h5ad")

# stLearn wants normalize_total WITHOUT log1p
adata.X = adata.layers["norm_no_log"].copy()

lrs = st.tl.cci.load_lrs(["connectomeDB2020_lit"], species=species)

# --- mode branch ---
gridded = False
if resolution_mode == "single_cell":
    # matches stLearn's Xenium tutorial: cell_cell_interaction_xenium.html
    N_ROW = N_COL = 125
    adata = st.tl.cci.grid(adata, n_row=N_ROW, n_col=N_COL, use_label="_ccc_cell_type")
    gridded = True
    xr = adata.obsm["spatial"][:, 0].ptp()
    yr = adata.obsm["spatial"][:, 1].ptp()
    grid_pitch_um = min(xr / N_ROW, yr / N_COL)
    distance = max(3 * median_nn_um, grid_pitch_um)
    spot_mixtures = True
else:
    # Visium / ST / Slide-seq
    distance = None                      # spot + immediate neighbours per stLearn CCI tutorial
    spot_mixtures = bool(prep.get("cell_type_col") in adata.uns)  # True iff deconv proportions

st.tl.cci.run(adata, lrs,
              min_spots=20, distance=distance, n_pairs=500,
              n_cpus=4, random_state=1337)
st.tl.cci.adj_pvals(adata, correct_axis="spot",
                    pval_adj_cutoff=0.05, adj_method="fdr_bh")
st.tl.cci.run_cci(adata, use_label="_ccc_cell_type",
                  min_spots=3, spot_mixtures=spot_mixtures,
                  n_perms=500, n_cpus=4, random_state=1337)

os.makedirs("logs", exist_ok=True)
lr_summary = adata.uns["lr_summary"].reset_index().rename(columns={"index": "lr_pair"})
lr_summary.to_csv("stlearn_lr_summary.csv", index=False)

rows = []
per_lr = adata.uns["per_lr_cci__ccc_cell_type"]   # dict LR -> DataFrame
for lr, df in per_lr.items():
    ligand, receptor = lr.split("_", 1)
    for src in df.index:
        for tgt in df.columns:
            rows.append({"ligand": ligand, "receptor": receptor,
                         "source": src, "target": tgt,
                         "n_sig_spots": int(df.loc[src, tgt])})
pd.DataFrame(rows).to_csv("stlearn_per_lr_cci.csv", index=False)

json.dump({"species": species,
           "resolution_mode": resolution_mode,
           "gridded": gridded,
           "distance": (float(distance) if distance is not None else None),
           "spot_mixtures": spot_mixtures,
           "n_lr_pairs_loaded": int(len(lrs)),
           "n_lr_pairs_significant": int((lr_summary["n_spots_sig"] > 0).sum()),
           "n_permutations": 500},
          open("logs/ccc_stlearn.json", "w"), indent=2)
adata.write("ccc_prepped.h5ad")
print("stLearn CCI done; gridded:", gridded,
      "LRs significant:", (lr_summary['n_spots_sig'] > 0).sum())
```

## Common Issues

- **`.X` is log1p → all `lr_scores` collapse near zero.** The tutorial explicitly says "NOTE: no log1p". The data-prep skill stashed `layers['norm_no_log']` exactly so this skill could swap it in.
- **`distance=None` uses Visium's default neighbour distance.** Only valid for `spot_multicell` platforms. For imaging data the correct approach is to grid first (`st.tl.cci.grid`) and then pass a distance derived from `median_nn_um` or the grid pitch — do not pass `None` to imaging inputs.
- **`spot_mixtures=False` on ungridded single-cell data (the "stLearn\*" fallback).** Loses information and structurally over-calls autocrine interactions when a cell's spatial neighbours share its own cell type. Prefer the grid path.
- **Skipping the grid step on imaging data.** Produces "N spots with no neighbours" warnings, huge neighbour graphs, and hours of runtime for little signal. Grid.
- **`n_pairs` too low → noisy permutation p-values.** 500 is reasonable; 1000+ for publication.
- **`spot_mixtures=True` requires a cell-type proportion matrix in `uns[use_label]`.** Deconvolution upstream is required if true; else use `False` (one cell type per spot/cell).
- **`per_lr_cci_*` LR naming.** The key uses `<ligand>_<receptor>`; if a ligand name contains an underscore (rare), `split('_', 1)` splits at the first one — confirm format before trusting downstream joins.
- **`run_cci` is slow.** Scales as O(n_lrs · n_perms · n_celltypes²). Consider filtering `lr_summary` to `n_spots_sig > 0` LRs before `run_cci` for large datasets.

## References

- stLearn CCI tutorial (Visium): <https://stlearn.readthedocs.io/en/latest/tutorials/cell_cell_interaction.html>
- stLearn Xenium CCI tutorial (grid path): <https://stlearn.readthedocs.io/en/latest/tutorials/cell_cell_interaction_xenium.html>
- stLearn paper: Pham et al., *Nature Communications* 2023 — "Robust mapping of spatiotemporal trajectories and cell-cell interactions in healthy and diseased tissues."
- connectomeDB2020: Raredon et al., *Sci. Adv.* 2019.
- Related skills: [[ccc-data-prep]], [[ccc-liana]], [[ccc-commot]].
