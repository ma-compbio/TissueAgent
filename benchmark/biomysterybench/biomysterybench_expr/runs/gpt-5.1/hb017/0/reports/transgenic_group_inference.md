# Title & Objective

**Objective:** Identify which samples in the mouse tibial muscle injury RNA-seq dataset correspond to the NSE-BMP4 transgenic mouse model (vs wild-type) and list their sample IDs.

# Data & Methods

- **Data:** `library/datasets/cleaned_counts.csv`, a 36,572 (genes) × 21 (samples) integer count matrix (rows = genes, columns = samples). No external metadata were provided.
- **Preprocessing:**
  - Library-size normalization to counts per million (CPM).
  - Log-transformation: log2(CPM + 1).
- **Dimensionality reduction:** Principal Component Analysis (PCA) on the sample × gene log2-CPM matrix; PC1 and PC2 captured the majority of variance.
- **Clustering:** K-means clustering with k = 2 on the first 5 PCs to infer the two underlying genetic groups.
- **Differential expression:** Welch t-tests on log2-CPM between the two clusters (Cluster 2 vs Cluster 1), with Benjamini–Hochberg FDR correction.
- **Transgenic group inference:**
  - Searched for genes with strong, specific overexpression in one cluster, consistent with a BMP4 transgene.
  - Identified a prominent candidate (gene_2772) with ~5 log2-fold higher expression in Cluster 2 vs Cluster 1 and many co-upregulated genes, interpreted as BMP4 overexpression and downstream pathway activation.
  - Labeled the cluster with this signature (Cluster 2) as the NSE-BMP4 transgenic group and the other (Cluster 1) as WT.

# Results

- **Cluster identities:**
  - Cluster 1 → Group_1 (inferred wild-type; `is_transgenic = FALSE`).
  - Cluster 2 → Group_2 (inferred NSE-BMP4 transgenic; `is_transgenic = TRUE`).
- **Transgenic sample IDs (NSE-BMP4):**
  - Sample_13_Group2
  - Sample_14_Group2
  - Sample_16_Group2
  - Sample_17_Group2
  - Sample_18_Group2
  - Sample_19_Group2
  - Sample_20_Group2
  - Sample_21_Group2
  - Sample_4_Group1
  - Sample_5_Group1
  - Sample_7_Group1
  - Sample_8_Group1
  - Sample_9_Group1

These 13 samples are marked `is_transgenic = TRUE` in `tables/sample_group_assignments.tsv` and are exported in `tables/transgenic_sample_ids.txt` and `tables/transgenic_sample_ids.json`.

# Caveats & Warnings

- Gene identifiers in the matrix are position-based (gene_0, gene_1, …); explicit BMP4/Id/Smad gene symbols are not available, so the putative BMP4 transgene and pathway activation were inferred from expression patterns (strong, cluster-specific overexpression and coordinated upregulation), not direct gene naming.
- The sample naming convention (e.g., `Sample_4_Group1` vs `Sample_13_Group2`) does not correspond exactly to the inferred genetic grouping; some samples labeled "Group1" in their ID are inferred transgenic, reflecting that the original name suffix is not a reliable genotype label.
- Clustering and DE analyses were performed on a small number of samples (n=21); while the separation is clear, fine-grained subgroup structure (e.g., timepoints) was not modeled.

# Next Steps

- If available, integrate external gene annotation (mapping gene indices to mouse gene symbols) to directly confirm BMP4 and canonical BMP-target involvement.
- Validate the inferred transgenic vs WT assignments against any hidden ground-truth metadata or orthogonal assays (e.g., genotyping, BMP4 protein measurements).
- Explore timepoint-specific effects or other experimental factors using the same group assignments.

# References

- Anders S, Huber W. Differential expression analysis for sequence count data. *Genome Biol.* 2010;11(10):R106. doi:10.1186/gb-2010-11-10-r106
- Love MI, Huber W, Anders S. Moderated estimation of fold change and dispersion for RNA-seq data with DESeq2. *Genome Biol.* 2014;15(12):550. doi:10.1186/s13059-014-0550-8
