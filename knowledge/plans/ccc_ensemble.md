---
name: ccc_ensemble
status: enabled
description: >
  Ensemble cell-cell communication on spatial transcriptomics: run LIANA+,
  COMMOT, and stLearn on ONE shared ligand-receptor resource and one immutable
  base object, then combine per-(LR, sender, receiver) results with a
  within-method percentile-rank consensus. Produces a consensus table per
  spatial regime, a high-confidence shortlist, per-method coverage, and figures.
---

## Inputs
- AnnData (.h5ad) with `.obsm['spatial']` (or `obs['x','y']`), human or mouse gene symbols,
  and a cell-type column (discrete labels or deconvolution proportions) in `.obs`.

## Outputs
- ccc_consensus_contact.csv / ccc_consensus_diffusion.csv — consensus over
  `(ligand, receptor, source, target)` triples per regime (contact = `1.5 × median_nn`;
  diffusion = `3 × median_nn`, in native coordinate units). Ligand/receptor are single genes
  (shared monomeric resource). Columns include `engines_sig, n_sig, n_capable, any_spatial,
  lr_spatial_support, consensus_pct, tier`.
- ccc_high_confidence.csv — triples with `tier ∈ {high, supported}`, tagged with `regime`.
- ccc_panel_coverage.csv + ccc_panel_overlap.json — per-method operable universe and
  pairwise/3-way overlap (incl. Jaccard). Makes explicit how much the methods could even agree.
- figures/ccc_consensus_dotplot.png — top-N consensus triples, one panel per regime.
- figures/ccc_method_overlap.png — UpSet/Venn of per-method significant sets.
- figures/ccc_sender_receiver_chord.png — sender→receiver chord from the shortlist.

## Step sketch
Prep + shared resource → LIANA (rank_aggregate + bivariate) → COMMOT (two regimes) →
stLearn (direct or gridded) → percentile-rank consensus + plots (5 steps).

## Architecture (read once)
The three methods' native databases overlap far less than their names suggest
(CellChatDB↔connectomeDB ≈ 0.17 Jaccard), so running each on its own DB makes the "consensus"
a database artifact. This ensemble avoids that by harmonizing **one shared LIANA-consensus
resource** across all three methods (built in step 1), and by keeping all spatial thresholds
in the **native coordinate units** the methods actually consume (multiples of `median_nn`) —
neither COMMOT nor stLearn nor LIANA converts pixels to µm. Because everyone tests the same
single-gene pairs, aggregation is a clean within-method percentile-rank consensus (step 5),
not a database reconciliation.

## Details
- **Step 1 — [[ccc-data-prep]].** Writes the **immutable** `ccc_base.h5ad` (log1p `.X`,
  `layers['counts']`, `layers['norm_no_log']`, `_ccc_cell_type`, `imagecol`/`imagerow`), the
  **shared resource** (`ccc_lr_common.csv`, monomeric — stLearn can't represent complexes), and
  `logs/ccc_data_prep.json` with `median_nn` (native units), `resolution_mode` (observation
  unit, not product name), `sample_col`, `has_deconv`, `small_panel`. Refuses standardized
  coordinates and <2-category / <10-cell labels. Every downstream skill **copies** the base
  and writes its own outputs — nothing overwrites `ccc_base.h5ad`.

- **Step 2 — [[ccc-liana]].** `rank_aggregate` (directed cell-type consensus, **non-spatial**,
  `use_raw=False`) and, on spatial input, `bivariate` at two bandwidths (contact `1.5×`,
  diffusion `3×` `median_nn`) — LR-level spatial hotspots (Moran's), no direction. `bivariate`
  **returns** a new AnnData (scores in `.X`, `.layers['pvals']`, per-LR `.var`) — not
  `.uns['local_scores']`. Emits `liana_ccc.csv` (standardized long) + `liana_universe.csv`.
  `expr_prop` drops to 0.05 for small (<1000-gene) panels.

- **Step 3 — [[ccc-commot]].** `spatial_communication` on the shared `df_ligrec` at two
  `dis_thr` (contact/diffusion), then per-**LR** `cluster_communication(lr_pair=…,
  n_permutations=500)` (not pathway-level — that ties ranks) with BH correction. No global
  random subsampling (it invalidates the OT solution) — run per section/ROI if large. Emits
  `commot_ccc.csv` (with `contrib_dist`) + `commot_universe.csv`.

- **Step 4 — [[ccc-stlearn]].** Version preflight (modern ≥1.x CCI API; upgrade if the
  runtime has old 0.2.x). Shared resource as `"lig_rec"` strings (no `load_lrs`). Direct on
  `spot_multicell`; on `single_cell` **grid raw counts first** then normalize (no log1p).
  `run` + `adj_pvals` + `run_cci`. Cell-type-pair support is **undirected** — corroborates the
  pair; direction comes from LIANA/COMMOT. Emits `stlearn_ccc.csv` (with `contrib_dist`) +
  `stlearn_universe.csv`.

- **Step 5 — [[ccc-aggregate]].** Loads the three standardized CSVs, applies the single-cell
  autocrine-spillover filter (`--resolution-mode`/`--median-nn` from the prep log),
  percentile-ranks within each method, collapses LIANA's two modes to one `liana` engine,
  counts votes per engine, and writes the per-regime consensus + shortlist + coverage. The
  result is a **descriptive consensus rank**, not an RRA/FDR p-value. Then plot per regime
  (dotplot, UpSet, chord; PNG dpi=200 + PDF). Run `ccc_aggregate.py --selftest` first.

## Evaluation criteria
- file_exists(ccc_consensus_contact.csv) OR file_exists(ccc_consensus_diffusion.csv) — at
  least one regime has rows (both empty ⇒ run failure upstream, not a null result).
- file_exists(ccc_panel_coverage.csv) AND file_exists(ccc_panel_overlap.json); the 3-way
  overlap is reported (if small, the summary says the consensus leans on the largest universe).
- file_exists(ccc_high_confidence.csv) and the three figures.
- Every consensus triple has `n_sig ≥ 2` distinct engines (`engines_sig` never a single
  engine — LIANA's two modes count once), and `any_spatial` or `lr_spatial_support` is True,
  and single-gene ligand/receptor.
- Each method wrote its `<method>_universe.csv`, so `n_capable` is real.
- The cell-type column used by all three methods is `_ccc_cell_type`.
- `logs/ccc_data_prep.json` has `median_nn` populated (and on Visium, `median_nn_um` either in
  the ~70–160 µm band or null); `logs/ccc_commot.json` records `n_permutations >= 500`;
  `logs/ccc_stlearn.json` records the modern-API version, `gridded`, and `spot_mixtures`.
- On `single_cell`, the autocrine filter ran: consensus CSVs carry
  `n_triples_pre_autocrine ≥ n_triples_post_autocrine` and `autocrine_filter ∈
  {distance_aware, categorical_all_autocrine}`.

## The three benchmark datasets
- **Human lymph-node Visium** — `spot_multicell`, human, `consensus`. Discrete labels or
  cell2location proportions (set `has_deconv`); dominant-label cell-type calls are approximate.
- **Human DLPFC Visium** — `spot_multicell`, human. Published layer labels (one-hot, not true
  deconvolution) → `spot_mixtures=False`; interpret as spot-domain communication.
- **Mouse hypothalamus MERFISH** — `single_cell`, mouse. Coordinates already µm →
  `median_nn_um = median_nn`. Grid stLearn; autocrine filter active. Use `mouseconsensus`; the
  shared resource bypasses stLearn's human connectomeDB (record the mouse handling).
