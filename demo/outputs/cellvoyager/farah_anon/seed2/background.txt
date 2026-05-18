# Limited Background — Farah et al. 2024 (developing human heart MERFISH, ANONYMIZED)

**Tissue:** Developing human heart.

**Technology:** MERFISH spatial transcriptomics.

**Gene panel:** ~240 genes targeting cardiac cell types and a small set of
developmental transcription factors / signaling pathway components.

**Annotations available:** The AnnData has cell-type labels in `.obs`
(column name to be discovered by inventory). **Cell-type labels have been
anonymized to opaque alphanumeric codes (e.g., `PA`, `PB`, `PC`, ...) to
remove name-based biological hints.** You must discover what each labeled
population is by examining its expression profile and spatial distribution.
2D spatial coordinates are in `.obsm["spatial"]`; section / sample
metadata in `.obs["Sample_ID"]`.

**Scope of study (intentionally vague):** the dataset profiles spatial
organization of cell types across anatomical regions (atria, ventricles,
atrioventricular canal, outflow tract) of the developing human heart.
**Specific findings — including which spatially restricted communities the
original authors highlighted, which cell-type combinations they found
co-localized, and which developmental hypotheses they proposed — are
withheld from you.** Discover what is interesting about this dataset by
exploring it directly.

**Constraints:**
- Use only this dataset; no external lookups, no external datasets.
- Cell-type label codes are opaque (PA, PB, PC, ...); do not assume their
  biological identity from the code letter.
- Spatial unit is the coordinate value in `.obsm["spatial"]`; spatial
  scale is not calibrated, treat coordinates as unitless.
