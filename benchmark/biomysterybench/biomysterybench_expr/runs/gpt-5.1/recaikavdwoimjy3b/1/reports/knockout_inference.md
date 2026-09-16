# Knockout Inference from RNA-seq Counts (Samples 1–6)

## Title & Objective

**Objective:** Use only the provided RNA-seq count matrix (no labels or metadata) to infer which gene(s) were knocked out in samples **1–3** relative to samples **4–6**.

## Data & Methods

### Data
- Source: `library/datasets/anonyomized_rnaseq_count.tsv.gz`.
- Structure: 58,721 genes (rows) × 6 samples (columns) of raw RNA-seq counts.
- Harmonized to `project/outputs/tables/expression_matrix.tsv` with:
  - First column: `GeneID` (Ensembl-style identifiers, e.g. `ENSG00000152804.10`).
  - Columns `1`–`6`: samples 1–6.

Samples were assigned to groups by index:
- Knockout (KO) group: **samples 1,2,3**.
- Control group: **samples 4,5,6**.

### Processing and statistics
1. **Group-wise summaries** (raw counts)
   - For each gene:
     - `knockout_mean`, `knockout_variance` from samples 1–3.
     - `control_mean`, `control_variance` from samples 4–6.

2. **Fold-change and log2 fold-change (KO vs control)**
   - Pseudocount 0.5 to stabilize ratios:
     - `fold_change_knockout_over_control = (KO_mean + 0.5) / (Ctrl_mean + 0.5)`.
     - `log2FC_knockout_over_control = log2(fold_change_knockout_over_control)`.

3. **T-like statistic on log scale**
   - Transformed counts: `log2(count + 1)`.
   - For each gene, computed KO and control means/variances on this scale, then a Welch-style statistic:
     - `t_stat_log2_counts_ko_vs_ctrl = (KO_log_mean − Ctrl_log_mean) / SE`,
       with `SE = sqrt(ko_log_var/3 + ctrl_log_var/3)`.
   - Used only for **ranking**, not formal inference.

4. **Differential-expression ranking**
   - All genes were ranked by `log2FC_knockout_over_control` (ascending).
   - Most negative values (strongly down in KO vs control) appear at the top of
     `differential_expression_ranked.tsv`.

5. **Knockout-like pattern detection**
   - From `expression_matrix.tsv`, additional per-gene metrics:
     - `ko_nz`: number of KO samples (1–3) with count > 0.
     - `ctrl_nz`: number of control samples (4–6) with count > 0.
     - `ko_max`: max count in KO samples.
     - `ctrl_min`: min count in control samples.
     - `ko_sum`, `ctrl_sum`: sums across KO and control samples.
   - These were joined with group statistics and DE metrics.

### Knockout-like criteria
A gene was required to satisfy **all** of the following stringent criteria to be considered a knockout-like candidate:

1. **Strong downregulation in KO (log scale)**
   - `log2FC_knockout_over_control ≤ -2`  (≥4-fold lower in KO).
   - `t_stat_log2_counts_ko_vs_ctrl ≤ -10` (very strong negative effect).

2. **Near-complete absence in KO samples**
   - `ko_nz = 0` (all three KO samples have exactly 0 counts).
   - `knockout_mean ≤ 0.1` and `knockout_variance ≤ 0.1`.

3. **Consistent, appreciable expression in controls**
   - `ctrl_nz = 3` (all control samples express the gene).
   - `control_mean ≥ 5` counts.
   - `ctrl_min ≥ 2` counts.

### Candidate ranking
- Starting from 58,721 genes:
  - Filter 1 (log2FC ≤ -2, t-stat ≤ -10): **23 genes**.
  - Filter 2 (KO all zeros, KO mean/var ≤ 0.1): **11 genes**.
  - Filter 3 (all controls non-zero, control_mean ≥ 5, ctrl_min ≥ 2): **4 genes**.

- For the 4 surviving candidates, a composite **knockout_score** was defined:
  - `neg_log2fc = -log2FC_knockout_over_control`.
  - `neg_t = -t_stat_log2_counts_ko_vs_ctrl`.
  - `ctrl_signal = log2(1 + control_mean)`.
  - `knockout_score = neg_log2fc × neg_t × ctrl_signal`.
- Candidates were ranked by descending `knockout_score`.

## Results

### Key quantitative findings
Among all 58,721 genes, **4 genes** showed a textbook knockout-like pattern under the criteria above. Their core metrics are summarized below (means/variances on raw counts):

1. **ENSG00000152804.10** (primary candidate)
   - KO counts (samples 1–3): `0, 0, 0`  
     - `knockout_mean = 0.0`, `knockout_variance = 0.0`, `ko_nz = 0`.
   - Control counts (samples 4–6): `28, 29, 28`  
     - `control_mean ≈ 28.33`, `control_variance ≈ 0.33`, `ctrl_nz = 3`, `ctrl_min = 28`.
   - Differential metrics:
     - `log2FC_knockout_over_control ≈ -5.85`.
     - `t_stat_log2_counts_ko_vs_ctrl ≈ -298.98`.
     - Highest `knockout_score` among all candidates.

2. **ENSG00000178498.15** (secondary)
   - KO counts: all zeros; `knockout_mean = 0.0`, `knockout_variance = 0.0`, `ko_nz = 0`.
   - Control counts: non-zero in all samples, `control_mean = 51.0`, `ctrl_min = 26`.
   - `log2FC ≈ -6.69`, `t_stat ≈ -13.15`.

3. **ENSG00000230872.1** (secondary)
   - KO counts: all zeros; `knockout_mean = 0.0`, `knockout_variance = 0.0`, `ko_nz = 0`.
   - Control counts: `control_mean ≈ 5.67`, `ctrl_min = 5`.
   - `log2FC ≈ -3.62`, `t_stat ≈ -36.87`.

4. **ENSG00000100181.22** (secondary)
   - KO counts: all zeros; `knockout_mean = 0.0`, `knockout_variance = 0.0`, `ko_nz = 0`.
   - Control counts: `control_mean ≈ 5.67`, `ctrl_min = 4`.
   - `log2FC ≈ -3.62`, `t_stat ≈ -10.74`.

All four genes exhibit:
- Complete absence of expression in KO samples (1–3).
- Consistent, appreciable expression in all control samples (4–6).
- Strong negative log2 fold-changes and t-statistics.

Among them, **ENSG00000152804.10** stands out due to:
- Perfect KO silence (0 counts across 1–3) and very tight, moderate-to-high expression in all controls.
- Extremely large negative t-statistic (≈ -299), reflecting highly consistent downregulation across replicates.
- The highest composite knockout_score, indicating the strongest and cleanest knockout-like signal.

## Caveats & Warnings
- Only **expression data** were available; no biological annotation or prior knowledge was used. The selected gene is identified by its **Ensembl-style GeneID** (`ENSG00000152804.10`), which may need mapping to an official HGNC symbol externally.
- Statistical testing used a simple Welch-style t-like statistic on log2(count+1) without formal p-value or multiple-testing correction; metrics were used purely for **ranking**.
- Sample size is small (n=3 per group), so variance estimates are noisy; this is mitigated here by focusing on genes with complete absence in KO and strong presence in all controls.

## Next Steps
- Map the Ensembl identifier **ENSG00000152804.10** to its official gene symbol using a genome annotation resource (e.g., Ensembl, GENCODE, or biomaRt).
- Optionally inspect the broader set of strongly downregulated genes (e.g., the top 50 in `differential_expression_ranked.tsv`) to understand pathway-level effects of the knockout.
- If additional datasets or replicates become available, validate that **ENSG00000152804.10** consistently shows this knockout-like pattern across experiments.

## References
- RNA-seq DE-style transformation and statistics concepts are broadly aligned with:
  - Love MI et al. (2014). *Moderated estimation of fold change and dispersion for RNA-seq data with DESeq2.* Genome Biol. 15(12):550. doi:10.1186/s13059-014-0550-8 (for conceptual background only; not directly applied here).
