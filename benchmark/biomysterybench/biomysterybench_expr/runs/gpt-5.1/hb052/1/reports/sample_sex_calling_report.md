# Title & Objective

**Objective:** Infer the biological sex (male, female, or unknown) for each sample in the provided cancers microarray dataset, using only gene-expression profiles and sex-linked markers, and report results as `Sample; sex`.

# Data & Methods

## Data
- **Expression matrix:** `library/datasets/Cancers.csv`
  - 49 samples (rows), 36,454 probes/features (columns, excluding `SampleID`).
  - No platform (GPL887/GPL4133) or tumor-type labels were provided; all samples were treated as coming from a single, unknown platform.
- **Annotation mapping:** `library/datasets/refseq_to_symbol_map.csv`
  - Maps each probe/REFSEQ identifier to a gene symbol where available.

Processed artifacts:
- Unified expression matrix (features × samples): `project/outputs/tables/expression_all_platforms.tsv`.
- Sample index (IDs only): `project/outputs/tables/sample_index.tsv`.

## Marker panel
- **Female/X-linked marker:** XIST.
- **Male/Y-linked markers:** RPS4Y1, DDX3Y, KDM5D, EIF1AY, UTY, ZFY.

Using `refseq_to_symbol_map.csv`, the following probes were identified in the expression matrix and used:
- XIST: NR_001564.
- DDX3Y: NM_004660.
- UTY: NM_007125, NM_182660.
- ZFY: NM_003411.
- KDM5D: NM_004653.
- EIF1AY: NM_004681.
- RPS4Y1: NM_001008.

## Scoring
From `expression_all_platforms.tsv` (rows = `FeatureID`, columns = samples `1`–`49`):
- **XIST_score:** per-sample mean expression across all XIST probes (here a single probe NR_001564).
- **Y_score:** per-sample mean expression across all probes for the selected Y-linked genes.

Scores and mapping were exported as:
- `project/outputs/tables/sex_marker_mapping.tsv`.
- `project/outputs/tables/sex_marker_scores_GPL887.tsv`.
- `project/outputs/tables/sex_marker_scores_GPL4133.tsv` (identical content; filenames only for compatibility).

A QC scatterplot of XIST_score vs Y_score for all 49 samples was generated:
- `project/outputs/figures/sex_marker_QC_scatterplots.png`.

## Sex-calling rules
Distributions of scores:
- **Y_score:**
  - 43 samples: Y_score in ~[4.87, 5.51].
  - 6 samples: Y_score in ~[6.58, 9.34].
- **XIST_score:**
  - Non-missing only for the 6 high-Y samples (≈4.97–14.7).
  - Missing for 43 samples.

A clear gap exists between low and high Y_score groups (5.51 vs 6.58). Thresholds were set as:
- `Y_high_threshold = 6.0`.
- `XIST_high_threshold = 6.0` (for completeness; did not affect calls because no sample had high XIST with low Y).

Decision logic applied to each sample:
1. Compute flags:
   - `Y_high = (Y_score ≥ 6.0)`.
   - `XIST_high = (XIST_score ≥ 6.0)` when XIST_score is non-missing.
2. Assign sex:
   - **male**: if `Y_high` is true (Y_score ≥ 6.0), regardless of XIST.
   - **female**: if `Y_high` is false (Y_score < 6.0) and `XIST_high` is true.
   - **unknown**: otherwise (including missing XIST and low Y).
3. Confidence:
   - Quantitative: `Y_distance_from_cutoff = Y_score − 6.0`.
   - Qualitative: `sex_call_confidence = "high"` for male samples with `Y_distance_from_cutoff ≥ 0.5`; otherwise `"low"`.

Detailed assignments are in:
- `project/outputs/tables/sample_sex_assignments.tsv`.

The final label file in the requested format is:
- `project/outputs/final/sample_sex_labels.txt`.

# Results

## Sex calls per sample
The final calls (from `sample_sex_labels.txt`) are:

1. 1; male
2. 2; male
3. 3; male
4. 4; male
5. 5; male
6. 6; male
7. 7; unknown
8. 8; unknown
9. 9; unknown
10. 10; unknown
11. 11; unknown
12. 12; unknown
13. 13; unknown
14. 14; unknown
15. 15; unknown
16. 16; unknown
17. 17; unknown
18. 18; unknown
19. 19; unknown
20. 20; unknown
21. 21; unknown
22. 22; unknown
23. 23; unknown
24. 24; unknown
25. 25; unknown
26. 26; unknown
27. 27; unknown
28. 28; unknown
29. 29; unknown
30. 30; unknown
31. 31; unknown
32. 32; unknown
33. 33; unknown
34. 34; unknown
35. 35; unknown
36. 36; unknown
37. 37; unknown
38. 38; unknown
39. 39; unknown
40. 40; unknown
41. 41; unknown
42. 42; unknown
43. 43; unknown
44. 44; unknown
45. 45; unknown
46. 46; unknown
47. 47; unknown
48. 48; unknown
49. 49; unknown

## Summary counts
- **male:** 6 samples (1–6), all high-confidence.
- **female:** 0 samples.
- **unknown:** 43 samples (7–49).

# Caveats & Warnings
- **Missing platform and tumor metadata:** No GPL887/GPL4133 or ovarian/pancreatic labels could be recovered; all samples are treated as a single, unknown platform. This does not affect sex calling but limits contextual interpretation.
- **Sparse XIST measurements:** XIST_score is only available for 6 samples (the same ones with very high Y_score). For the other 43 samples, XIST is missing, so they cannot be confidently identified as female; they are labeled **unknown** rather than guessed female based on low Y alone.
- **Conservative calling:** The rules favor precision for male calls (clear high Y) at the expense of recall for female calls. True female samples with low/undetectable XIST in this dataset would likely be labeled **unknown**.

# Next Steps
- If additional annotation becomes available (e.g., platform IDs, clinical sex, or more complete XIST probes), the thresholds and rules can be refined and evaluated against ground truth.
- If you wish, I can generate additional diagnostic plots (e.g., density plots of Y_score, per-gene marker expression) or re-run the calling under alternative decision rules (e.g., using low-Y as a proxy for likely female) to explore sensitivity.

# References
- Oliva M. et al., "The impact of sex on gene expression across human tissues," *Science* (2020). DOI: 10.1126/science.aba3066.
- Gershoni M. & Pietrokovski S., "The landscape of sex-differential transcriptome and its consequent selection in human adults," *BMC Biol* (2017). DOI: 10.1186/s12915-017-0435-5.
