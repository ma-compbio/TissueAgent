# Circadian Rhythmicity Analysis Summary

## Title & Objective
Identify the single gene in the provided normalized RNA-sequencing time-series dataset that exhibits the strongest evidence of ~24-hour circadian rhythmicity, and report its name exactly as in the dataset.

## Data & Methods

### Data
- Source: `library/datasets/RHYTHMIC.txt`.
- Structure: 100 genes × 12 timepoints.
- Columns:
  - `GENE`: gene identifiers (e.g., `GENE15`).
  - `ZT0`, `ZT4`, ..., `ZT44`: normalized expression values at Zeitgeber times 0–44 hours in 4 h increments.

### Preprocessing & Time Axis
- Constructed a time-ordered expression matrix (`expression_matrix_time_ordered.tsv`):
  - Rows: 100 genes.
  - Columns: 12 timepoints ordered as ZT0, ZT4, ..., ZT44.
- Parsed timepoints from column names into numeric hours (`timepoints_assigned.tsv`):
  - `sample_id`: `ZT0` … `ZT44`.
  - `time`: 0, 4, …, 44 (hours).

### Rhythmicity Modeling (Fixed 24 h Period)
For each gene, we quantified 24 h rhythmicity using a sinusoidal regression model:

\[
\text{expression}(t) = \beta_0 + \beta_1 \sin(2\pi t/24) + \beta_2 \cos(2\pi t/24) + \varepsilon.
\]

- Fitting: ordinary least squares (OLS) for each gene separately.
- Hypothesis test: F-test comparing the full model (intercept + sin + cos) vs. a reduced intercept-only model, testing
  - H0: \(\beta_1 = \beta_2 = 0\) (no 24 h rhythm).
- Derived metrics per gene (saved in `gene_rhythmicity_scores.tsv`):
  - `F_stat`: F-statistic for the two sinusoidal terms.
  - `p_value`: F-test p-value for H0.
  - `amplitude`: \(\sqrt{\beta_1^2 + \beta_2^2}\).
  - `phase_peak_time_h`: estimated peak time in hours, wrapped to [0, 24).
  - `neg_log10_p`: -log10(`p_value`), used as a rhythmicity score (higher = more rhythmic).

Diagnostic plots:
- `top_rhythmic_genes_heatmap.png`: expression heatmap of the top 20 genes by `neg_log10_p` across time.
- `example_periodic_fit_top_gene.png`: observed expression and fitted 24 h sinusoid for a strongly rhythmic gene.

### Gene Selection Strategy
- Primary ranking metric: ascending `p_value` (strongest evidence for 24 h rhythm).
- Tie-breaker (not needed here but defined): descending `amplitude` (larger oscillation preferred).
- The top-ranked gene and its metrics were collected into `top_circadian_gene.tsv`.

## Results

- The gene with the strongest evidence for ~24 h circadian rhythmicity is:
  - **GENE15**

Key rhythmicity metrics for GENE15:
- `F_stat`: 22.2736
- `p_value`: 3.27 × 10⁻⁴
- `neg_log10_p`: 3.485
- `amplitude`: 2.388
- `phase_peak_time_h`: 12.11 h (peak around ZT12; trough approximately 12 h later, near ZT0/ZT24).

Visual inspection (from `top_circadian_gene_GENE15_diagnostics.png`) shows:
- A clear oscillatory pattern over the 0–44 h window with a prominent peak near 12 h and a trough near the beginning/end of the cycle, consistent with a ~24 h rhythm.
- The fitted 24 h sinusoidal curve closely tracks the observed time-course for GENE15.

## Caveats & Warnings
- **No replicates:** Each gene–timepoint pair has a single measurement; within-timepoint variance cannot be estimated, so p-values should be interpreted as approximate.
- **Unknown normalization:** The dataset contains normalized expression values, but the exact normalization pipeline is not documented. Results reflect relative, not absolute, expression.
- **Fixed 24 h assumption:** Rhythmicity was evaluated only at a 24 h period; genes with strong rhythms at other periods (e.g., 12 h) are not specifically assessed.

## Next Steps
- Validate GENE15’s circadian behavior in independent datasets or with experimental time-course assays.
- Extend analysis to test a range of possible periods (e.g., 20–28 h) and include multiple-testing correction if formal significance thresholds are required.
- Incorporate biological context (e.g., gene annotations, pathways) to interpret GENE15’s role in circadian regulation.

## References
- Hughes ME, Hogenesch JB, Kornacker K. JTK_CYCLE: An efficient nonparametric algorithm for detecting rhythmic components in genome-scale data sets. *J Biol Rhythms.* 2010;25(5):372–380. doi:10.1177/0748730410379711
- Zielinski T, Moore AM, Troup E, Halliday KJ, Millar AJ. Strengths and limitations of period estimation methods for circadian data. *PLoS One.* 2014;9(5):e96462. doi:10.1371/journal.pone.0096462
