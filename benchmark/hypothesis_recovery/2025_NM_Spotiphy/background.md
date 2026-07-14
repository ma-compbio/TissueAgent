# Limited Background — Spotiphy mouse-brain spatial study context

**Tissue:** Mouse brain (wild-type and/or Alzheimer’s disease model), depending on
the provided AnnData file.

**Technology:** Spatial transcriptomics and/or imaging-based spatial profiling
(Visium / Xenium / CosMx). The object may be spot-level or near-single-cell.

**Annotations available:** cell-type or region labels may be present in `.obs`
(column names to be discovered by inventory). Spatial coordinates in
`.obsm["spatial"]` when available.

**Scope of study (intentionally vague):** the dataset is used to study spatial
organization of cell types and regional specification in the mouse brain,
including disease-associated states when an AD model is present.
**Specific findings — including which cell types show regional specification,
which disease-associated microglia / astrocyte programs the authors reported,
and which spatial domains they highlighted — are withheld from you.**
Discover structure by exploring the data directly.

**Constraints:**
- Use only this dataset; no external atlases beyond genes present in the object.
- Do not relabel author-provided cell types if present.
- Treat spatial coordinates as unitless if uncalibrated.
