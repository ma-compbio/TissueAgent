# Label Inference Methods Summary

## Main Expression Input
- **File:** `project/outputs/data/expression_matrix_standardized.tsv`
- **Role:** Standardized main expression matrix used for all downstream label inference.
- **Dimensions:** 49,181 genes × 70 samples (from `expression_qc_summary.tsv`).
- **Data type (inferred):** The original expression (prior to standardization) appears to be **likely raw counts with many zeros/low counts**, with a mean library size of ~1,000,000 counts per sample and strong right-skew (max ≈ 426,600). The standardized matrix used here contains continuous `float64` values derived from this raw matrix (e.g. z-scored/log-transformed expression).

## Tissue Subtype Inference (Step 2)

### Dimensionality Reduction and Clustering
- **Input:** Standardized expression matrix (`expression_matrix_standardized.tsv`).
- **Preprocessing (conceptual):**
  - Genes were treated as features and samples as observations.
  - Standardized expression (per-gene scaling) was used to place genes on a comparable scale.
- **Dimensionality reduction:** A low-dimensional embedding (e.g. PCA followed by a non-linear method such as UMAP or t-SNE) was computed on the sample × gene matrix to capture major axes of variation across samples.
- **Clustering:** Samples were grouped into clusters (putative tissue subtypes) in the reduced space using an unsupervised clustering algorithm (e.g. graph-based clustering or k-means). Each cluster was then characterized by its marker genes.

### Cluster Marker Gene Identification
- **Input table:** `project/outputs/tables/cluster_marker_genes.tsv`.
- **Content:** For each cluster, genes are ranked by a **Score**, with additional statistics:
  - `Cluster`: cluster identifier.
  - `Gene`: gene symbol.
  - `Score`: marker strength statistic.
  - `logFC`: log fold-change of average expression in the cluster vs outside.
  - `avg_in_cluster`, `avg_outside`: mean standardized expression inside vs outside the cluster.
- **Interpretation:** High `Score` and positive `logFC` indicate genes specifically enriched in a given cluster, serving as canonical markers for tissue identity.

### Cluster Annotation to Tissue Labels
- **Approach:**
  1. **Marker-based interpretation:** For each cluster, the top-ranked genes in `cluster_marker_genes.tsv` were examined and compared against known tissue marker gene sets (e.g. heart: *TNNI3, TNNT2, MYH7, MYH6, ACTC1, DES, MB*; liver: *ALB, APOA1, FGB*; brain/cortex: neuronal and glial markers; whole blood: hemoglobin and immune markers).
  2. **Cluster-to-tissue mapping:** Clusters whose top markers matched a coherent tissue signature were annotated as that tissue.
  3. **Per-sample labeling:** Each sample was assigned the tissue label corresponding to its cluster, resulting in `project/outputs/tables/sample_tissue_labels.tsv` with columns `Sample` and `Tissue`.
- **Example:** Cluster 0 shows strong enrichment for classic cardiac muscle markers (*TNNI3, MB, ACTC1, DES, TNNT2, MYL7, MYH7, MYH6*), and was therefore annotated as **Heart**. All samples in this cluster received the tissue label `Heart`.

## Sex Label Inference (Step 3)

### Marker Genes and Features
- **Input:** Standardized expression for sex-linked genes across the 70 samples.
- **Key markers used conceptually:**
  - **Y-linked genes:** e.g. *RPS4Y1, DDX3Y, EIF1AY, KDM5D, UTY*.
  - **XIST:** X-chromosome inactivation gene, typically high in XX (female) samples and low in XY (male) samples.

### Decision Rule
- For each sample, expression of the above markers was summarized (e.g. mean or max standardized expression per marker set):
  - Compute a composite **Y-score** from Y-linked genes.
  - Use **XIST** expression as an additional indicator of female sex.
- **Label assignment (conceptual rule):**
  - If **Y-score is high** and **XIST is low** → label **`Male`**.
  - If **Y-score is low/absent** and **XIST is moderate to high** → label **`Female`**.
  - Very low expression for all sex markers, or conflicting signal, would render a sample ambiguous.
- The final inferred sex labels were stored in `project/outputs/tables/sample_sex_labels.tsv` with columns `Sample` and `Sex`.

## Final Per-Sample Tissue and Sex Table

### Merging Strategy
- **Tissue labels input:** `project/outputs/tables/sample_tissue_labels.tsv` (columns: `Sample`, `Tissue`).
- **Sex labels input:** `project/outputs/tables/sample_sex_labels.tsv` (columns: `Sample`, `Sex`).
- **Merge:** An **inner join** on `Sample` was performed so that only samples present in **both** label tables were kept.
- **Output columns (in order):** `Sample`, `Tissue`, `Sex`.
- **Final file:** `project/outputs/tables/sample_tissue_sex_final.tsv`.

### Coverage and Consistency with Expression Matrix
- **Main expression reference:** `project/outputs/data/expression_matrix_standardized.tsv`.
- **From QC summary (`expression_qc_summary.tsv`):**
  - `n_genes` = 49,181
  - `n_samples` = 70
- **Observed sample counts:**
  - Number of samples in expression matrix: 70
  - Number of samples with tissue labels: 70
  - Number of samples with sex labels: 70
  - Number of samples in the inner-merged table: 70
- **Discrepancies:**
  - No samples from the expression matrix were missing in either the tissue or sex label tables.
  - Therefore, **all 70 expression samples** are represented in `sample_tissue_sex_final.tsv`.

## Assumptions, Ambiguities, and Notes
- **Assumptions about methods:** The exact clustering algorithm and dimensionality reduction method (e.g. PCA+UMAP vs PCA-only; k-means vs graph clustering) are not explicitly encoded in the available summary files, so they are described conceptually. The presence of `cluster_marker_genes.tsv` with classic marker statistics implies a standard pipeline of (1) clustering on low-dimensional expression, followed by (2) differential expression per cluster.
- **Marker-based annotation:** Tissue labels rely on canonical marker interpretation; clusters with mixed or less specific markers would require manual review, though no such unresolved clusters are indicated by the existing summary.
- **Sex inference robustness:** Sex labels are assumed to be robust when Y-linked markers and XIST show the expected patterns. In cases of very low marker expression or discordance (not observed here), samples would need to be flagged as ambiguous; no such ambiguous samples are reported in the current label tables.
- **Sample set consistency:** Since all 70 samples appear in the expression matrix, tissue label table, and sex label table, the final merged table contains a complete set of samples with no exclusions.
