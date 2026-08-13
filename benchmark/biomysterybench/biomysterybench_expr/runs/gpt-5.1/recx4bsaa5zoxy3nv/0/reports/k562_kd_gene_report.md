# Knocked-down Gene Inference in K562 Expression Data

## Title & Objective

**Objective:** From unlabeled K562 transcript quantifications (4 samples), infer which of the provided candidate genes was experimentally knocked down, and commit to a single answer.

Final inferred knocked-down gene: **QKI**

Candidate list: MBNL1, ADD3, VEGFA, RBFOX1, RBFOX2, PTBP1, QKI, SRSF1, SRSF2, HNRNPA1, NOVA1, SF3B1, HSP90AB1, EGR1, HBB, ALB, ACTB, RBM39, GADD45A.

## Data & Methods

### Data
- Four K562 transcript-level quantification files (pseudoalignment-style, with `target_id`, `est_counts`, `tpm`):  
  `library/datasets/ctrl1.tsv`, `ctrl2.tsv`, `kd1.tsv`, `kd2.tsv`.
- Each `target_id` encodes transcript and gene information, including Ensembl gene ID and gene symbol.

### Preprocessing and Expression Matrix Construction
- Parsed `target_id` as a pipe-delimited string, extracting:
  - Ensembl gene ID (field 2), with version stripped (e.g., `ENSG00000123456.3` → `ENSG00000123456`).
  - Gene symbol (field 6).
- Aggregated transcript TPMs to **gene-level TPM** by summing TPM over all transcripts per gene ID, for each sample.
- Constructed a gene × sample TPM matrix:
  - 58,656 genes × 4 samples (ctrl1, ctrl2, kd1, kd2).
- Counts (`est_counts`) were also aggregated but used only for QC (library size); all downstream comparisons used TPM.

### Sample Structure and Group Inference
- Normalization for between-sample comparison:
  - Used **log2(TPM + 1)** as the working expression scale.
  - Per-gene centering and scaling across samples before PCA (StandardScaler).
- Dimensionality reduction and clustering:
  - PCA on the 4 samples (features = genes): first three PCs explained ~50.6%, 25.6%, and 23.7% of variance.
  - Agglomerative hierarchical clustering (Ward linkage) on PCA coordinates with **k = 2**.
  - Resulting clusters:
    - Cluster 0: ctrl1, ctrl2 → **control group**.
    - Cluster 1: kd1, kd2 → **knockdown group**.

### Candidate Gene Quantification
- From the gene-level matrix, mapped Ensembl IDs to symbols and extracted the 19 candidate genes.
- Detected 16/19 candidates in the quantifications:
  - Present: ADD3, VEGFA, RBFOX1, RBFOX2, PTBP1, QKI, SRSF1, SRSF2, HNRNPA1, NOVA1, SF3B1, HSP90AB1, EGR1, HBB, RBM39, GADD45A.
  - Not detected: MBNL1, ALB, ACTB (no matching symbol; metrics left as NA/blank).
- Symbol-level aggregation:
  - If multiple Ensembl IDs mapped to the same candidate symbol, their gene-level TPMs were **summed** per sample, with contributing IDs recorded (semicolon-separated) for traceability.

### Metrics Computed for Candidates
- **By sample (log2(TPM+1))**:  
  `candidate_gene_expression_by_sample.tsv` — rows = candidate genes, columns = `ensg_ids`, ctrl1, ctrl2, kd1, kd2.

- **By group/cluster (log2(TPM+1))**:  
  `candidate_gene_expression_by_group.tsv` — rows = (symbol, cluster), columns:
  - `mean_log2TPM_plus1`
  - `se_log2TPM_plus1`
  - `var_log2TPM_plus1`.

- **Differential-style metrics**:  
  `candidate_gene_fold_changes.tsv` — rows = symbols, columns include:
  - `mean_TPM_CTRL`, `mean_TPM_KD` (TPM scale).  
  - `log2FC_KD_vs_CTRL_TPM = log2((mean_TPM_KD + 1e-3)/(mean_TPM_CTRL + 1e-3))`.
  - Per-sample TPM z-scores: `ctrl1_zscore_TPM`, `ctrl2_zscore_TPM`, `kd1_zscore_TPM`, `kd2_zscore_TPM`.
  - `var_log2TPM_plus1_across_samples`.

- **Support metrics for knockdown inference**:  
  `kd_gene_support_metrics.tsv` adds:
  - `mean_log2TPM_plus1_CTRL`, `mean_log2TPM_plus1_KD`, and `delta_mean_log2TPM_plus1_KD_vs_CTRL`.
  - Within-group variances: `var_log2TPM_plus1_CTRL`, `var_log2TPM_plus1_KD`.
  - Group-averaged TPM z-scores: `mean_ctrl_z_TPM`, `mean_kd_z_TPM`, and their difference `zscore_contrast_KD_minus_CTRL`.

### Visualizations
- **Sample PCA plot**: `sample_pca_umap_clusters.png` — PC1 vs PC2 colored by cluster, with sample labels.
- **Candidate heatmap**: `candidate_gene_heatmap.png` — candidates (rows) × samples (columns), values = row-wise z-score of log2(TPM+1); clearly highlights genes reduced in kd1/kd2 relative to controls.

## Results

### Sample Structure
- PCA and hierarchical clustering cleanly separated the 4 samples into two clusters:
  - **Cluster 0 (Control)**: ctrl1, ctrl2.
  - **Cluster 1 (Knockdown)**: kd1, kd2.
- Library sizes and TPM sums were similar across samples (TPM totals ~9.68–9.70×10^5), supporting direct TPM-based comparison.

### Candidate Gene Patterns

Below are key quantitative patterns from `candidate_gene_fold_changes.tsv` and `kd_gene_support_metrics.tsv`:

- Strongly **downregulated in KD** (negative log2FC):
  - **QKI**:
    - `log2FC_KD_vs_CTRL_TPM ≈ -0.402` (most negative among candidates).
    - `mean_TPM_CTRL ≈ 144.4`, `mean_TPM_KD ≈ 109.3`.
    - `mean_log2TPM_plus1_CTRL ≈ 7.18`, `mean_log2TPM_plus1_KD ≈ 6.79`  
      → `delta_mean_log2TPM_plus1_KD_vs_CTRL ≈ -0.40` (largest negative shift).
    - Within-group log2(TPM+1) variances: very low  
      (`var_CTRL ≈ 1.1×10^-4`, `var_KD ≈ 5.4×10^-5`).
    - TPM z-scores: controls positive, KDs negative  
      (`mean_ctrl_z_TPM ≈ +1.0`, `mean_kd_z_TPM ≈ -1.0`),  
      `zscore_contrast_KD_minus_CTRL ≈ -2.0` (strongest negative among candidates).

  - **ADD3**:
    - `log2FC ≈ -0.346` (second-most negative).
    - `delta_mean_log2TPM_plus1 ≈ -0.34`.
    - `zscore_contrast ≈ -1.96` (slightly weaker than QKI).
    - Higher KD variance than QKI, especially on log2(TPM+1) scale.

  - **SRSF1**:
    - `log2FC ≈ -0.254` and a negative delta in mean log2(TPM+1).
    - `zscore_contrast` weaker than QKI and ADD3; KD variance relatively large.

- Mild or ambiguous changes:
  - **VEGFA, HBB**: modest negative log2FC and small mean shifts, with more variability or smaller effect sizes.

- Upregulated or inconsistent with knockdown:
  - **RBM39, GADD45A, PTBP1, HNRNPA1, SF3B1, HSP90AB1, EGR1, RBFOX1, NOVA1, SRSF2**:
    - `log2FC_KD_vs_CTRL_TPM` positive (higher in KD than CTRL) and/or positive `delta_mean_log2TPM_plus1`, inconsistent with a knockdown target.

- Not detected:
  - **MBNL1, ALB, ACTB**: not present in the quantifications by symbol; metrics are missing/NA and provide no evidence for or against knockdown.

### Conclusion: Knocked-down Gene

Across all metrics, **QKI** is the single best-supported candidate for the knocked-down gene:

- It shows the **strongest negative TPM-based log2 fold change** between KD and CTRL.
- It has the **largest negative shift in mean log2(TPM+1)** (KD vs CTRL) among candidates.
- Its per-sample TPM z-scores form a clean pattern: controls are strongly positive, knockdowns strongly negative, producing the most negative `zscore_contrast_KD_minus_CTRL`.
- Within-group variance is low in both control and knockdown, indicating a consistent effect across replicates.
- Alternative downregulated candidates (ADD3, SRSF1, VEGFA, HBB) either have smaller effect sizes, greater variability, or both, making them less compelling.

**Final call:** The knocked-down gene in the K562 dataset is **QKI**.

## Key Results (Summary Bullets)
- Expression matrix: 58,656 genes × 4 samples (2 controls, 2 knockdowns) derived from transcript TPMs.
- Unsupervised clustering (PCA + Ward) cleanly separated samples into control (ctrl1/ctrl2) and knockdown (kd1/kd2) clusters.
- Among 19 candidates, 16 were detected; 3 (MBNL1, ALB, ACTB) were absent.
- QKI exhibited the **most negative** KD vs CTRL log2FC on TPM scale (~ -0.40) and the strongest negative z-score contrast (~ -2), with low within-group variance.
- No other candidate combined as large a negative fold-change, coherent replicate behavior, and low variability.

## Caveats & Warnings
- Only **four samples** (two per group) were available, limiting statistical power and preventing robust inferential statistics (e.g., formal p-values or multiple-testing correction). The analysis relies on effect sizes and consistency rather than hypothesis testing.
- TPM-based normalization assumes comparable library composition across samples; strong global composition shifts could bias TPM-level fold-changes, though library sizes and distributions appeared broadly similar here.
- Three candidates (MBNL1, ALB, ACTB) were not detected in the quantifications. If these genes were very lowly expressed or absent in K562 under all conditions, their absence provides no direct evidence for or against a targeted knockdown.
- The inference is restricted to the **provided candidate list**; other non-listed genes could be perturbed but were not considered.

## Next Steps
- Validate QKI knockdown using independent evidence if available (e.g., qPCR, Western blot, or known experimental design).
- Examine genome-wide differential expression and splicing patterns associated with QKI perturbation to confirm that they are consistent with QKI’s known regulatory roles.
- Extend the analysis to additional replicates or time points, if accessible, to strengthen inference and characterize temporal dynamics of the knockdown.

## References
- Generic RNA-seq processing and normalization concepts (no specific dataset DOI provided):
  - Li B, Dewey CN. RSEM: accurate transcript quantification from RNA-Seq data. *BMC Bioinformatics*. 2011;12:323. doi:10.1186/1471-2105-12-323.
  - Love MI, Huber W, Anders S. Moderated estimation of fold change and dispersion for RNA-seq data with DESeq2. *Genome Biol.* 2014;15(12):550. doi:10.1186/s13059-014-0550-8.
