---
name: ccc_ensemble
status: enabled
description: >
  Ensemble cell-cell communication analysis on spatial transcriptomics data:
  runs LIANA+, COMMOT, and stLearn on the same preprocessed object, then
  aggregates per-(LR, sender, receiver) results across methods via Robust
  Rank Aggregation. Produces a consensus ranked table, an intersection
  shortlist of LRs significant under all three methods, and three figures.
---

## Inputs
- AnnData (.h5ad) with .obsm['spatial'] (or obs['x','y']), human or mouse gene symbols, and a cell-type column in .obs.

## Outputs
- ccc_consensus_ranked.csv — every (LR, sender, receiver) triple scored by all three methods, with an RRA aggregated p-value and BH-FDR.
- ccc_high_confidence.csv — intersection shortlist: triples significant (FDR < 0.05) in all three methods.
- figures/ccc_consensus_dotplot.png — top-N consensus interactions (RRA p-value).
- figures/ccc_method_overlap.png — UpSet/Venn of per-method significant sets.
- figures/ccc_sender_receiver_chord.png — chord of cluster→cluster aggregate signal from the shortlist.

## Step Sketch
Preprocess → LIANA+ → COMMOT → stLearn → Aggregate + Plot (5 steps total)

## Details
- Step 1 — Apply the `ccc-data-prep` skill. Produces the single, shared `adata` that all three methods consume (raw layer + log-normalized .X + cell-type column verified + species-correct gene symbols + spatial coords confirmed). DO NOT re-preprocess between methods; stLearn's quirk (it wants normalized-but-not-log1p counts) is handled inside the stLearn skill from the saved `layers['norm_no_log']`.
- Step 2 — Apply the `ccc-liana` skill with `groupby='_ccc_cell_type'`, `resource_name='consensus'` (human) or `'mouseconsensus'` (mouse), `expr_prop=0.1`. Writes results to `adata.uns['liana_res']` and `liana_res.csv`.
- Step 3 — Apply the `ccc-commot` skill. Loads CellChatDB matching species, runs `ct.tl.spatial_communication`, then `ct.tl.cluster_communication(..., clustering='_ccc_cell_type', n_permutations=500)` per pathway so a per-pathway p-value lands in `adata.uns['commot_cluster-...']`. Writes flat `commot_cluster_results.csv`.
- Step 4 — Apply the `ccc-stlearn` skill. Runs `st.tl.cci.run` (LR hotspot test) → `st.tl.cci.adj_pvals` → `st.tl.cci.run_cci(use_label='_ccc_cell_type', spot_mixtures=False, n_perms=500)`. Per-LR cluster CCI lands in `adata.uns['per_lr_cci__ccc_cell_type']`. Writes `stlearn_lr_summary.csv` and `stlearn_per_lr_cci.csv`.
- Step 5 — Aggregate and plot. For each method, build a long-format DataFrame with columns `[ligand, receptor, source, target, method, pvalue, rank_normalized]`:
    - LIANA+ → `liana_res.csv`; use `specificity_rank` as `pvalue` (already a normalized rank with permutation semantics).
    - COMMOT → `commot_cluster_results.csv`; use the cluster-pair permutation `pvalue` from `ct.tl.cluster_communication`.
    - stLearn → `stlearn_per_lr_cci.csv`; convert `n_sig_spots` to a pseudo-pvalue with `1 / (1 + n_sig_spots)` before within-method ranking.
  Concatenate; for each `(ligand, receptor, source, target)` triple present in ≥2 methods, apply Robust Rank Aggregation (Stuart's method) over per-method normalized ranks → `rra_pvalue`, then BH-FDR → `rra_fdr`. Write `ccc_consensus_ranked.csv` sorted by `rra_pvalue`.
  Compute the intersection shortlist: triples with per-method raw `pvalue < 0.05` in all three methods → `ccc_high_confidence.csv`.
  Plot: LIANA `li.pl.dotplot` over the top-20 RRA triples (uses `adata.uns['liana_res']` already loaded); a `matplotlib`/`upsetplot` UpSet of the three significant sets; a `pycirclize` chord of sender→receiver aggregate signal from the shortlist. Save as PNG (dpi=200) AND PDF where the format supports it. See the RRA snippet in `[[ccc-data-prep]]`'s References for the canonical implementation.

## Evaluation Criteria
- file_exists(ccc_consensus_ranked.csv) AND row_count > 0
- file_exists(ccc_high_confidence.csv)
- file_exists(figures/ccc_consensus_dotplot.png)
- file_exists(figures/ccc_method_overlap.png)
- file_exists(figures/ccc_sender_receiver_chord.png)
- Every triple in ccc_consensus_ranked.csv has a non-null rank from ≥2 methods and an `rra_pvalue` in [0, 1].
- The cell-type column used by all three methods is identical (sanity-check via assertion in step 5).
