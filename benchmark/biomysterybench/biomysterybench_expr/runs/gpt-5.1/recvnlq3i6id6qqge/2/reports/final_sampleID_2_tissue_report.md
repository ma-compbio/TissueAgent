# Title & Objective

**Task:** Infer the tissue of origin for `sampleID_2` from an anonymized bulk RNA-seq expression matrix, using no external metadata.

**Specific objective:** Determine the tissue and, if possible, anatomical sub-region corresponding to the column that matches the user’s `sampleID_2` (mapped in the data as `rnaseqSampleID_2`).

---

## Data & Methods

### Data
- **Expression matrix:** `library/datasets/anonymizedGeneExp.tsv.gz`
  - Size: 55,600 genes × 1,802 samples.
  - Orientation: rows = genes, columns = samples.
  - Gene IDs: human gene symbols (e.g., DDX11L1, WASH7P, GFAP, MOG).
  - Sample IDs: `rnaseqSampleID_1` … `rnaseqSampleID_1802`.
  - No column named literally `sampleID_2`; the only plausible match is **`rnaseqSampleID_2`**, which was treated as the user’s `sampleID_2` throughout.

- **QC summaries:**
  - `tables/expression_matrix_summary.tsv`: confirms matrix size, orientation, sparsity (~46% zeros), and that `contains_sampleID_2 = False`, `contains_rnaseqSampleID_2 = True`.
  - `tables/sample_qc_metrics.tsv`: per-sample total counts, detected genes, and basic statistics.
  - `tables/gene_qc_metrics.tsv`: per-gene detection rates and expression statistics.

### Overview of analysis pipeline

1. **QC and matrix characterization (Step 1)**
   - Loaded the full matrix into memory.
   - Verified: rows = genes, columns = samples; gene IDs are symbols; samples are `rnaseqSampleID_*`.
   - Confirmed `rnaseqSampleID_2` is present and has typical library size and gene-detection metrics (non-outlier).

2. **Tissue-marker scoring (Step 2)**
   - Curated marker gene sets for 18 tissues/regions:
     - Liver, Heart, Skeletal_muscle, Whole_brain, Cerebral_cortex, Cerebellum, Hippocampus, Kidney, Lung, Whole_blood_immune, Adipose_tissue, Pancreas, Small_intestine, Colon, Stomach, Skin, Thyroid, Spleen.
   - Intersected marker sets with expressed genes; each tissue retained ≥16 markers (many ~20–50).
   - Computed **gene-wise z-scores** across samples.
   - For each tissue and sample, computed the mean z-score of that tissue’s detected marker genes → **sample × tissue score matrix**.
   - Saved to `tables/sample_by_tissue_scores.tsv` and visualized as a clustered heatmap (`figures/sample_tissue_score_heatmap.png`), highlighting `rnaseqSampleID_2`.

3. **Unsupervised clustering and cluster interpretation (Step 3)**
   - Preprocessing:
     - Applied **log1p** transform to expression values.
     - Selected the **top ~3,000 most variable genes** across samples.
     - Z-scored each selected gene across samples.
   - Dimensionality reduction:
     - Performed PCA, retaining 50 PCs.
     - Used first 20 PCs for clustering and UMAP visualization.
   - Clustering:
     - Ran K-means for k = 2–10; chose **k = 9** by silhouette score (best ≈ 0.43).
     - Final model: `KMeans(n_clusters=9, n_init=50, random_state=0)`.
     - Wrote assignments to `tables/sample_cluster_assignments.tsv` (including `rnaseqSampleID_2`).
   - Cluster marker genes:
     - For each cluster vs all others, used Welch’s t-test on log1p expression per gene.
     - Computed log2 fold-change on linear expression with a small pseudocount.
     - Retained genes with log2FC > 0.5 and ranked by `log2FC × (−log10 p-value)`.
     - Full table: `tables/cluster_markers.tsv`; top 50 markers for the `rnaseqSampleID_2` cluster: `tables/cluster_markers_cluster2_top50.tsv`.
   - Visualization & interpretation:
     - UMAP on first 20 PCs; colored points by cluster; highlighted `rnaseqSampleID_2` (`figures/sample_clustering_plot.png`).
     - Used mean tissue scores per cluster (`tables/cluster_tissue_score_means.tsv`) plus marker genes to assign tissue labels to clusters (e.g., immune/blood, liver, adipose, muscle, brain).
     - Summarized methods and interpretations in `reports/cluster_annotation_summary.md`.

4. **Integrated tissue call for `rnaseqSampleID_2` (Step 4)**
   - Extracted `rnaseqSampleID_2` tissue scores from `sample_by_tissue_scores.tsv`.
   - For each tissue, computed:
     - Raw score, mean and SD across samples.
     - Z-score and percentile for `rnaseqSampleID_2` within that tissue’s score distribution.
   - Confirmed cluster label for `rnaseqSampleID_2` from `sample_cluster_assignments.tsv`.
   - Combined tissue-score enrichment, cluster membership, and cluster marker genes into a single tissue/anatomical-region call.
   - Summarized in `reports/sampleID_2_tissue_call.md` and `tables/sampleID_2_tissue_scores.tsv`.

---

## Results

### 1. Tissue-score profile of rnaseqSampleID_2

From `tables/sampleID_2_tissue_scores.tsv` and `tables/sample_by_tissue_scores.tsv`:

- **Brain-related tissues:**
  - Whole_brain: raw score 1.36; **z ≈ 2.08; 93rd percentile**.
  - Cerebral_cortex: raw score 0.97; **z ≈ 2.32; 96th percentile**.
  - Hippocampus: raw score 0.86; **z ≈ 1.31; 90th percentile**.
  - Cerebellum: raw score 0.42; **z ≈ 0.62; 90th percentile**.

- **Non-brain tissues:**
  - All show modestly negative or near-zero scores and sit around the mid or lower percentiles of their distributions, e.g.:
    - Liver: z ≈ −0.17; ~29th percentile.
    - Whole_blood_immune: z ≈ −0.46; ~18th percentile.
    - Spleen: z ≈ −0.48; ~16th percentile.
    - Adipose_tissue, Skin, Lung, Colon, Heart, Skeletal_muscle: similarly unremarkable or negatively enriched.

**Interpretation:** rnaseqSampleID_2 is strongly enriched for **brain** expression signatures (especially cortex and hippocampus) and not enriched for any canonical non-brain tissue.

### 2. Clustering and cluster markers

- From `tables/sample_cluster_assignments.tsv`:
  - **rnaseqSampleID_2 is assigned to cluster 2.**

- High-level cluster identities (from marker genes + mean tissue scores):
  - Cluster 0: Immune/blood–spleen (RAC2, IL2RG, LCP1, etc.; high Whole_blood_immune, Spleen scores).
  - Cluster 1: Visceral/vascular smooth muscle (MYH11, CNN1, TAGLN).
  - **Cluster 2: CNS brain (rnaseqSampleID_2’s cluster).**
  - Cluster 3: Skin / stratified squamous epithelium (KRT5, PKP3, TACSTD2).
  - Cluster 4: Liver/hepatic (SERPINA5, GSTA1/2, APOA1).
  - Cluster 5: Cardiac/skeletal muscle (MYH7, TNNC1, CKM).
  - Cluster 6: Adipose tissue (FABP4, ADIPOQ, PLIN1).
  - Cluster 7: Stromal/mesenchymal fibroblast-rich.
  - Cluster 8: Glandular/simple epithelium (EPCAM, KRT8/18, TFF3) from organs like lung, colon, kidney, thyroid.

- **Cluster 2 marker genes** (top examples from `cluster_markers_cluster2_top50.tsv`):
  - Astrocyte markers:
    - **GFAP, KCNJ10, KCNJ9, MT3.**
  - Oligodendrocyte/myelin markers:
    - **OPALIN, OLIG1, OLIG2, MOG, PLP1, MBP, MOBP, PMP2, BCAS1.**
  - Neuronal/synaptic markers:
    - **GRM3, ELAVL3, KIF5A, STMN4, NTSR2, CEND1, TAGLN3, CTNND2, CPNE6.**
  - Extracellular matrix / perineuronal net components:
    - **BCAN, NCAN, TNR, CSPG5.**

- Mean tissue scores for cluster 2 (from `cluster_tissue_score_means.tsv`):
  - Strongly positive for Whole_brain, Cerebral_cortex, Hippocampus, and Cerebellum.
  - Near-zero or negative for non-brain tissues.

**Interpretation:** Cluster 2 represents **central nervous system brain tissue** with a mixture of neurons, astrocytes, and oligodendrocytes, and pronounced myelin/white-matter signatures.

### 3. Integrated call for sampleID_2

Bringing tissue scores and clustering together:

- rnaseqSampleID_2’s tissue scores show:
  - Very high enrichment for **Whole_brain, Cerebral_cortex, and Hippocampus** (90–96th percentiles).
  - Modest but notable enrichment for Cerebellum (90th percentile).
  - No enrichment for liver, muscle, blood, adipose, skin, kidney, or other peripheral tissues.

- rnaseqSampleID_2 sits in **cluster 2**, whose marker genes are:
  - Highly specific to CNS brain (glial and neuronal markers).
  - Incompatible with non-brain tissues: e.g., no albumin/APO genes (liver), no keratin 5/14 (skin), no MYH7/CKM (striated muscle), no FABP4/ADIPOQ (adipose), no classic blood markers.

- Within CNS tissues, the combination of:
  - High **Cerebral_cortex** and **Hippocampus** scores.
  - Presence of forebrain-biased neuronal genes (e.g., GRM3, ELAVL3, CTNND2, TAGLN3).
  - Strong glial/myelin gene expression (OPALIN, OLIG1/2, MOG, PLP1, MBP, MOBP, PMP2).

supports a forebrain origin with substantial white-matter content.

**Final integrated call:**

- **Tissue:** Central nervous system **brain**.
- **Anatomical region (best-effort):** **Forebrain**, most consistent with **cerebral cortex and/or hippocampus**, including both gray-matter and adjacent white-matter (glial/myelin-rich) components.

---

## Caveats & Warnings

- **Sample ID mapping:**
  - The matrix does not contain an exact column named `sampleID_2`; instead, it uses `rnaseqSampleID_*`. The analysis assumes **`sampleID_2` ≡ `rnaseqSampleID_2`**, which is strongly implied by the naming scheme but not explicitly stated in the data.

- **Bulk tissue resolution:**
  - Data are bulk RNA-seq, so the inferred tissue represents the aggregate of many cell types. The call of “forebrain cortex/hippocampus with white-matter content” is based on mixed neuronal and glial markers and cannot resolve precise subfields (e.g., specific cortical layers or hippocampal subregions).

- **Reference-free, marker-based inference:**
  - Tissue labels are inferred from curated marker sets and unsupervised clustering, not from matched anatomical metadata. While the markers used are standard and the evidence is concordant, fine-grained regional classification is approximate.

- **Cluster heterogeneity within brain:**
  - Cluster 2 aggregates multiple brain samples that likely span cortex, hippocampus, and cerebellum. rnaseqSampleID_2 is on the forebrain-enriched end of this cluster, but an exact anatomical locus cannot be guaranteed from expression alone.

---

## Next Steps

- If finer anatomical detail is needed within brain:
  - Restrict analysis to **brain-only samples** and re-cluster at higher resolution to separate cortex, hippocampus, and cerebellum.
  - Incorporate **more region-specific and layer-specific brain markers** (e.g., layer 2/3 vs 5/6 cortical markers, hippocampal CA vs dentate gyrus markers).
  - If available, integrate **anatomical metadata or imaging/spatial data**.

- For broader validation:
  - Compare rnaseqSampleID_2’s profile to public reference datasets (e.g., GTEx brain regions, Allen Brain Atlas bulk profiles) via correlation.
  - Cross-check the inferred tissue against any external information (e.g., known sample labels, if they become available) to confirm the mapping of `rnaseqSampleID_2` to the true `sampleID_2`.

---

## References

- GTEx Consortium. The Genotype-Tissue Expression (GTEx) project. *Nat Genet.* 2013. doi:10.1038/ng.2653
- Uhlén M, et al. Tissue-based map of the human proteome. *Science.* 2015. doi:10.1126/science.1260419
- Darmanis S, et al. A survey of human brain transcriptome diversity at the single cell level. *PNAS.* 2015. doi:10.1073/pnas.1507125112
- Zeisel A, et al. Cell types in the mouse cortex and hippocampus revealed by single-cell RNA-seq. *Science.* 2015. doi:10.1126/science.aaa1934
