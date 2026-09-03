---
name: ccc_ensemble
status: disabled
description: >
  Ensemble cell-cell communication on spatial transcriptomics: run four
  complementary members — LIANA+ (non-spatial expression consensus), COMMOT
  (spatial optimal transport), stLearn (spatial co-expression) and decoupler+PROGENy
  (downstream transcriptional response) — on ONE shared monomeric ligand-receptor
  resource and one immutable base object, then combine per-LR results by the mean of
  the four members' percentile ranks. Produces a single ranked ensemble table of
  ligand-receptor pairs supported across the expression, spatial and downstream axes.
---

## Inputs
- AnnData (.h5ad) for **one spatial section** with `.obsm['spatial']` (native-unit coords, not
  standardized), raw counts, human or mouse **gene symbols**, and a discrete cell-type / domain
  label column in `.obs` (≥2 categories, ≥10 cells each). If no labels ship with the data,
  derive spatial domains by unsupervised clustering in Step 1.

## Outputs
- **ccc_ensemble.csv** — the final ranked table, one row per LR pair scored by **all four**
  members, sorted by `ensemble_score` descending. Columns: `ligand, receptor, liana_score,
  commot_score, stlearn_score, decoupler_score, liana_pct, commot_pct, stlearn_pct,
  decoupler_pct, ensemble_score`. Ligand/receptor are single genes (shared monomeric resource);
  `ensemble_score ∈ [0,1]` is the mean of the four tools' percentile ranks. The top rows are the
  high-confidence ensemble calls.
- Intermediates (all **data** files): `ccc_base.h5ad` (immutable base, carries `obs['_dact']`),
  `ccc_lr_common.csv` (shared resource), `liana_scores.csv`, `commot_scores.csv`,
  `stlearn_scores.csv`, `decoupler_scores.csv`, `logs/ccc_data_prep.json`.

## Step sketch
Prep + shared resource + PROGENy activity → LIANA (rank_aggregate) → COMMOT (spatial OT) →
stLearn (spatial co-expression) → decoupler (downstream response) → mean-of-percentile-ranks
ensemble (6 steps).

## ⚠️ Fixed, validated pipeline — do not deviate
This ensemble is **exactly** LIANA+ ⊕ COMMOT ⊕ stLearn ⊕ decoupler combined by a
mean-of-percentile-ranks consensus, reproduced from a validated analysis. Each step **ships a
runnable script** under its skill's `scripts/` folder (materialized at
`project/skills/<skill>/scripts/`); run it in the kernel with `%run` (or import its function) —
do not paste code from the skill and do not reimplement the method. Cross-step communication
flows only through the saved **data** artifacts (`ccc_base.h5ad`, `ccc_lr_common.csv`,
`*_scores.csv`, the JSON log). Run each skill's shipped script **exactly** as written (do not
edit the script bodies). Do **not**: drop or add a member
(the four are fixed), add a second COMMOT/stLearn distance regime, add cluster-level permutation
tests, change the scores or the mean-of-percentile-ranks combiner (not `min`, not weighted), add
p-values/FDR, or add any evaluation/benchmark metrics. If a step fails, fix the environment or
the inputs — never the method.

## Architecture (read once)
The four members measure genuinely different, weakly-correlated quantities, and that is the point:
- **LIANA+ `rank_aggregate`** — non-spatial expression consensus. Rewards specific, strong LR
  co-expression across cell groups; blind to physical location.
- **COMMOT `spatial_communication`** — spatial optimal transport. Scores a pair only if ligand
  can be routed to nearby receptor within a distance threshold; spatially precise but ignores
  cell-group specificity and can route weak signal.
- **stLearn `cci.lr`** — spatial co-expression. Rewards a ligand spot whose neighbours express
  the receptor (and vice versa); a local co-presence statistic on the same radius graph,
  complementary to COMMOT's global transport (the two are ~0.84 correlated).
- **decoupler + PROGENy** — downstream transcriptional response. Asks whether the receiving
  cells show a downstream pathway response; built on footprint genes disjoint from the LR genes,
  so it is orthogonal to the three co-presence/routing members by construction (per-pair Spearman
  ≈ 0.02–0.17 vs the others). This is the decorrelated member that lifts the ensemble above the
  individual tools — the earlier 2-member (LIANA+COMMOT) ensemble was mid-pack; adding the
  orthogonal spatial and downstream axes moves it to the top of a balanced multi-metric panel.

The ensemble promotes a pair only when it ranks high **across these axes**, which strips each
member's characteristic false positives. All four run on **one shared monomeric LR resource**
(built in Step 1) — the members' native databases overlap only ~0.17 Jaccard, so without a
shared resource "consensus" would measure database agreement, not method agreement. All spatial
thresholds stay in the **native coordinate units** the methods consume (a multiple of
`median_nn`); COMMOT does not convert pixels to µm.

## Details
- **Step 1 — [[ccc-data-prep]].** Runs the shipped `ccc_data_prep.py` (via `%run` with
  `--adata/--cell-type/--species` flags), which writes the **immutable** `ccc_base.h5ad` (log1p `.X`,
  `layers['counts']`, `obs['_ct']`, native-unit `obsm['spatial']`, and `obs['_dact']` = the
  PROGENy per-cell response amplitude); the **shared resource** `ccc_lr_common.csv` (monomeric,
  expression-filtered, capped at `MAX_PAIRS`); and
  `logs/ccc_data_prep.json` with `species`, `median_nn` (native units), `small_panel`,
  `dis_mult`, `knn_k`, `n_footprint_genes`. Subsets to a contiguous central patch (`crop_central`,
  `CROP_N`) and, **crucially, computes the PROGENy activity on the full transcriptome BEFORE
  gene-slimming** (footprint genes are mostly non-LR), then `slim_to_lr_genes`. Every downstream
  skill **copies** the base — nothing overwrites it.
- **Step 2 — [[ccc-liana]].** `run_liana` → LIANA+ `rank_aggregate` on the shared resource
  (`use_raw=False`), scoring each pair `liana_score = 1 - min magnitude_rank`. Emits
  `liana_scores.csv` (`ligand, receptor, liana_score`).
- **Step 3 — [[ccc-commot]].** `run_commot` → COMMOT `spatial_communication` on the shared
  resource at a single `dis_thr = 1.5 × median_nn`, scoring each routed pair by total OT flow.
  No global random subsampling (it invalidates the OT solution). Emits `commot_scores.csv`
  (`ligand, receptor, commot_score`).
- **Step 4 — [[ccc-stlearn]].** `run_stlearn` → the vectorised stLearn `cci.lr` co-expression
  statistic on the shared resource at the **same** `dis_thr = 1.5 × median_nn`, scoring each
  pair by its summed neighbourhood co-expression. Emits `stlearn_scores.csv`
  (`ligand, receptor, stlearn_score`).
- **Step 5 — [[ccc-decoupler]].** `run_decoupler` → on an independent kNN graph, scores each
  pair by whether its actively-receiving cells (receptor present AND ligand arriving) co-locate
  with the downstream PROGENy response `obs['_dact']` from Step 1. Emits `decoupler_scores.csv`
  (`ligand, receptor, decoupler_score`).
- **Step 6 — [[ccc-aggregate]].** `build_ensemble` → over the pairs scored by **all four**
  members, percentile-rank each score and take the **mean**. Emits the final `ccc_ensemble.csv`,
  sorted by `ensemble_score`.

## Evaluation criteria (of the run, not the method)
- `file_exists(ccc_ensemble.csv)` and it is non-empty (all four `*_scores.csv` had overlapping
  LR pairs; empty ⇒ a run failure upstream, not a null result).
- Each member is produced by running its skill's shipped script
  (`%run project/skills/<skill>/scripts/*.py`) — not by pasting or reimplementing the code.
  `ccc_base.h5ad`, `ccc_lr_common.csv`, `liana_scores.csv`, `commot_scores.csv`,
  `stlearn_scores.csv`, `decoupler_scores.csv` all exist.
- Every ensemble row has all four member scores populated (the universe is the intersection by
  design) and single-gene ligand/receptor.
- `ccc_base.h5ad` carries `obs['_dact']`; `logs/ccc_data_prep.json` has `median_nn` and
  `n_footprint_genes` populated; COMMOT and stLearn used `dis_thr = dis_mult × median_nn`.
- The cell/domain column used by LIANA is `_ct`.

## Notes on the members (not dataset-specific)
- **stLearn ≈ COMMOT** (~0.84 correlated) — keep both anyway; together they still add a spatial
  axis decorrelated from expression and downstream, and dropping stLearn is a different method.
- **decoupler is the orthogonal member but the least reproducible** — it is what lifts the
  ensemble on spatial coherence and cell-type adjacency, at some cost to cross-fold stability.
  The `mean` combiner (not the old `min`) is what recovers its gains. On very sparse targeted-
  imaging panels its PROGENy footprint overlap is small (~100 genes) and it is the least
  reliable axis; report `n_footprint_genes` but do not drop the member.
