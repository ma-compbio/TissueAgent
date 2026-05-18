# Withheld Ground Truth — Farah et al. 2024 (ANONYMIZED variant)

**This file is the recovery target for the label-leakage control. It is
NOT visible to the Hypothesis Agent. The eval harness uses it to score
whether the agent's generated hypotheses recover (or are close to) the
author's actual finding, given that cell-type labels were anonymized.**

## Label mapping (for the judge ONLY — agent never sees this)

The original Farah dataset has these named populations. In the anonymized
variant, each is renamed to a code so the agent cannot identify the
AVC-restricted cardiomyocyte subtype by its literal name:

| Original | Code | n cells | Note |
|---|---|---|---|
| ncCM-AVC-like | **PV** | 2,292 | **AVC-restricted CM subtype (recovery target)** |
| aFibro | **PM** | 7,417 | **Atrial fibroblast (recovery target)** |
| ncCM-IFT-like | PW | 2,027 | other rare CM subtype |
| vCM-LV-AV | PN | 7,348 | AV-region ventricular CM |
| vCM-RV-AV | PO | 5,845 | AV-region ventricular CM |
| ... (full map at `demo/data/farah_anon_label_map.json`) | | | |

## Author's Core Claim (same as non-anon ground truth)

The inner portion of the atrioventricular canal (AVC) forms an **AVN/AV
ring cellular community (CC)** composed of:

1. **ncCM-AVC-like cardiomyocytes** (= **PV** in anon) — a non-compact
   cardiomyocyte subtype spatially restricted to the AVC region, distinct
   in expression program from ventricular and atrial cardiomyocytes
   elsewhere.
2. **Atrial fibroblasts (aFibro = PM** in anon**)** localized within this
   AVC community, exhibiting an expression program distinct from aFibro
   found elsewhere in the atria.

The authors hypothesized this AVN/AV ring CC represents a developmental
structure giving rise to the **atrioventricular node (AVN)** — i.e., a
progenitor-like specialized community rather than a generic atrial / AVC
neighborhood.

## What "recovery" means in the anonymized setting

The agent receives only the anonymized labels (PA, PB, ..., PZ, PAA). It
recovers the claim if its final `hypotheses.json` contains one or more
hypotheses that, when **the judge maps codes back to original labels**,
match on:

- **Spatial locus:** identifies the AVC region (it may say "a particular
  spatially restricted region" without using the word AVC) as containing a
  special community.
- **Cell-type composition:** identifies that PV co-localizes with PM
  (== ncCM-AVC-like + aFibro after decoding). A pure-name match cannot
  happen here — the agent must observe the spatial co-localization and
  identify the SPECIFIC code combination. **The judge will accept any
  hypothesis whose specified labels decode to ncCM-AVC-like + aFibro**.
- **Functional interpretation:** proposes a developmental / progenitor
  role, or links the community to conduction-system specification.

## Scoring rubric (same as non-anon)

| Aspect | 0 | 1 | 2 |
|---|---|---|---|
| Spatial locus (AVC region as distinct) | not mentioned | mentioned generically | AVC specifically called out |
| Cell-type composition (CM subtype + aFibro) | wrong / missing codes | one of the two | both, decoded as ncCM-AVC-like + aFibro |
| Functional interpretation (AVN / progenitor / conduction) | absent | broad development claim | specific AVN / conduction link |
| Specificity (within-celltype subtype, not just celltype) | only celltype level | mentions heterogeneity | identifies a spatially-defined subtype |

Total 0–8. ≥5 = good recovery, ≥3 = partial, <3 = miss.

**Important for the judge:** when the agent's hypothesis names specific
codes (e.g., "PV co-localizes with PM in region Y"), look up the codes
against the mapping above and score the *decoded* identities, not the
raw codes.
