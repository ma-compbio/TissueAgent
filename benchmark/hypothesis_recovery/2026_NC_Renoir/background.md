# Limited Background — Renoir spatial ligand–target study

**Tissue:** Multiple spatial transcriptomics contexts spanning development and
disease (e.g. brain, breast tumor, fetal liver, liver cancer), depending on the
provided AnnData file.

**Technology:** Spatial transcriptomics at spot-to-single-cell resolution
(Visium / Visium HD / Xenium), optionally with a matched single-cell reference.

**Annotations available:** cell-type labels or deconvolution abundances in
`.obs` / `.obsm`, spatial coordinates in `.obsm["spatial"]`. Gene expression
covers ligands, receptors, and downstream targets present in the panel /
transcriptome.

**Scope of study (intentionally vague):** the dataset is used to study how
ligand activity relates to downstream target programs across spatial niches
with specific cell-type composition.
**Specific findings — including which ligand–target pairs, communication niches,
or cell–cell interactions the authors reported — are withheld from you.**
Discover interesting spatial communication structure by exploring the data.

**Constraints:**
- Use only this dataset; no external ligand–target databases beyond what you
  can justify from genes present in the object (or clearly document if you load
  a standard LR list).
- Do not relabel author-provided cell types.
- Treat spatial coordinates as unitless if uncalibrated.
