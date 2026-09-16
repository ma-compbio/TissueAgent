# Title & Objective

**Title:** Tissue identity prediction for an unknown human RNA-seq sample

**Objective:**
Infer which of 68 possible human tissues best matches an unknown bulk RNA-seq sample by comparing its expression profile to a reference panel of 2,555 labeled samples, and report the predicted tissue label exactly as in the reference metadata.

---

# Data & Methods

## Data
- **Reference expression matrix** (`library/datasets/gene_read_counts_2555_tissue_samples.csv`)
  - 58,988 genes × 2,555 samples.
  - Rows: genes labeled by Ensembl-style `gene_id`.
  - Columns: reference samples; IDs match `metadata_2555_tissue_samples.csv:sample_id`.
- **Unknown sample expression** (`library/datasets/gene_read_counts_unknown_tissue_sample.csv`)
  - 58,988 genes × 1 sample.
  - Same `gene_id` set and order as the reference matrix.
- **Sample metadata** (`library/datasets/metadata_2555_tissue_samples.csv`)
  - 2,555 rows, one per reference sample.
  - Key columns: `sample_id`, `tissue` (68 distinct tissue labels).

Aligned and processed versions of these files were written under `project/outputs/tables/`.

## Preprocessing & Normalization
1. **Alignment on genes and samples**
   - Verified that reference and unknown data share exactly 58,988 genes with identical `gene_id` values and no duplicates.
   - Constructed aligned matrices:
     - `reference_expression_aligned.parquet`: 58,988 genes × 2,555 samples.
     - `unknown_sample_aligned.csv`: 58,988 genes × 1 column `unknown_sample`.

2. **Library-size normalization and log-transform**
   - For each sample (all 2,555 reference samples and the unknown):
     - Library size = sum of counts over all genes.
     - Counts per million (CPM): `CPM = (counts / library_size) × 1e6`.
     - Log-transform: `log1p_CPM = log(1 + CPM)` using the natural log.
   - Outputs:
     - `reference_normalized.parquet`: log1p-CPM, 58,988 × 2,555.
     - `unknown_normalized.csv`: log1p-CPM, 58,988 genes × 1 sample.
   - Summary statistics (from `normalization_summary.tsv`):
     - Reference library sizes: min ≈ 2.76×10⁷, median ≈ 6.14×10⁷, max ≈ 3.32×10⁸.
     - Unknown library size: ≈ 6.75×10⁷.
     - No zero library sizes; no NA/inf values after normalization.

## Similarity Computation
1. **Per-sample similarity** (`sample_similarity_scores.tsv`)
   - For each reference sample, using the 58,988 aligned genes:
     - **Pearson correlation** between its log1p-CPM profile and the unknown sample.
     - **Spearman correlation** (rank-based Pearson on ranked expression values).
     - **Cosine similarity** (optional but computed).
   - All 2,555 samples produced valid Pearson, Spearman, and cosine values.

2. **Tissue-level aggregation** (`tissue_similarity_summary.tsv`)
   - Grouped reference samples by **tissue** label.
   - For each tissue (68 total), computed:
     - `n_samples`.
     - `pearson_correlation_mean`, `median`, `max`, `95th_percentile`.
     - Analogous statistics for Spearman and cosine similarity.
   - Defined **`tissue_score` = `pearson_correlation_mean`**.
   - Ranked tissues in descending `tissue_score` (column `tissue_rank`, 1 = most similar).

3. **Visualization**
   - `tissue_similarity_ranking.png`: bar/point plot of the **top 20 tissues** by `tissue_score` (mean Pearson correlation).

---

# Results

- **Predicted tissue (final answer): _Prostate_**
  - This is the tissue with **`tissue_rank = 1`** and the highest `tissue_score` (mean Pearson correlation).

## Key quantitative findings

From `tissue_similarity_summary.tsv`:

- **Prostate**
  - `n_samples`: 52
  - `tissue_score` (mean Pearson correlation): **≈ 0.9797**
  - `pearson_correlation_max`: **≈ 0.9905**
  - `spearman_correlation_mean`: ≈ 0.9202
  - `spearman_correlation_max`: ≈ 0.9322
  - `cosine_similarity_mean`: ≈ 0.9850
  - `cosine_similarity_max`: ≈ 0.9930

- **Top 5 tissues by mean Pearson correlation (`tissue_score`)**
  1. Prostate — ~0.9797 (52 samples)
  2. Bladder — ~0.9506 (43 samples)
  3. Cervix - Endocervix — ~0.9496 (23 samples)
  4. Thyroid — ~0.9479 (52 samples)
  5. Colon - Transverse - Muscularis — ~0.9479 (9 samples)

The margin between Prostate and the next-best tissue (Bladder) is ~0.029 in mean Pearson correlation, which is substantial given the already high correlation regime.

From `top_reference_matches.tsv` (top 50 samples by Pearson correlation):

- **All of the top 50 individual reference matches are annotated as Prostate.**
- The highest Pearson correlations between the unknown sample and individual Prostate samples are ≈ 0.990–0.991, with similarly high Spearman and cosine values.

Taken together, both tissue-level aggregation and individual top matches strongly support **Prostate** as the correct tissue label.

---

# Caveats & Warnings

- **High similarity for several tissues:**
  - Non-Prostate tissues such as Bladder, Cervix - Endocervix, Thyroid, and some colon and stomach tissues also show high mean Pearson correlations (>0.94). This likely reflects biological similarity and shared expression programs across tissues, but they remain clearly below Prostate in `tissue_score` and lack representation among the very top per-sample matches.

- **Single normalization and similarity scheme:**
  - The classification is based on log1p-CPM normalization and Pearson-centered similarity, with Spearman and cosine used as corroborating metrics. Alternative normalization schemes (e.g., TMM, quantile normalization) or classifiers might yield slightly different score magnitudes but are unlikely to overturn the strong dominance of Prostate.

- **Reference-dependent conclusion:**
  - The tissue call assumes that the reference metadata (tissue labels) are correct and that the 68-tissue panel adequately represents the space of possible tissues. If the unknown sample came from a tissue not present in the panel or from an unusual disease state, the algorithm would still assign the closest available tissue, here Prostate.

---

# Next Steps

- **Optional robustness checks**
  - Recompute similarities using alternative normalizations or distance measures (e.g., z-scored expression, Euclidean distance) to confirm the stability of the Prostate call.
  - Perform gene set–level similarity (e.g., tissue marker panels) to show that Prostate-specific marker genes are highly expressed in the unknown sample.

- **Visualization for interpretation**
  - Generate heatmaps of the unknown sample versus top Prostate and non-Prostate samples for key marker genes to provide more interpretable, gene-level evidence.

- **Extension to classifiers**
  - Train a supervised multi-class classifier (e.g., regularized logistic regression or random forest) on the reference panel and confirm that it also predicts Prostate for the unknown sample.

---

# References

- The 2,555-sample, 68-tissue panel and associated metadata provided in `library/datasets/` (no external DOIs or PMIDs supplied with the task).
