# Group identity inference for NSE-BMP4 transgenic vs WT

## Data and normalization

- Input count matrix: `library/datasets/cleaned_counts.csv` with 36572 genes and 21 samples.

- Counts were normalized per sample by library size (CPM), followed by log2-transformation with a pseudocount of 1 (log2(CPM + 1)).

- No additional gene filtering was applied beyond removal of zero-variance genes (none in this dataset).

## Dimensionality reduction and clustering

- PCA was performed on the sample-by-gene log2-CPM matrix.

- PC1 and PC2 together explained approximately 55.1% and 17.4% of the variance, respectively.

- K-means clustering (k=2) on the first 5 PCs separated the 21 samples into two main clusters.

- Cluster sizes: Cluster 1 = 8 samples, Cluster 2 = 13 samples.

## Differential expression between the two clusters

- For each gene, we compared expression between Cluster 2 and Cluster 1 using a Welch t-test on log2-CPM values and computed log2 fold change (Cluster 2 minus Cluster 1).

- P-values were adjusted for multiple testing using Benjamini–Hochberg FDR.

- At FDR < 0.05, 10999 genes were upregulated in Cluster 2 and 1626 genes were upregulated in Cluster 1.

## Putative BMP4 overexpression and pathway activation

- We searched for genes with strong upregulation in one cluster, consistent with a transgene (very high expression in one group and low in the other).

- A prominent candidate is **gene_2772**, which shows a large log2 fold change between Cluster 2 and Cluster 1.

- Mean log2-CPM of gene_2772: Cluster 1 = 1.92, Cluster 2 = 6.98.

- Several additional genes (e.g., gene_7390, gene_7089, gene_4161, gene_7972, gene_13431) also show strong upregulation in Cluster 2 with large positive log2 fold changes, suggestive of coordinated pathway activation.

Given the expected biology (BMP4 transgene driving overexpression of BMP4 and activation of downstream targets), the cluster with higher expression of gene_2772 and many co-upregulated genes is the most plausible NSE-BMP4 transgenic group.

## Inferred group identities

- We define two abstract group labels: `Group_1` and `Group_2` to represent the two genetic states.

- Based on the expression patterns described above, **Cluster 2** is inferred to correspond to the **NSE-BMP4 transgenic** genotype, while **Cluster 1** corresponds to **WT**.

- Accordingly, we map clusters to group labels as follows:

  - Cluster 1 → `Group_1` (WT, `is_transgenic = FALSE`)

  - Cluster 2 → `Group_2` (NSE-BMP4 transgenic, `is_transgenic = TRUE`)

These assignments are reflected in `tables/sample_group_assignments.tsv`.
