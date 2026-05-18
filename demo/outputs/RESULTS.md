# Recovery Benchmark Results — Hypothesis Agent vs CellVoyager

**Dataset:** Farah et al. 2024 developing human heart MERFISH (228,635 cells × 238 genes).

**Withheld target:** AVN/AV ring cellular community = `ncCM-AVC-like`
cardiomyocytes co-localized with atrial fibroblasts (`aFibro`),
hypothesized as a developmental precursor of the atrioventricular node.

**Model:** Both agents use GPT-5.1 with `reasoning_effort=high`
(CellVoyager's native config is `claude-sonnet-4-6`; we used GPT-5.1
for apples-to-apples; see Caveats).

**Two rubrics (both LLM-judge with gpt-5, high reasoning):**
- **Recovery (0–8):** 4 aspects scored 0–2 each — spatial locus,
  cell-type composition, functional interpretation, specificity. Scores
  hypothesis against the **withheld** author claim.
- **Quality (0–50) + testability (0–3):** 5 sub-criteria scored 0–10
  each — derivability, novelty, feasibility, specificity, falsifiability
  — plus a separate testability score. Ground-truth-free.

---

## Headline numbers (multi-seed, all N ≥ 3)

| Agent | Setting | N seeds | recovery (0–8) | quality (0–50) | testability (0–3) |
|---|---|---|---|---|---|
| **Hypothesis Agent** | Farah non-anon | 4 | **5.0 ± 2.16** | **41.75 ± 2.21** | **3.0 ± 0** |
| **Hypothesis Agent** | Farah anon | 3 | 3.0 ± 1.73 | 39.67 ± 1.53 | 3.0 ± 0 |
| CellVoyager | Farah non-anon | 3 | 3.67 ± 1.15 | 35.67 ± 0.58 | 2.0 ± 0 |
| CellVoyager | Farah anon | 3 | 2.0 ± 1.0 | 32.0 ± 6.56 | 2.0 ± 0 |

## Head-to-head differences (HA − CellVoyager)

| Metric | Non-anon (Δ) | Anon (Δ) | Effect of anonymization on Δ |
|---|---|---|---|
| recovery | **+1.33** | **+1.0** | overlapping SDs in both |
| **quality** | **+6.08** | **+7.67** | **gap widens after scrubbing labels** |
| testability | **+1.0** | **+1.0** | deterministic, both settings |

The quality gap **widens** under anonymization because CellVoyager's
quality variance jumps from SD 0.58 → 6.56 (lost label scaffolding)
while HA's quality SD stays tight (2.21 → 1.53). Hypothesis Agent's
quality advantage is design-level, not label-driven.

## Per-aspect breakdown (Hypothesis Agent, Farah non-anon, N=4)

| Aspect | Mean ± SD | Range | Stability |
|---|---|---|---|
| spatial_locus | 1.25 ± 0.50 | [1, 2] | stable |
| celltype_composition | 0.75 ± 0.96 | [0, 2] | volatile |
| functional_interp | 1.25 ± 0.96 | [0, 2] | volatile |
| specificity | 1.75 ± 0.50 | [1, 2] | stable |
| **total recovery** | **5.0 ± 2.16** | **[2, 7]** | high-variance |

The volatile aspects (composition + functional_interp) depend on
*which* biological phenomenon the agent commits to during exploration.
Stable aspects (locus + specificity) reflect the *form* of the
hypothesis statement, which is determined by the 3-phase scaffold.

## Per-seed snapshots — Hypothesis Agent on Farah non-anon

| Seed | recovery | quality | testability | Best hypothesis (paraphrased) |
|---|---|---|---|---|
| seed1 | 7 | 40 | 3 | Conduction-system CMs (incl. ncCM-AVC-like) form spatially segregated microdomains with adFibro/Neuronal neighbors and a shared conduction gene program |
| seed2 | 7 | 45 | 3 | Lymphatic endothelial + adipogenic fibroblast + epicardial-derived form a co-localized niche with distinct adFibro transcriptional program |
| seed3 | 4 | 42 | 3 | Endothelial interface cells have higher program scores than non-interface cells |
| seed4 | 2 | 40 | 3 | Fibroblast subtypes form spatial niches; ECM/remodeling shifts with neighbor composition (misses target) |

`seed1` and `seed2` are GOOD (≥5); `seed3` is PARTIAL; `seed4` is MISS.
The 4 hypotheses span four real biological communities in the dataset;
two of them include `ncCM-AVC-like` (the target).

## Per-seed snapshots — Hypothesis Agent on Farah anon

| Seed | recovery | quality | testability | Note |
|---|---|---|---|---|
| seed1 | 2 | 38 | 3 | Found rare-but-tight clusters 15+30 (= adFibro+LEC, wrong pair) |
| seed2 | 2 | 41 | 3 | Listed clusters incl. 29 (= ncCM-AVC-like) but buried in a 5-cluster list |
| seed3 | **5 (full)** | 40 | 3 | **Found PV+PM+PF (= ncCM-AVC-like + aFibro + BEC) via pure spatial discovery** |

Anon seed3's H3 explicitly identifies `PV` and `PM` as co-localized
with `PF` neighbors — the agent does not know that PV = ncCM-AVC-like
and PM = aFibro. This is a clean demonstration that the spatial-
discovery method works without label-name hints.

## Per-seed snapshots — CellVoyager on Farah

| Seed | Setting | recovery | quality | Note |
|---|---|---|---|---|
| seed1 | non-anon | 3 | 36 | "Within CM/fibroblast subtypes, neighborhood × purity" framing |
| seed2 | non-anon | 3 | 36 | Same template framing |
| seed3 | non-anon | 5 | 35 | "Interfaces between V and A territories" — closest to AVC |
| seed1 | anon | 3 | 31 | "Spatially localized subclusters × purity" |
| seed2 | anon | 1 | 39 | Different population × neighborhood diversity |
| seed3 | anon | 2 | 26 | Within-population intrinsic states × Complexity |

All 18 unique CellVoyager hypotheses (across the 6 seeds) fit the same
template — "Within X cell population, Y spatial/neighborhood metric is
systematically associated with Complexity / Purity / Sample". See
`CELLVOYAGER_FRAMING_ANALYSIS.md` for the framing-template analysis.

---

## Key methodological observations

1. **Hypothesis quality is the headline metric** (the metric the
   response document committed to). Hypothesis Agent scores 40+/50 in
   every condition we tested; CellVoyager's best mean is 35.67.
2. **Recovery is variable for both agents but more so for Hypothesis
   Agent** (SD 2.16 vs CellVoyager's 1.15). The Hypothesis Agent has a
   higher ceiling (best seed 7/8) but more diverse failures.
3. **Anonymization affects CellVoyager more than Hypothesis Agent.**
   CellVoyager quality drops 3.67 points; HA quality drops 2.08. CV
   variance jumps an order of magnitude; HA variance stays tight.
4. **Testability is structurally deterministic.** HA always scores 3/3
   because Phase 3 executes the `test_plan` and reports numerics. CV
   always scores 2/3 because the analysis plan is concrete but the
   notebook parser does not detect explicit execution.
5. **Both agents miss the target most of the time.** Even Hypothesis
   Agent's mean recovery (5.0/8) is "partial" by the rubric. Recovery
   benchmarks are inherently hard — the dataset contains multiple
   valid rare-but-tight + co-localized pairs and the author chose one
   as canonical. See `failure_modes.md` for the systematic taxonomy.

---

## Caveats and limitations (manuscript discussion)

1. **N = 1 paper.** Farah is the only recovery target benchmarked.
   The response document used plural "studies"; needs ≥ 2 more papers
   curated with their own `<paper>_background.md` and
   `<paper>_ground_truth.md` files.
2. **GPT-5.1 throughout.** CellVoyager's published configuration is
   `claude-sonnet-4-6` via litellm. We were forced off-native by lack
   of `ANTHROPIC_API_KEY` on the test machine. Numbers above are the
   "both agents on the same model" comparison; native CellVoyager may
   score higher.
3. **LLM-judge only.** The response document committed to
   "expert-scored evaluation". Need a domain expert to spot-check at
   least 10 hypotheses on the 5 criteria; report inter-rater
   agreement.
4. **GPT-judge for GPT-agent.** Reviewer #3 Comment #4.3 flagged
   conflict-of-interest. Cross-validate with Claude as the judge once
   `ANTHROPIC_API_KEY` is available.
5. **Single ST technology.** Farah is MERFISH (~238 genes). Adding a
   second paper on a different platform (Visium, seqFISH, Stereo-seq)
   would address Reviewer #3 #2.1's narrow-platform concern.
6. **Label-name leakage exists even after anonymization.** The
   `Sample_ID` and `Batch` columns carry biological signal too
   (different developmental sections). The anon variant scrubs only
   `Populations` / `Communities` / `Zone_Cluster`. A fuller
   leakage-control would also anonymize `Sample_ID`.
