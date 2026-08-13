# Title & Objective

**Objective:** Identify which anonymized sample (Sample1–Sample32) in a 32-sample human TPM expression matrix corresponds to an **E2F6** siRNA knockdown, using only the expression data.


# Data & Methods

**Data**
- File: `library/datasets/matrixTpm_anonymized.tsv`
- Structure: 59,526 genes (rows) × 33 columns (1 gene identifier column `gene_name` + 32 sample columns `Sample1`–`Sample32`).
- Values: TPM (tags per million) expression.

**Methods**
1. **Data validation & QC**
   - Confirmed matrix orientation: genes as rows, samples as columns.
   - Computed per-sample QC metrics (total TPM, mean, median, SD, 5th/25th/75th/95th percentiles, number of genes with TPM>1).
   - Computed per-gene summaries (mean TPM, SD, coefficient of variation, min/max across samples).

2. **E2F6 and E2F-family retrieval**
   - Searched `gene_name` for E2F-family members and related entries.
   - Identified a **single canonical E2F6 row** with `gene_name == "E2F6"`:
     - Row values (TPM across Sample1–Sample32):
       - `17.78, 21.62, 20.17, 18.01, 23.46, 16.06, 21.07, 23.60, 23.24, 25.59, 23.63, 20.38, 25.35, 22.22, 20.89, 18.54, 16.54, 19.31, 21.55, 16.84, 18.22, 16.66, 15.45, 20.12, 9.00, 20.10, 18.43, 24.68, 26.26, 24.59, 19.49, 19.29`.

3. **Per-sample E2F6 metrics**
   - For the canonical E2F6 row:
     - Computed raw TPM per sample.
     - Computed z-scores across the 32 samples (population SD, ddof=0).
     - Computed ranks of expression (rank 1 = lowest TPM, rank 32 = highest TPM).

4. **Candidate knockdown call**
   - Identified the sample with:
     - The **lowest E2F6 TPM**.
     - The **most negative E2F6 z-score**.
     - The **lowest rank** (1 of 32).
   - This sample was designated as the predicted E2F6 knockdown.

5. **E2F-target gene cross-check (supporting analysis)**
   - Defined a panel of canonical E2F/cell-cycle targets present in `gene_name` (exact symbol matches):
     - `MCM2, MCM3, MCM4, MCM5, MCM6, MCM7, CCNE1, CCNE2, CDC6, CDC45, ORC1, CDK2, PCNA, CCNB1, CCNB2, CCNA2, RRM1, RRM2, TYMS`.
   - For each gene, computed z-scores across the 32 samples.
   - For each sample, computed the **mean E2F-target z-score** as a simple summary signature.
   - Used this as **supporting evidence** for the candidate E2F6 knockdown sample.


# Results

- **Predicted E2F6 knockdown sample:** **Sample25**.

**Evidence from E2F6 expression**
- E2F6 TPM range across samples: **9.0–26.26 TPM**.
- Key per-sample metrics for E2F6 (subset):

  | Sample   | E2F6 TPM | E2F6 z-score | E2F6 rank (1=lowest) | Mean E2F-target z-score |
  |----------|----------|--------------|-----------------------|-------------------------|
  | Sample6  | 16.06    | -1.17        | 3                     | -0.21                   |
  | Sample17 | 16.54    | -1.04        | 4                     | -1.90                   |
  | Sample22 | 16.66    | -1.01        | 5                     | -2.49                   |
  | Sample23 | 15.45    | -1.34        | 2                     | -0.09                   |
  | **Sample25** | **9.00**     | **-3.15**       | **1**                    | **-0.10**                  |
  | Sample29 | 26.26    |  1.68        | 32                    |  0.51                   |

- **Sample25** is **uniquely** lowest in E2F6 TPM (9.0 TPM) and has the most negative z-score (~−3.15), giving it rank 1 (lowest expression) among all 32 samples.
- No other sample is tied with Sample25 in TPM or z-score; the separation is clear.

**Supporting E2F-target signature**
- The mean E2F-target z-score for Sample25 is modestly negative (~−0.10), indicating a slight broad reduction in expression of canonical E2F/cell-cycle targets relative to the cohort.
- Some other samples (e.g., Sample17, Sample22) show stronger negative E2F-target signatures, but they do **not** have the uniquely low E2F6 expression seen in Sample25.
- Thus, the **primary evidence** is the E2F6 gene itself; the target-panel analysis serves only as mild additional support.


# Caveats & Warnings

- **Relative, not absolute, inference:** The knockdown call is based on **relative E2F6 expression within this 32-sample set**. Absolute TPM magnitudes may depend on library size and quantification specifics.
- **Modest target-gene effect:** The E2F-target panel shows only a **modest** global decrease in Sample25, suggesting partial knockdown, compensatory regulation by other E2F family members, or biological/technical variability. This does not affect the clear E2F6 mRNA depletion in Sample25.
- **No external controls/metadata:** Without explicit control samples or experimental metadata, the identification necessarily assumes that **one** sample corresponds to an E2F6 knockdown and that E2F6 TPM is a reliable direct readout of knockdown efficacy.


# Next Steps

- If available, repeat the same procedure for other genes in the panel to map each anonymized sample to its corresponding siRNA target.
- Validate the E2F6 knockdown call using independent information (e.g., experimental design records, qPCR/Western data) if accessible.
- Extend the analysis to pathway-level or cell-cycle–phase signatures to explore the functional consequences of E2F6 depletion in Sample25.


# References

- Bracken AP et al. *Cell Cycle control by the E2F transcription factors.* Front Biosci. 2004. PMID: [14766372](https://pubmed.ncbi.nlm.nih.gov/14766372/)
- Kent LN, Leone G. *The broken cycle: E2F dysfunction in cancer.* Nat Rev Cancer. 2019. PMID: [30659284](https://pubmed.ncbi.nlm.nih.gov/30659284/)
