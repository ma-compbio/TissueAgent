# CCC Ensemble Agent — Benchmark Plan (revised)

Benchmarks the spatial-transcriptomics agent as one more CCC "method" slotted into
the SpatialCCCbench apparatus, evaluating both the **decisions** the agent makes
(orchestration correctness) and the **calls** it emits (output quality). This
revision fixes eight issues in the earlier real-data-only design: no ground-truth
anchor, agent/reference circularity, confounded branch coverage, low-power
comparisons, conflated variance sources, a circular spatial-autocorrelation
metric, unpinned "expected biology", and missing robustness/cost metrics.

Companion to `knowledge/plans/ccc_ensemble.md` and the `ccc-*` skills. Read those
first — this plan treats the ensemble output contract (regimes, `engines_sig`,
`n_capable`, autocrine diagnostics, panel coverage) as fixed.

---

## 1. What we are measuring

The agent under test runs the five-step ensemble (`ccc-data-prep` → `ccc-liana` →
`ccc-commot` → `ccc-stlearn` → `ccc-aggregate`) and emits a high-confidence
consensus plus per-engine outputs. We score two layers **independently** so a
code defect never masquerades as a decision error and vice versa:

| Layer | Question | Oracle |
|---|---|---|
| **A. Orchestration correctness** | Did the agent make the right adaptive decisions for this dataset? | A hand-authored expected-decision table per dataset (categorical + tolerance bands). |
| **B. Output quality** | Are the emitted interactions good? | A ground-truth simulation (primary) + DB-controlled tool concordance + pre-registered biology (secondary). |

**Scope rule (cross-cutting fix).** Layer A scores *decisions only*. Implementation
correctness of the skills is a **precondition**, verified once by the skills'
selftests and a smoke run, not re-scored per benchmark run. Before any scoring:

- `python knowledge/skills/ccc-aggregate/scripts/ccc_aggregate.py --selftest` passes
  (shared-resource unification; LIANA-as-one-engine; single-cell autocrine drop).
- A single smoke run on the simulation produces all expected files with the
  autocrine diagnostic columns populated and the Visium µm sanity band satisfied.

If a precondition fails, fix the skill — do not encode the defect as an expected
decision.

---

## 2. Datasets (fix C: decouple the branch matrix; fix A: add ground truth)

The agent's decision tree branches on three axes: **species** (human/mouse),
**modality** (sequencing spot vs single-cell imaging), and **cell-type input**
(deconvolution proportions vs cluster labels). Three real datasets cannot cover a
2×2×2 space, and the original mouse-brain MERFISH confounded species × imaging ×
gridding × the connectomeDB-is-human-derived branch all at once. We add a
ground-truth simulation and two decoupling datasets:

| # | Dataset | Species | Modality | Res. mode | Cell-type input | Role |
|---|---|---|---|---|---|---|
| S | **scMultiSim** CCC simulation (known LR ground truth) | — | synthetic spot **and** synthetic single-cell variants | both | labels (true) | **Ground-truth anchor** (fix A) |
| 1 | Lymph-node **Visium** (human 10x) | human | sequencing | spot_multicell | labels (+ optional deconv) | Human · seq · Visium |
| 2 | DLPFC **Visium** (human, one pinned section of 12) | human | sequencing | spot_multicell | labels | Human · seq · Visium; laminar biology |
| 3 | Mouse-brain **MERFISH** (one section) | mouse | imaging | single_cell | labels | Mouse · imaging · gridding |
| 4 | Mouse **Visium** (e.g. mouse brain/kidney 10x) | mouse | sequencing | spot_multicell | labels | **Decouples** species from imaging (fix C) |
| 5 | Human **Xenium** (e.g. breast) | human | imaging | single_cell | labels (+ segmentation) | **Decouples** imaging from species (fix C) |

With 4 & 5 added, each axis varies while the others are held: species is testable
on {1,2} vs {4} at fixed modality; modality on {1,2,4} vs {3,5} with species
balanced; the human-derived-connectomeDB / stLearn-species branch is exercised by
the mouse pair {3,4} rather than only inside the imaging dataset. A failure is now
attributable to a single decision.

The simulation (S) is the **only** dataset with true positives, so it carries the
correctness claims; the real datasets carry realism, robustness, and biology.

**Pinning (fix G).** Record exact accession/section IDs, Space Ranger / vendor
pipeline versions, gene panels, and the scMultiSim seed and LR-network config in
`benchmark/manifest.json`. The DLPFC section and lymph-node sample are fixed, not
"a DLPFC Visium".

---

## 3. Layer A — orchestration correctness

Per dataset, a hand-authored expected-decision record. The agent's decisions are
LLM-nondeterministic, so score **agreement rate across `R` repeated runs** (R ≥ 10)
per decision, not a single run.

Checked decisions (categorical unless noted):

| Decision | Source of truth | Type | Acceptance |
|---|---|---|---|
| LR resource species | `logs/ccc_data_prep.json.species` + shared resource built (`consensus`/`mouseconsensus`); stLearn species/mapping | categorical | resource species matches dataset; mouse records shared-resource mapping or stLearn drop |
| `resolution_mode` | `logs/ccc_data_prep.json` | categorical | matches modality (observation unit) |
| Coordinate unit + µm calibration | `logs/ccc_data_prep.json.median_nn` (native) + `median_nn_um` (reporting) | numeric band | `median_nn_um` within ±20% of the known platform pitch (Visium ~100 µm; imaging from vendor) or null if unconvertible |
| Per-regime `dis_thr` | `logs/ccc_commot.json` | numeric band | contact ≈ `1.5×`, diffusion ≈ `3×` `median_nn` (native units) |
| LIANA bandwidths (contact + diffusion) | `logs/ccc_liana.json.bandwidths` | numeric band | contact ≈ `1.5×`, diffusion ≈ `3×` `median_nn` (±25%) |
| Small-panel `expr_prop` drop | `logs/ccc_liana.json.expr_prop` | categorical | 0.05 iff `small_panel` |
| Gridding | `logs/ccc_stlearn.json.gridded` | categorical | True iff `single_cell` |
| `spot_mixtures` | `logs/ccc_stlearn.json` | categorical | True on gridded/deconv, False otherwise |
| Autocrine filter | consensus `autocrine_filter` col | categorical | `distance_aware`/`categorical_all_autocrine` on `single_cell`, `not_applied` on spot |
| Shared-universe single-gene calls | consensus `ligand`/`receptor` single genes + `engines_sig` | structural | single-gene pairs (monomeric shared resource); no single-engine `engines_sig` |
| Refusals | run log | categorical | correctly refuses normalized-coord / <2-category / null-`median_nn` inputs (see §6) |

**Scoring.** Per decision: `p̂ = (#runs correct)/R`, with a Wilson interval. A
dataset "passes" a decision at `p̂ ≥ 0.9`. Report the full matrix
(decision × dataset) plus a per-decision mean across datasets. Numeric-band
decisions score the fraction of runs landing in-band. Continuous parameters
(`dis_thr`, bandwidth) are **never** required to match a point value — only the
band — because they are derived from a continuous `median_nn_um`.

---

## 4. Layer B — output quality

Three references, in decreasing strength. All comparisons happen at the ensemble's
native granularity (exploded gene-pair triples `(ligand_gene, receptor_gene,
source, target)`) and — critically — **within a shared operable LR universe** so
we compare methods on interactions they could all have found.

### B1. Ground-truth recovery on the simulation (primary)

scMultiSim emits true active LR interactions per cell-type pair. Compute, for the
agent's high-confidence consensus and for **each individual engine**:

- Precision / recall / F1 vs the true interaction set, restricted to the
  simulated panel.
- Precision–recall curve by sweeping the agent's `consensus_pct` / `tier` (and each engine's own
  p/rank), so precision is read at matched recall rather than at one operating
  point.

This is the only place true precision/recall is defined; it anchors everything
else. Run both the spot and single-cell simulation variants so the gridding and
autocrine paths are exercised against ground truth (the MERFISH/Xenium real sets
cannot verify that the autocrine filter drops *false* autocrine specifically —
the simulation can, by planting autocrine-negative touching cells).

### B2. DB-controlled tool concordance on real data (secondary, fix B & D)

No real dataset has ground truth, so "concordance with a held-out consensus of
independent tools" measures agreement, not accuracy — and, uncontrolled, mostly
measures **database overlap** (CellChatDB↔connectomeDB Jaccard ≈ 0.17). We control
for both:

- **Reference tools must be engine-disjoint** from the agent (no LIANA/COMMOT/
  stLearn). Use e.g. CellChat (R), CellPhoneDB, NicheNet, Squidpy `ligrec`.
- **Shared universe.** Restrict every precision/recall computation to the
  intersection of the agent's operable universe (`ccc_panel_coverage.csv`) and the
  reference tool's DB ∩ panel. Report the size of this comparable set per dataset;
  when it is small (expected — the 3-way overlap is the point of
  `ccc_panel_overlap.json`), flag low power and widen CIs.
- **Consensus strata.** Build the reference at several agreement strata (≥1, ≥2,
  ≥3 tools). Score the agent's **precision** against the strict stratum and its
  **recall** against the lenient stratum, so a deliberately conservative agent is
  not rewarded for disagreeing with the crowd nor penalized for missing
  crowd-only calls.
- **Report both raw and DB-matched** concordance. If they diverge, the divergence
  *is* the database-confounding, and we say so.

Primary axis here is **within-universe precision at a matched call rate**; recall
is secondary with explicit CIs because the comparable set is small.

### B3. Pre-registered biological signal (secondary, fix G)

Before running, register expected interactions/pathways and ROIs per real dataset
in `benchmark/expected_biology.yaml` (e.g. germinal-center B–Tfh signaling in
lymph node; laminar excitatory–inhibitory signaling across DLPFC layers;
region-specific neuromodulatory pairs in mouse brain). Score enrichment of the
agent's high-confidence calls in the pre-registered set and ROI localization of
the corresponding COMMOT/stLearn spatial signal. Pre-registration prevents
post-hoc rationalization; anything discovered but not registered is reported as
exploratory, not scored.

### B4. Spatial autocorrelation — descriptive only (fix F)

Report Moran's I of the consensus calls' spatial signal, but **do not score on
it**: COMMOT and stLearn bake in spatial structure, so autocorrelation is partly
guaranteed by construction and mostly reflects which engine dominated. It is a
description of the output, not a quality axis.

### B5. Fusion ablation — the headline (fix: elevate)

For every metric above, report **each individual engine alone vs the fused
consensus** on the same axis and universe. This isolates what aggregation
contributes: the expected, and testable, story is that fusion trades a little
recall for a large precision gain over any single engine on B1, and improves
DB-robustness on B2. This ablation is the primary scientific result, not an
aside — present it first in the results.

---

## 5. Variance protocol (fix E: separate the two noise sources)

Output variance has two distinct sources; measure them separately.

1. **Decision stability** — vary the agent (temperature as configured), hold every
   method seed fixed (`random_state=1337`, `n_permutations=500`). `R` runs per
   dataset. Feeds Layer A and gives a decision-induced spread on Layer B metrics.
2. **Method variance** — freeze the agent's chosen parameters/branches from one
   representative run, then vary only the permutation seeds across `M` runs
   (M ≥ 5). Gives the statistical-test-induced spread with decisions held constant.

Report Layer B metrics as mean ± CI decomposed into these two components (e.g. a
simple nested variance estimate). This tells us whether output spread comes from
the LLM choosing differently or from the permutation tests — they have different
fixes.

---

## 6. Robustness and cost (fix H)

First-class metrics for an *agent* benchmark, missing from the original plan:

- **Valid-run rate.** Fraction of the `R` runs per dataset that complete and emit
  the full output contract. A run that crashes or emits a partial contract counts
  against this, separately from decision correctness.
- **Correct-refusal rate.** Feed deliberately broken inputs (pre-normalized
  coordinates, `<2` cell-type categories, null `median_nn_um`, Ensembl IDs) and
  confirm the agent refuses with an actionable message rather than producing
  garbage. Each refusal case is a fixture in `benchmark/refusal_cases/`.
- **Cost.** Wall-clock and token cost per run, per dataset, broken down by step
  (the per-LR COMMOT loop and stLearn `run_cci` dominate; track them).

---

## 7. Reporting structure

Emit one `benchmark/report.md` plus machine-readable `benchmark/results.json`:

1. **Fusion ablation** (B5) — engines vs consensus on ground-truth PR (B1) and
   DB-controlled precision (B2). The headline.
2. **Ground-truth table** (B1) — precision/recall/F1, spot and single-cell.
3. **Orchestration matrix** (Layer A) — decision × dataset agreement rates + CIs.
4. **DB-controlled concordance** (B2) — with comparable-set sizes and raw-vs-matched.
5. **Biology** (B3) — pre-registered enrichment/ROI hits; exploratory findings
   listed separately.
6. **Variance decomposition** (§5), **robustness & cost** (§6).
7. **Descriptive** — spatial autocorrelation (B4), panel-overlap summaries.

Every table states its universe and n. Any bounded coverage (top-N, sampling,
dropped low-power comparisons) is logged explicitly — silent truncation reads as
"covered everything" when it did not.

---

## 8. Fix traceability

| Fix | Section |
|---|---|
| A — ground-truth anchor (scMultiSim) | §2 (S), §4 B1 |
| B — agent/reference circularity, DB control | §4 B2 |
| C — decouple confounded branches | §2 (datasets 4, 5) |
| D — comparable-set size, precision-first | §4 B2 |
| E — separate decision vs method variance | §5 |
| F — demote spatial autocorrelation | §4 B4 |
| G — pre-register biology, pin versions | §2 pinning, §4 B3 |
| H — robustness & cost metrics | §6 |
| Cross-cutting — decisions vs implementation | §1 scope rule |
| Elevate — fusion ablation as headline | §4 B5, §7 |
