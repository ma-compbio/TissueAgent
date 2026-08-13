# Title & Objective

**Objective:** Infer the biological sex (male, female, or unknown) of each sample in the ovarian and pancreatic cancer microarray dataset (49 samples total) using only expression profiles, and provide final labels in the format `SampleID; sex`.

# Data & Methods

**Data sources**
- `library/datasets/Cancers.csv`: Microarray expression matrix with 49 samples (rows) × 36,454 probes (columns, plus a `SampleID` column).
- `library/datasets/refseq_to_symbol_map.csv`: Mapping of 36,454 probe/RefSeq identifiers (`REFSEQ`) to gene symbols (`SYMBOL`).

**Preprocessing and gene-level matrix construction**
- Treated rows of `Cancers.csv` as samples and columns (other than `SampleID`) as probes.
- Mapped all probe IDs to gene symbols via `refseq_to_symbol_map.csv`.
- Dropped probes with missing/empty gene symbols.
- Collapsed multiple probes per gene by taking the mean expression per gene × sample.
- Resulting gene-level matrix: 17,524 genes × 49 samples, saved as `tables/gene_expression_matrix.tsv` (genes as rows; samples 1–49 as columns).

**Platform structure and marker coverage**
- Inferred three platform-like probe sets via shared NA patterns:
  - **P1:** Probes with no NAs across any sample (measured on all 49 samples).
  - **P2:** Probes non-NA only in samples 1–6.
  - **P3:** Probes non-NA only in samples 7–49.
- Sex-linked markers present in the matrix:
  - Female-associated: XIST.
  - Male-associated (Y-linked): RPS4Y1, DDX3Y, KDM5D, EIF1AY, UTY.
- Coverage per platform (from `tables/sex_marker_coverage.tsv`):
  - **P1:** RPS4Y1, DDX3Y, KDM5D, EIF1AY, UTY present; XIST absent.
  - **P2:** XIST present; Y markers absent.
  - **P3:** None of the above markers present.
- Consequently, XIST is measured only in samples 1–6; Y markers are measured for all samples.

**Sex-marker scoring**
- Loaded `tables/gene_expression_matrix.tsv` and extracted rows for XIST and the five Y-linked genes.
- For each marker gene, computed a z-score across the 49 samples (ignoring NAs):
  - z_g(sample) = (expression_g(sample) − mean_g) / sd_g.
- Defined sex scores per sample:
  - **Female_score:** z-scored XIST only.
    - Defined for samples 1–6 (XIST present); NA for samples 7–49.
  - **Male_score:** mean of z-scores across the five Y-linked genes (RPS4Y1, DDX3Y, KDM5D, EIF1AY, UTY).
    - Defined for all 49 samples.
- Also computed:
  - `XIST_raw`: raw XIST expression (samples 1–6 only).
  - `Y_markers_mean_raw`: mean of raw expression of the five Y-linked genes.
- Saved these metrics in `tables/sex_marker_scores.tsv`.

**Decision rules for sex assignment**
- Thresholds selected from score distributions (quantiles) and used consistently:
  - `male_high` (Male_score) = 1.0
  - `male_low` (Male_score) = -0.45
  - `female_high` (Female_score) = 0.8
  - `female_low` (Female_score) = -0.6
  - `y_high` (Y_markers_mean_raw) = 6.98
  - `y_low` (Y_markers_mean_raw) = 5.12

- **Samples with XIST (Female_score not NA; samples 1–6)**
  - Assigned **female** if:
    - Female_score ≥ 0.8 **and** Male_score < 1.0.
  - Assigned **male** if:
    - Female_score ≤ -0.6 **and** Male_score ≥ 1.0.
  - Otherwise assigned **unknown**.

- **Samples without XIST (Female_score NA; samples 7–49)**
  - Assigned **male** if:
    - Male_score ≥ 1.0 **or** Y_markers_mean_raw ≥ 6.98.
  - Assigned **female** if:
    - Male_score ≤ -0.45 **and** Y_markers_mean_raw ≤ 5.12.
  - Otherwise assigned **unknown**.

These rules are intentionally conservative, favoring `unknown` when XIST is absent or XIST and Y markers give conflicting signals.

# Results

**Overall assignments (49 samples)**
- Male: 3 samples (IDs 4, 5, 6).
- Female: 5 samples (IDs 3, 23, 30, 41, 49).
- Unknown: 41 samples (all others).

**Final per-sample sex labels (as requested)**

The final labels are provided in `reports/sample_sex_assignments_formatted.txt` as one sample per line in the form `SampleID; sex`:

1; unknown  
2; unknown  
3; female  
4; male  
5; male  
6; male  
7; unknown  
8; unknown  
9; unknown  
10; unknown  
11; unknown  
12; unknown  
13; unknown  
14; unknown  
15; unknown  
16; unknown  
17; unknown  
18; unknown  
19; unknown  
20; unknown  
21; unknown  
22; unknown  
23; female  
24; unknown  
25; unknown  
26; unknown  
27; unknown  
28; unknown  
29; unknown  
30; female  
31; unknown  
32; unknown  
33; unknown  
34; unknown  
35; unknown  
36; unknown  
37; unknown  
38; unknown  
39; unknown  
40; unknown  
41; female  
42; unknown  
43; unknown  
44; unknown  
45; unknown  
46; unknown  
47; unknown  
48; unknown  
49; female

# Caveats & Warnings

- **Tumor context:** These are cancer biopsies; copy-number alterations, tumor purity, and clonal heterogeneity can distort sex-marker expression (e.g., Y loss in male tumors or XIST dysregulation), so inferred sex may not always equal the patient’s karyotype.
- **Incomplete marker coverage:** XIST is available only for 6 samples, so most calls rely solely on Y markers; this especially limits confident female calls.
- **Conservative thresholds:** The rules were designed to avoid false positives, leading to many `unknown` assignments where evidence is intermediate.
- **Platform effects:** Platform-specific measurement and missingness patterns (P1–P3) could introduce biases in expression levels that were not explicitly batch-corrected.

# Next Steps

- If ground-truth sex labels become available, evaluate and, if needed, recalibrate the decision thresholds.
- Consider more sophisticated modeling (e.g., mixture modeling or classification using a broader sex-biased gene set) to reduce the `unknown` fraction.
- Incorporate additional metadata (e.g., tissue of origin or clinical annotations) if available in future datasets to explore clustering of sex with other variables.

# References

- Toker L, Feng M, Pavlidis P. "Whose sample is it anyway?" Widespread misannotation of samples in transcriptomics studies. *F1000Research*. 2016;5:2103. doi:10.12688/f1000research.9692.2
- Lopes-Ramos CM et al. Gene regulatory network differences between sexes. *Trends Genet*. 2020;36(10): 857–868. doi:10.1016/j.tig.2020.07.004
