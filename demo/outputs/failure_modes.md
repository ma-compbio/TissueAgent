# Hypothesis Agent — Failure-Mode Taxonomy

**Scope:** systematic look at how the Hypothesis Agent fails the recovery
benchmark when it does fail. Companion to `cellvoyager_analysis.md` (CV
failure modes). Drawn from 7 multi-seed runs of the Hypothesis Agent on
Farah (4 non-anon + 3 anonymized).

The Farah recovery target is the AVN/AV ring cellular community
= `ncCM-AVC-like` cardiomyocytes (cluster 29 in `leiden`) co-localized
with atrial fibroblasts (`aFibro`, cluster 14).

---

## Recovery distribution across the 7 retained HA runs

| Class | Count | Runs |
|---|---|---|
| GOOD (≥ 5) | 3 | non-anon seed1 (7), non-anon seed2 (7), anon seed3 (5) |
| PARTIAL (3–4) | 1 | non-anon seed3 (4) |
| MISS (≤ 2) | 3 | non-anon seed4 (2), anon seed1 (2), anon seed2 (2) |

Bulk success rate: 3/7 hit GOOD; 4/7 hit at least PARTIAL.

---

## Mode A: Wrong rare-but-tight pair (most common miss)

**Symptom:** the agent correctly identifies the *methodology*
(rare-but-tight cell-type populations co-localized with specific
neighbors), generates a real biological hypothesis around one such
pair, but the pair chosen is not the one the Farah authors highlighted.

**Examples (current data):**

- **non-anon seed4 (recovery = 2 MISS).** Best hypothesis: "Endothelial
  microdomains dominated by lymphatic endothelial cells (LEC) ...
  enriched in lymphangiogenic / vascular signaling gene programs."
  Real biology, wrong pair.
- **anon seed1 (recovery = 2 MISS).** Best hypothesis identifies
  "rare, spatially compact clusters that form strongly enriched mutual
  neighbor pairs, especially clusters '15' and '30'". Decoded:
  cluster 15 = `adFibro`, cluster 30 = `LEC`. Again a real
  fibroblast–lymphatic interface, again not the AV ring.

**Root cause:** the Farah dataset contains *multiple* valid rare-but-
tight + co-localized pairs:

| Leiden | Population | n cells | Pair partner | Comment |
|---|---|---|---|---|
| 29 | ncCM-AVC-like | 2,292 | 14 (aFibro) | **recovery target** |
| 28 | ncCM-IFT-like | 2,027 | 19 (His-Purkinje CMs) | conduction-system, real biology |
| 15 | adFibro | 1,562 | 30 (LEC) | lymphatic-stromal interface, real biology |

The methodology surfaces all three. Without further guidance, the
agent picks whichever pair stood out most strongly in *its* specific
exploration — and which pair stands out depends on LLM seed.

**Frequency:** ≥ 2 of 7 in current data.

---

## Mode B: Buried target in a long list

**Symptom:** the agent's hypothesis statement *includes* the recovery
target (cluster 29 = `ncCM-AVC-like`) but in a list of 4–5 other rare
clusters, without singling it out for specific characterization. The
judge cannot give a focused recovery score because the target is not
the hypothesis's focus.

**Example: anon seed2 (recovery = 2 MISS).** Hypothesis:
> "Rare, spatially tight leiden clusters 28, 15, 20, **29**, and 31 are
> closer to the tissue boundary than more abundant diffuse clusters
> and show modest enrichment for selected proliferation or progenitor
> transcription-factor programs..."

Cluster 29 (= ncCM-AVC-like) is in the list but is one of five, with
no per-cluster characterization.

**Root cause:** the rare-but-tight Phase 1 step asks for "top 3–5 by
concentration". The agent reasonably lists those literally. Phase 2
doesn't enforce *one hypothesis per pair* — combined-list hypotheses
survive into final output and dilute recovery scoring.

**Frequency:** 1 of 7 in current data.

---

## Mode C: Multi-valid-pair underdetermination (intrinsic to recovery framing)

This isn't really a *failure* of the agent — it's a feature of the
recovery benchmark. The dataset contains several biologically valid
specialized communities; the author paper highlighted one (AV ring CC)
as canonical. An agent without a prior toward the author's narrative
will sometimes pick a different valid community.

**Why it matters for the manuscript:** the rubric only credits recovery
of the author's specific claim. A hypothesis that proposes
adFibro + LEC as a distinct lymphatic-stromal community is *correct
biology* by any standard — it is just not the claim that was
withheld. Counting these as "miss" undersells the agent.

A future rubric extension could add a "biological validity" dimension
that credits these honest non-recoveries.

---

## Success-mode anatomy (what GOOD runs share)

The 3 GOOD recovery runs (non-anon seed1, non-anon seed2, anon seed3)
all have two features in common:

1. **A hypothesis statement that names a non-abundant CM subtype or
   its anonymized code** (e.g. `ncCM-AVC-like`, `PV`,
   `vCM-His-Purkinje`).
2. **A co-localization claim with a non-CM partner** (`aFibro`, `PM`,
   `Neuronal`, `adFibro` etc).

The cleanest case is **anon seed3**, which identifies `PV + PM + PF`
(= ncCM-AVC-like + aFibro + BEC) via pure spatial discovery — the
agent has no idea that PV means ncCM-AVC-like. This is the agent
genuinely doing biology, not pattern-matching label strings.

---

## What this tells the manuscript

- **HA's recovery score is bimodal-ish.** Most runs cleanly succeed
  (PARTIAL or GOOD: 4/7) or cleanly miss (MISS: 3/7), with only one
  in between. The mean (5.0/8 for non-anon) flattens this.
- **Failure modes are systematic and analyzable.** Mode A (wrong pair)
  is the dominant miss mode; Mode B (buried target) is rarer but
  tractable; Mode C (multi-valid-pair) is a property of the recovery
  framing and would require a richer rubric to handle fairly.
- **The dataset contains multiple legitimate biological communities.**
  Counting non-author-match as "miss" undersells the agent. A
  biological-validity dimension on the rubric (TODO) would improve
  fairness.

---

## Comparison with CellVoyager failure modes

| Mode | HA (7 runs) | CV (6 runs) |
|---|---|---|
| Mode A (wrong rare-but-tight pair) | 2 / 7 | 0 / 6 (doesn't reach rare-pop scan in its framing) |
| Mode B (buried target) | 1 / 7 | 0 / 6 |
| Mode C (multi-valid-pair underdetermination) | always present | not applicable |
| Metadata-driven framing (CV's universal mode) | 0 / 7 (rare-but-tight rule prevents) | 6 / 6 |

HA's failures are *diverse*; CV's are *monotone*. This is a direct
consequence of the design contrast in `cellvoyager_analysis.md`. In
a multi-paper benchmark (N ≥ 3), HA's diversity is an asset (different
recovery targets hit by different seeds). CV's monotone framing means
it will likely succeed only on recovery targets that match its
"within-X × metadata × neighborhood" template.
