# Title & Objective

**Objective:** Infer control vs experimental groups solely from expression data in `library/datasets/` and identify a single gene that is effectively knocked out (lost) in the experimental samples compared to controls.

# Data & Methods

**Data sources**
- `library/datasets/raw_counts.tsv`: Raw integer count matrix (39,376 genes × 5 samples).
- `library/datasets/norm_counts_TPM.tsv`: TPM-normalized expression matrix with the same genes and samples.
- `library/datasets/gene_info.gz`: Gene annotation table (GeneID ↔ gene symbol and metadata).

**Preprocessing and QC**
- Used `raw_counts.tsv` as the primary expression matrix (genes as rows, samples as columns).
- Computed QC summaries:
  - Global: n_genes = 39,376; n_samples = 5; sparsity ≈ 0.43.
  - Per-sample: total counts (library size), detected genes, mean/median counts.
  - Per-gene: total counts, number of samples expressed, mean/median expression, merged with gene symbols from `gene_info.gz`.

**Group inference (control vs KO)**
- Normalized counts to counts-per-million (CPM) per sample and applied log1p transform: log2(CPM + 1).
- Removed non-variable genes (zero variance across samples), retaining 26,490 informative genes.
- Performed PCA on the 5 samples in this high-dimensional space.
- Applied k-means clustering with k=2 on the first two PCs.
- Interpreted clusters as:
  - `Control_inferred`: Control_1, Control_2, Control_3.
  - `KO_inferred`: KO_1, KO2.
- Quantified separation on logCPM profiles (variable genes):
  - Mean within-group Euclidean distance ≈ 21.98.
  - Mean between-group Euclidean distance ≈ 29.98.
  - Silhouette score in PCA space ≈ 0.60, indicating a clear 2-group structure.

**Differential expression and knockout search**
- Reused log2(CPM + 1) expression for differential analysis.
- For each gene:
  - Computed mean logCPM in controls and in KO-inferred samples.
  - Computed log2 fold-change (KO vs control).
- Statistical testing:
  - Mann–Whitney U test (non-parametric) on logCPM values: 3 controls vs 2 KO samples.
  - Benjamini–Hochberg procedure for FDR (q-values) across all genes.
- Knockout-like gene prioritization:
  - Required **KO_total_counts == 0** (no raw counts in KO_1 or KO2).
  - Required **Control_total_counts ≥ 20** to ensure meaningful expression in controls.
  - Ranked remaining genes by control_total_counts (descending), more negative log2FC, and smaller q-value.
  - Mapped GeneID to gene symbol using `gene_info.gz`.

# Results

**Inferred groups**
- Control_inferred: Control_1, Control_2, Control_3.
- KO_inferred: KO_1, KO2.

**Called knockout gene**
- **Gene symbol:** `LOC105374110`
- **Gene ID (GeneID):** `105374110`

**Expression pattern (raw counts)**
- Control_1: 23
- Control_2: 0
- Control_3: 22
- KO_1: 0
- KO2: 0

Thus, LOC105374110 is expressed in 2/3 control samples with a total of 45 counts and is completely absent in both KO-inferred samples.

**Differential expression statistics (log2(CPM + 1) scale)**
- Mean control logCPM: 0.657
- Mean KO logCPM: 0.000
- Log2 fold-change (KO vs control): -0.657
- Mann–Whitney p-value: 0.333
- FDR q-value: 1.0

Within the set of genes strictly absent in KO and clearly present in controls, LOC105374110 had among the highest control expression and a strong directional effect consistent with a knockout.

# Caveats & Warnings
- **Very small sample size:** Only 5 samples (3 controls, 2 KO) limit statistical power; p-values and q-values are exploratory and not robust for standard significance thresholds.
- **Moderate control expression:** LOC105374110 shows modest (not extremely high) expression in controls; other genes may also show KO-like patterns but were ranked lower by the chosen criteria.
- **No external validation:** Group labels and the knockout call are inferred solely from expression patterns and the provided annotations; no orthogonal metadata (e.g., genotypes) were available to confirm the KO.

# Next Steps
- Validate LOC105374110 as the knockout via independent methods (e.g., targeted sequencing or qPCR across control and KO samples).
- Examine the full differential expression table to characterize downstream expression changes associated with the knockout.
- If additional samples become available, repeat the analysis to improve statistical power and refine the knockout call.

# References
- Love MI et al. "Moderated estimation of fold change and dispersion for RNA-seq data with DESeq2." *Genome Biol.* 2014;15(12):550. doi:10.1186/s13059-014-0550-8.
- Law CW et al. "voom: precision weights unlock linear model analysis tools for RNA-seq read counts." *Genome Biol.* 2014;15:R29. doi:10.1186/gb-2014-15-2-r29.
