# Title & Objective

**Task:** Infer the five developmental stages represented in a Bicyclus anynana bulk RNA-seq dataset, using only the gene expression matrix (no labels), and order these stages from earliest to latest. For each stage, group the biological replicate samples.

**Objective:** Recover (1) which samples belong to the same developmental time point and (2) the correct temporal ordering of these five stages.

---

# Data & Methods

## Data
- Input file: `library/datasets/butterfly_data.csv`
- Dimensions: 16,420 genes × 15 samples (columns `Sample_1`–`Sample_15`).
- No external metadata (labels, time points, or covariates) were used.

## Normalization & QC
1. **Normalization**
   - Treated input values as raw counts.
   - Computed per-sample library sizes (column sums).
   - Converted to counts-per-million (CPM): `CPM_ij = counts_ij / library_size_j * 1e6`.
   - Applied natural log transform: `log_cpm = log1p(CPM)`.
   - Saved normalized matrix: `tables/butterfly_normalized_expression.tsv` (genes × samples).

2. **QC metrics** (per sample, based on log-CPM unless noted otherwise):
   - `library_size`: total raw counts.
   - `mean_expression`, `variance_expression`: across genes.
   - `fraction_zeros`: fraction of genes with zero raw counts.
   - `mean_correlation_to_others`: mean Pearson correlation to all other samples.
   - `correlation_outlier_flag`: TRUE if mean correlation < (median − 2 × MAD) across samples.
   - All samples were **retained**; outlier flags are annotative.

   QC summary table: `tables/butterfly_sample_qc_summary.tsv`.

## Clustering Samples into 5 Stages
1. Loaded `butterfly_normalized_expression.tsv`, transposed to a 15 (samples) × 16,420 (genes) matrix.
2. Removed zero-variance genes; standardized each gene across samples (z-score).
3. Performed PCA on the standardized matrix; used the first 5 principal components.
4. Applied k-means clustering (k = 5, `n_init = 50`) on the 5D PC scores.
5. Saved assignments: `tables/butterfly_sample_stage_clusters.tsv` (columns: `sample_id`, `cluster_id` in {1,…,5}).
6. Visualizations:
   - `figures/butterfly_sample_pca.png`: samples in PC1–PC2 colored by cluster.
   - `figures/butterfly_sample_clustering_heatmap.png`: Euclidean distance heatmap between samples in PC space, ordered by cluster.

## Ordering Clusters Along a Developmental Trajectory
1. **Cluster centroids**
   - For each gene and each cluster, computed the mean log-CPM across all samples in that cluster.
   - Output: `tables/butterfly_cluster_centroid_profiles.tsv` (genes × 5 clusters; columns `cluster_1`–`cluster_5`).

2. **PCA on centroids**
   - PCA was run on the 5 centroid profiles (clusters as observations).
   - PC1 captured ~46% of centroid variance; PC2 ~30%.
   - PC1 scores for clusters:
     - cluster_1: PC1 ≈ −27.4
     - cluster_2: PC1 ≈ −54.5
     - cluster_3: PC1 ≈  29.6
     - cluster_4: PC1 ≈ −49.1
     - cluster_5: PC1 ≈ 101.4

3. **Developmental ordering criterion**
   - Assumed PC1 reflects the major developmental progression.
   - Ordered clusters by increasing PC1 value (earliest = lowest PC1):
     - cluster_2 → cluster_4 → cluster_1 → cluster_3 → cluster_5
   - Saved as `tables/butterfly_stage_order.tsv` with columns:
     - `stage_rank` (1–5; 1 = earliest)
     - `cluster_id` (2, 4, 1, 3, 5 in order).

4. **Monotonic gene-expression support**
   - For each gene, examined its centroid expression along [cluster_2, cluster_4, cluster_1, cluster_3, cluster_5].
   - Counted genes that were monotonic non-decreasing or non-increasing along this sequence.
   - Found 2,313 / 16,420 genes with monotonic patterns, supporting a smooth transcriptional trajectory consistent with this order.

5. **Trajectory visualization**
   - `figures/butterfly_developmental_trajectory.png`: cluster centroids in PC1–PC2 with an arrowed path following cluster_2 → 4 → 1 → 3 → 5.

## Assembling Final Stage Labels and Replicates
- Joined `butterfly_stage_order.tsv` with `butterfly_sample_stage_clusters.tsv` via `cluster_id`.
- Mapped `stage_rank = 1..5` to `Stage_1..Stage_5`.
- For each stage, listed all samples with matching `cluster_id`.
- Result saved as plain text: `reports/butterfly_ordered_stages_with_samples.txt`.

---

# Results

## Final Developmental Stage Order (Earliest → Latest)

Using the inferred trajectory (cluster_id 2 → 4 → 1 → 3 → 5), the stages and their biological replicates are:

- **Stage_1 (earliest; cluster_id = 2):**
  - Samples: `Sample_13`, `Sample_14`, `Sample_15`

- **Stage_2 (cluster_id = 4):**
  - Samples: `Sample_7`, `Sample_8`, `Sample_9`

- **Stage_3 (cluster_id = 1):**
  - Samples: `Sample_4`, `Sample_5`, `Sample_6`

- **Stage_4 (cluster_id = 3):**
  - Samples: `Sample_1`, `Sample_2`, `Sample_3`, `Sample_11`

- **Stage_5 (latest; cluster_id = 5):**
  - Samples: `Sample_10`, `Sample_12`

This matches the contents of `reports/butterfly_ordered_stages_with_samples.txt`.

---

# Caveats & Warnings

- **Unsupervised nature of the solution:**
  - No ground-truth labels were available; the stage order is inferred solely from transcriptomic structure (PCA + clustering + monotonic patterns).
  - While the approach is standard and internally consistent, it has not been benchmarked against known developmental annotations for this dataset.

- **Outlier samples:**
  - QC flagged `Sample_10`, `Sample_12`, `Sample_14`, and `Sample_15` as lower-correlation outliers (mean correlation below a robust threshold), but they were **not** removed.
  - These samples still contributed to cluster centroids and may slightly influence the inferred trajectory.

- **Small number of samples per stage:**
  - Some inferred stages have only 2–3 replicates, which can make centroid estimates less stable than in larger cohorts.

- **Method-specific assumptions:**
  - Developmental direction was aligned with PC1 of the centroid PCA; alternative methods (e.g., more complex trajectory inference) could in principle suggest a different ordering if, for instance, PC2 were more biologically relevant.

---

# Next Steps

- **Biological validation:**
  - Cross-check the inferred order against known Bicyclus anynana developmental markers or time-resolved datasets, if available.

- **Gene-level characterization:**
  - Identify key genes or pathways that change monotonically across Stage_1 → Stage_5 to biologically annotate each developmental stage.

- **Robustness checks:**
  - Re-run clustering with alternative distance metrics (e.g., correlation distance) or methods (hierarchical clustering) and confirm that the stage groups and order are stable.

- **Outlier sensitivity analysis:**
  - Repeat the trajectory inference excluding QC-flagged samples to assess their impact on ordering.

---

# References

1. Love MI, Huber W, Anders S. Moderated estimation of fold change and dispersion for RNA-seq data with DESeq2. *Genome Biol.* 2014;15(12):550. doi:10.1186/s13059-014-0550-8.
2. Robinson MD, Oshlack A. A scaling normalization method for differential expression analysis of RNA-seq data. *Genome Biol.* 2010;11(3):R25. doi:10.1186/gb-2010-11-3-r25.
3. Ringnér M. What is principal component analysis? *Nat Biotechnol.* 2008;26(3):303–304. doi:10.1038/nbt0308-303.
