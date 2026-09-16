# Title & Objective

**Objective:** Use only the expression data in `library/datasets/` to infer which gene was knocked out in the experimental samples versus control samples, and commit to a single gene identifier.

# Data & Methods

**Data used**
- `library/datasets/norm_counts_TPM.tsv`: normalized TPM-like expression matrix (39,376 genes × 5 samples).
- `library/datasets/raw_counts.tsv`: raw count matrix with the same structure (used only for confirmation of structure/sparsity).

Genes are rows, samples are columns; the first column is `GeneID` (numeric NCBI-style IDs), remaining columns are samples: `Control_1`, `Control_2`, `Control_3`, `KO_1`, `KO_2`.

**1. Sample grouping (inferring experimental vs control)**
- Used `norm_counts_TPM.tsv` as primary input.
- Removed zero-variance genes, retaining 26,490 informative genes.
- Log2-transformed TPM values (log2(TPM + 1)) and standardized each gene (mean 0, SD 1).
- Performed PCA on the 5 samples and hierarchical clustering (Euclidean distance, Ward linkage).
- Identified two clearly separated clusters:
  - Group1: {KO_1, KO_2}
  - Group2: {Control_1, Control_2, Control_3}
- Saved assignments in `tables/sample_group_assignments.tsv` and visualized with:
  - `figures/sample_clustering_embedding.png` (PCA embedding)
  - `figures/sample_dendrogram.png` (sample dendrogram).

**2. Per-gene group statistics and knockout-like pattern search**
- For each gene in `norm_counts_TPM.tsv`, and using the inferred groups:
  - Computed mean and median expression per group (Group1 = KO, Group2 = Control).
  - Computed detection fraction per group (fraction of samples with TPM > 0).
  - Calculated log2 fold-change (Group1 vs Group2) using a small pseudocount (1e-3):
    - log2FC = log2((mean_Group1 + 1e-3) / (mean_Group2 + 1e-3)).
- Defined knockout-like genes by two sets of criteria:
  - **Stringent criteria**:
    - mean_Group1 ≤ 0.05 TPM, detection_Group1 ≤ 0.5.
    - mean_Group2 ≥ 5.0 TPM, detection_Group2 ≥ 0.66.
    - log2FC_Group1_vs_Group2 ≤ -1.0.
  - **Relaxed criteria** (for a slightly broader candidate pool):
    - mean_Group1 ≤ 0.1 TPM.
    - mean_Group2 ≥ 3.0 TPM, detection_Group2 ≥ 0.66.
    - log2FC_Group1_vs_Group2 ≤ -1.0.
- Ranked all genes by a composite **knockout_score** (sum of ranks for low KO mean/detection, high control mean/detection, and negative log2FC).
- Saved full statistics to `tables/differential_expression_results.tsv` and a filtered, ranked candidate list to `tables/knockout_candidate_genes_ranked.tsv`.

**3. Final gene selection**
- Examined the top candidates from `knockout_candidate_genes_ranked.tsv`.
- Compared means, medians, detection fractions, log2FC, and knockout_score across candidates.
- Selected the single best gene with the clearest on/off (control vs KO) pattern.
- Documented the choice and rationale in `reports/knockout_gene_selection.md` and `tables/final_knockout_gene.tsv`.

# Results

**Inferred group structure**
- Two strongly separated sample groups:
  - **Group1 (experimental / KO):** KO_1, KO_2
  - **Group2 (control):** Control_1, Control_2, Control_3

**Knockout-like genes (top candidates)**
- Under stringent criteria, only **one** gene passed all filters:
  - **GeneID 100126348**
    - Group1 (KO): mean = 0.000 TPM, median = 0.000, detection = 0.000
    - Group2 (Control): mean ≈ 6.401 TPM, median ≈ 6.845, detection = 1.000
    - log2FC_Group1_vs_Group2 ≈ -12.64
    - Lowest knockout_score among all genes; flagged as `stringent_hit = True`.
- Under relaxed criteria, two additional genes appeared but were weaker:
  - **100616396** and **100616150** — both completely off in KOs, but with lower mean and incomplete detection in controls and slightly less extreme log2FC.

**Final answer (one knocked-out gene)**
- The gene showing the clearest knockout-like pattern in the experimental samples is:

  **GeneID: 100126348**

- This gene is robustly expressed in all three control samples and completely absent in both KO samples.

# Caveats & Warnings
- The final answer is provided as a **numeric GeneID (100126348)** rather than a gene symbol; no external annotation resources were used to map IDs to symbols.
- Group identities (KO vs control) were inferred purely from expression patterns but are entirely consistent with the sample naming (`Control_*` vs `KO_*`).
- Only this dataset was analyzed; no biological validation or cross-dataset replication was performed.

# Next Steps
- If gene symbols are required, map GeneID 100126348 to its official symbol using an external gene annotation resource (e.g., NCBI Gene or Ensembl).
- Optionally, inspect the raw counts file (`raw_counts.tsv`) for the same gene to confirm the zero-vs-nonzero pattern at the count level.
- Perform downstream pathway or functional analysis on 100126348 and its network neighbors to interpret the biological consequences of its knockout.

# References
- No external publications were referenced; all inferences were based solely on the provided expression data and internal computations.
