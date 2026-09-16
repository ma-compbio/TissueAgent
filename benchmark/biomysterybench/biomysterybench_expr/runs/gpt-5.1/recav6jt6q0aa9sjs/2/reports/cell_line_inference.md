# Cell-line inference for sample A

## Data inspected

Inputs used for this step:

- Gene-level TPM table: `project/outputs/tables/sample_A_expression_tpm.tsv`
- Gene-level counts table: `project/outputs/tables/sample_A_expression_counts.tsv`
- QC summary: `project/outputs/tables/sample_A_expression_summary_qc.tsv`
- Marker panel descriptions: `project/outputs/tables/marker_gene_panels_description.tsv`
- Marker panel scores for sample A: `project/outputs/tables/sample_A_marker_panel_scores.tsv`

The expression tables for sample A use internal numeric `gene_id` values originating from an RSEM-style quantification. These IDs are not standard Ensembl gene IDs or gene symbols. The counts table confirms the presence of a `metric` column with values `RSEM_expected_count`, consistent with RSEM output.

## Marker panels and ID-mapping limitation

The marker panels in `marker_gene_panels_description.tsv` are defined using canonical human gene symbols in the `marker_genes` column (e.g., **PTPRC**, **CD34**, **ALB**, **EPCAM**, **KRT8**, **POU5F1**, etc.). The panel set includes:

- Lineage panels (hematopoietic, B cell, myeloid, hepatocyte, lung epithelial, breast epithelial, colon epithelial, prostate epithelial, neuronal, fibroblast/mesenchymal, endothelial, pluripotency, proliferation, etc.).
- Cell line-specific panels for 13 canonical lines: K562, GM12878, HepG2, A549, MCF-7, HCT116, HeLa-S3, H1-hESC, HUVEC, IMR-90, SK-N-SH, LNCaP, and PC-3.

However, there is no annotation file in the workspace that maps the internal numeric `gene_id` values in the RSEM outputs to Ensembl IDs or gene symbols. As a result, none of the canonical marker gene symbols in the panels can be reliably matched to the expression tables.

This is confirmed by the marker panel scores in `sample_A_marker_panel_scores.tsv`:

- All panels have `mean_TPM = 0`, `median_TPM = 0`, `max_TPM = 0`.
- All panels have `n_genes_detected = 0`, while `n_genes_in_panel` reflects only the conceptual panel size.
- The `notes` field explicitly states that no marker genes matched the internal `gene_id` values and that the RSEM `gene_id` values are Ensembl-like but cannot be mapped to canonical symbols in this context.

Consequently, there is **no discriminative marker-panel signal** available to distinguish between candidate lineages or cell lines for sample A.

## Implications for cell-line ranking

Because of the ID-mapping failure:

- Lineage-level scores (e.g., hematopoietic vs. epithelial vs. neuronal) are all zero and therefore non-informative.
- Cell line-specific panel scores for K562, GM12878, HepG2, A549, MCF-7, HCT116, HeLa-S3, H1-hESC, HUVEC, IMR-90, SK-N-SH, LNCaP, and PC-3 are also all zero.
- The QC summary (`sample_A_expression_summary_qc.tsv`) provides only global metrics such as number of expressed genes, total TPM, total counts, and distributional summaries (median, mean, 90th percentile). These metrics do not carry clear, lineage-specific signatures (e.g., they do not reveal which genes account for the high TPM), so they cannot be used in a principled way to favor a particular cell line.

Under these constraints, there is **no expression-based evidence** in the available data that allows a robust similarity comparison between sample A and any specific cell line.

## Construction of the cell-line ranking

Despite the lack of discriminative information, a formal ranking of 24 candidate cell lines is still required. To satisfy this requirement while remaining transparent and conservative, the following strategy was used:

1. **Candidate set definition**

   - The 13 cell lines that have explicit marker panels in `marker_gene_panels_description.tsv` were included:
     - K562, GM12878, HepG2, A549, MCF7, HCT116, HeLaS3, H1hESC, HUVEC, IMR90, SKNSH, LNCaP, PC3.
   - To reach 24 total candidates, 11 additional widely used human cell lines were added to approximate a typical ENCODE/CCLE-style panel:
     - HEL, Jurkat, U2OS, Saos-2, TF-1, NB4, HL-60, BT-20, T-47D, Calu-3, SW480.
   - This yields the following 24 candidates (sorted alphabetically):
     - A549, BT-20, Calu-3, GM12878, H1hESC, HCT116, HEL, HL-60, HUVEC, HeLaS3, HepG2, IMR90, Jurkat, K562, LNCaP, MCF7, NB4, PC3, SKNSH, SW480, Saos-2, T-47D, TF-1, U2OS.

2. **Scoring and ranking rule**

   - Because all marker panel scores for sample A are zero and there is no way to map gene IDs to symbols, it is not possible to compute any meaningful similarity score between sample A and any of the 24 candidate lines.
   - Therefore, all cell lines were assigned an identical placeholder `score` of **0.0**, explicitly indicating the absence of discriminative evidence.
   - Ranks were then assigned purely by **alphabetical order of `cell_line_id`**, which is an arbitrary but fully transparent ordering mechanism.
   - The `evidence_summary` field for every row in the ranking table states: *"No discriminative marker signal; rank based on alphabetical order only."*

3. **Output table**

   The resulting ranking table is saved at:

   - `project/outputs/tables/cell_line_ranking.tsv`

   with columns:

   - `rank` (1–24, based on alphabetical order)
   - `cell_line_id` (one of the 24 candidates listed above)
   - `score` (0.0 for all lines)
   - `evidence_summary` (text as described above)

## Selected "best-matching" cell line

By construction, the top-ranked cell line in the alphabetical list is **A549**. However, it is crucial to emphasize that:

- This choice is **not supported by any expression-based evidence** from sample A.
- The selection of A549 as the "best match" is **purely a consequence of alphabetical ordering** under conditions where all cell lines have identical (zero) scores.

In other words, there is **no biological justification** in the current data for preferring A549 over any of the other 23 candidate lines.

## Limitations and what additional data are needed

The main limitation is the inability to map internal RSEM `gene_id` values to standard gene identifiers. Without such a mapping, it is impossible to:

- Evaluate expression of specific marker genes (e.g., PTPRC, ALB, EPCAM, KRT8, POU5F1) in sample A.
- Compute lineage or cell-line-specific marker panel scores that reflect actual biology.
- Compare sample A to reference expression profiles from ENCODE or CCLE at the gene level.

To make a robust and evidence-based cell-line inference, the following would be required:

1. **A gene ID mapping file**: A table linking the internal RSEM `gene_id` values to Ensembl gene IDs and/or HGNC gene symbols. This could be generated at quantification time (e.g., from the RSEM reference) or obtained from the alignment/quantification pipeline.

2. **Recomputed marker panel scores**: Using the mapping, re-derive marker panel scores for sample A by aggregating TPM (or counts) for the marker genes defined in each panel.

3. **Reference expression profiles**: Optionally, obtain matched gene-level expression matrices for a panel of known cell lines, allowing direct similarity metrics (e.g., correlation, cosine similarity) between sample A and each reference line.

With these components in place, one could:

- Determine which lineage panels are most strongly expressed in sample A.
- Identify which cell-line marker signatures best match the sample.
- Provide a quantitatively supported ranking, along with uncertainty estimates.

## Conclusion

Given the current inputs and the unresolved gene-identifier mapping, the cell-line ranking for sample A is necessarily **arbitrary** and **non-informative**. All candidate cell lines receive identical scores, and alphabetical ordering is used solely to produce a formal ranking. The reported "best match" (A549) should therefore be interpreted strictly as a placeholder in the absence of adequate annotation, not as a biologically meaningful inference.