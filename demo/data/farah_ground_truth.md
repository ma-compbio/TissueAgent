# Withheld Ground Truth — Farah et al. 2024

**This file is the recovery target. It is NOT visible to the Hypothesis Agent.
The eval harness uses it to score whether the agent's generated hypotheses
recover (or are close to) the author's actual finding.**

## Author's Core Claim

The inner portion of the atrioventricular canal (AVC) forms an **AVN/AV ring
cellular community (CC)** composed of:

1. **ncCM-AVC-like cardiomyocytes** — a non-compact cardiomyocyte subtype
   spatially restricted to the AVC region, distinct in expression program from
   ventricular and atrial cardiomyocytes elsewhere.
2. **Atrial fibroblasts (aFibro)** localized within this AVC community,
   exhibiting an expression program distinct from aFibro found elsewhere in
   the atria.

The authors hypothesized that this AVN/AV ring CC represents a developmental
structure giving rise to the **atrioventricular node (AVN)** — i.e., a
progenitor-like specialized community rather than a generic atrial / AVC
neighborhood.

## What "Recovery" Means

The agent is given (dataset, limited background) and runs explore → narrow.
It recovers the claim if its final `hypotheses.json` contains one or more
hypotheses that match on:

- **Spatial locus**: identifies the AVC region as containing a special
  cellular community (vs. uniform mixing across the heart).
- **Cell-type composition**: identifies that this community co-localizes
  cardiomyocytes (especially an AVC-restricted subtype) with fibroblasts
  (especially atrial fibroblasts).
- **Functional interpretation**: proposes a developmental / progenitor role,
  or links the community to conduction-system / AVN specification.

A hypothesis that matches on **spatial locus + cell-type composition** is a
**partial recovery**. A hypothesis that adds the **functional/progenitor
interpretation** is a **full recovery**.

## Scoring Rubric (for the LLM judge / expert reviewer)

| Aspect | 0 | 1 | 2 |
|---|---|---|---|
| Spatial locus (AVC region as distinct) | not mentioned | mentioned generically | AVC specifically called out |
| Cell-type composition (CM subtype + aFibro) | wrong / missing | one of the two | both, co-localized |
| Functional interpretation (AVN / progenitor / conduction) | absent | broad development claim | specific AVN / conduction link |
| Specificity (within-celltype subtype, not just celltype) | only celltype level | mentions heterogeneity | identifies a spatially-defined subtype |

Total: 0–8. ≥5 = good recovery, ≥3 = partial, <3 = miss.
