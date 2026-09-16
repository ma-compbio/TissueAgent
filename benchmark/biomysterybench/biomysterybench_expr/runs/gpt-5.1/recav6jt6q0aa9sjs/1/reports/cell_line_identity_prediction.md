# Cell line identity prediction for sample A

## 1. ID harmonization and data preparation

**Inputs**
- Sample expression: `project/outputs/tables/sample_A_tpm_vector.tsv` (columns: `gene_id`, `TPM`).
- Marker signatures: `project/outputs/tables/cell_line_marker_signatures.tsv` (columns: `cell_line`, `gene_symbol`, `weight`).

**Gene ID harmonization**
- The sample file contains a mix of:
  - Ensembl gene IDs with version (e.g. `ENSG00000000419.12`).
  - Numeric IDs without the `ENSG` prefix (treated as gene symbols for robustness, but none overlapped the marker set).
- Marker signatures are provided as HGNC gene symbols.

**Mapping strategy**
1. Identified Ensembl-like IDs in the sample as those where `gene_id` starts with `"ENSG"`.
2. Stripped Ensembl version suffixes (e.g. `ENSG00000000419.12 → ENSG00000000419`).
3. Mapped Ensembl IDs to HGNC symbols using **mygene.info** via the `mygene` Python package with parameters:
   - `scopes = 'ensembl.gene'`
   - `fields = 'symbol'`
   - `species = 'human'` (Ensembl GRCh38-based annotations)
4. For non-Ensembl `gene_id` entries, used the raw `gene_id` string as `gene_symbol`.
5. Dropped sample rows for which no HGNC symbol was returned.
6. Aggregated TPM values by `gene_symbol` (sum of TPM per symbol, though most symbols are unique).

**Result of harmonization**
- Starting from 59,429 rows, 13,787 rows without a resolvable symbol were dropped.
- Final aggregated sample expression: 44,555 unique `gene_symbol` entries.
- Marker set: 295 unique HGNC symbols.
- Overlap between sample symbols and marker symbols: 293 genes, indicating almost all marker genes are present in the sample after mapping.

## 2. Scoring methodology

For each gene in the aggregated sample:
- Defined a TPM floor to avoid log-transform artifacts from zeros:
  - `TPM_capped = max(TPM, 0.01)`
  - `log2_TPM_plus1 = log2(TPM_capped + 1)`
- Computed a global rank by TPM:
  - Genes were sorted by TPM descending.
  - `rank` = 1 for the highest-TPM gene.
  - `rank_frac = 1 - (rank - 1) / N` where N is the total number of genes (so 1.0 = top gene, ~0.5 = median, 0.0 = undetected marker).

For each cell line and its marker set:
- Merged `cell_line_marker_signatures.tsv` with the sample gene table by `gene_symbol`.
- For any marker not detected in the sample, set `TPM = 0`, then applied the same capping and log transform.

**Primary score (used for ranking):**
- **Weighted mean log2 expression of marker genes**:

  \[
  S_{\text{primary}}(c) = \frac{\sum_{g \in M_c} w_g \cdot \log_2(\text{TPM}_g^{\text{capped}} + 1)}{\sum_{g \in M_c} w_g}
  \]

  where:
  - \(M_c\) = marker genes for cell line \(c\)
  - \(w_g\) = marker weight from the signature table.

**Secondary metrics:**
1. **Fraction of markers expressed above 1 TPM**:

   \[
   f_{\ge 1}(c) = \frac{\#\{g \in M_c : \text{TPM}_g \ge 1\}}{|M_c|}
   \]

2. **Weighted mean rank fraction** (rank-based enrichment):

   \[
   R_{\text{wmean}}(c) = \frac{\sum_{g \in M_c} w_g \cdot \text{rank\_frac}_g}{\sum_{g \in M_c} w_g}
   \]

These metrics ensure that both absolute expression and relative ranking of markers in the global transcriptome are considered, and that undetected markers (TPM = 0, rank_frac = 0) penalize the scores.

All scores were computed reproducibly in Python and saved to:
- `project/outputs/tables/cell_line_candidate_scores.tsv`

## 3. Cell line scores and ranking

The following table summarizes the scores for the 24 candidate cell lines (sorted by the primary score):

| Rank | Cell line           | Primary score (weighted mean log2(TPM+1)) | Fraction markers TPM ≥ 1 | Weighted mean rank_frac | n_markers | sum_weight |
|------|---------------------|-------------------------------------------:|--------------------------:|-------------------------:|----------:|-----------:|
| 1    | K562                | 5.61                                      | 0.86                     | 0.88                    | 28        | 71        |
| 2    | PC-3                | 2.55                                      | 0.48                     | 0.61                    | 25        | 55        |
| 3    | A549                | 2.45                                      | 0.48                     | 0.67                    | 25        | 62        |
| 4    | HEK293              | 2.42                                      | 0.48                     | 0.65                    | 25        | 53        |
| 5    | MCF-7               | 2.38                                      | 0.48                     | 0.72                    | 23        | 58        |
| 6    | DU145               | 2.34                                      | 0.44                     | 0.60                    | 25        | 55        |
| 7    | Epithelial_generic  | 2.32                                      | 0.44                     | 0.65                    | 25        | 58        |
| 8    | MDA-MB-231          | 2.26                                      | 0.48                     | 0.73                    | 25        | 62        |
| 9    | SW620               | 2.06                                      | 0.41                     | 0.60                    | 27        | 65        |
| 10   | HCT116              | 2.04                                      | 0.40                     | 0.60                    | 25        | 60        |
| 11   | Panc1               | 2.01                                      | 0.32                     | 0.62                    | 25        | 59        |
| 12   | HFFc6               | 1.78                                      | 0.52                     | 0.68                    | 26        | 58        |
| 13   | BJ                  | 1.74                                      | 0.48                     | 0.60                    | 30        | 68        |
| 14   | HepG2               | 1.74                                      | 0.30                     | 0.65                    | 25        | 57        |
| 15   | IMR-90              | 1.73                                      | 0.48                     | 0.60                    | 25        | 63        |
| 16   | H1                  | 1.48                                      | 0.36                     | 0.62                    | 25        | 58        |
| 17   | H9                  | 1.48                                      | 0.36                     | 0.58                    | 25        | 59        |
| 18   | hiPSC               | 1.43                                      | 0.32                     | 0.58                    | 25        | 63        |
| 19   | Caco-2              | 1.24                                      | 0.21                     | 0.59                    | 25        | 57        |
| 20   | HL-60               | 1.14                                      | 0.58                     | 0.62                    | 28        | 68        |
| 21   | THP-1               | 1.00                                      | 0.50                     | 0.58                    | 26        | 59        |
| 22   | BE2C                | 0.71                                      | 0.46                     | 0.49                    | 25        | 59        |
| 23   | SH-SY5Y             | 0.49                                      | 0.15                     | 0.47                    | 25        | 58        |
| 24   | SK-N-SH             | 0.48                                      | 0.16                     | 0.47                    | 25        | 58        |

Key observations:
- **K562 is a clear outlier**, with a primary score >2-fold higher than any other candidate and the highest fraction of markers expressed ≥1 TPM.
- Other top-scoring lines (PC-3, A549, HEK293, MCF-7, etc.) have substantially lower primary scores (~2.3–2.6 versus 5.6) and are not hematopoietic.

## 4. Marker-level inspection

### K562 (erythroleukemia)

K562’s marker set includes hemoglobin genes, erythroid transcription factors, erythroid surface markers, and the BCR–ABL1 fusion partners. In the sample, these markers are strikingly high:

- **Hemoglobin and erythroid structural genes**
  - **HBG2**: 1,638.6 TPM
  - **HBG1**: 1,394.8 TPM
  - **HBA1**: 1,373.2 TPM
  - **HBA2**: 337.2 TPM
  - **GYPA**: 264.0 TPM
  - **GYPB**: 154.8 TPM
  - **ALAS2**: 38.4 TPM
  - **AHSP**: 30.7 TPM
- **Erythroid transcription factors / regulators**
  - **GATA1**: 141.5 TPM
  - **NFE2**: 138.5 TPM
  - **TAL1**: 79.7 TPM
  - **KLF1**: 36.1 TPM
  - **LMO2**: 28.7 TPM
  - **HEMGN**: 163.9 TPM
- **Surface receptors / signaling**
  - **TFRC (CD71)**: 98.1 TPM
  - **EPOR**: 5.4 TPM
  - **KIT**: 0.33 TPM (low but detected)
  - **CD34**: not clearly expressed (0 TPM), consistent with a more erythroid-committed phenotype.
- **BCR–ABL1 fusion partners**
  - **BCR**: 50.4 TPM
  - **ABL1**: 51.1 TPM

This concerted, high-level expression of fetal/adult hemoglobins and canonical erythroid TFs is highly characteristic of K562 cells and not expected in non-erythroid lines.

### Myeloid leukemia lines (HL-60, THP-1)

- HL-60 and THP-1 show moderate expression of some myeloid markers (e.g., **SPI1**, **CSF3R**, **ITGAM**, **FCGR2A**, **PTPRC**, **MS4A3**), but:
  - Their primary scores (~1.0–1.1) are far below K562’s 5.6.
  - They lack the strong hemoglobin and erythroid TF signature that dominates the sample.

### Hepatocyte-like, lung epithelial, and pluripotent lines

- **HepG2** shows expression of some liver-related genes (e.g., **AFP**, **APOE**, complement components, keratins KRT8/18), but the overall pattern is weaker and not accompanied by robust hepatocyte master regulators at very high levels.
- **A549** and other epithelial lines show strong epithelial keratin expression (e.g., **EPCAM**, **KRT8**, **KRT18**, **KRT19**) and metabolic markers (e.g., **SLC2A1**, **ALDH1A1**, **ABCA3**), but these do not reach the extreme expression levels and coherence seen for erythroid markers.
- **H1/H9/hiPSC** do not exhibit a pluripotency transcription factor signature (e.g., OCT4/POU5F1, SOX2, NANOG) at levels that would rival the erythroid program.

### Fibroblast and neuronal lines

- **Fibroblast-like lines** (BJ, IMR-90, HFFc6) show ECM and mesenchymal markers (e.g., COL1A1, COL1A2, FN1, VIM, ITGA5, ITGB1, SPARC, TAGLN), but again, their primary scores are far below K562 and do not dominate the transcriptome.
- **Neuronal/neuroblastoma lines** (SK-N-SH, SH-SY5Y, BE2C) show modest expression of neuronal markers (e.g., ENO2, NTRK1, TUBB3, SYP) at low-to-moderate TPM, but these signatures are much weaker than the erythroid program.

## 5. Final prediction and rationale

**Predicted originating cell line: `K562`**

**Key supporting markers (3–5 illustrative genes):**
1. **HBG2 (γ-globin)** – 1,638.6 TPM
2. **HBG1 (γ-globin)** – 1,394.8 TPM
3. **HBA1 (α-globin)** – 1,373.2 TPM
4. **GATA1 (erythroid TF)** – 141.5 TPM
5. **HEMGN (erythroid nuclear protein)** – 163.9 TPM

These genes, together with many other hemoglobin subunits, erythroid transcription factors (NFE2, TAL1, KLF1, LMO2) and erythroid surface markers (GYPA/B, TFRC), form a highly coherent erythroid/megakaryocytic transcriptional program that is quintessential for K562 cells.

**Why other candidates were rejected (close runner-ups):**
- **PC-3, A549, HEK293, MCF-7, DU145, MDA-MB-231, epithelial_generic**
  - Although these lines have moderately high scores (~2.3–2.6), they are driven by epithelial or carcinoma marker sets (keratins, adhesion molecules, growth factor receptors) rather than hemoglobin and erythroid TFs.
  - Their marker expression levels and coherence do not approach the strength of the erythroid signature.
- **HepG2**
  - Shows liver-related markers (AFP, APOE, complement factors) but with lower overall scores and without a dominant hepatocyte transcription factor program.
- **HL-60 and THP-1**
  - Exhibit myeloid markers but at substantially lower abundance and with much weaker primary scores. They do not show the hallmark hemoglobin and erythroid TF expression seen here.
- **Fibroblast and neuronal lines (BJ, IMR-90, HFFc6, SK-N-SH, SH-SY5Y, BE2C)**
  - Display some lineage-appropriate markers but are clearly outscored by K562 both quantitatively (primary score) and qualitatively (lineage program).

## 6. Reproducibility

All computations were performed in Python using:
- `pandas` for data handling.
- `mygene` (mygene.info API) for Ensembl-to-HGNC symbol mapping (Ensembl GRCh38-based).
- Explicit formulae for TPM capping, log2 transformation, and ranking as described above.

Outputs written in this analysis:
- Cell line scores: `project/outputs/tables/cell_line_candidate_scores.tsv`
- This report: `project/outputs/reports/cell_line_identity_prediction.md`
