# NSE-BMP4 Transgenic Group Inference Report

## Title & Objective

**Objective:** Use only the RNA-seq expression matrix (no explicit genotype labels) to determine which anonymous group (Group_1 or Group_2) corresponds to the NSE-BMP4 transgenic mouse model, and list the sample IDs in that transgenic group.

## Data & Methods

**Data:**
- Bulk RNA-seq count matrix: `library/datasets/cleaned_counts.csv` (36,572 genes × 21 samples) from mouse tibial muscle across post-injury timepoints.
- No genotype labels were provided; instead, each sample ID encodes membership in **Group_1** or **Group_2** (e.g., `Sample_10_Group2`).

**Preprocessing & QC:**
- Parsed 21 samples into 9 **Group_1** and 12 **Group_2** samples using the `Sample_<n>_Group<digit>` pattern.
- Calculated per-sample metrics:
  - Library size (total counts), number of genes detected (count > 0), mean and variance of counts.
- Summarized QC by group; all 21 samples had valid labels and were retained.

**Group-wise gene analysis:**
- For each of 36,572 genes, computed:
  - `mean_expression_Group_1`, `mean_expression_Group_2` (mean raw counts by group).
  - `fraction_nonzero_Group_1`, `fraction_nonzero_Group_2` (proportion of samples with count > 0).
  - `log2_fold_change` = log2((mean_Group_1 + 1)/(mean_Group_2 + 1)) with pseudocount 1.
  - Presence/absence differences and a Mann–Whitney U p-value with BH–FDR correction.
- Defined **strongly enriched** genes as those with:
  - |log2FC| ≥ 2, and
  - mean expression in the higher-expression group ≥ 50 counts.

**Candidate transgene-like genes:**
- Constructed a prioritized list of candidate transgene-like genes based on:
  - Large |log2FC|, substantial detection-rate difference between groups, and
  - High absolute expression in the higher-expression group.
- Kept the top 45 genes satisfying |log2FC| ≥ 2 and notable detection differences, ranked by a composite effect-size score.

**Transgenic group inference:**
- Compared how many genes show strong, high-level, group-specific expression in each group.
- The group with a large set of strongly enriched, highly expressed genes was interpreted as carrying the NSE-BMP4 transgene.

## Results

- **Inferred transgenic group:** **Group_2**.
- Evidence from all genes (`gene_group_difference_summary.tsv`):
  - Using the strict definition (|log2FC| ≥ 2 and high mean expression), **55 genes** are strongly enriched overall.
  - **All 55** strongly enriched genes favor **Group_2**; **Group_1 has 0** such genes.
- Evidence from focused candidates (`candidate_transgene_signature_genes.tsv`):
  - 45 top candidate transgene-like genes were identified.
  - **44 of 45** have higher expression in **Group_2**.
  - Group_2 candidates show:
    - Maximum |log2FC| ≈ **11.9** (≈3,000–4,000-fold difference) and
    - Maximum mean expression ≈ **5,455** counts in the higher-expression group.
  - Group_1 has only a single candidate gene with modest expression (~4.7 counts) and a much smaller effect size (~2.1), not forming a coherent high-level signature.
- These patterns indicate a robust, specific expression program that is present in Group_2 and largely absent in Group_1, consistent with Group_2 being the NSE-BMP4 transgenic group.

**Final inferred NSE-BMP4 transgenic samples (all Group_2):**
- Sample_10_Group2
- Sample_11_Group2
- Sample_12_Group2
- Sample_13_Group2
- Sample_14_Group2
- Sample_15_Group2
- Sample_16_Group2
- Sample_17_Group2
- Sample_18_Group2
- Sample_19_Group2
- Sample_20_Group2
- Sample_21_Group2

## Caveats & Warnings

- Gene identifiers in the count matrix are numeric row indices without gene symbols, so it was not possible to directly confirm the presence of a gene named **BMP4** or related annotations; the inference is based purely on expression patterns.
- Statistical p-values are limited by small sample sizes (9 vs 12) and heavy multiple-testing correction; therefore, the decision relies primarily on effect sizes and expression magnitudes rather than formal significance testing.

## Next Steps

- If a gene-annotation file (mapping row indices to gene symbols) becomes available, re-map the candidate genes to confirm which feature corresponds to **BMP4** or the NSE-BMP4 construct.
- Use the inferred transgenic samples (Group_2) to perform downstream analyses such as time-course modeling, pathway enrichment, or differential expression vs Group_1 at each timepoint.

## References

- Benjamini Y, Hochberg Y. Controlling the false discovery rate: a practical and powerful approach to multiple testing. *J R Stat Soc B*. 1995;57(1):289–300.
