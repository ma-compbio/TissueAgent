# Title & Objective

**Objective:** Use the provided normalized RNA-sequencing time-series dataset (RHYTHMIC.txt) to identify the gene that exhibits the clearest 24-hour circadian rhythmicity, and report its gene name exactly as it appears in the dataset.

# Data & Methods

## Data
- Source: `library/datasets/RHYTHMIC.txt`.
- Structure: 100 genes × 12 timepoints.
- Orientation:
  - Rows: genes (IDs like `GENE1`, `GENE2`, …).
  - Columns: Zeitgeber time (ZT) points from **ZT0** to **ZT44** in 4-hour increments.
- Timepoints:
  - ZT labels (ordered): ZT0, ZT4, ZT8, ZT12, ZT16, ZT20, ZT24, ZT28, ZT32, ZT36, ZT40, ZT44.
  - Numeric hours: 0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44.
- Expression values:
  - Range: approximately **-3.50** to **3.58**.
  - Mean: ~**0.18**.
  - No missing values detected.
  - Values appear to be normalized/log-transformed.

## Methods

1. **Matrix preparation**
   - Parsed `RHYTHMIC.txt` into a gene-by-time matrix.
   - Constructed a numeric time vector `t` (in hours) aligned with the ordered ZT columns: [0, 4, 8, …, 44].

2. **24-hour rhythmicity modeling (cosinor regression)**
   - For each gene, fit a fixed-period (24 h) cosinor model:
     - \( y(t) = M + \beta_{\cos} \cos(\omega t) + \beta_{\sin} \sin(\omega t) + \varepsilon \)
     - Where \( \omega = 2\pi/24 \) hours⁻¹, \( y(t) \) is expression at time \( t \).
   - Estimated, for each gene:
     - **Amplitude**: \( A = \sqrt{\beta_{\cos}^2 + \beta_{\sin}^2} \).
     - **Phase (acrophase)** in hours:
       - Used mapping \( \beta_{\cos} = A \cos\varphi, \ \beta_{\sin} = -A \sin\varphi \).
       - Computed \( \varphi = \operatorname{atan2}(-\beta_{\sin}, \beta_{\cos}) \), normalized to [0, 2π).
       - Converted to hours: `phase_hours = φ * 24 / (2π)`.
   - **Significance testing**:
     - F-test of rhythmicity vs. flat expression:
       - Null model: intercept only (no cosine/sine terms).
       - Full model: intercept + cos(ωt) + sin(ωt).
       - p-value obtained from F-statistic for the joint hypothesis \( \beta_{\cos} = \beta_{\sin} = 0 \).

3. **Multiple testing correction and ranking**
   - Applied Benjamini–Hochberg FDR correction across all 100 genes to obtain **p_adj**.
   - Ranked genes by:
     1. **p_adj** (ascending: smallest is strongest evidence of rhythmicity).
     2. **Amplitude** (descending) to break ties.
   - Assigned `rank = 1` to the best 24-hour rhythmic gene.

4. **Outputs generated**
   - `project/outputs/tables/gene_rhythmicity_scores.tsv`:
     - Columns: `gene_id`, `amplitude`, `phase_hours`, `p_value`, `p_adj`, `rank`.
   - `project/outputs/reports/top_circadian_gene.txt`:
     - Human-readable summary of the top-ranked circadian gene.

# Results

- The fixed-period 24 h cosinor analysis across all 100 genes identified **GENE15** as the **top circadian candidate**.
- Key quantitative metrics for **GENE15** (from `gene_rhythmicity_scores.tsv`):
  - **Rank:** 1 (best 24 h rhythmicity in the dataset).
  - **Amplitude:** ~**2.388**.
  - **Phase (acrophase):** ~**11.89 hours**.
  - **Raw p-value:** ~**3.27 × 10⁻⁴**.
  - **Adjusted p-value (FDR):** ~**0.0327**.
- Interpretation:
  - Among all genes, **GENE15** shows the strongest evidence for a 24-hour oscillation in expression over the 0–44 h timecourse.
  - Its phase (~12 h) indicates a peak around the middle of the circadian cycle sampled here (near ZT12).

# Caveats & Warnings

- **Single-model choice (cosinor):**
  - A standard 24 h cosinor model (single sinusoid) was used. Genes with more complex or non-sinusoidal rhythmic patterns might be underrepresented by this model.
- **Fixed period at 24 h:**
  - The analysis specifically tested for a 24-hour period. Genes with strong rhythms at different periods (e.g., ultradian or longer than 24 h) would not be detected as such here.
- **Moderate sample size:**
  - Only 12 timepoints over 44 h were available, which is typical but not dense; very subtle rhythms may have limited power for detection.

# Next Steps

- If desired, visually inspect the timecourse of **GENE15** (expression vs. time) to confirm the fit and intuitive oscillatory behavior.
- Extend the analysis to search for multi-harmonic or alternative-period rhythms (e.g., scan 20–28 h) to check robustness.
- Compare **GENE15** with other top-ranked genes (e.g., those with low `p_adj` and relatively high amplitudes) to identify a broader set of putative circadian genes.

# References

- Refinetti R, Lissen GC, Halberg F. **Procedures for numerical analysis of circadian rhythms.** Biol Rhythm Res. 2007;38(4):275–325. doi:10.1080/09291010600903692
- Cornelissen G. **Cosinor-based rhythmometry.** Theor Biol Med Model. 2014;11:16. doi:10.1186/1742-4682-11-16
