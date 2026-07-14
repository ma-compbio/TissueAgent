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
- ccc_consensus_contact.csv — RRA consensus over (LR, sender, receiver) triples in the **contact/juxtacrine** regime (COMMOT `dis_thr_contact`; LIANA `bandwidth = 2 × median_nn`; stLearn direct-neighbour / gridded contact scale).
- ccc_consensus_diffusion.csv — RRA consensus in the **secreted/diffusion** regime (larger dis_thr / bandwidth / gridded distance).
- ccc_high_confidence.csv — intersection shortlist: triples significant (FDR < 0.05) in ≥2 methods AND present in ≥2 methods' LR universes (guarded against method-panel disjointness).
- ccc_panel_coverage.csv — per-method LR-universe size, filtered size, and the pairwise intersection (essential to interpret consensus rankings).
- figures/ccc_consensus_dotplot.png — top-N consensus interactions (RRA p-value); one panel per regime.
- figures/ccc_method_overlap.png — UpSet/Venn of per-method significant sets, per regime.
- figures/ccc_sender_receiver_chord.png — chord of cluster→cluster aggregate signal from the shortlist.

## Step Sketch
Preprocess (with platform calibration) → LIANA+ (rank_aggregate + bivariate) → COMMOT (per-regime) → stLearn (Visium direct OR gridded imaging) → Aggregate + Plot per regime (5 steps total)

## Details
- Step 1 — Apply the `ccc-data-prep` skill. Produces the single, shared `adata` **and** the platform calibration record `logs/ccc_data_prep.json` containing `{platform, resolution_mode, coord_unit, median_nn_um, spot_diameter_um, small_panel}`. Every downstream skill reads this JSON and refuses to run without `median_nn_um`. Detects and REFUSES pre-normalized coordinates.
- Step 2 — Apply the `ccc-liana` skill. Runs `li.mt.rank_aggregate` (cluster-level, orthogonal check) AND, on any spatial input, ALSO runs `li.mt.bivariate` on the `spatial_neighbors` graph with `bandwidth` derived from `median_nn_um`. Writes `liana_res.csv` and (when spatial) `liana_bivariate.csv`. `expr_prop` auto-drops to 0.05 for small (<1000 gene) imaging panels.
- Step 3 — Apply the `ccc-commot` skill. Runs `ct.tl.spatial_communication` **three times, once per CellChatDB signaling category** (`Cell-Cell Contact`, `Secreted Signaling`, `ECM-Receptor`) with `dis_thr_contact / dis_thr_secreted / dis_thr_ecm` derived from `median_nn_um`. Each pathway gets its own `ct.tl.cluster_communication(n_permutations=500)`. Writes `commot_cluster_results.csv` with `signaling_type` + `dis_thr_um` tags on every row.
- Step 4 — Apply the `ccc-stlearn` skill. On `spot_multicell` platforms: direct path (`distance=None`, `spot_mixtures=True` if deconv exists else `False`). On `single_cell` platforms: **grid first** (`st.tl.cci.grid(n_row=125, n_col=125, use_label='_ccc_cell_type')`) per stLearn's Xenium tutorial, then `distance = 3 × median_nn_um`, `spot_mixtures=True`. Writes `stlearn_lr_summary.csv`, `stlearn_per_lr_cci.csv`, and records `gridded=True/False` in `logs/ccc_stlearn.json`.
- Step 5 — Aggregate and plot. Sub-steps:

    **5a. Panel-coverage sanity check.** Build `ccc_panel_coverage.csv` reporting per-method: `n_lr_loaded`, `n_lr_after_expression_filter`, and pairwise intersection sizes. If pairwise intersection <20 LRs, warn — RRA aggregation across near-disjoint LR universes is unreliable.

    **5b. Split by regime.** Route each method's rows into `contact` / `diffusion` buckets:
    - LIANA+ `rank_aggregate` → `diffusion` bucket (it's cluster-level, no spatial scale; treat as the paracrine/co-expression signal).
    - LIANA+ `bivariate` → `contact` bucket (`bandwidth = 2 × median_nn_um` is contact-scale).
    - COMMOT rows → routed by their `signaling_type` column: `Cell-Cell Contact` → `contact`, `Secreted Signaling` + `ECM-Receptor` → `diffusion`.
    - stLearn rows → `contact` when direct-neighbour or gridded contact-distance; when in Visium direct mode, treat as diffusion.

    **5c. Per-method p-value harmonization.** For each method build `[ligand, receptor, source, target, method, pvalue, rank_normalized]`:
    - LIANA+ `rank_aggregate` → use `specificity_rank` as pvalue.
    - LIANA+ `bivariate` → use the local-score global p-value from Moran's R (or `1 - |cosine|` fallback).
    - COMMOT → use the cluster-pair permutation `pvalue` directly.
    - **stLearn (fix)** → RANK `n_sig_spots` within-method as `rank(method='average', pct=True)`, **only for LRs with n_spots ≥ min_spots**. Do NOT use the previous `1/(1 + n_sig_spots)` collapse — it ties every zero-hit LR at exactly the same value and biases the tail.

    **5d. Segmentation-spillover autocrine filter (single-cell platforms only).** For `resolution_mode == 'single_cell'`, drop triples where `source == target` AND the contributing cell-pair distance distribution has median < 1.5 × `median_nn_um` (i.e. immediate segmentation neighbours). Xenium/MERFISH boundary spillover produces false-positive autocrine calls that would dominate the shortlist.

    **5e. RRA within each regime.** For each `(ligand, receptor, source, target)` triple present in ≥2 methods AND in ≥2 methods' LR universes, apply Robust Rank Aggregation (Stuart's method) over per-method normalized ranks → `rra_pvalue`, then BH-FDR → `rra_fdr`. Emit `ccc_consensus_contact.csv` and `ccc_consensus_diffusion.csv`, each sorted by `rra_pvalue`.

    **5f. High-confidence shortlist.** Triples with per-method raw `pvalue < 0.05` in ≥2 methods within the SAME regime → `ccc_high_confidence.csv` with a `regime` column.

    **5g. Plot per regime.** LIANA `li.pl.dotplot` over top-20 RRA triples per regime (two panels); `upsetplot` UpSet of significant sets per regime; `pycirclize` chord of sender→receiver aggregate signal from the shortlist. Save as PNG (dpi=200) AND PDF.

## Evaluation Criteria
- file_exists(ccc_consensus_contact.csv) OR file_exists(ccc_consensus_diffusion.csv) — at least one regime must have rows (an ensemble producing zero contact AND zero diffusion is a run failure, not a null result).
- file_exists(ccc_panel_coverage.csv) AND per-method pairwise LR intersection ≥ 20.
- file_exists(ccc_high_confidence.csv).
- file_exists(figures/ccc_consensus_dotplot.png), figures/ccc_method_overlap.png, figures/ccc_sender_receiver_chord.png.
- Every triple in the consensus CSVs has a non-null rank from ≥2 methods and an `rra_pvalue` in [0, 1].
- The cell-type column used by all three methods is identical (assert against `_ccc_cell_type` in step 5).
- `logs/ccc_data_prep.json` has `median_nn_um` populated; `logs/ccc_commot.json` records `n_permutations >= 500` per regime; `logs/ccc_stlearn.json` records `n_permutations >= 500` and the chosen `spot_mixtures`.
- For `resolution_mode == 'single_cell'`, the autocrine-spillover filter was applied (record the pre/post row counts in a diagnostic column of the consensus CSVs).
