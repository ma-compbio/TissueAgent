# Method I/O, the percentile-rank math, and the shared-universe contract

Deep-dive backing `ccc_aggregate.py`. Read before changing the consensus logic.

## 1. Why aggregation is a clean join now

Earlier designs reconciled three *native* databases downstream (explode complexes to
gene-pairs, RRA, operable-universe padding) because the databases disagree on membership and
granularity:

| DB (method) | pairs | % complex (`_`) |
|---|---|---|
| consensus (LIANA) | ~4600 | 24% |
| CellChatDB (COMMOT) | ~1900 | 48% |
| connectomeDB2020 (stLearn) | ~2300 | 0% |

Pairwise Jaccard: consensus∩CellChatDB ≈ 0.35, consensus∩connectomeDB ≈ 0.33,
**CellChatDB∩connectomeDB ≈ 0.17**. A literal `(ligand, receptor)` join across native DBs
therefore fails to unify a complex with its single-gene subunit and biases the consensus
toward whichever DB is a superset.

We now fix this **upstream**: [[ccc-data-prep]] builds one shared LIANA-consensus **monomeric**
resource (`ccc_lr_common.csv`) and all three methods run on it. Every method reports the same
single-gene `(ligand, receptor)` universe, so aggregation joins on the literal pair — no
explosion, no reconciliation. (The resource is monomeric because stLearn's `L_R` format
can't represent heteromeric complexes — single genes are the common denominator across all
three engines. A complex-aware LIANA+COMMOT lane could be added as a separate 2-method
product, but the primary 3-method consensus stays monomeric.)

## 2. Standardized long schema (each method emits this)

`engine, mode, regime, level, spatial, ligand, receptor, source, target, score,
higher_better, pvalue, contrib_dist`

| engine | mode | level | regime | source/target | score (`higher_better`) |
|---|---|---|---|---|---|
| liana | rank_aggregate | celltype_pair | coexpr | cell types | `specificity_rank` (False) |
| liana | bivariate | lr | contact / diffusion | NaN | `morans` (True), `pvalue=morans_pvals` |
| commot | cluster | celltype_pair | contact / diffusion | cell types | OT cluster strength (True) |
| stlearn | cci | celltype_pair | contact | cell types (undirected) | `n_sig_spots` (True) |

`contrib_dist` is in `obsm['spatial']` units (native), used only by the autocrine filter.

## 3. Engines vs modes

Votes count per **engine**, not per file. LIANA's `rank_aggregate` and `bivariate` are one
`liana` engine; they are collapsed (strongest rank) to a single vote before the ">=2 engines"
gate, so LIANA never self-consensuses. This is why the output column is `engines_sig` and
`n_sig` counts distinct engines.

`bivariate` is LR-level (no direction). It cannot supply a `(source, target)` vote; instead a
bivariate hit at a regime sets `lr_spatial_support=True` on that regime's triples sharing the
LR pair. This lets it corroborate a spatial call without fabricating a sender/receiver.

## 4. Within-method percentile rank (the consensus math)

Within each `(engine, mode, regime)` group, convert `score` to a percentile rank so stronger
evidence → higher `rank_pct` (`higher_better` flips the direction). Collapse each engine's
modes to its strongest rank per triple. Pivot triples × engine → `rank_pct`; then:

- `n_sig` = engines with a non-NaN rank (agreed).
- `consensus_pct` = mean of the engines' `rank_pct` (higher = stronger). This is a
  **descriptive consensus rank**, not a p-value: percentile ranks are comparable across
  methods (they normalize away each method's raw scale), but their mean has no null
  distribution, so we never call it an RRA/FDR p-value.
- `n_capable` = engines whose `<method>_universe.csv` contained the pair (could have found it).

Reporting `n_capable` next to `n_sig` distinguishes "2 of 2 able-to-see agreed" from a blind
"2 of 3", and flags single-universe-only pairs instead of dropping them silently.

## 5. Tiers

- **high**: `n_sig ≥ 2`, `consensus_pct ≥ 0.95`, and at least one spatial engine.
- **supported**: `n_sig ≥ 2`, `consensus_pct ≥ 0.80`.
- **method_specific**: everything else that passed the ≥2-engine + spatial gates.

`ccc_high_confidence.csv` = `{high, supported}`. Tiers are deliberately coarse and threshold
choices are visible in `_tier()` — tune them there, not by post-hoc filtering.

## 6. Autocrine-spillover filter (single-cell only)

On segmented single-cell data a cell's transcripts bleed into touching same-type neighbours,
manufacturing false `source==target` calls. Distance-aware mode drops autocrine triples whose
`contrib_dist < factor × median_nn` (default `factor=1.5`, native units). With no
`contrib_dist`, it drops all autocrine rows and records `categorical_all_autocrine`. No-op on
`spot_multicell`. Pre/post triple counts are attached to every consensus row.

## 7. Regimes

- LIANA `rank_aggregate` → `coexpr` (non-spatial), folded into **both** regimes as
  corroboration but never sole support (`require_spatial`).
- contact: LIANA `bivariate` (contact bw), COMMOT (contact `dis_thr`), stLearn (direct/grid).
- diffusion: LIANA `bivariate` (diffusion bw), COMMOT (diffusion `dis_thr`). stLearn does not
  run a diffusion pass, so diffusion is a 2-spatial-engine regime; that's expected.

All radii are multiples of `median_nn` in native coordinate units (contact `1.5×`, diffusion
`3×`), so the regimes mean the same physical scale across methods regardless of pixel/µm.

## 8. Species

connectomeDB is human-derived, but here all methods use the shared resource, so mouse runs on
`mouseconsensus` (LIANA) and COMMOT's native mouse CellChatDB is bypassed by the shared
`df_ligrec`. If the shared resource can't be mouse-mapped for stLearn, [[ccc-data-prep]] drops
stLearn and this becomes a 2-method LIANA+COMMOT consensus (recorded in the prep log).
