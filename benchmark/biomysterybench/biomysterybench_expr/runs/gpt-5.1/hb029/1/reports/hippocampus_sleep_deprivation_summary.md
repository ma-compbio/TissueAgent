# Title & Objective

**Objective:** Infer, from unlabeled hippocampus bulk RNA-seq data (8 samples), which samples came from sleep-deprived mice and which from controls, using only gene expression patterns.

# Data & Methods

- **Input data:** `library/datasets/hb029_counts_cleaned.csv` (51,826 genes × 8 samples; columns: sample1–sample8).
- **Preprocessing & QC:**
  - Confirmed 8 samples with integer count data and no missing values.
  - Computed per-sample QC (library size, detected genes, count distribution) and a dataset inventory.
  - Normalized to counts-per-million (CPM) and applied log1p transform; stored raw and normalized data in `hb029_normalized.h5ad`.
- **Clustering:**
  - Selected the top 2,000 most variable genes (by variance of log1p CPM across samples).
  - Computed a sample–sample Pearson correlation matrix on these genes and derived a correlation distance (1 – correlation).
  - Performed hierarchical clustering (average linkage) and defined a two-cluster split:
    - Cluster1: sample1, sample2, sample3, sample5, sample6, sample7
    - Cluster2: sample4, sample8
  - Ran PCA on the same 2,000-gene matrix to obtain PC1/PC2 for visualization.
- **Differential expression:**
  - Compared Cluster1 vs Cluster2 using Welch’s t-tests per gene on log1p(CPM) values.
  - For each gene, computed log2 fold-change (Cluster1 / Cluster2 on CPM scale with pseudocount), mean log1p expression per cluster, mean CPM per cluster, t statistic, p-value, and Benjamini–Hochberg FDR.
  - Constructed full DE results (`de_results_cluster1_vs_cluster2.tsv`) and extracted top ~50 markers up in each cluster (`top_markers_by_cluster.tsv`).
  - Ensembl IDs were retained; gene-symbol mapping was not possible due to lack of local annotation and no internet access.
- **Heuristic assignment of sleep deprivation:**
  - Summarized log2FC and FDR distributions among top markers for each cluster.
  - Defined the cluster with higher median log2FC among its markers as the more "activated" cluster.
  - By biological prior (sleep deprivation → stronger neural transcriptional activation), labeled the more activated cluster as **sleep_deprived** and the other as **control**.

# Results

- **Clustering outcome:**
  - Cluster1: sample1, sample2, sample3, sample5, sample6, sample7
  - Cluster2: sample4, sample8
- **Marker statistics (from `top_markers_by_cluster.tsv`):**
  - Cluster1 (n=50 markers):
    - log2FC_mean ≈ 3.73; log2FC_median ≈ 1.55
    - log2FC_range ≈ [0.12, 23.88]
    - Median FDR ≈ 0.30; 6/50 markers with FDR < 0.25
  - Cluster2 (n=50 markers):
    - log2FC_mean ≈ -1.35; log2FC_median ≈ -0.76
    - log2FC_range ≈ [-3.73, -0.11]
    - Median FDR ≈ 0.24; 29/50 markers with FDR < 0.25
- **Interpretation of clusters:**
  - Cluster1 shows markedly higher positive log2FC values among its markers (mean ~3.7, median ~1.55, maximum ~23.9), consistent with a more globally upregulated/activated state.
  - Cluster2 markers have negative mean and median log2FC, consistent with relatively reduced expression compared with Cluster1.
  - Using the predefined heuristic, Cluster1 is considered the "activated" cluster and is therefore labeled **sleep_deprived**; Cluster2 is labeled **control**.
- **Final inferred conditions per sample (from `sample_condition_assignments.tsv`):
  - Sleep-deprived (Cluster1): **sample1, sample2, sample3, sample5, sample6, sample7**
  - Control (Cluster2): **sample4, sample8**

# Caveats & Warnings

- No gene-symbol annotations or pathway databases were available; the inference uses only the magnitude and direction of differential expression, not specific biological pathways or known sleep-deprivation markers.
- Sample size is very small (6 vs 2), and FDR values are modest; the DE signal is not uniformly strong, and results should be viewed as heuristic.
- The assignment of the more activated cluster to sleep deprivation is based on general biological expectations rather than direct validation.

# Next Steps

- If gene annotation becomes available, re-map Ensembl IDs to gene symbols and verify whether typical sleep-deprivation markers (e.g., immediate early genes, stress-response genes) are enriched in the inferred sleep-deprived cluster.
- Perform formal functional enrichment (GO, KEGG, or MSigDB) on upregulated genes per cluster to validate the condition labels.
- Validate the inferred labels against any external metadata or orthogonal measurements, if obtainable in the future.

# References

- Benjamini Y, Hochberg Y. Controlling the False Discovery Rate: A Practical and Powerful Approach to Multiple Testing. *J R Stat Soc Series B*. 1995.
- Anders S, Huber W. Differential expression analysis for sequence count data. *Genome Biology*. 2010.
