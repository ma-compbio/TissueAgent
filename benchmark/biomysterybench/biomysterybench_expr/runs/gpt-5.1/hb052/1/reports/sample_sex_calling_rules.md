# Sex calling based on XIST and Y marker scores

## Inputs and context
- Sex-marker scores were computed from the unified expression matrix (`expression_all_platforms.tsv`).
- The true microarray platform for all 49 samples is unknown; the same sex-calling rules were applied uniformly to all samples.
- This analysis uses the file `project/outputs/tables/sex_marker_scores_GPL887.tsv` (identical to the GPL4133 version) and the sample index in `project/outputs/tables/sample_index.tsv`.

## Marker distributions
- **Y_score** values form a clear two-group structure:
  - 43 samples have Y_score between approximately 4.87 and 5.51 (median ~5.22).
  - 6 samples have markedly higher Y_score between ~6.58 and 9.34.
- **XIST_score** is only available for 6 samples; these six are exactly the ones with high Y_score. Their XIST_score ranges from ~4.97 to ~14.7.
- Because XIST_score is missing for most samples and never appears high in the absence of high Y_score, it provides limited additional information for this dataset.

## Decision rules
The following simple, threshold-based rules were applied to assign sex labels:

1. **Define high Y-score**
   - The highest Y_score among the low-Y group is 5.51, and the lowest Y_score among the high-Y group is 6.58.
   - The midpoint between these two values is ≈ 6.04, which was rounded to a transparent cutoff:
   - **Y_high_threshold = 6.0**.

2. **Define high XIST-score**
   - XIST_score exists only for the 6 high-Y samples and ranges from ~4.97 to ~14.7, with median ~6.07.
   - For completeness and for possible reuse, a **XIST_high_threshold = 6.0** was defined to indicate relatively high XIST expression.

3. **Sex calling logic** (applied to every sample independently):

   - Let `Y_high = (Y_score ≥ 6.0)` and `XIST_high = (XIST_score ≥ 6.0)` when XIST_score is available.
   - **Male**: if `Y_high` is true (Y_score ≥ 6.0), regardless of XIST_score.
   - **Female**: if `Y_high` is false (Y_score < 6.0) **and** `XIST_high` is true (XIST_score ≥ 6.0).
   - **Unknown**: all remaining cases (including missing XIST_score and low/ambiguous Y_score).

## Handling of missing values and special cases
- **Missing XIST_score**:
  - For 43/49 samples, XIST_score is missing. These samples were **not** called female based on the absence of Y signal alone; instead, they were labeled **unknown** unless Y_score exceeded the male threshold.
  - This conservative approach avoids over-calling female in the absence of positive XIST evidence.
- **High Y_score with or without XIST_score**:
  - All 6 samples with Y_score ≥ 6.0 were called **male**. These are also the only samples with non-missing XIST_score in this dataset.
- **Both markers low or ambiguous**:
  - For samples with Y_score < 6.0 and either low XIST_score (< 6.0) or missing XIST_score, the sex label was set to **unknown**.

## Summary of sex calls
- Using the rules above, the final counts are:
  - **male**: 6 samples
  - **female**: 0 samples
  - **unknown**: 43 samples

## Confidence estimates
- A simple quantitative confidence metric was computed as `Y_distance_from_cutoff = Y_score − 6.0`.
- A qualitative confidence label was assigned as follows:
  - **high**: for samples called male with `Y_distance_from_cutoff ≥ 0.5`.
  - **low**: for all other samples (including all unknowns).
- In this dataset, all 6 male calls have high Y_score well above the cutoff and are labeled as **high-confidence**.

## Uniform treatment of platform
- All samples have platform recorded as `unknown` in the input files.
- No platform-specific behavior was used; the same marker thresholds and logic were applied to all 49 samples.