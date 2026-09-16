# Bicyclus anynana developmental stage ordering from RNA-seq

## Title & Objective
Infer the relative developmental chronology of five stages in a Bicyclus anynana RNA-seq dataset using only expression data, and group sample IDs into biological replicates for each stage.

## Data & Methods
- **Input data**: `library/datasets/butterfly_data.csv` (16,420 genes × 15 samples; columns `Sample_1`–`Sample_15`).
- **Preprocessing**:
  - Filtered low-expression genes: retained genes with count > 1 in at least 2 samples (16,420 → 14,542 genes).
  - Normalization: library-size normalization to counts-per-million (CPM), followed by log2(CPM + 1) transformation.
- **Sample similarity & clustering**:
  - Computed sample–sample distance as 1 − Pearson correlation on log-normalized expression (all 14,542 genes).
  - Performed PCA on samples; first 5 PCs explained ~88% of variance (PC1 ≈ 35.7%, PC2 ≈ 25.9%).
  - Ran k-means clustering (k = 5) on PC1–PC5 to define five replicate groups (Cluster_1–Cluster_5).
  - Generated a hierarchical clustering dendrogram (average linkage) from the same distance matrix.
- **Developmental axis and stage ordering**:
  - Defined a 1D developmental axis as PC1 from PCA on the normalized expression matrix.
  - Assigned each sample its PC1 coordinate and computed mean PC1 per cluster.
  - Ordered clusters by mean PC1 (ascending) and mapped them to Stage_1 (earliest) through Stage_5 (latest).

## Results
- **Cluster composition (replicate groups)**:
  - Cluster_1: Sample_7, Sample_8, Sample_9
  - Cluster_2: Sample_1, Sample_2, Sample_3, Sample_11
  - Cluster_3: Sample_10, Sample_12
  - Cluster_4: Sample_13, Sample_14, Sample_15
  - Cluster_5: Sample_4, Sample_5, Sample_6

- **Developmental axis (PC1) cluster means**:
  - Cluster_3: mean PC1 ≈ -130.1
  - Cluster_2: mean PC1 ≈ -65.3
  - Cluster_5: mean PC1 ≈ 13.2
  - Cluster_1: mean PC1 ≈ 67.0
  - Cluster_4: mean PC1 ≈ 93.6

- **Inferred developmental stage order (earliest → latest)**:
  - **Stage_1** (earliest): Cluster_3 → Sample_10, Sample_12
  - **Stage_2**: Cluster_2 → Sample_1, Sample_2, Sample_3, Sample_11
  - **Stage_3**: Cluster_5 → Sample_4, Sample_5, Sample_6
  - **Stage_4**: Cluster_1 → Sample_7, Sample_8, Sample_9
  - **Stage_5** (latest): Cluster_4 → Sample_13, Sample_14, Sample_15

## Caveats & Warnings
- **Axis interpretation**: PC1 was assumed to reflect developmental progression; without external markers, earlier vs. later orientation relies on the dominant expression gradient and is not independently validated.
- **Small sample size per stage**: Two stages have only 2–3 replicates, which can increase uncertainty in cluster-level means along the axis (though clusters are well separated in PC space).

## Next Steps
- Validate the inferred order using known stage-specific marker genes or external developmental annotations, if available.
- Explore differential expression between consecutive stages to identify genes driving progression.
- Consider alternative trajectory inference methods or nonlinear embeddings to confirm the robustness of the inferred chronology.

## References
- Love MI, Huber W, Anders S. Moderated estimation of fold change and dispersion for RNA-seq data with DESeq2. *Genome Biol.* 2014;15(12):550. doi:10.1186/s13059-014-0550-8
- Robinson MD, McCarthy DJ, Smyth GK. edgeR: a Bioconductor package for differential expression analysis of digital gene expression data. *Bioinformatics*. 2010;26(1):139-140. doi:10.1093/bioinformatics/btp616
