# Title & Objective

**Objective:** Identify which anonymized sample (Sample1–Sample32) corresponds to an **E2F6** siRNA knockdown using only genome-wide TPM expression data.

---

# Data & Methods

## Data
- **Source file:** `library/datasets/matrixTpm_anonymized.tsv`
- **Format:** TSV; rows = genes, columns = samples.
- **Dimensions:** 59,526 genes × 32 samples.
- **Sample labels:** `Sample1`–`Sample32` (anonymized).
- **Expression units:** Tags per million (TPM), already normalized.
- **Key check:** The gene **E2F6** is present as a row identifier.

## Methods

1. **Matrix loading and QC**
   - Loaded `matrixTpm_anonymized.tsv` with `gene_name` as the row index.
   - Verified orientation: genes as rows, samples as columns.
   - Computed basic per-sample statistics (mean, median, SD, min, max TPM) across all genes.

2. **E2F6 expression profiling**
   - Extracted the **E2F6** row (TPM values) across all 32 samples.
   - Calculated across samples:
     - Mean E2F6 TPM: ~20.25
     - Standard deviation (sample SD): ~3.63
   - For each sample, computed a **z-score**:
     \[
     z = \frac{\text{E2F6 TPM} - \mu_{E2F6}}{\sigma_{E2F6}}
     \]
     where \(\mu_{E2F6}\) and \(\sigma_{E2F6}\) are the mean and SD of E2F6 TPM across the 32 samples.

3. **Ranking and knockdown call**
   - Built a table of samples with columns: `sample`, `E2F6_TPM`, `E2F6_zscore`.
   - Sorted samples from **lowest to highest** E2F6 TPM.
   - Designated the sample with the **lowest E2F6 TPM** (and most negative z-score) as the **E2F6 knockdown**.

---

# Results

## E2F6 expression across samples

Key summary of E2F6 TPM across 32 samples:
- **Mean TPM:** 20.25
- **SD:** 3.63
- **Minimum TPM:** 9.00 (Sample25; z ≈ -3.10)
- **Maximum TPM:** 26.26 (Sample29; z ≈ 1.65)

Top of the rank-ordered E2F6 table (lowest expression first):

| Rank | Sample   | E2F6_TPM | E2F6_zscore |
|------|----------|----------|-------------|
| 1    | Sample25 | 9.00     | -3.10       |
| 2    | Sample23 | 15.45    | -1.32       |
| 3    | Sample6  | 16.06    | -1.15       |
| 4    | Sample17 | 16.54    | -1.02       |
| 5    | Sample22 | 16.66    | -0.99       |

The remaining samples have progressively higher E2F6 expression, with most clustered near or above the mean.

## Called E2F6 knockdown sample

- **Chosen E2F6 knockdown sample:** **Sample25**
- **E2F6 TPM (Sample25):** 9.000
- **E2F6 z-score (Sample25):** -3.098851

**Justification:**
- Sample25 has by far the **lowest E2F6 TPM** among all 32 samples.
- The next-lowest sample, Sample23, has E2F6 TPM = 15.450 (z = -1.322867), which is much higher than Sample25, indicating a large expression drop unique to Sample25.
- This pattern (a strong, isolated reduction of the targeted gene) is consistent with an effective **E2F6 siRNA knockdown** in Sample25.

---

# Caveats & Warnings

- **Single-gene criterion only:** The call is based solely on the E2F6 mRNA level itself; no downstream pathway or off-target effects were considered.
- **Relative inference:** Without explicit control labels, the designation of Sample25 as the knockdown is relative ("lowest E2F6 among 32") but strongly supported by the large gap to the next sample.

---

# Next Steps

- **Cross-check with target genes:** If target or pathway annotation is available, verify that known E2F6-regulated genes show expected expression changes in Sample25.
- **Generalize approach:** Apply the same ranking logic to other genes of interest to map additional knockdowns to sample IDs.

---

# References

- TPM normalization concept: Wagner GP, Kin K, Lynch VJ. *Measurement of mRNA abundance using RNA-seq data: RPKM measure is inconsistent among samples.* Theory Biosci. 2012;131(4):281–285. doi:10.1007/s12064-012-0162-3
