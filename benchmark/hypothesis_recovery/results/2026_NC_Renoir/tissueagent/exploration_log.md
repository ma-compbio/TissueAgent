# Dataset inventory

- n_obs (spots/cells): 1162
- n_vars (genes/features): 19237
- Technology/platform: unspecified in AnnData (likely Visium or similar 10x spatial based on obs/obsm structure)
- Tissue/organ: not annotated in .uns/.obs under standard keys
- Species: not annotated in .uns/.obs under standard keys
- .uns keys: paper_id, sample_id, source
- Major obs annotation fields: subtype, Classification
- Major var annotation fields: none detected
- Spatial coordinates present: yes
- Spatial .obsm keys: spatial

# QC summary

- total_counts: mean=11342.50, min=627.00, max=57645.00
- n_genes_by_counts: mean=3685.49, min=504.00, max=8864.00

# Initial observations

- The dataset appears to be a spatial transcriptomics experiment with a single `spatial` coordinate matrix in `adata.obsm`. The presence of `array_row`/`array_col` and `in_tissue` in `adata.obs` is consistent with 10x Genomics Visium output.
- Cell/spot-level annotations include at least a `subtype` label and a broader `Classification` field, plus patient-level information (`patientid`). These will be useful for downstream differential and spatial analyses.
- QC metrics (`nCount_RNA`, `nFeature_RNA`) show a wide dynamic range of counts and detected genes per spot, suggesting variable RNA content across the tissue. Further filtering thresholds may be required in subsequent steps.

# Linked paper summary (brief)

The following summary was loaded from `project/outputs/briefs/paper_summary.txt` and may provide biological context for the dataset:

> # Limited Background — Renoir spatial ligand–target study
> 
> **Tissue:** Multiple spatial transcriptomics contexts spanning development and
> disease (e.g. brain, breast tumor, fetal liver, liver cancer), depending on the
> provided AnnData file.
> 
> **Technology:** Spatial transcriptomics at spot-to-single-cell resolution
> (Visium / Visium HD / Xenium), optionally with a matched single-cell reference.
> 
> **Annotations available:** cell-type labels or deconvolution abundances in
> `.obs` / `.obsm`, spatial coordinates in `.obsm["spatial"]`. Gene expression
> covers ligands, receptors, and downstream targets present in the panel /
> transcriptome.
> 
> **Scope of study (intentionally vague):** the dataset is used to study how
> ligand activity relates to downstream target programs across spatial niches
> with specific cell-type composition.
> **Specific findings — including which ligand–target pairs, communication niches,
> or cell–cell interactions the authors reported — are withheld from you.**
> Discover interesting spatial communication structure by exploring the data.
> 
> **Constraints:**
> - Use only this dataset; no external ligand–target databases beyond what you
>   can justify from genes present in the object (or clearly document if you load
>   a standard LR list).
> - Do not relabel author-provided cell types.
> - Treat spatial coordinates as unitless if uncalibrated.

# Spatial and expression exploration

OBSERVATION 1: The tissue contains several distinct histological regions as captured by the `Classification` field, with "Invasive cancer + lymphocytes", "DCIS", "Normal + stroma + lymphocytes", and stromal/lymphoid compartments all represented at substantial frequencies.
Evidence: Value counts of `adata.obs['Classification']` (DCIS n=273; Invasive cancer + lymphocytes n=317; Normal + stroma + lymphocytes n=240; Stroma-related classes and Lymphocytes making up the remainder) from the categorical summary in this analysis.

OBSERVATION 2: Spatially, the major `Classification` categories form contiguous domains rather than being intermixed randomly, suggesting well-organized histological architecture across the section.
Evidence: Panel "Spatial layout by Classification" in `project/outputs/figures/exploratory_plots_overview.png` shows visually distinct clusters/regions of similarly colored spots corresponding to different classifications.

OBSERVATION 3: UMI counts and detected gene numbers vary smoothly across the tissue, with higher `nCount_RNA` and `nFeature_RNA` values concentrated in central, dense tissue regions and lower values toward the periphery.
Evidence: Panels "UMI count per spot" and "Detected genes per spot" in `project/outputs/figures/exploratory_plots_overview.png` together with histograms in `project/outputs/figures/qc_distributions.png` show broad right-skewed distributions and spatial gradients correlated with tissue-dense versus sparse regions.

OBSERVATION 4: Immune-enriched classifications are spatially associated with invasive cancer regions, consistent with immune infiltration at tumor borders.
Evidence: In the "Spatial layout by Classification" panel of `exploratory_plots_overview.png`, spots labeled "Invasive cancer + lymphocytes" and "Lymphocytes" frequently occur at adjacent or partially overlapping areas, and the neighbor classification heatmap in `project/outputs/figures/neighbor_classification_heatmap.png` shows that lymphocyte-classified spots have high neighbor proportions of "Invasive cancer + lymphocytes" and vice versa.

OBSERVATION 5: Normal/stromal regions form large, coherent domains that are spatially separated from the invasive cancer core but still show localized pockets of lymphocytes.
Evidence: The categories "Normal + stroma + lymphocytes", "Stroma", and "Stroma + adipose tissue" occupy broad territories in the spatial classification plot, while the neighbor heatmap indicates that "Normal + stroma + lymphocytes" spots are most often neighbored by the same class but have nonzero neighbor proportions of "Lymphocytes".

OBSERVATION 6: Epithelial and basal markers (EPCAM, KRT8, KRT18, KRT14, KRT5) exhibit region-specific expression consistent with tumor epithelial compartments, with EPCAM/KRT8/KRT18 strongest in putative luminal-like tumor areas and KRT14/KRT5 enriched in more basal-like or peripheral zones.
Evidence: Spatial expression panels for these genes in `project/outputs/figures/spatial_gene_panel.png` show high-intensity clusters that overlap primarily with regions annotated as "Invasive cancer + lymphocytes" and/or DCIS, with complementary patterns between luminal and basal keratins.

OBSERVATION 7: Immune lineage markers for T cells and B cells (CD3D, CD3E, CD2, MS4A1, CD79A) localize to discrete foci often near or surrounding tumor regions, rather than being uniformly distributed across the section.
Evidence: In `spatial_gene_panel.png`, expression of these immune markers is concentrated in clusters that coincide with or border the lymphocyte-rich and "Invasive cancer + lymphocytes" annotated areas, leaving stromal-only regions largely low-expressing.

OBSERVATION 8: Myeloid and stromal markers (LYZ, CD68, COL1A1, COL1A2, VIM) are broadly expressed in non-epithelial regions, with fibroblast/ECM markers (COL1A1/COL1A2) forming large stromal domains and myeloid markers (LYZ/CD68) appearing in more punctate patterns.
Evidence: `spatial_gene_panel.png` shows COL1A1/COL1A2/VIM enriched in regions corresponding to "Stroma" and "Stroma + adipose tissue" classifications, while LYZ/CD68 expression is more spotty and overlaps with both stromal and immune-associated classifications.

OBSERVATION 9: Neighborhood analysis indicates strong homotypic clustering within each major `Classification`, with spots most frequently neighbored by the same class, but also reveals prominent interfaces between lymphocyte-rich and invasive cancer regions.
Evidence: The row-normalized neighbor classification proportions in `project/outputs/figures/neighbor_classification_heatmap.png` show high diagonal values (self-neighboring) for each class, yet lymphocyte-classified spots have substantial neighbor proportions of "Invasive cancer + lymphocytes" and DCIS, and vice versa.

OBSERVATION 10: The two ambiguous/low-confidence categories ("Artefact" and the rare NA labels in `Classification`) are spatially isolated and do not form substantial neighborhoods with any single biological class, suggesting they correspond to technical or edge effects.
Evidence: Value counts of `Classification` show very low frequencies for "Artefact" and NA, and these classes contribute minimally to neighbor co-occurrence in the neighbor heatmap, with small, dispersed spatial footprints in the classification plot.
