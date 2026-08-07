---
name: ccc_ensemble
status: enabled
description: >
  Ensemble cell-cell communication on spatial transcriptomics: run LIANA+
  (non-spatial expression consensus) and COMMOT (spatial optimal transport) on
  ONE shared monomeric ligand-receptor resource and one immutable base object,
  then combine per-LR results with a within-method percentile-rank consensus.
  Produces a single ranked ensemble table of ligand-receptor pairs supported by
  BOTH the expression and spatial axes.
---

## Inputs
- AnnData (.h5ad) for **one spatial section** with `.obsm['spatial']` (native-unit coords, not
  standardized), raw counts, human or mouse **gene symbols**, and a discrete cell-type / domain
  label column in `.obs` (≥2 categories, ≥10 cells each). If no labels ship with the data,
  derive spatial domains by unsupervised clustering in Step 1.

## Outputs
- **ccc_ensemble.csv** — the final ranked table, one row per LR pair scored by **both** tools,
  sorted by `ensemble_score` descending. Columns: `ligand, receptor, liana_score,
  commot_score, liana_pct, commot_pct, ensemble_score`. Ligand/receptor are single genes
  (shared monomeric resource); `ensemble_score ∈ [0,1]` is the mean of the two tools'
  percentile ranks. The top rows are the high-confidence ensemble calls.
- Intermediates: `ensemble_ccc.py` (shared library), `ccc_base.h5ad` (immutable base),
  `ccc_lr_common.csv` (shared resource), `liana_scores.csv`, `commot_scores.csv`,
  `logs/ccc_data_prep.json`.

## Step sketch
Prep + shared library + shared resource → LIANA (rank_aggregate) → COMMOT (spatial OT) →
percentile-rank ensemble (4 steps).

## ⚠️ Fixed, validated pipeline — do not deviate
This ensemble is **exactly** LIANA+ ⊕ COMMOT combined by percentile-rank consensus, reproduced
from a validated analysis. The method code lives in `ensemble_ccc.py` (written verbatim in
Step 1); every step imports from it and uses the driver in its skill **exactly**. Do **not**:
add or swap methods (no stLearn, no bivariate, no cluster-level permutation tests), add a
second COMMOT regime, change scores or the 50/50 percentile weighting, add p-values/FDR, or add
any evaluation/benchmark metrics. If a step fails, fix the environment or the inputs — never
the method.

## Architecture (read once)
The two methods measure genuinely different quantities, and that is the point:
- **LIANA+ `rank_aggregate`** — non-spatial expression consensus. Rewards specific, strong LR
  co-expression across cell groups; blind to physical location.
- **COMMOT `spatial_communication`** — spatial optimal transport. Scores an LR pair only if
  ligand can be routed to nearby receptor within a distance threshold; spatially precise but
  ignores cell-group specificity and can route weak signal.

The ensemble promotes a pair only when **both** axes agree, which strips LIANA's
spatially-incoherent hits and COMMOT's low-expression hits. Both tools run on **one shared
monomeric LR resource** (built in Step 1) — their native databases overlap only ~0.17 Jaccard,
so without a shared resource "consensus" would measure database agreement, not method
agreement. All spatial thresholds stay in the **native coordinate units** the methods consume
(a multiple of `median_nn`); COMMOT does not convert pixels to µm.

## Details
- **Step 1 — [[ccc-data-prep]].** Writes the verbatim **shared library** `ensemble_ccc.py`; the
  **immutable** `ccc_base.h5ad` (log1p `.X`, `layers['counts']`, `obs['_ct']`, native-unit
  `obsm['spatial']`); the **shared resource** `ccc_lr_common.csv` (monomeric, expression-
  filtered, capped at `MAX_PAIRS`); and `logs/ccc_data_prep.json` with `species`, `median_nn`
  (native units), `small_panel`, `dis_mult`. Subsets to LR-candidate genes and, for COMMOT
  tractability, to a contiguous central patch (`crop_central`, `CROP_N`). Every downstream skill
  **copies** the base — nothing overwrites it.
- **Step 2 — [[ccc-liana]].** `run_liana` → LIANA+ `rank_aggregate` on the shared resource
  (`use_raw=False`), scoring each pair `liana_score = 1 - min magnitude_rank`. Emits
  `liana_scores.csv` (`ligand, receptor, liana_score`).
- **Step 3 — [[ccc-commot]].** `run_commot` → COMMOT `spatial_communication` on the shared
  resource at a single `dis_thr = 1.5 × median_nn`, scoring each routed pair by total OT flow.
  No global random subsampling (it invalidates the OT solution). Emits `commot_scores.csv`
  (`ligand, receptor, commot_score`).
- **Step 4 — [[ccc-aggregate]].** `build_ensemble` → over the pairs scored by **both** tools,
  percentile-rank each score and take the mean. Emits the final `ccc_ensemble.csv`, sorted by
  `ensemble_score`.

## Evaluation criteria (of the run, not the method)
- `file_exists(ccc_ensemble.csv)` and it is non-empty (both `*_scores.csv` had overlapping LR
  pairs; empty ⇒ a run failure upstream, not a null result).
- `ensemble_ccc.py` was written verbatim and imports cleanly; `ccc_base.h5ad`,
  `ccc_lr_common.csv`, `liana_scores.csv`, `commot_scores.csv` all exist.
- Every ensemble row has both `liana_score` and `commot_score` populated (the universe is the
  intersection by design) and single-gene ligand/receptor.
- `logs/ccc_data_prep.json` has `median_nn` populated; COMMOT used `dis_thr = dis_mult ×
  median_nn`.
- The cell/domain column used by LIANA is `_ct`.

## The three reference datasets (one section each)
- **Human lymph-node Visium** — `spot`, human, `consensus`. No labels ship → derive domains by
  unsupervised clustering (e.g. KMeans on PCA of HVGs) in Step 1.
- **Human DLPFC Visium** — `spot`, human. Subset to one section (e.g. `sample_name == 151673`);
  map Ensembl var_names to symbols; use `layer_guess` cortical layers as domain labels.
- **Mouse hypothalamus MERFISH** — `single_cell`, mouse. Subset to one animal/Bregma slice;
  drop `control`/blank features; use `Cell_class` labels; use the `mouseconsensus` resource.
</content>
