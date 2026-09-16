# NSE-BMP4 Transgenic Group Inference

We inferred which latent group corresponds to the NSE-BMP4 transgenic mouse model using per-gene expression differences between Group_1 and Group_2, together with the pre-filtered candidate transgene-like genes.

Across all genes (`gene_group_difference_summary.tsv`), we defined "strongly enriched" genes as those with absolute log2-fold-change ≥ 2 and mean expression in the higher-expression group ≥ 50, to capture a stringent, high-level transgene-like signature. Under this criterion, all strongly enriched genes (n = 55) favored **Group_2**, while **Group_1** had essentially none. Within the focused set of candidate transgene-like genes (`candidate_transgene_signature_genes.tsv`), 44 of 45 genes showed higher expression in Group_2, with many displaying large-magnitude log2-fold-changes (up to ~11.9) and high mean expression in Group_2 (up to ~5454.8). These patterns are consistent with a strong, specific transgene-driven expression signature in Group_2 and a lack of such a signature in Group_1.

Taken together, these observations strongly indicate that **Group_2** corresponds to the **NSE-BMP4 transgenic** condition, with Group_1 serving as the non-transgenic control-like group.

## Inferred Transgenic Samples

Based on the sample-level metadata in `sample_metadata.tsv`, all samples annotated as belonging to Group_2 should be treated as NSE-BMP4 transgenic in downstream analyses. The inferred transgenic sample IDs are listed below.

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