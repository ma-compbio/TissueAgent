---
name: ccc-data-prep
description: Step 1 of the ccc_ensemble workflow. Runs the shipped prep script that preprocesses a spatial transcriptomics AnnData once into an immutable base object (log1p .X, `_ct` labels, native-unit spatial coords), computes the PROGENy per-cell downstream-response amplitude (on the FULL transcriptome, before gene-slimming) into obs['_dact'], and builds the ONE shared monomeric ligand-receptor resource all four members (LIANA+, COMMOT, stLearn, decoupler) run on. Emits ccc_base.h5ad, ccc_lr_common.csv, and a calibration log.
applies_to: [coding_agent]
tags: [ccc, ligand-receptor, spatial, preprocessing, ensemble, progeny, decoupler]
status: enable
---

# CCC Data Prep — shared setup for the 4-member ensemble

## ⚠️ How to run this (read first)

This skill **ships a runnable script**. To save time/tokens, do **not** list/cat/read the script or this SKILL file first; do **not** write your own version or paste code. Run the shipped script in the kernel, adjusting only the dataset flags:

```python
%run project/skills/ccc-data-prep/scripts/ccc_data_prep.py \
    --adata project/uploads/spatial.h5ad --cell-type cell_type --species human
```

Flags (defaults in parentheses): `--adata` (`project/uploads/spatial.h5ad`), `--cell-type`
(`cell_type`), `--species` (`human`; `human`|`mouse`), `--crop-n` (`2000`), `--max-pairs`
(`50`), `--knn-k` (`6`). The script writes `ccc_base.h5ad`, `ccc_lr_common.csv`, and
`logs/ccc_data_prep.json`. If you need the helpers as functions instead, import them (do not
reimplement them):

```python
import sys; sys.path.insert(0, "project/skills/ccc-data-prep/scripts")
from ccc_data_prep import (build_shared_resource, compute_cell_activity, crop_central,
                           median_nn_distance, prime_resources, slim_to_lr_genes)
```

The script is the validated implementation and is authoritative for the installed library
versions. Do NOT edit it. In particular, do **not**:

- build the LR resource yourself or from OmniPath (`omnipath`, `import_intercell_network`,
  `dc.op` interactions) — the shared resource comes **only** from `build_shared_resource`,
  which uses LIANA's `li.rs.select_resource`. A panel-vs-OmniPath intersection typically yields
  **0 pairs** and silently empties the whole ensemble.
- hand-roll PROGENy (no manual weight matrix, no `pg.groupby('pathway')`, no `dc.op.progeny`
  followed by your own z-score × weight sum). `compute_cell_activity` calls `dc.mt.ulm` on the
  **human** net (`organism="human"`; `organism="mouse"` 404s) and stores the length-`n_obs`
  amplitude in `obs['_dact']`.
- change the fixed parameters. `dis_mult` is **1.5** and the default `knn_k` is **6** — these
  are the values later steps read from the JSON log. Do not raise them (e.g. 3.0 / 20).

## Preconditions the agent must handle BEFORE running

The script reads a single, analysis-ready h5ad. Prepare it first if needed:

- **Ensembl IDs → symbols.** All members match on **gene symbols**. If `var_names` are Ensembl
  IDs, remap to symbols and re-save the h5ad, then point `--adata` at it (Ensembl IDs give ~0
  LR pairs and near-zero PROGENy overlap).
- **No discrete cell-type column.** If none ships with the data, derive spatial domains by
  unsupervised clustering first, write that column, and pass it via `--cell-type`.
- **Multi-sample data.** CCC must be run **per physical section** — mixing sections mixes
  coordinate systems. Subset to one coherent section first and point `--adata` at it.

## When to use

Run this **once** at the start of a `ccc_ensemble` workflow, before [[ccc-liana]],
[[ccc-commot]], [[ccc-stlearn]], [[ccc-decoupler]] and [[ccc-aggregate]]. It:

1. **Writes the immutable base object** (`ccc_base.h5ad`): `.X` log1p-normalized (all
   members consume `.X`), `obs['_ct']` discrete labels, `obsm['spatial']` float `(n,2)`
   native-unit coords, and **`obs['_dact']` = the PROGENy per-cell response amplitude**.
2. **Computes the PROGENy activity before slimming** — pathway activity is estimated on the
   **full transcriptome** (footprint genes are mostly *not* LR genes), so the script does it
   *before* dropping non-LR genes, then carries it in `obs['_dact']`.
3. **Builds the one shared LR resource** (`ccc_lr_common.csv`): monomeric, expression-
   filtered, capped at `--max-pairs`.

## Input

- **Spatial h5ad** — `.obsm['spatial']` populated (or `obs['x','y']`); raw counts in `.X`
  or `layers['counts']`; human or mouse **gene symbols** (map Ensembl IDs first).
- **species** — `"human"` or `"mouse"` (explicit, via `--species`; never inferred from casing).
- **cell_type_col** — `.obs` column of discrete labels (≥2 categories, ≥10 cells each).

## Output (project working dir)

- `ccc_base.h5ad` — immutable. `.X` log1p; `layers['counts']` raw; `obs['_ct']` categorical
  labels; `obsm['spatial']` float `(n,2)`; `obs['_dact']` PROGENy per-cell amplitude.
- `ccc_lr_common.csv` — shared monomeric resource, columns `ligand,receptor`.
- `logs/ccc_data_prep.json` — calibration record every downstream step reads:

  ```json
  {
    "species": "human|mouse", "median_nn": 118.0,   // in obsm['spatial'] UNITS
    "small_panel": false, "n_obs": 2000, "n_pairs": 50,
    "crop_n": 2000, "max_pairs": 50, "dis_mult": 1.5, "knn_k": 6,
    "n_footprint_genes": 431, "n_pathways": 14      // PROGENy overlap (honesty record)
  }
  ```

## Success criteria

- `ccc_base.h5ad` loads with `.X` log1p, `layers['counts']`, `obs['_ct']` (≥2 categories,
  ≥10 cells each), `obsm['spatial']` float `(n,2)` no NaN, finite `obs['_dact']`.
- `median_nn > 0`; `ccc_lr_common.csv` has ≥4 pairs.
- `logs/ccc_data_prep.json` has `species`, `median_nn`, `small_panel`, `n_footprint_genes`.
  A low `n_footprint_genes` on targeted panels is a real caveat to report, not a failure.

## What the script does (order matters: crop → PROGENy activity → slim)

`main()` primes the LR resources, log1p-normalizes, derives `obs['_ct']`, crops to a
contiguous central patch (`crop_central`, never random subsampling), computes the PROGENy
amplitude on the **full** transcriptome (`compute_cell_activity` → `obs['_dact']`), then slims
to LR-candidate genes (`slim_to_lr_genes`), calibrates `median_nn`, builds the shared resource
(`build_shared_resource`), and writes the three artifacts plus the JSON log.

## Common issues

- **Ensembl IDs → ~0 LR pairs (and near-zero PROGENy overlap).** Map Ensembl → symbols first.
- **PROGENy mouse download 404.** The script deliberately loads the human net and upper-cases
  mouse symbols; do not switch to `organism="mouse"`. On targeted panels the overlap is small
  (~100 genes) — record it; the decoupler axis is least reliable there.
- **Standardized coords.** If `obsm['spatial']` is mean-centered/scaled, radii are meaningless.

