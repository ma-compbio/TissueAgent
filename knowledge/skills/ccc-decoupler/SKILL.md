---
name: ccc-decoupler
description: Step 5 of the ccc_ensemble workflow. The downstream-response member. Runs the shipped run_decoupler scorer, scoring each shared-resource LR pair by whether its actively-receiving cells (receptor present AND ligand arriving over a kNN graph) co-locate with the PROGENy downstream response amplitude computed in ccc-data-prep (obs['_dact']). Writes decoupler_scores.csv for the ensemble aggregator.
applies_to: [coding_agent]
tags: [ccc, decoupler, progeny, downstream, pathway, ensemble]
status: enable
---

# CCC — decoupler + PROGENy (downstream-response axis)

## ⚠️ How to run this

This skill **ships a runnable script** — do NOT write your own decoupler step and do NOT
paste code from this file. Run the shipped script in the kernel:

```python
%run project/skills/ccc-decoupler/scripts/ccc_decoupler.py
```

It reads the per-cell activity that [[ccc-data-prep]] stored in `obs['_dact']`, scores every
pair, and writes `decoupler_scores.csv`. If you need the scorer as a function instead, import
it (do not reimplement it):

```python
import sys; sys.path.insert(0, "project/skills/ccc-decoupler/scripts")
from ccc_decoupler import run_decoupler
```

The script is authoritative. Do **not** recompute PROGENy here (the slimmed base no longer
has the full transcriptome — it reads `obs['_dact']`), do not call `dc.op.progeny`/`dc.mt.ulm`
again, and do not build your own weight-matrix score. The statistic is the **signed, z-centred
coherence** `D = mean_i[z(recv)_i · z(a)_i]` — it takes **both signs** (a result where every
`decoupler_score` is positive means the statistic was changed). It uses `k = knn_k` from the
JSON log (it is **6**); do not raise it. If it fails, fix the environment/inputs.

## When to use

Step 5 of the `ccc_ensemble` plan, after [[ccc-data-prep]]. This is the **only mechanistically
orthogonal** member. The other three all measure LR *co-presence* (expression in [[ccc-liana]],
OT routing in [[ccc-commot]], neighbourhood co-expression in [[ccc-stlearn]]) and are 0.30–0.84
correlated. This one asks whether the **receiving cells show a downstream transcriptional
response**, built on PROGENy footprint genes disjoint from the LR genes, so its per-pair score
is decorrelated from the other three (per-pair Spearman ≈ 0.02–0.17). That decorrelation is
why adding it improves the ensemble.

## The method (two stages)

**Stage 1 — per-cell response amplitude (already done in [[ccc-data-prep]]).** On the full
log-normalised transcriptome, decoupler's ULM with the PROGENy network gives a cells × ~14
activity matrix, reduced to a per-cell amplitude `a_i = ‖z(activity_i)‖₂` and stored in
`obs['_dact']`. This step just reads it.

**Stage 2 — per-pair score (this step, in the shipped script).** On an independent
row-normalised kNN graph `W`:

```
recv_i  = z(R)_i · (W · z(L))_i          # receptor present AND ligand arriving from neighbours
D(pair) = mean_i [ z(recv)_i · z(a)_i ]  # active-receiving co-located with downstream response
```

## Input (data files from Step 1)

- `project/outputs/ccc_base.h5ad` — `.X` log1p, `obsm['spatial']`, and **`obs['_dact']`**.
- `project/outputs/ccc_lr_common.csv` — shared monomeric resource.
- `project/outputs/logs/ccc_data_prep.json` — read `knn_k` and `n_footprint_genes`.

## Output

- `project/outputs/decoupler_scores.csv` — columns `ligand, receptor, decoupler_score`
  (higher = receiving cells respond more strongly). One row per LR pair.

## Success criteria

- `decoupler_scores.csv` has columns `ligand, receptor, decoupler_score` and is non-empty.
- `obs['_dact']` was present in `ccc_base.h5ad` (else re-run [[ccc-data-prep]] — activity
  cannot be recomputed here, the base is gene-slimmed).
- Scores are finite; both signs are expected (a centred coherence statistic).

## What the script does

`_knn_W(coords, k)` builds a row-normalised kNN operator, and `run_decoupler(adata_slim,
resource, cell_activity, k)` computes `D(pair) = mean_i[z(recv)_i · z(a)_i]` per pair from the
LR genes plus the precomputed `_dact` amplitude. `main()` reads `knn_k` from the prep log,
asserts `obs['_dact']` is present, scores, and writes `decoupler_scores.csv`.

## Honest limitations (report these)

- **PROGENy is a coarse downstream proxy** (~14 pathways) — captures *that* cells respond, not
  *which* receptor drove it.
- **Reproducibility is this member's weak spot** — `D` is the least stable member across
  spatial folds and drags the ensemble's reproducibility down. Accepted trade for orthogonality.
- **Mouse axis is least reliable** — human PROGENy net on upper-cased mouse symbols, and
  targeted panels overlap only ~100 footprint genes. Report `n_footprint_genes`.

## Common issues

- **`obs['_dact']` missing.** Re-run [[ccc-data-prep]]; it must be computed on the full
  transcriptome before slimming.
- **Do not recompute activity here.** The receiving score only needs the LR genes (present in
  the slimmed base) plus the precomputed `_dact` vector.

## References

- decoupler 2.x: `dc.op.progeny`, `dc.mt.ulm`. PROGENy: Schubert et al., *Nat. Commun.* 2018.
- Related skills: [[ccc-data-prep]], [[ccc-liana]], [[ccc-commot]], [[ccc-stlearn]],
  [[ccc-aggregate]].
