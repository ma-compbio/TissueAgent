# Limited Background — Farah et al. 2024 (developing human heart MERFISH)

**Tissue:** Developing human heart.

**Technology:** MERFISH spatial transcriptomics.

**Gene panel:** ~140 genes selected to mark cardiac cell types and a small set
of developmental transcription factors / signaling pathway components.

**Annotations available:** the AnnData has cell-type labels in `.obs` (column
name to be discovered by inventory) covering cardiomyocyte subtypes
(ventricular, atrial, AVC-region), fibroblasts (atrial, ventricular, valve),
endothelial cells, epicardium, and immune cells. 2D spatial coordinates are in
`.obsm["spatial"]` and section / region metadata in `.obs`.

**Scope of study (intentionally vague):** the dataset profiles spatial
organization of cell types across anatomical regions (atria, ventricles,
atrioventricular canal, outflow tract) of the developing human heart.
**Specific findings — including which spatially restricted communities the
original authors highlighted, which cell-type combinations they found
co-localized, and which developmental hypotheses they proposed — are withheld
from you.** Discover what is interesting about this dataset by exploring it
directly.

**Constraints:**
- Use only this dataset; no external lookups, no external datasets.
- Cell-type labels are author-provided; do not relabel them.
- Spatial unit is the coordinate value in `.obsm["spatial"]`; spatial scale is
  not calibrated, treat coordinates as unitless.
