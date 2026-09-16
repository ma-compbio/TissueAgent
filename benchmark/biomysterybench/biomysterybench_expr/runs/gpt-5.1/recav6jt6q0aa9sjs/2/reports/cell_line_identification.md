# Cell-line identification for sample A

## Title & Objective

**Objective:** Use the provided RNA-seq gene expression quantification for a single sample (sample A) to assign it to one of 24 candidate human cell lines, committing to a single best-matching label under the constraint that only the expression data in `library/datasets/` may be used.

**Final assigned cell line:** **A549** (human lung adenocarcinoma epithelial cell line).

> **Important:** This assignment is *not* supported by expression-based evidence from this dataset. As explained below, the available quantification lacks any mapping from internal gene IDs to gene symbols or Ensembl IDs, so standard marker-based lineage/cell-line inference cannot be performed. A549 is selected purely by an explicit, documented tie-breaking rule (alphabetical order) once it was established that no candidate can be distinguished from the others.

## Data & Methods

### Data

- Source quantification file: `library/datasets/sample_A_gene_quantifications.tsv` (RSEM-style gene-level output).
- Derived tables:
  - `project/outputs/tables/sample_A_expression_tpm.tsv` — gene-level TPM.
  - `project/outputs/tables/sample_A_expression_counts.tsv` — RSEM expected counts.
  - `project/outputs/tables/sample_A_expression_summary_qc.tsv` — basic QC statistics.

Key properties:
- `gene_id` is an internal numeric ID (e.g., `10904`, `12954`) and is the *only* identifier provided for each row.
- TPM and counts correspond to standard RSEM columns (`TPM`, `expected_count`).
- No file in the workspace provides a mapping from `gene_id` to Ensembl IDs or HGNC gene symbols.

### Methods

1. **Expression matrix preparation**
   - Parsed the RSEM gene-level table and extracted TPM and expected counts per `gene_id`.
   - Generated QC metrics: number of genes with TPM>0, counts>0, total TPM, total counts, median and 90th percentile TPM, etc.

2. **Conceptual marker panel design**
   - Constructed biologically motivated marker panels (using standard *gene symbols* only) for:
     - Broad lineages: hematopoietic, B-cell/lymphoblastoid, myeloid, hepatocyte (liver), lung epithelial, breast epithelial, colon epithelial, prostate epithelial, neuronal, fibroblast/mesenchymal, pluripotent/stem.
     - Specific canonical cell lines: K562, GM12878, HepG2, A549, MCF-7, HCT116, HeLa-S3, H1-hESC, HUVEC, IMR-90, SK-N-SH, LNCaP, PC-3.
   - These definitions are recorded in `project/outputs/tables/marker_gene_panels_description.tsv` as semicolon-separated gene symbols.

3. **Marker panel scoring attempt**
   - Attempted to match marker genes (symbols) to the `gene_id` column in `sample_A_expression_tpm.tsv` by exact string comparison.
   - As expected, **no markers matched**, because `gene_id` consists of numeric/internal IDs rather than symbols.
   - Consequently, for every panel, the computed scores are:
     - `mean_TPM = 0`, `median_TPM = 0`, `max_TPM = 0`.
     - `n_genes_detected = 0` (no marker with TPM>0 because no marker could be linked).
     - `n_genes_in_panel` reflects only the intended conceptual panel size.
   - These results are recorded in `project/outputs/tables/sample_A_marker_panel_scores.tsv`, with a `notes` field explaining that markers could not be mapped to the internal IDs.
   - A heatmap of `max_TPM` per panel (`project/outputs/figures/sample_A_marker_panel_heatmap.png`) is generated but is uniformly zero and therefore non-discriminative.

4. **Cell-line ranking and final label selection**
   - Because all marker panel scores are zero and no gene ID→symbol mapping exists, **no lineage or cell-line signature can be extracted** from the data.
   - To still fulfill the task requirement of committing to a single label, a transparent tie-breaking strategy was applied:
     - A set of 24 candidate cell lines was assembled, including many common ENCODE/CCLE lines (e.g., K562, GM12878, HepG2, A549, MCF7, HCT116, HeLaS3, H1hESC, HUVEC, IMR90, SKNSH, LNCaP, PC3, HL-60, etc.).
     - Every cell line was assigned the **same numeric score (0.0)**, explicitly indicating no discriminative evidence.
     - A ranking was then produced by **alphabetical order** of `cell_line_id`.
   - In this alphabetical list, **A549** appears first and is therefore designated as `rank = 1` and treated as the "best match" for the purpose of this exercise.
   - The full ranking is stored in `project/outputs/tables/cell_line_ranking.tsv`, with `evidence_summary` stating: *"No discriminative marker signal; rank based on alphabetical order only."* for every line.

## Results

- **Assigned cell line:** **A549** (by alphabetical tie-break among 24 candidates with identical scores).
- **Global expression/QC characteristics of sample A** (from `sample_A_expression_summary_qc.tsv`):
  - Detected genes (TPM>0): 23,088.
  - Detected genes (expected_count>0): 23,190.
  - Total TPM: ~9.86 × 10^5.
  - Total expected counts: ~4.26 × 10^7.
  - Median TPM: 0.0.
  - 90th percentile TPM: 17.76.
  - Mean TPM: ~16.6.
  - Median expected count: 0.0.
  - 90th percentile expected count: 1,286.
  - Mean expected count: ~716.6.

These QC metrics indicate a typical bulk RNA-seq profile (many lowly expressed genes with a minority of highly expressed ones), but without gene identities they provide no specific clue about which of the 24 candidate lines is most similar.

## Caveats & Warnings

- **No gene ID→symbol mapping available:** The quantification uses internal numeric `gene_id` values without any accompanying annotation table. Because of this, canonical lineage or cell-line marker genes (defined by symbols like *ALB*, *EPCAM*, *GATA1*, *POU5F1*, etc.) cannot be linked to the expression matrix.
- **Marker panels non-informative:** All lineage and cell-line marker panels have zero scores for sample A. This is not biologically meaningful; it simply reflects the inability to map markers to the internal IDs.
- **Ranking is arbitrary, not evidence-based:** All 24 candidate cell lines were assigned identical scores (0.0). The choice of A549 as the "best match" arises solely from alphabetical ordering and should not be interpreted as a biological inference.
- **No differential or reference comparison:** There are no reference expression profiles for the candidate lines in the workspace, so even with a mapping, additional work would be required to perform a robust similarity-based classification.

## Next Steps

If you want a biologically meaningful cell-line assignment from this dataset, the following would be required:

1. **Obtain a gene ID mapping file** linking the internal RSEM `gene_id` values to Ensembl IDs and/or HGNC symbols.
2. **Recompute marker-panel scores** using the mapping, so each panel can be summarized by the TPM of its constituent genes.
3. **Introduce reference expression profiles** for the 24 candidate cell lines (or access public panels such as CCLE/ENCODE), and compute similarity metrics (e.g., Pearson correlation or cosine similarity) between sample A and each reference profile.
4. **Re-run the classification** using these enriched resources, yielding an evidence-based ranking and a defensible single best-matching cell line.

## References

- Li B, Dewey CN. RSEM: accurate transcript quantification from RNA-Seq data with or without a reference genome. *BMC Bioinformatics*. 2011;12:323. doi:10.1186/1471-2105-12-323.
- Barretina J, et al. The Cancer Cell Line Encyclopedia enables predictive modelling of anticancer drug sensitivity. *Nature*. 2012;483(7391):603–607. doi:10.1038/nature11003.
- ENCODE Project Consortium. An integrated encyclopedia of DNA elements in the human genome. *Nature*. 2012;489(7414):57–74. doi:10.1038/nature11247.
