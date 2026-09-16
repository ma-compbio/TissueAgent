# Title & Objective

**Objective:** Identify, from the provided normalized RNA-sequencing time-series dataset, the single gene that exhibits the strongest circadian rhythmicity with a fixed 24-hour period, and report its gene name exactly as it appears in the dataset.

# Data & Methods

**Data:**
- Input file: `library/datasets/RHYTHMIC.txt`
- Structure: one row per gene (e.g., `GENE1`–`GENE100`), columns for gene ID and 12 time points labeled as Zeitgeber times (e.g., `ZT0`, `ZT4`, ..., `ZT44`). Values are normalized expression measurements.

**Preprocessing & Tidy Data:**
- Parsed `RHYTHMIC.txt` into:
  - `project/outputs/tables/rhythmic_wide_matrix.tsv`: wide matrix with rows as genes and columns as time points; first column `gene` contains gene IDs exactly as in the input.
  - `project/outputs/tables/rhythmic_long_table.tsv`: long-format table with columns `gene`, `time` (e.g., `ZT0`), and `expression`.
  - `project/outputs/tables/rhythmic_timepoints_metadata.tsv`: mapping of time labels to numeric Zeitgeber times with columns:
    - `time` (e.g., `ZT0`, `ZT4`, ..., `ZT44`)
    - `time_numeric` (e.g., 0, 4, ..., 44), extracted as hours from the label.

**Rhythmicity Modeling (24-hour cosinor):**
- For each gene, a fixed-period 24-hour cosinor regression model was fit to expression over time using the numeric Zeitgeber times:
  
  \[
  \text{expression}(t) = \text{mesor} + A \cos\left(\frac{2\pi t}{24}\right) + B \sin\left(\frac{2\pi t}{24}\right) + \varepsilon,
  \]
  
  where:
  - *mesor* is the mean level (intercept),
  - *A* and *B* are cosine and sine coefficients,
  - *t* is Zeitgeber time in hours, from `time_numeric`,
  - the period is fixed at 24 h for all genes.

- Model fitting used ordinary least squares (OLS) for each gene, based on the long-format expression data joined with the time metadata.

**Per-gene metrics computed:**
- `mesor`: intercept from the regression.
- `amplitude`: \(\sqrt{A^2 + B^2}\), representing oscillation magnitude.
- `phase`: phase of the rhythm converted to hours:
  - `phase_radians = atan2(B, A)`
  - `phase_hours = (phase_radians / (2π)) * 24`, wrapped into [0, 24).
- `p_value`: p-value from a joint F-test of the null hypothesis \(A = 0, B = 0\) (i.e., no 24 h rhythmic component) versus the full cosinor model.
- `r_squared`: coefficient of determination from the model fit.

All metrics were collected in:
- `project/outputs/tables/gene_rhythmicity_scores_24h.tsv` with columns:
  - `gene`, `mesor`, `amplitude`, `phase`, `p_value`, `r_squared`, `phase_unit` (set to `hours`).

**Ranking and Selection of the Top Circadian Gene:**
- Genes were ranked deterministically using the following criteria:
  1. Primary: `p_value` ascending (smallest p-value = strongest evidence of 24 h rhythm).
  2. Tie-breaker 1: `r_squared` descending (higher goodness-of-fit preferred).
  3. Tie-breaker 2: `gene` ID lexicographically ascending (for any remaining ties).

- The top-ranked gene and its metrics were written to:
  - `project/outputs/tables/top_circadian_gene.tsv`
- A brief text summary was written to:
  - `project/outputs/reports/circadian_gene_call.txt`

A diagnostic time-course plot for the most rhythmic gene, showing observed expression and the fitted 24 h curve, was also generated:
- `project/outputs/figures/example_timecourse_top_rhythmic_gene.png`

# Results

- **Most circadian (24 h rhythmic) gene:** `GENE15`

From `top_circadian_gene.tsv`, the selected gene and its key statistics are:

- `gene`: **GENE15**
- `mesor`: -0.31237
- `amplitude`: 2.38784
- `phase`: 12.1091 hours
- `p_value`: 0.000327172
- `r_squared`: 0.831924
- `phase_unit`: hours

Interpretation:
- `GENE15` shows a strong 24-hour oscillatory component with a large amplitude and high r_squared, and a highly significant p_value for the cosinor terms. The phase of ~12.1 h indicates its peak within the circadian cycle under the assumed Zeitgeber time reference.

# Caveats & Warnings

- **Fixed 24 h period only:** The analysis tests only a 24-hour period; genes with non-24 h rhythms or complex multi-harmonic patterns are not evaluated for alternative periods.
- **Single dataset context:** Results are specific to this normalized dataset and its sampling scheme (12 time points from ZT0 to ZT44). No biological or technical replicates or additional metadata (e.g., tissues, conditions) were available, so uncertainty due to variability cannot be explicitly modeled.
- **Model assumptions:** The cosinor model assumes a sinusoidal shape and homoscedastic errors. Deviations from these assumptions could affect p_values and r_squared but are standard for circadian screening.

# Next Steps

- Inspect `gene_rhythmicity_scores_24h.tsv` to review the full ranked list of genes and explore other highly rhythmic candidates.
- Examine `example_timecourse_top_rhythmic_gene.png` to visually confirm that `GENE15` follows a clear 24 h pattern.
- If additional data become available (e.g., replicates, multiple conditions), extend the modeling to mixed-effects cosinor models or compare rhythms across conditions.

# References

- Cornelissen G. Cosinor-based rhythmometry. *Theoretical Biology and Medical Modelling*. 2014;11:16. doi:10.1186/1742-4682-11-16.
