# Sex Assignment Summary

## Data Overview

We used per-sample sex marker scores from `sex_marker_scores.tsv` (49 samples) with the following relevant columns:

- `Female_score`: z-scored XIST expression (defined for 6 samples, corresponding to samples with XIST measured).
- `Male_score`: mean z-score across Y-linked markers (defined for all 49 samples).
- `XIST_raw`: raw XIST expression (available for the same 6 samples as `Female_score`).
- `Y_markers_mean_raw`: raw mean expression of Y-linked markers (available for all 49 samples).

## Score Distributions and Relationships

- `Male_score` is centered near 0 with most samples between approximately -0.6 and 0, and a small subset with strongly positive scores:
  - Quantiles: min -0.60, 0.10 -0.47, 0.25 -0.40, 0.50 -0.30, 0.75 -0.20, 0.90 1.02, max 3.59.
  - The highly positive tail (>= ~1.0) corresponds to samples with very high raw Y-marker expression (`Y_markers_mean_raw` up to ~10.4), clearly distinct from the rest of the cohort.
- `Y_markers_mean_raw` is similarly compact for most samples, with a few clear high outliers:
  - Quantiles: min 4.99, 0.10 5.12, 0.25 5.21, 0.50 5.39, 0.75 5.52, 0.90 6.98, max 10.36.
  - Samples with `Y_markers_mean_raw` >= ~7 coincide with the high `Male_score` samples.
- `Female_score` is only defined for 6 samples (those with XIST):
  - Range: -0.76 to 1.31, with two high-XIST samples (`Female_score` ~1.25–1.31) and four low-XIST samples (`Female_score` ~-0.75 to -0.37).
  - Among these 6, the two high-XIST samples have moderate `Male_score` (~1.0–1.16) and moderately elevated Y-marker raw expression (~6.95–7.12), while the four low-XIST samples have very high `Male_score` (1.70–3.59) and strongly elevated Y-marker raw expression (~8.6–10.4).

These patterns suggest a small group of strongly Y-positive samples (likely male) and one or two XIST-high samples (likely female) among the XIST-available subset, with the majority of XIST-missing samples clustering near the overall baseline of the distribution.

## Decision Rules for Sex Assignment

We defined explicit, reproducible rules that use both XIST-derived `Female_score` (when available) and Y-marker-derived `Male_score`/`Y_markers_mean_raw`. Each sample is assigned one of {"male", "female", "unknown"}.

### Common Parameters / Thresholds

From the observed distributions, we selected the following thresholds (on the per-sample scores):

- `male_high` = 1.0 (Male_score): threshold for clearly elevated Y-marker z-score.
- `male_very_high` = 2.0 (Male_score): very strong Y-marker evidence (used only in interpretation, not directly in rules).
- `male_low` = -0.45 (Male_score): threshold for distinctly low Y-marker z-score, near the lower decile.
- `female_high` = 0.8 (Female_score): threshold for clearly high XIST.
- `female_low` = -0.6 (Female_score): threshold for clearly low XIST.
- `y_high` = 6.98 (Y_markers_mean_raw): ~90th percentile of raw Y markers, indicating clearly elevated Y expression.
- `y_low` = 5.12 (Y_markers_mean_raw): ~10th percentile of raw Y markers, indicating low Y expression relative to the cohort.

### Rules for Samples with XIST (Female_score not NA; Samples 1–6)

For samples with defined `Female_score` and `XIST_raw`:

1. **Female** (`Assigned_sex = "female"`):
   - Condition: `Female_score >= 0.8` **and** `Male_score < 1.0`.
   - Rationale: high XIST with at most moderate Y-markers.
   - Decision_basis label: `XIST_high_and_Male_not_high`.

2. **Male** (`Assigned_sex = "male"`):
   - Condition: `Female_score <= -0.6` **and** `Male_score >= 1.0`.
   - Rationale: clearly low XIST combined with clearly elevated Y-markers.
   - Decision_basis label: `XIST_low_and_Male_high`.

3. **Unknown** (`Assigned_sex = "unknown"`):
   - Condition: all other XIST-available samples (i.e., those not meeting the female or male criteria above).
   - Rationale: conflicting or intermediate XIST/Y-marker profiles.
   - Decision_basis label: `XIST_available_but_ambiguous`.

### Rules for Samples without XIST (Female_score NA; Samples 7–49)

For samples lacking XIST measurements, we rely on `Male_score` and `Y_markers_mean_raw`:

1. **Male** (`Assigned_sex = "male"`):
   - Condition: `Male_score >= 1.0` **or** `Y_markers_mean_raw >= 6.98`.
   - Rationale: strong Y-marker signal in z-score and/or raw scale, consistent with the clearly Y-positive tail observed in the 6 XIST-available samples.
   - Decision_basis label: `Male_or_Y_high_no_XIST`.

2. **Female** (`Assigned_sex = "female"`):
   - Condition: `Male_score <= -0.45` **and** `Y_markers_mean_raw <= 5.12`.
   - Rationale: both z-scored and raw Y-marker signals are in the distinctly low tail of the distribution, indicating little to no detectable Y expression.
   - Decision_basis label: `Male_low_and_Y_low_no_XIST`.

3. **Unknown** (`Assigned_sex = "unknown"`):
   - Condition: all other no-XIST samples (i.e., not meeting the male or female criteria above).
   - Rationale: intermediate or ambiguous Y-marker levels that do not clearly support a male or female call.
   - Decision_basis label: `No_XIST_ambiguous`.

## Resulting Assignments

Applying the above rules to all 49 samples yields the following overall counts:

- `male`: 3 samples.
- `female`: 5 samples.
- `unknown`: 41 samples.

### Patterns among XIST-Available Samples (1–6)

- Samples with high XIST and moderate Y-markers:
  - One sample (SampleID 3) met the `female` criteria (`Female_score` ~1.25, `Male_score` ~0.98, moderate Y raw), and was called **female**.
  - A second XIST-high sample (SampleID 2, `Female_score` ~1.31, `Male_score` ~1.16, `Y_markers_mean_raw` ~7.12) had both strong XIST and relatively high Y markers; it did **not** satisfy the strict female rule and was conservatively labeled **unknown**.
- Samples with low XIST and strong Y-markers:
  - Three samples (SampleIDs 4–6) had low `Female_score` (~-0.75 to -0.38) and elevated `Male_score` (1.70–3.59) with very high `Y_markers_mean_raw` (8.59–10.36). These were called **male**.
- One sample with intermediate XIST and very high Y (`SampleID 1`, `Female_score` ~-0.37, `Male_score` ~3.59) fell into the low-XIST/high-Y pattern but did not meet the stricter `female_low <= -0.6` cutoff, and was classified as **unknown** to avoid over-calling.

### Patterns among XIST-Missing Samples (7–49)

- **Male calls**: No XIST-missing samples reached the `Male_score >= 1.0` or `Y_markers_mean_raw >= 6.98` thresholds. Therefore, all three male calls come from the XIST-available subset (samples 4–6).
- **Female calls**: Four XIST-missing samples had both low `Male_score` (<= -0.47 to -0.60) and low `Y_markers_mean_raw` (~4.99–5.09), satisfying the female rule and were designated **female**.
- **Unknowns**: The remaining 39 XIST-missing samples had intermediate `Male_score` values (-0.54 to -0.09) and `Y_markers_mean_raw` around the cohort median (~5.21–5.72), without clearly indicating male or female.

## Caveats and Limitations

1. **Limited XIST coverage**: Only 6 of 49 samples have XIST measurements, constraining our ability to learn sex-specific patterns directly from XIST/Y-marker combinations. For the majority of samples, assignments rely solely on Y markers.
2. **Stringent thresholds**: Thresholds were intentionally chosen conservatively (using tails of the observed distributions) to minimize misclassification at the expense of more `unknown` labels. This may under-call sex for borderline cases.
3. **Tumor and platform effects**: Both XIST and Y-linked gene expression can be influenced by tumor purity, copy number aberrations, X-inactivation escape, and technical factors (e.g., platform sensitivity to sex chromosomes). Some biologically male tumors might show low Y expression and be labeled `unknown` or even `female` if Y expression is extremely low.
4. **Small reference for male/female exemplars**: The clear male and female examples are few (3 XIST-available males, 1–2 strong XIST females), so data-driven thresholding is approximate.
5. **Contextual metadata**: We did not incorporate clinical or anatomical metadata (e.g., ovarian vs pancreatic origin). Such information could help validate or adjust assignments (for example, ovarian tumors are expected to predominantly arise in XX individuals), but is not used in these rules.

## Summary

We combined XIST-based `Female_score` (when available) with Y-marker-derived `Male_score` and `Y_markers_mean_raw` to assign sex labels. Clear male calls require both low XIST (if measured) and high Y expression; clear female calls require high XIST and non-elevated Y (for XIST-available samples) or distinctly low Y expression (for XIST-missing samples). All other cases are labeled `unknown`. This framework is explicit and reproducible, and can be refined in future iterations if additional reference samples or external sex annotations become available.