# Title & Objective

Infer the most likely freshly FACS-sorted PBMC cell type of origin for the provided bulk RNA-seq count data by matching it against a PBMC SingleCellExperiment reference, and report the exact `cellType` label string.

# Data & Methods

**Data**
- Bulk RNA-seq counts: `library/datasets/bulk_RNA_seq_counts.csv`
  - 35,413 genes × 2 bulk samples (`sample_1`, `sample_2`).
  - First column: Ensembl gene IDs (treated as `ensembl_id`).
  - Second column: `gene_symbol` (annotation, not used as the primary matching key).
- PBMC reference: `library/datasets/anonymized_pbmc_reference.rds`
  - Parsed as a SingleCellExperiment-like structure using a Python reader.
  - Expression assay: `counts` (20,264 genes × 161,764 cells).
  - Cell-type labels taken from `colData` column named exactly `cellType` (31 distinct levels).

**Preprocessing & Harmonization**
1. **Bulk QC summary**
   - Computed per-sample statistics:
     - Library size, number of detected genes (non-zero), and min/median/mean/max counts per gene.
   - Results saved in `tables/bulk_counts_summary.tsv`.

2. **Gene intersection**
   - Ensembl IDs from bulk (`ensembl_id`) were intersected with gene IDs from the PBMC reference (`counts.Dimnames[0]`).
   - Shared set: 16,596 Ensembl genes.
   - Intersection table (`ensembl_id`, `gene_symbol`) saved as `tables/gene_intersection.tsv`.

3. **Pseudobulk cell-type signatures**
   - For each `cellType` in the PBMC reference (31 total), raw counts were **summed** across all cells of that type for each gene.
   - Normalization applied identically to both pseudobulk and bulk (after restricting to intersected genes):
     - Library-size normalization to counts-per-million (CPM).
     - `log1p(CPM)` transform.
   - Pseudobulk signatures exported as a gene-by-cellType matrix (`ensembl_id` rows, 31 `cellType` columns) in `tables/celltype_pseudobulk_signatures.tsv`.

4. **Bulk normalization on intersected gene set**
   - Bulk counts were restricted to the 16,596 intersected genes and normalized using the same CPM + log1p pipeline.

5. **Similarity computation**
   - For each bulk sample (`sample_1`, `sample_2`) and each cell-type pseudobulk profile, Pearson correlation was computed across all intersected genes.
   - For each cell type, correlations from the two bulk samples were averaged:
     - `pearson_mean = (pearson_sample_1 + pearson_sample_2) / 2`.
   - Full similarity table saved as `tables/bulk_vs_celltype_similarity.tsv`.

6. **Prediction selection**
   - Cell types were ranked by `pearson_mean` in descending order.
   - The top-ranked `cellType` was designated as the predicted origin.
   - The second-best match and the difference in `pearson_mean` were also recorded.
   - Summary table saved as `tables/predicted_celltype.tsv` and narrative in `reports/prediction_summary.md`.

# Results

- **Predicted PBMC cell type (exact `cellType` label):** `CD4 TCM`
- **Aggregated similarity (pearson_mean) for CD4 TCM:** 0.878685
- **Second-best cell type:** `Treg`
  - `pearson_mean` for Treg: 0.875776
- **Margin between best and second-best:** 0.002910 (CD4 TCM − Treg)

Interpretation: CD4 TCM has the highest mean Pearson correlation to the bulk RNA-seq profiles, but the similarity margin over Treg is small, indicating that the bulk samples closely resemble both central memory CD4 T cells and regulatory T cells, with a slight edge for CD4 TCM.

# Caveats & Warnings

- The margin between CD4 TCM and Treg (≈0.0029 in `pearson_mean`) is small, so while CD4 TCM is the top-scoring type, the prediction is not sharply separated from Treg and may reflect a mixture or closely related T-cell states.
- Cell-type distribution summary for the PBMC reference (`reference_celltype_counts.tsv`) remains header-only; while this does not affect the correlation-based matching, it limits insight into how abundant each reference cell type is.

# Next Steps

- If desired, inspect `tables/bulk_vs_celltype_similarity.tsv` to see the full ranking and how other T- and non-T-cell types compare.
- Perform marker-gene-level inspection (e.g., canonical CD4 TCM vs Treg markers) using the intersected genes to biologically validate the predicted match.
- If you have access to the original SingleCellExperiment in R, you can further explore `cellType` hierarchies and verify how CD4 TCM and Treg are defined in this reference.

# References

- Lun ATL, McCarthy DJ, Marioni JC. A step-by-step workflow for low-level analysis of single-cell RNA-seq data with Bioconductor. F1000Res. 2016;5:2122. doi:10.12688/f1000research.9501.2
- Hao Y, Hao S, Andersen-Nissen E, et al. Integrated analysis of multimodal single-cell data. Cell. 2021;184(13):3573-3587.e29. doi:10.1016/j.cell.2021.04.048
