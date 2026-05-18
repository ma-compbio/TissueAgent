# Limited Background — Lohoff et al. seqFISH

**Tissue:** Mouse embryo (gastrulation / early organogenesis stage).

**Technology:** seqFISH spatial transcriptomics.

**Gene panel:** ~350 genes, targeting cell-type marker genes and developmental
transcription factors.

**Annotations available:** the AnnData has cell-type labels in `.obs` (column
name to be discovered by inventory) and 2D spatial coordinates in
`.obsm["spatial"]`. The cell-type vocabulary covers mesoderm-, ectoderm-, and
endoderm-derived embryonic structures.

**Scope of study (intentionally vague):** the dataset profiles cell-type
spatial organization during early organogenesis. **Specific findings —
including which regions, niches, or cell-cell interactions the original
authors highlighted — are withheld from you.** Discover what is interesting
about this dataset by exploring it directly.

**Constraints:**
- Use only this dataset; no external lookups, no external datasets.
- Cell-type labels are author-provided; do not relabel them.
- Spatial unit is the coordinate value in `.obsm["spatial"]`; spatial scale is
  not calibrated, treat coordinates as unitless.
