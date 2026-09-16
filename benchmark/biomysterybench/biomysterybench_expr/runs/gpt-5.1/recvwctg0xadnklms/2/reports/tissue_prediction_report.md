# Title & Objective

**Task:** Infer the human tissue of origin for a single RNA-seq sample using a reference panel of 2,555 bulk RNA-seq samples spanning 68 tissues.

**Objective:** Use gene-expression similarity to assign the unknown sample to one of the 68 tissues, and report the tissue name exactly as it appears in the reference metadata `tissue` column.

---

## Data & Methods

**Inputs (from `library/datasets/`):**
- `gene_read_counts_2555_tissue_samples.csv`: raw count matrix for 2,555 reference samples (58,988 genes × 2,555 samples; first column `gene_id`).
- `metadata_2555_tissue_samples.csv`: sample metadata with at least `sample_id` and `tissue` (68 distinct tissues across 2,555 samples).
- `gene_read_counts_unknown_tissue_sample.csv`: raw counts for the unknown sample (58,988 genes × 1 sample; first column `gene_id`, column name `unknown_sample`).

**1. Harmonization of expression matrices**
- Verified that reference and unknown count matrices share 58,988 genes and a consistent `gene_id` format.
- Resolved any potential duplicate gene IDs by summing counts within each matrix (no change in gene count in this dataset).
- Ensured metadata/sample alignment:
  - Confirmed all `metadata.sample_id` values match the non-`gene_id` columns of the reference matrix.
  - Reordered reference expression columns to match the metadata order.
- Created harmonized matrices with genes as rows and samples as columns:
  - `reference_expression_harmonized.tsv`: 58,988 genes × 2,555 samples.
  - `unknown_expression_harmonized.tsv`: 58,988 genes × 1 sample.
  - `shared_genes.tsv`: ordered list of the 58,988 shared `gene_id`s.

**2. Joint normalization across samples**
- Concatenated the harmonized reference and unknown matrices to form one genes × 2,556 samples matrix.
- Computed per-sample library sizes as column sums of raw counts.
- Applied library-size scaling to Counts Per Million (CPM):  
  \(\text{CPM}_{ij} = \text{counts}_{ij} / \text{library\_size}_j \times 10^6\).
- Performed log-transformation:  
  \(\text{log2\_CPM}_{ij} = \log_2(\text{CPM}_{ij} + 1)\).
- Split back into:
  - `reference_expression_normalized.tsv`: 58,988 genes × 2,555 samples.
  - `unknown_expression_normalized.tsv`: 58,988 genes × 1 sample.
- Generated `normalization_summary.tsv` with per-sample library size, scaling factor, and min/median/max of log2-CPM.

**3. Sample-level similarity computation**
- Using the normalized matrices, confirmed identical gene ordering between reference and unknown.
- For each of the 2,555 reference samples, computed similarity to the unknown sample over all 58,988 genes:
  - **Primary metric:** Pearson correlation.
  - **Additional metrics:** Spearman correlation, cosine similarity.
- Produced `sample_similarity_scores.tsv` with columns:
  - `sample_id`, `pearson`, `spearman`, `cosine`, `rank_pearson`, `rank_spearman`, `rank_cosine`.
  - Table sorted in descending order of `pearson`.
- Created `sample_similarity_rank_plot.png`: Pearson similarity vs rank, highlighting the top 10 most similar samples.

**4. Tissue-level aggregation**
- Joined `sample_similarity_scores.tsv` with `metadata_2555_tissue_samples.csv` via `sample_id` (inner join; all 2,555 samples retained).
- Confirmed presence of 68 unique tissues in the joined dataset.
- Grouped by `tissue` and calculated, per tissue:
  - `pearson_mean`, `pearson_median` (primary aggregation metrics).
  - `spearman_mean`, `cosine_mean`.
  - `n_samples` (number of reference samples per tissue).
- Saved results in `tissue_level_similarity.tsv`, sorted by `pearson_mean` (descending).
- Generated `tissue_similarity_barplot.png`: horizontal barplot of the top 20 tissues by `pearson_mean`.

**5. Final tissue assignment**
- Selected the top-ranked tissue based on:
  1. Highest `pearson_mean`.
  2. If tied, higher `pearson_median`.
  3. If still tied, larger `n_samples`.
- Extracted the `tissue` string exactly as in the metadata and wrote:
  - `predicted_tissue.txt`: single line containing only the tissue name.
  - `prediction_summary.md`: brief narrative justification.

---

## Results

**Predicted tissue of origin for the unknown RNA-seq sample:**

- **Prostate**

**Key quantitative results:**
- From `tissue_level_similarity.tsv` (top tissues by mean Pearson similarity, abridged):
  - Prostate: `pearson_mean` ≈ 0.9797, `pearson_median` ≈ 0.9808, `n_samples` = 52.
  - Bladder: `pearson_mean` ≈ 0.9506, `n_samples` = 43.
  - Cervix - Endocervix: `pearson_mean` ≈ 0.9496, `n_samples` = 23.
  - Thyroid: `pearson_mean` ≈ 0.9479, `n_samples` = 52.
  - Several other tissues follow with still lower `pearson_mean`.
- The margin between Prostate and the next-best tissues is substantial (~0.03 in mean Pearson), and Prostate also has a relatively large number of supporting reference samples (52), indicating that the high similarity is not driven by a single outlier.

---

## Caveats & Warnings

- **Normalization choice:** A simple CPM + log2 transformation was used rather than more sophisticated methods (e.g., TMM, DESeq2 size factors, or batch correction). While adequate for global similarity, it may not fully correct complex technical effects.
- **Reference-panel dependence:** The prediction is contingent on the composition and quality of the 2,555-sample reference panel. If certain tissues are underrepresented or absent, similarities may be biased toward better-represented tissues.
- **One-sample classification:** Only a single unknown sample was classified. There is no direct validation on held-out unknowns within this run, so the confidence is inferred from relative similarity margins rather than formal error rates.

---

## Next Steps

- If available, cross-check the predicted tissue (Prostate) against any orthogonal information (e.g., known markers, histology, or clinical data).
- Perform gene-level inspection of known prostate markers (e.g., KLK3/PSA, TMPRSS2) in the unknown sample versus top-matching and non-matching tissues to qualitatively validate the prediction.
- If more unknown samples are provided, repeat the same pipeline to assess consistency of tissue assignments and refine normalization or similarity metrics if needed.

---

## References

- Love MI, Huber W, Anders S. *Moderated estimation of fold change and dispersion for RNA-seq data with DESeq2.* Genome Biol. 2014;15(12):550. doi:10.1186/s13059-014-0550-8
- Robinson MD, McCarthy DJ, Smyth GK. *edgeR: a Bioconductor package for differential expression analysis of digital gene expression data.* Bioinformatics. 2010;26(1):139–140. doi:10.1093/bioinformatics/btp616
- Wang Z, Gerstein M, Snyder M. *RNA-Seq: a revolutionary tool for transcriptomics.* Nat Rev Genet. 2009;10(1):57–63. doi:10.1038/nrg2484
