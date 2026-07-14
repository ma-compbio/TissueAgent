# Limited Background — Tumor spatial transcriptomics (SpaCET study context)

**Tissue:** Human tumor tissue profiled by spot-based spatial transcriptomics
(e.g. Visium), typically containing mixed malignant, stromal, and immune cells.

**Technology:** Spatial transcriptomics with multi-cellular spots; optional
matched scRNA-seq references for lineage signatures.

**Annotations available:** may include histology-derived region labels, inferred
cell-type / lineage fractions, gene-module scores, or author-provided spot
annotations. Spatial coordinates in `.obsm["spatial"]`.

**Scope of study (intentionally vague):** the dataset is used to study cellular
composition and intercellular interactions in the tumor microenvironment.
**Specific findings — including which lineages dominate which regions, which
cell–cell interactions at the tumor–immune interface the authors reported, and
which ligand–receptor programs they linked to progression — are withheld from
you.** Discover structure by exploring the data directly.

**Constraints:**
- Use only this dataset; no external tumor atlases.
- Do not invent cell-type labels beyond what is present or clearly inferable.
- Treat spatial coordinates as unitless if uncalibrated.
