# Sleep-deprivation labeling based on gene-expression signatures

## 1. Gene-signature to Ensembl ID mapping

The following activity- and stress-related genes were mapped from mouse gene symbols to Ensembl mouse gene IDs using the `mygene` service (species=10090). All mapped Ensembl IDs were present in the expression matrix (after stripping version suffixes):

| Symbol | Ensembl mouse gene ID | Description |
|--------|-----------------------|-------------|
| Fos | ENSMUSG00000021250 | Fos proto-oncogene, AP-1 transcription factor subunit |
| Fosb | ENSMUSG00000003545 | Fos B proto-oncogene, AP-1 transcription factor subunit |
| Egr1 | ENSMUSG00000038418 | early growth response 1 |
| Egr2 | ENSMUSG00000037868 | early growth response 2 |
| Egr3 | ENSMUSG00000033730 | early growth response 3 |
| Arc | ENSMUSG00000022602 | activity regulated cytoskeletal-associated protein |
| Nr4a1 | ENSMUSG00000023034 | nuclear receptor subfamily 4, group A, member 1 |
| Nr4a2 | ENSMUSG00000026826 | nuclear receptor subfamily 4, group A, member 2 |
| Nr4a3 | ENSMUSG00000028341 | nuclear receptor subfamily 4, group A, member 3 |
| Bdnf | ENSMUSG00000048482 | brain derived neurotrophic factor |
| Homer1 | ENSMUSG00000007617 | homer scaffolding protein 1 |
| Junb | ENSMUSG00000052837 | jun B proto-oncogene, AP-1 transcription factor subunit |
| Npas4 | ENSMUSG00000045903 | neuronal PAS domain protein 4 |
| Dusp1 | ENSMUSG00000024190 | dual specificity phosphatase 1 |
| Dusp6 | ENSMUSG00000019960 | dual specificity phosphatase 6 |
| Hspa1a | ENSMUSG00000091971 | heat shock protein family A (Hsp70) member 1A |
| Hspa1b | ENSMUSG00000090877 | heat shock protein family A (Hsp70) member 1B |
| Atf3 | ENSMUSG00000026628 | activating transcription factor 3 |

## 2. Signature scores by sample and cluster

For each sample, a sleep-deprivation / neuronal-activity / stress signature score was computed as the mean of per-gene z-scored log-expression across the 18 mapped signature genes. Z-scoring was performed across all 8 samples for each gene individually.

### 2.1 Per-sample signature scores

| Sample ID | Cluster ID | Signature score (mean z) |
|-----------|-----------:|-------------------------:|
| sample1 | 0 | -0.7084 |
| sample2 | 0 | 1.2678 |
| sample3 | 2 | -0.9791 |
| sample4 | 1 | -0.1252 |
| sample5 | 0 | 0.5601 |
| sample6 | 0 | 0.2565 |
| sample7 | 2 | -0.2153 |
| sample8 | 1 | -0.0563 |

### 2.2 Summary statistics by cluster

Signature score distribution by cluster (mean ± SD, range, n):

| Cluster ID | n | Mean score | SD | Min | Max |
|-----------:|---:|-----------:|----:|----:|----:|
| 0 | 4 | 0.3440 | 0.8196 | -0.7084 | 1.2678 |
| 1 | 2 | -0.0908 | 0.0487 | -0.1252 | -0.0563 |
| 2 | 2 | -0.5972 | 0.5401 | -0.9791 | -0.2153 |

Cluster 0 shows the highest mean signature score (0.34), whereas clusters 1 and 2 have negative mean scores (-0.09 and -0.60, respectively), indicating relatively lower activity/stress-related gene expression.

## 3. Differential-expression patterns of signature genes

Differential expression (cluster vs. rest) was computed for all genes using Welch t-tests on log-transformed expression, followed by Benjamini–Hochberg FDR correction. For the 18 signature genes, the direction of log-fold change (logFC) per cluster was summarized.

Summary of differential-expression directions for the 18 signature genes:

| Cluster ID | # signature genes | # up (logFC>0) | # down (logFC<0) | Mean logFC | Median logFC |
|-----------:|------------------:|---------------:|-----------------:|-----------:|-------------:|
| 0 | 18 | 14 | 4 | 0.178 | 0.225 |
| 1 | 18 | 6 | 12 | -0.043 | -0.049 |
| 2 | 18 | 3 | 15 | -0.194 | -0.202 |

Cluster 0 has most signature genes up-regulated relative to the other clusters (14/18 with positive logFC, mean logFC ≈ 0.18), whereas clusters 1 and 2 show overall negative mean logFC for the same genes. This pattern is consistent with cluster 0 capturing animals with elevated neuronal activity / stress / sleep-deprivation signatures.

## 4. Cluster labeled as sleep-deprived

Integrating the evidence from per-sample signature scores and cluster-wise differential expression of canonical immediate-early and stress-responsive genes (e.g. **Fos**, **Fosb**, **Egr1–3**, **Arc**, **Nr4a1–3**, **Bdnf**, **Npas4**, **Dusp1**, **Hspa1a/b**, **Atf3**), cluster **0** shows the clearest up-regulation of this signature. Therefore, cluster **0** is labeled as representing **sleep-deprived mice**.

The samples inferred to be from sleep-deprived mice (cluster 0) are:

- sample1
- sample2
- sample5
- sample6

A machine-readable list of these samples is provided in `project/outputs/tables/sleep_deprived_samples.tsv`.
