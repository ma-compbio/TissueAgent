# Title & Objective

**Objective:** Infer the human tissue of origin for a single RNA-seq sample, using only its gene expression profile and a reference panel of 2,555 labeled bulk RNA-seq samples spanning 68 tissues. Output a single tissue label exactly matching the reference metadata.

# Data & Methods

**Data inspected**
- `library/datasets/gene_read_counts_unknown_tissue_sample.csv`
  - 58,988 genes × 1 sample; column `gene_id` (Ensembl IDs) plus one expression column.
- `library/datasets/gene_read_counts_2555_tissue_samples.csv`
  - 58,988 genes × 2,555 labeled samples; `gene_id` column (Ensembl) + one column per sample.
- `library/datasets/metadata_2555_tissue_samples.csv`
  - 2,555 rows; columns: `sample_id`, `tissue` (68 distinct tissue labels, vocabulary for the answer).

**Preprocessing & normalization**
- Aligned genes by `gene_id` between reference and unknown matrices (full overlap of 58,988 genes).
- Treated values as raw or near-raw counts based on integer-valued matrices and count-like ranges.
- Per-sample normalization:
  - Computed counts-per-million (CPM): `CPM = counts / library_size * 1e6`.
  - Applied log-transform: `log2(CPM + 1)` to stabilize variance and reduce library-size effects.
- Gene filtering:
  - Removed genes with zero variance across all 2,556 samples (2,555 reference + 1 unknown) to avoid degenerate z-scores.

**Similarity computation**
- Standardization:
  - For each gene, computed z-scores across all samples: `(value - mean_gene) / sd_gene` using the log2(CPM+1) matrix.
- Sample-level similarity between the unknown sample and each labeled reference sample:
  - Similarity = mean over genes of `z_gene_unknown × z_gene_reference`.
  - This is equivalent to a Pearson-like correlation after per-gene standardization, capturing pattern similarity across genes.
- Tissue-level aggregation (68 tissues from `metadata_2555_tissue_samples.csv`):
  - For each tissue:
    - Collected all corresponding reference samples.
    - Computed:
      - `n_reference_samples`
      - `mean_similarity` (primary score, used as `similarity_score`)
      - `median_similarity`
      - `max_similarity`
      - `std_similarity`.
  - Ranked tissues in descending order of `similarity_score`.

**Marker-gene support for the top tissue**
- Operated again in log2(CPM+1) space on the same set of variant genes.
- For the top-scoring tissue (Prostate):
  - For each gene, computed:
    - `mean_expr_top_tissue`: mean expression across Prostate reference samples.
    - `mean_expr_other_tissues`: mean expression across all non-Prostate samples.
    - `log2_fc_top_vs_others = mean_expr_top_tissue - mean_expr_other_tissues`.
    - `expr_unknown_sample`: expression of the gene in the unknown sample.
  - Filtered to genes with:
    - `log2_fc_top_vs_others > 0` (upregulated in Prostate vs others).
    - `expr_unknown_sample ≥ 2` in log2(CPM+1) (to keep markers actually expressed in the unknown sample).
  - Ranked genes by `log2_fc_top_vs_others` (descending), breaking ties by `expr_unknown_sample`.
  - Reported the top 50 markers as most supportive of the Prostate call.

# Results

- **Final predicted tissue label:** `Prostate`

**Per-tissue similarity ranking (top tissues)**  
(Source: `tables/tissue_similarity_scores.tsv`)

- Prostate  
  - `n_reference_samples`: 52  
  - `similarity_score` (mean_similarity): ~0.3112  
  - `median_similarity`: ~0.3240  
  - `max_similarity`: ~0.5186
- Pituitary  
  - `n_reference_samples`: 51  
  - `similarity_score`: ~0.1310
- Thyroid  
  - `n_reference_samples`: 52  
  - `similarity_score`: ~0.1283
- Testis  
  - `n_reference_samples`: 42  
  - `similarity_score`: ~0.1190
- Cervix - Endocervix  
  - `n_reference_samples`: 23  
  - `similarity_score`: ~0.1050

Full ranking for all 68 tissues is in `tables/tissue_similarity_scores.tsv`; the rows are sorted by `similarity_score` (highest first) and the top row is Prostate.

**Marker-gene evidence for Prostate**  
(Source: `tables/top_markers_supporting_prediction.tsv`)

- Top Prostate-enriched markers (examples):
  - ENSG00000142515:  
    - `mean_expr_top_tissue` ≈ 11.87 (log2(CPM+1))  
    - `mean_expr_other_tissues` ≈ 0.42  
    - `log2_fc_top_vs_others` ≈ 11.45  
    - `expr_unknown_sample` ≈ 13.59
  - ENSG00000167751:  
    - `mean_expr_top_tissue` ≈ 11.29  
    - `mean_expr_other_tissues` ≈ 0.42  
    - `log2_fc_top_vs_others` ≈ 10.88  
    - `expr_unknown_sample` ≈ 12.90
  - ENSG00000263639, ENSG00000014257, ENSG00000167749, ENSG00000159184, and others show similarly strong Prostate-vs-others upregulation and high expression in the unknown sample.
- Overall pattern:
  - All 50 reported markers have substantial positive `log2_fc_top_vs_others` (often >4), indicating strong Prostate specificity in the reference panel.
  - A large fraction of these markers are expressed in the unknown sample at levels comparable to or exceeding the Prostate mean, consistent with a Prostate origin.

# Caveats & Warnings

- **Bulk tissue resolution:** The method compares bulk RNA-seq profiles; it cannot distinguish fine-grained sub-regions or cell subtypes within a tissue. The label `Prostate` is at the same granularity as the metadata.
- **Normalization assumptions:** Counts were treated as raw and normalized via CPM and log2(CPM+1); if the original values were pre-normalized in a nonstandard way, this could slightly affect similarity magnitudes, though the strong Prostate signal is unlikely to change.
- **Single-sample classification:** Only one unknown sample was classified; no cross-validation or hold-out testing of the classifier was performed here. The result relies on the assumption that the reference panel is representative of typical tissue expression.

# Next Steps

- If desired, map the top marker gene Ensembl IDs to gene symbols to qualitatively confirm they correspond to known Prostate-associated genes.
- Extend the approach to classify additional unknown samples (if present in future datasets) using the same normalization and similarity pipeline for consistency.
- Optionally implement alternative similarity metrics (e.g., cosine similarity, Spearman correlation) to confirm robustness of the Prostate call, though current evidence is already strongly supportive.

# References

- GTEx Consortium (for tissue-resolved human expression panels, conceptually similar to the provided reference matrix):  
  - PMID: [23715323](https://pubmed.ncbi.nlm.nih.gov/23715323/)  
  - PMID: [25954001](https://pubmed.ncbi.nlm.nih.gov/25954001/)
