# Title & Objective

**Title:** Sex assignment of cancer microarray samples using X/Y-linked gene expression

**Objective:**
Assign a sex label (male, female, or unknown) to each sample in the available cancer microarray dataset based solely on expression patterns of canonical sex-linked marker genes, and provide the final results in the format `SampleID; sex`.

---

# Data & Methods

## Data
- Source directory: `library/datasets/`
- Expression matrix: `Cancers.csv`
  - 49 samples
  - 36,454 expression features (probes/RefSeq-like IDs) plus a `SampleID` column.
- Probe→gene map: `refseq_to_symbol_map.csv`
  - Maps 36,454 probe IDs to HGNC gene symbols.
- No explicit metadata for platform (GPL887/GPL4133) or cancer type (ovarian/pancreatic) were present; all samples were therefore treated uniformly with platform/cancer_type marked as `unknown`.

## Marker selection and aggregation
- Target genes:
  - X-linked inactivation marker: **XIST**
  - Y-linked markers: **RPS4Y1, KDM5D (SMCY), DDX3Y, EIF1AY, UTY, USP9Y, ZFY**
  - TSIX was requested but had no non-missing values and was not used.
- Using `refseq_to_symbol_map.csv`, probes mapping to these genes were identified:
  - XIST: 1 probe
  - RPS4Y1, KDM5D, DDX3Y, EIF1AY, USP9Y, ZFY: 1 probe each
  - UTY: 2 probes (aggregated)
- For each sample, probe-level expression for a given gene was summarized to **gene-level** by taking the mean across all probes for that gene (affects only UTY).

## Marker expression matrix
- Constructed `project/outputs/tables/sex_marker_expression_by_sample.tsv` with:
  - Rows: 49 samples (indexed by `SampleID`).
  - Columns:
    - `SampleID`
    - `platform` (all `unknown`)
    - `cancer_type` (all `unknown`)
    - Gene-level expression for: DDX3Y, EIF1AY, KDM5D, RPS4Y1, USP9Y, UTY, ZFY, XIST, TSIX (TSIX all NaN).

## Sex-calling strategy
1. **Z-score transformation per gene**
   - For each marker gene, a z-score was computed across samples:
     - `z = (expression − gene_mean) / gene_sd`.
   - Y-linked genes used: DDX3Y, EIF1AY, KDM5D, RPS4Y1, USP9Y, UTY, ZFY.
   - X-linked: XIST (TSIX excluded as all NaN).

2. **Composite Y metrics**
   - **Y_mean_z**: mean z-score across the 7 Y-linked markers per sample.
   - **Y_max_z**: maximum z-score across the 7 Y-linked markers per sample.
   - **Y_high_genes_z1.5**: count of Y-linked markers with z > 1.5 (captures concordant high Y expression).

3. **XIST behavior**
   - XIST non-missing in only 6/49 samples.
   - Among those 6, XIST showed a clear high-expression subset:
     - Median ~6.1, max ~14.7 (log-scale units as given).
     - High-XIST samples: XIST_z > ~1.2.
   - Thresholds:
     - **High XIST:** XIST_z > 0.8.
     - **Moderately high XIST:** XIST_z > 0.5.

4. **Decision rules**
   Sex labels were assigned per sample using the following rules:

   - **Confident male ("very_strong_Y_lowXIST")**
     - Y_mean_z > 1.5, **and**
     - Y_high_genes_z1.5 ≥ 5 (≥5 of 7 Y markers with z > 1.5), **and**
     - XIST_z < 0.5 or XIST missing.

   - **Additional male ("strong_Y_multi_markers_verylow_XIST")**
     - Y_mean_z > 1.0, **and**
     - Y_high_genes_z1.5 ≥ 4, **and**
     - XIST_z < 0.0 or XIST missing.

   - **Confident female ("high_XIST_uniformly_lowY")**
     - XIST_z > 0.8, **and**
     - Y_mean_z < 0.5, **and**
     - Y_max_z < 1.0.

   - **Weaker female ("moderate_XIST_noY")**
     - XIST_z > 0.5, **and**
     - Y_mean_z < 0.8, **and**
     - Y_max_z < 1.5.

   - **Unknown**
     - Any sample not satisfying the male or female rules above, including:
       - Strong or moderate Y **and** strong XIST (conflicting).
       - Low Y with missing XIST (insufficient evidence for female).

5. **Output tables**
   - `project/outputs/tables/sample_sex_calls.tsv`:
     - Columns: `SampleID`, `sex` (male/female/unknown), `Y_mean_z`, `Y_max_z`, `XIST_z`, `Y_high_genes_z1.5`, `decision_reason`.
   - Final user-facing file: `project/outputs/reports/sample_sex_assignments_final.txt`:
     - Each line: `SampleID; sex`.

---

# Results

- Total samples analyzed: **49**.
- Sex assignments:
  - **male:** 3 samples (SampleID 1, 4, 6)
  - **female:** 0 samples
  - **unknown:** 46 samples

## Per-sample assignments (final output format)
The complete assignment file is stored at `project/outputs/reports/sample_sex_assignments_final.txt`. Its contents are:

```
1; male
2; unknown
3; unknown
4; male
5; unknown
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
23; unknown
24; unknown
25; unknown
26; unknown
27; unknown
28; unknown
29; unknown
30; unknown
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
41; unknown
42; unknown
43; unknown
44; unknown
45; unknown
46; unknown
47; unknown
48; unknown
49; unknown
```

Key patterns:
- **Male samples (1, 4, 6):** All seven Y-linked markers strongly elevated (Y_mean_z ≈ 2.9–3.7; all Y markers z > 1.5) and XIST_z < 0, consistent with male expression profiles.
- **Ambiguous high-Y/high-XIST samples (2, 3):** Moderate-to-strong Y (Y_mean_z ≈ 0.93–1.38; three Y markers z > 1.5) and very high XIST (XIST_z > 1.2) → labelled **unknown**.
- **Remaining samples:** Low Y (Y_mean_z < 0.5) and missing XIST for 44 samples → labelled **unknown** because female calls require demonstrable XIST up-regulation.

---

# Caveats & Warnings

- **Missing metadata:** No platform IDs (GPL887/GPL4133) or ovarian/pancreatic labels were available in the workspace; all samples were treated generically with `platform = unknown` and `cancer_type = unknown`.
- **Sparse XIST data:** XIST is non-missing in only 6/49 samples; this prevents confident female calling for most samples and forces many `unknown` labels.
- **Ambiguous high-XIST/high-Y cases:** Two samples show both strong Y and strong XIST, which is biologically unusual (could reflect mosaicism, contamination, or technical artifacts); these were conservatively labelled `unknown`.
- **Dataset scope:** The rules and thresholds were tuned to this specific dataset via z-score distributions; while standard markers were used, thresholds may not directly transfer to other datasets without re-tuning.

---

# Next Steps

- If available, integrate external sample metadata (reported sex, platform, cancer type) to validate and, if necessary, refine the decision thresholds.
- Investigate why XIST is missing in most samples (platform coverage vs preprocessing) and consider re-normalization or re-annotation if raw data are accessible.
- For ambiguous samples with both high Y and high XIST, examine raw data and potential sample swaps or contamination.
- Apply the same marker-based pipeline to other related datasets to assess robustness and adjust cutoffs if consistent discrepancies are observed.

---

# References

- Tukiainen, T. et al. (2017). Landscape of X chromosome inactivation across human tissues. *Nature*. doi:10.1038/nature24265
- Gershoni, M., & Pietrokovski, S. (2017). The landscape of sex-differential transcriptome and its consequent selection in human adults. *BMC Biology*. doi:10.1186/s12915-017-0381-6
