# Title & Objective

**Objective:** Infer which gene(s) were knocked out in samples 1–3 (KO) versus 4–6 (control) using only the anonymized RNA-seq count matrix in `library/datasets/`, and commit to a single knockout call.

---

## Data & Methods

**Data:**
- `library/datasets/anonyomized_rnaseq_count.tsv.gz`
  - 58,721 genes × 6 samples.
  - `GeneID` (Ensembl-like IDs) in rows; samples `sample_rnaseq1`–`sample_rnaseq6` in columns.
  - Integer raw RNA-seq counts.

**QC and normalization:**
- Computed per-sample QC:
  - Library sizes ≈ 5.6–7.6M counts; ~21k–24k nonzero genes per sample.
- Normalization:
  - DESeq-like library-size scaling: size factors = library_size / geometric mean of library sizes.
  - Normalized counts = raw_count / size_factor.
  - Transform: natural log1p: log(1 + normalized_count).
- Low-count gene filtering:
  - Kept genes with counts ≥ 5 in at least 2 samples.
  - Genes before filtering: 58,721; after: 16,703; all-zero genes before filtering: 29,334.

**Differential expression (DE):**
- Tool: PyDESeq2 (DESeq2-like model on raw counts).
- Design: `~ condition`.
- Groups:
  - KO: `sample_rnaseq1`, `sample_rnaseq2`, `sample_rnaseq3`.
  - Control: `sample_rnaseq4`, `sample_rnaseq5`, `sample_rnaseq6`.
- Contrast: KO vs control (positive log2FoldChange = higher in KO).
- Outputs per gene: baseMean, log2FoldChange, lfcSE, stat, pvalue, padj (BH FDR).

**KO-pattern scoring and candidate selection:**
- From normalized matrix, computed for each gene:
  - mean_KO = mean(expression in samples 1–3).
  - mean_control = mean(expression in samples 4–6).
  - Per-sample normalized expression for all 6 samples.
- Joined these with DE results.
- Stringent KO-candidate criteria (all must hold):
  - Control expression ("on"):
    - mean_control ≥ 3.0.
    - Each control sample ≥ 2.5.
  - KO expression ("off"):
    - mean_KO ≤ 0.5.
    - Each KO sample ≤ 0.5.
  - DE evidence:
    - log2FoldChange ≤ -3.0.
    - padj ≤ 0.01 and not NA.
- is_KO_candidate set to True only if all above conditions are satisfied.
- Composite score for ranking (after min–max scaling each feature across genes):
  - score = 0.5·scaled(-log2FoldChange) + 0.3·scaled(mean_control) + 0.2·scaled(max(mean_KO) − mean_KO).
- Ranking:
  - First by is_KO_candidate (True before False), then by composite_score (descending).

---

## Results

- DE analysis:
  - Genes tested with non-NA p-values: 29,387.
  - Significant at padj < 0.05: 5,841 genes.
- KO-pattern screening:
  - Genes after low-count filter: 16,703.
  - Genes passing all KO-candidate criteria (is_KO_candidate = True): **2**.
  - Top two KO-pattern genes:

  1. **ENSG00000178498.15**
     - KO-pattern metrics (from `ko_candidate_genes_ranked.tsv`):
       - is_KO_candidate: True.
       - composite_score: 0.8059 (highest of all genes).
       - mean_KO: 0.0.
       - mean_control: 3.82.
       - Per-sample normalized expression:
         - KO (samples 1–3): 0.0, 0.0, 0.0.
         - Control (samples 4–6): 4.13, 3.91, 3.43.
     - DE metrics (from `de_results_ko_vs_ctrl.tsv`):
       - baseMean: 23.75.
       - log2FoldChange: -7.99 (KO vs control).
       - padj: 2.8×10⁻⁴.

  2. **ENSG00000152804.10**
     - KO-pattern metrics:
       - is_KO_candidate: True.
       - composite_score: 0.7631 (second among all genes).
       - mean_KO: 0.0.
       - mean_control: 3.33.
       - KO (1–3): 0.0, 0.0, 0.0.
       - Control (4–6): 3.24, 3.25, 3.50.
     - DE metrics:
       - log2FoldChange: -7.19.
       - padj: 1.3×10⁻³.

- Other highly ranked genes (e.g. ENSG00000086289.11, ENSG00000196653.11, ENSG00000118508.4, ENSG00000183837.9) show strong down-regulation but
  - nonzero KO expression (partial suppression), or
  - weaker control expression, or
  - missing/less robust DE support.
  These patterns are compatible with downstream regulatory effects rather than direct knockouts.

**Final call:**
- Among all genes, **ENSG00000178498.15** has the strongest, cleanest knockout signature:
  - Completely off in all KO samples.
  - Robustly expressed in all control samples.
  - Very large negative log2 fold-change with strong FDR-adjusted significance.
  - Highest KO-pattern composite score.
- ENSG00000152804.10 also shows a strong on/off pattern but with consistently weaker metrics; no evidence suggests it is an equally primary co-target.
- Thus, we infer a **single knockout gene** in samples 1–3: **ENSG00000178498.15**.

---

## Caveats & Warnings

- **No external annotation provided:**
  - The dataset includes only Ensembl-like `GeneID`s and no gene symbol column or annotation file. The knockout is therefore reported in terms of `ENSG00000178498.15` rather than an HGNC symbol.
- **Model and threshold choices:**
  - KO-candidate thresholds (e.g., mean_control ≥ 3.0, KO ≤ 0.5, log2FC ≤ -3.0, padj ≤ 0.01) are stringent but somewhat heuristic; modest changes would not alter the identity of the top candidate but could affect the number of flagged genes.
- **Small sample size:**
  - Only 3 KO and 3 control samples; DE statistics and variance estimates rely on modeling assumptions typical for DESeq2-like methods.
- **Unobserved biology:**
  - Secondary and compensatory changes in other genes are expected and visible; the pipeline is designed to focus on the clearest direct knockout, but causal interpretation beyond the primary KO remains inferential.

---

## Next Steps

- If desired, obtain or construct a gene annotation mapping to translate `ENSG00000178498.15` to its official HGNC gene symbol.
- Validate the inferred knockout experimentally (e.g., via targeted qPCR or independent RNA-seq) and/or in complementary datasets.
- Explore pathway- and network-level consequences by analyzing other strongly down- or up-regulated genes around the inferred knockout.
- Repeat the analysis with alternative normalization or DE frameworks (e.g., edgeR, limma-voom) as a robustness check, though the primary KO call is unlikely to change.

---

## References

- Love MI, Huber W, Anders S. **Moderated estimation of fold change and dispersion for RNA-seq data with DESeq2.** *Genome Biol.* 2014;15(12):550. doi:10.1186/s13059-014-0550-8
- Anders S, Huber W. **Differential expression analysis for sequence count data.** *Genome Biol.* 2010;11(10):R106. doi:10.1186/gb-2010-11-10-r106
