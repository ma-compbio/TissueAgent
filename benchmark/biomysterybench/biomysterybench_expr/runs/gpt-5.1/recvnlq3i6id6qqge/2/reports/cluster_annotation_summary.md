# Sample Clustering and Tissue Interpretation

## Overview

We performed unsupervised clustering of 1,802 RNA-seq samples (55,600 genes) from the provided expression matrix (`anonymizedGeneExp.tsv.gz`) to identify major tissue-type groupings, derive cluster marker genes, and interpret the cluster containing **rnaseqSampleID_2**.

Key steps:
- Log1p transform of expression values.
- Selection of the top 3,000 most variable genes.
- Gene-wise Z-scoring across samples.
- PCA to 50 components, using the first 20 PCs for clustering and UMAP visualization.
- K-means clustering (k=9) based on silhouette analysis.
- Per-cluster marker gene detection using Welch's t-tests and log2 fold-change.
- Tissue interpretation using both marker genes and mean tissue scores from `sample_by_tissue_scores.tsv`.

## Dimensionality Reduction and Clustering

### Preprocessing
- Input: 55,600 genes × 1,802 samples; gene IDs are gene symbols, samples `rnaseqSampleID_*`.
- Transformation: natural-log transform `log1p(expression)` to stabilize variance.
- Highly variable genes: variance of log-expression across samples was computed per gene; the **top 3,000 most variable genes** were retained (3,002 due to ties).
- Standardization: for each selected gene, values were Z-scored across samples (mean 0, SD 1). Zero-variance genes were set to 0 after scaling.

### PCA
- PCA was run on the scaled HVG matrix (samples × genes).
- First 50 PCs retained; first 10 PCs explained ~74% of variance; first 20 PCs explained ~85% of variance.

### Clustering
- Clustering was performed on the first 20 PCs.
- K-means clustering was tested for k=2–10; silhouette scores increased up to k≈9 and peaked at **k=9 (silhouette ≈ 0.43)**.
- Final model: **K-means with k=9**, 50 random initializations, clustering in 20D PC space.

Cluster sizes:
- Cluster 0: 128 samples
- Cluster 1: 313 samples
- Cluster 2: 379 samples
- Cluster 3: 135 samples
- Cluster 4: 183 samples
- Cluster 5: 172 samples
- Cluster 6: 167 samples
- Cluster 7: 78 samples
- Cluster 8: 247 samples

**rnaseqSampleID_2** was assigned to **cluster 2**.

### Visualization
- UMAP was run on the first 20 PCs (n_neighbors=15, min_dist=0.3, Euclidean metric).
- The 2D embedding was used for visualization, coloring samples by K-means cluster.
- rnaseqSampleID_2 was highlighted with a distinct outline.

Output figure:
- `project/outputs/figures/sample_clustering_plot.png`

## Cluster Marker Genes

Marker detection was performed on the full gene set using log1p-transformed expression:

For each cluster:
- Samples were split into **in-cluster** vs **all other samples**.
- For each gene:
  - Mean log-expression in-cluster and outside were computed.
  - Welch's t-test was applied (in-cluster vs outside) on log-expression.
  - Mean linear-scale expression was also computed from the original matrix.
  - Log2 fold-change (log2FC) was computed on linear means with a small pseudocount (1e-6).
- Genes were filtered to those **upregulated in the cluster** (`log2FC > 0.5`).
- A ranking score was defined as `log2FC × (-log10 p-value)`.

All marker statistics are in:
- `project/outputs/tables/cluster_markers.tsv`

Each row contains:
- `cluster_label`, `gene_id`, `mean_in_cluster_log`, `mean_outside_log`,
- `mean_in_cluster_linear`, `mean_outside_linear`, `log2FC`, `t_stat`, `p_value`,
- and derived `neg_log10_p`, `rank_score`.

### Summary of Top Markers per Cluster (selected examples)

Below are representative top markers (by rank score) for each cluster, which guide tissue annotations.

- **Cluster 0**:
  - Top markers: **RAC2, IL2RG, LCP1, LAPTM5, CYTIP, CD37, NCF1, CD53, PLEK, ICAM3, CORO1A, MYO1G, CD300A, SASH3, ACAP1, IFI30, FERMT3, UCP2, TRAF3IP3**.
  - Interpretation: Strong enrichment for lymphocyte/myeloid immune markers (e.g., RAC2, IL2RG, CD37, CD53, LCP1), consistent with **blood/immune** tissues.

- **Cluster 1**:
  - Top markers: **MYH11, CNN1, TAGLN, CARMN, MYL9, LMOD1, ACTA2, SMTN, MYLK, MYOCD**, etc.
  - Interpretation: Smooth muscle / vascular markers (MYH11, ACTA2, TAGLN, CNN1) suggest **vascular/visceral smooth muscle**, likely enriched in **arterial/vascular or GI smooth muscle** samples.

- **Cluster 2** (contains rnaseqSampleID_2):
  - Top markers: **GFAP, OPALIN, OLIG2, MIR9-1HG, MT3, KCNJ9, VSTM2B, GRM3, OLIG1, KCNJ10, PMP2, STMN4, MOG, MOBP, ELAVL3, PLP1, NTSR2, KIF5A**.
  - Interpretation: A mix of astrocytic (GFAP, KCNJ10), oligodendrocyte/oligodendrocyte precursor (OPALIN, OLIG1, OLIG2, MOG, PLP1, MOBP, PMP2), and neuronal/brain markers (GRM3, ELAVL3, KIF5A, VSTM2B, MT3). This profile is characteristic of **central nervous system (CNS) brain tissue**, with a bias toward white-matter / glial-enriched brain regions.

- **Cluster 3**:
  - Top markers: **TRIM29, KRT5, PKP3, LYPD3, SDC1, LAD1, SFN, TACSTD2, RAB25, NECTIN4, EVPL, SERPINB5**.
  - Interpretation: Basal-type epithelial/keratinizing markers (KRT5, EVPL, LAD1, SFN) and TRIM29/NECTIN4 are suggestive of **stratified squamous epithelium**, likely **skin/keratinized epithelium**.

- **Cluster 4**:
  - Top markers: **SERPINA5, GSTA1, GSTA2, PAH, MAT1A, CYP2C8, ONECUT1, APOA1**, etc.
  - Interpretation: Classic hepatocyte/liver markers (GSTA1/2, MAT1A, CYP2C8, ONECUT1, APOA1) indicating **liver**.

- **Cluster 5**:
  - Top markers: **COX6A2, MB, TCAP, TNNC1, CKM, LMOD2, MYH7, NRAP, CSRP3, HRC, XIRP1, ACTN2, TRIM63, MYOZ2**.
  - Interpretation: Strong striated muscle and contractile apparatus markers (MB, CKM, MYH7, TNNC1, ACTN2) consistent with **cardiac and/or skeletal muscle**; tissue scores (below) help resolve the dominant subtype.

- **Cluster 6**:
  - Top markers: **FABP4, CD36, CIDEC, ADIPOQ, PLIN1, PPARG, CFD, AQP7, CIDEA, LGALS12, LPL**.
  - Interpretation: Adipocyte markers (FABP4, ADIPOQ, PPARG, PLIN1, LPL, CIDEA), pointing to **adipose tissue**.

- **Cluster 7**:
  - Top markers: **FN1, GPX8, FKBP10, COL6A3, COL1A2, ANPEP, DKK1, MME, HOXC6/HOXC10, CD248, COL1A1**.
  - Interpretation: Extracellular matrix/mesenchymal and HOX-patterned markers, likely **stromal/fibroblast-rich connective tissues**, possibly from **GI or other mucosal organs**.

- **Cluster 8**:
  - Top markers: **KRT18, EPCAM, TFF3, KRT8, CLDN3, TSPAN1, CDH1, F11R, SLCO2A1, SLC34A2, TMPRSS2**.
  - Interpretation: Simple epithelial markers with EPCAM, KRT8/18, tight junction proteins (CLDN3, F11R), and secretory factors (TFF3) characteristic of **glandular/epithelial tissues**, particularly **GI epithelium and related glands** (e.g., colon, stomach, or other mucosal epithelia).

## Tissue Score-Based Cluster Annotation

Using `sample_by_tissue_scores.tsv` (per-sample scaled tissue scores), we computed mean scores per cluster:

- **Cluster 0**:
  - Very high **Whole_blood_immune** (~+1.75) and **Spleen** (~+1.7); slightly negative for most solid tissues.
  - Annotation: **Peripheral blood / immune-rich tissues (blood, spleen)**.

- **Cluster 1**:
  - Mildly positive **Heart** (+0.10) and **Skeletal_muscle** (+0.10); otherwise near baseline.
  - Together with smooth muscle markers (MYH11, ACTA2), this points to **vascular/visceral smooth muscle**, possibly samples enriched in **vasculature or GI smooth muscle layers** rather than pure heart/skeletal muscle.

- **Cluster 2** (rnaseqSampleID_2 cluster):
  - Strongly positive **Whole_brain** (~+1.11), **Cerebral_cortex** (~+0.47), **Cerebellum** (~+0.70), **Hippocampus** (~+0.97).
  - Negative or near-neutral for non-brain tissues.
  - Combined with CNS glial/neuronal markers, this firmly indicates **brain tissue**, spanning multiple brain subregions.

- **Cluster 3**:
  - Markedly high **Skin** (~+2.25); others near or below zero.
  - Annotation: **Skin / epidermis**.

- **Cluster 4**:
  - Strongly positive **Liver** (~+0.88) and **Pancreas** (+0.63); modest positive **Kidney** and **Stomach**.
  - Given classic hepatocyte markers, the dominant identity is **Liver**; some cross-tissue signal (e.g., pancreas) may reflect shared metabolic/glandular programs or mixed tissue representation.

- **Cluster 5**:
  - Very high **Heart** (~+1.36) and **Skeletal_muscle** (~+1.58); negative for most others.
  - Annotation: **Cardiac and skeletal muscle**; likely enriched for **heart and limb muscle** samples.

- **Cluster 6**:
  - Very high **Adipose_tissue** (~+1.53); others roughly neutral or slightly negative.
  - Annotation: **Adipose tissue (white fat depots)**.

- **Cluster 7**:
  - Scores are generally modest; mild negative across many tissues, slight enrichment not clearly pointing to a single organ.
  - With COL1A1/COL1A2/FN1 and HOX genes, these may represent **stromal/connective tissue or fibroblast-rich samples**, possibly from multiple organs.

- **Cluster 8**:
  - Strongly positive **Kidney** (~+0.35), **Lung** (~+0.67), **Colon** (~+0.69), **Small_intestine** (~+0.45), **Stomach** (~+0.31), and **Thyroid** (~+0.89), as well as moderately positive **Whole_blood_immune** (~+0.25).
  - Together with EPCAM/KRT8/18/CLDN3/TFF3 markers, this cluster reflects **simple epithelial/glandular tissues**, including **GI epithelium (small intestine, colon, stomach)**, **lung epithelium**, **kidney epithelium**, and **thyroid**.

## Detailed Interpretation of rnaseqSampleID_2 Cluster (Cluster 2)

### Cluster Identity

- **Dominant tissue**: Central nervous system **brain**.
- **Evidence from tissue scores**:
  - Whole_brain, Cerebral_cortex, Cerebellum, and Hippocampus scores are all strongly positive at the cluster level, indicating samples closely match brain-specific expression signatures across multiple subregions.
- **Evidence from marker genes**:
  - **Astrocyte / glial markers**: GFAP, KCNJ10 (Kir4.1), MT3.
  - **Oligodendrocyte / myelin markers**: OPALIN, OLIG1, OLIG2, MOG, PLP1, MOBP, PMP2.
  - **Neuronal/brain-enriched markers**: GRM3 (metabotropic glutamate receptor), ELAVL3 (HuC), KIF5A, STMN4, VSTM2B, NTSR2.
  - These collectively indicate a mix of glial and neuronal expression, consistent with bulk **brain tissue** containing multiple neural cell types.

### Possible Anatomical Sub-regions

- The strong **Hippocampus** and **Cerebral_cortex** scores, combined with neuronal markers like GRM3, ELAVL3, and NTSR2, suggest enrichment for **forebrain** regions (cortex and hippocampus).
- Oligodendrocyte/myelin genes (MOG, PLP1, MOBP, PMP2, OPALIN) point to substantial **white matter** content, which can be prominent in many brain regions, including cortex and cerebellum.
- The positive **Cerebellum** scores indicate that some samples in this cluster also come from cerebellar tissue; however, the overall marker set is not cerebellum-exclusive. Thus, cluster 2 likely represents a **broad brain cluster** encompassing multiple subregions rather than a single anatomic structure.

### rnaseqSampleID_2 within Cluster 2

- **Cluster assignment**: rnaseqSampleID_2 → **cluster 2**.
- **Tissue score profile (from Step 2)**:
  - Very high **Whole_brain**, **Cerebral_cortex**, **Cerebellum**, and **Hippocampus** scores (relative to other tissues).
  - Low/negative scores for non-brain tissues (liver, heart, kidney, lung, adipose, etc.).
- **Interpretation**:
  - rnaseqSampleID_2 is best interpreted as a **brain sample**, likely from **forebrain regions** such as **cerebral cortex and/or hippocampus**, with typical representation of astrocytes, oligodendrocytes, and neurons.
  - The presence of strong myelin-related genes implies substantial white-matter content, so rnaseqSampleID_2 may derive from a region or dissection including both cortical gray matter and underlying white matter.

### Key Marker Genes Supporting the Brain Call

Top markers (by combined log2FC and significance) for cluster 2 include (all strongly overexpressed vs other clusters):
- **GFAP** – canonical astrocyte intermediate filament.
- **OPALIN, OLIG1, OLIG2, MOG, PLP1, MOBP, PMP2** – oligodendrocyte/myelin markers.
- **KCNJ10, KCNJ9** – inward-rectifier potassium channels enriched in astrocytes and certain neurons.
- **GRM3** – glutamate receptor highly expressed in neurons, especially cortex/limbic regions.
- **ELAVL3** – neuron-specific RNA-binding protein.
- **MT3** – metallothionein isoform enriched in neurons and astrocytes.
- **VSTM2B, NTSR2, KIF5A** – additional brain-enriched genes associated with neuronal function.

Together, these markers, the tissue scores, and the clustering pattern strongly support that **rnaseqSampleID_2 belongs to a CNS brain cluster (cluster 2), most consistent with cortex/hippocampus-enriched brain tissue containing mixed neuronal and glial populations**.

## Outputs

Generated artifacts:
- **Sample cluster assignments**: `project/outputs/tables/sample_cluster_assignments.tsv`
- **Cluster marker genes (all clusters)**: `project/outputs/tables/cluster_markers.tsv`
- **Top 50 markers for cluster 2 (rnaseqSampleID_2 cluster)**: `project/outputs/tables/cluster_markers_cluster2_top50.tsv`
- **UMAP clustering plot**: `project/outputs/figures/sample_clustering_plot.png`
- **Cluster annotation report (this file)**: `project/outputs/reports/cluster_annotation_summary.md`
