---
name: ccc-aggregate
description: Combine LIANA+, COMMOT, and stLearn ligand-receptor calls into a cross-method consensus for the ccc_ensemble workflow. Because all three methods ran on ONE shared resource (from ccc-data-prep), this is a clean within-method percentile-rank consensus over shared single-gene pairs — no database reconciliation. Splits contact vs diffusion regimes, counts votes per engine, filters single-cell autocrine spillover, and reports per-method operable coverage. Step 5 of the ccc_ensemble plan.
applies_to: [coding_agent]
tags: [ccc, ligand-receptor, aggregation, consensus]
status: enable
---

# CCC — Cross-method consensus

## When to use

**Step 5 of the `ccc_ensemble` plan**, after [[ccc-liana]], [[ccc-commot]], and
[[ccc-stlearn]] each wrote their standardized long CSV. This skill ranks and combines them.
Not a standalone CCC method.

## Why this is simple now

The hard part of cross-method CCC — reconciling three databases that disagree on membership
and granularity (LIANA/COMMOT name the `TGFBR1_TGFBR2` complex; stLearn names `TGFBR1`;
CellChatDB↔connectomeDB overlap ≈ 0.17 Jaccard) — is solved **upstream**: [[ccc-data-prep]]
builds one shared LIANA-consensus monomeric resource and all three methods run on it. So every
method reports the same single-gene `(ligand, receptor)` universe, and aggregation is a clean
join with no complex explosion.

Following the audit's guidance, we convert each method's native score to a **within-method
percentile rank**, then take the consensus of ranks. The output is a descriptive *consensus
rank*, **not** an RRA/BH p-value — custom rank aggregation is not calibrated across these
heterogeneous lists, so we don't dress it up as one.

## Input (project `outputs/`)

Each method writes one standardized long CSV with this schema:

`engine, mode, regime, level, spatial, ligand, receptor, source, target, score,
higher_better, pvalue, contrib_dist`

- `liana_ccc.csv` — `rank_aggregate` (level `celltype_pair`, regime `coexpr`, non-spatial) +
  `bivariate` (level `lr`, regime `contact`/`diffusion`, spatial).
- `commot_ccc.csv` — `cluster` (level `celltype_pair`, regime `contact`/`diffusion`, spatial).
- `stlearn_ccc.csv` — `cci` (level `celltype_pair`, regime `contact`, spatial, undirected).
- `<method>_universe.csv` *(one per method)* — operable `(ligand,receptor)` pairs; drives
  `n_capable` and coverage. If absent, `n_capable` is `NaN` and coverage is skipped.

## Output

- `ccc_consensus_contact.csv`, `ccc_consensus_diffusion.csv` — consensus per regime. Columns:
  `ligand, receptor, source, target, engines_sig, n_sig, n_capable, any_spatial,
  lr_spatial_support, consensus_pct, tier, n_triples_pre_autocrine,
  n_triples_post_autocrine, autocrine_filter`. `consensus_pct` = mean within-method
  percentile rank (higher = stronger); `tier ∈ {high, supported, method_specific}`.
- `ccc_high_confidence.csv` — `tier ∈ {high, supported}`, tagged with `regime`.
- `ccc_panel_coverage.csv` + `ccc_panel_overlap.json` — per-method operable-universe size and
  pairwise/3-way overlap (incl. Jaccard).

## Consensus rules (the important part)

- **Votes count per engine** (`liana`/`commot`/`stlearn`), never per mode. LIANA's
  `rank_aggregate` and `bivariate` are two modes of one engine — collapsed to a single
  `liana` vote, so LIANA can corroborate but never self-consensus.
- **Directed cell-type consensus** is over `(ligand, receptor, source, target)` at
  `level=celltype_pair`: LIANA `rank_aggregate` (folded into both regimes as co-expression
  corroboration), COMMOT `cluster`, stLearn `cci`. LIANA `bivariate` is LR-level and sets the
  `lr_spatial_support` flag on matching triples — it never invents a direction.
- **`require_spatial`** drops a row supported only by the non-spatial LIANA `rank_aggregate`
  (co-expression alone is not spatial communication).
- **Autocrine filter** (single-cell only): drops `source==target` triples whose
  `contrib_dist < 1.5 × median_nn` (segmentation spillover). No-op on `spot_multicell`.
- **Regimes stay separate**: a call strong in `contact` but absent in `diffusion` is
  scale-sensitive — report it, don't merge.
- **Missing = NaN, never 0.** `n_capable` (engines whose shared universe held the pair) sits
  next to `n_sig` (engines that agreed), so you can say "2 of the 2 able to see it agreed".

## Success criteria

- At least one regime CSV has rows (both empty ⇒ a run failure upstream, not a null result —
  investigate, don't lower thresholds).
- Every row has `n_sig ≥ 2` distinct engines (`engines_sig` is never a single engine), and
  either `any_spatial` or `lr_spatial_support` is True.
- On `single_cell` input the autocrine filter ran: `autocrine_filter ∈ {distance_aware,
  categorical_all_autocrine}` and `n_triples_pre_autocrine ≥ n_triples_post_autocrine`.
- Ligand/receptor are single genes (guaranteed by the shared monomeric resource).
- `ccc_panel_overlap.json` reports the real 3-way overlap; if small, say the consensus leans
  on whichever universe is largest — don't present it as three independent confirmations.

## Workflow

1. Confirm the three method CSVs exist. Missing one ⇒ 2-method consensus; record which.
2. Run the aggregator (from `outputs/`; `<assets_root>` is the Assets root printed above):

   ```bash
   python <assets_root>/scripts/ccc_aggregate.py \
     --liana liana_ccc.csv --commot commot_ccc.csv --stlearn stlearn_ccc.csv \
     --univ-liana liana_universe.csv --univ-commot commot_universe.csv \
     --univ-stlearn stlearn_universe.csv \
     --resolution-mode "$(python -c 'import json;print(json.load(open("logs/ccc_data_prep.json"))["resolution_mode"])')" \
     --median-nn "$(python -c 'import json;print(json.load(open("logs/ccc_data_prep.json"))["median_nn"])')" \
     --out .
   ```

   Drop flags for any file you don't have. Pass `--resolution-mode`/`--median-nn` (native
   units, from the prep log) so the single-cell autocrine filter runs.
3. Read `ccc_panel_overlap.json`; report the 3-way overlap in your summary.
4. Plot per regime: `li.pl.dotplot` over the top-20 consensus triples per regime; an UpSet of
   per-method significant sets; a sender→receiver chord from `ccc_high_confidence.csv`.
   Save PNG (dpi=200) + PDF.

Run `python <assets_root>/scripts/ccc_aggregate.py --selftest` once to verify the unification,
single-engine, and autocrine-filter invariants.

## Bundled scripts

| Script | Use |
|---|---|
| `scripts/ccc_aggregate.py` | Load → autocrine filter → within-method percentile rank → per-regime consensus. Importable and a CLI (`--help`, `--selftest`). |

Importable:

```python
import sys; sys.path.insert(0, "<assets_root>/scripts")
from ccc_aggregate import load_long, build_consensus, high_confidence, panel_coverage
```

## Common issues

- **Consensus empty though each method found plenty.** Usually the standardized CSVs weren't
  emitted with the schema above, or a `regime`/`level` value is off. Check one method's CSV
  columns against the schema.
- **A method contributes nothing.** Check its `<method>_universe.csv`: COMMOT loses pairs
  below its expression filter; stLearn contributes only pairs above `min_spots`. Low coverage
  is a real ceiling — report it.
- **Everything is `method_specific`.** Fewer than 2 engines agreed on most triples — expected
  when the biology is genuinely method-divergent or a method under-ran; not a bug to threshold
  away.
- **Mouse.** If stLearn was dropped (connectomeDB is human-derived; see [[ccc-data-prep]]),
  this is a 2-method LIANA+COMMOT consensus — pass only the two files.

## References

- `references/method-io.md` — exact per-method column maps, the percentile-rank math, the
  regime/engine semantics, and the operable-universe contract.
- Upstream skills: [[ccc-data-prep]], [[ccc-liana]], [[ccc-commot]], [[ccc-stlearn]];
  parent plan `ccc_ensemble`.
