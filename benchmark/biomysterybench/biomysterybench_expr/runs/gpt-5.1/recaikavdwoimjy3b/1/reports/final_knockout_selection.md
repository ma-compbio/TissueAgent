# Knockout-like gene selection

## Data sources

All analyses were based solely on the provided tables:

- `project/outputs/tables/gene_group_statistics.tsv` (group-wise means, variances, log2FC, t-statistics)
- `project/outputs/tables/differential_expression_ranked.tsv` (ranked differential expression summary)
- `project/outputs/tables/expression_matrix.tsv` (raw counts for samples 1–6)

Samples 1–3 were treated as the knockout (KO) group and samples 4–6 as controls.

## Definition of a knockout-like pattern

A gene was required to satisfy **all** of the following stringent criteria:

1. **Strong downregulation in KO (log2 scale)**
   - `log2FC_knockout_over_control` ≤ **-2** (at least 4-fold lower in KO on the log2(count+1) scale).
   - `t_stat_log2_counts_ko_vs_ctrl` ≤ **-10** (very strong evidence of downregulation in KO).

2. **Near-zero expression in all KO samples**
   - `ko_nz` = number of KO samples (1–3) with >0 counts.
   - Required: `ko_nz` = **0** (all three KO samples have zero counts).
   - `knockout_mean` ≤ **0.1** and `knockout_variance` ≤ **0.1** (confirms essentially zero mean and variance on the raw-count scale).

3. **Consistent, appreciable expression in all control samples**
   - `ctrl_nz` = number of control samples (4–6) with >0 counts; required: `ctrl_nz` = **3** (all control samples express the gene).
   - `control_mean` ≥ **5** counts.
   - `ctrl_min` (minimum of samples 4–6) ≥ **2** counts (guards against a single near-zero control sample).

These thresholds were chosen to reflect an ideal gene knockout: complete absence of expression in all KO samples, coupled with clear, consistent expression in all controls, and strong differential-expression statistics.

## Filter progression

Starting from all genes in `gene_group_statistics.tsv` (58721 genes):

1. **Strong downregulation in KO**: log2FC ≤ -2 and t-stat ≤ -10  →  **23** genes.
2. **Near-zero KO expression**: KO all zeros (`ko_nz` = 0) and knockout_mean/variance ≤ 0.1  →  **11** genes.
3. **Consistent control expression**: all controls non-zero (`ctrl_nz` = 3), control_mean ≥ 5, ctrl_min ≥ 2  →  **4** genes.

The final knockout-like candidate set therefore contains **4 genes**.

## Ranking of candidates

For all genes that passed the knockout-like filters, I computed a composite **`knockout_score`** to rank how cleanly they fit the desired pattern:

- Let `neg_log2fc` = -`log2FC_knockout_over_control` (larger means stronger KO downregulation).
- Let `neg_t` = -`t_stat_log2_counts_ko_vs_ctrl` (larger means stronger statistical support for downregulation).
- Let `ctrl_signal` = log2(1 + `control_mean`) (captures overall control expression strength in a smoothly increasing way).

The score is defined as:

```text
knockout_score = neg_log2fc × neg_t × ctrl_signal
```

All surviving candidates have exactly zero KO counts and robust control expression, so this score primarily discriminates genes by the strength of their differential signal and by how highly they are expressed in controls.

The full ranked candidate table is written to:

- `project/outputs/tables/knockout_gene_candidates.tsv`

## Final knockout gene selection

Based on the ranking, the **primary knockout-like gene** is:

- **ENSG00000152804.10**  
  - KO expression: mean 0.0, variance 0.0, all KO samples have zero counts (`ko_nz` = 0).  
  - Control expression: mean 28.33 counts, variance 0.33; all three controls are expressed (`ctrl_nz` = 3) with a minimum control count of 28.  
  - Differential signal: log2FC_knockout_over_control = -5.85, t_stat_log2_counts_ko_vs_ctrl = -299.0.  
  - This yields the highest knockout_score among all candidates, driven by an extremely strong negative t-statistic and substantial control expression while KO samples remain completely silent.

The remaining genes that passed all filters are retained as **secondary candidates**:

- ENSG00000178498.15: KO samples all zero, control mean 51.00, min control count 26, log2FC -6.69, t-stat -13.2.
- ENSG00000230872.1: KO samples all zero, control mean 5.67, min control count 5, log2FC -3.62, t-stat -36.9.
- ENSG00000100181.22: KO samples all zero, control mean 5.67, min control count 4, log2FC -3.62, t-stat -10.7.

These secondary genes also show a textbook knockout-like pattern (zero KO counts and consistent, appreciable control expression), but their knockout_scores are lower because either the differential t-statistic is less extreme or the control expression level is more modest compared with the primary candidate.

## Output files

The following outputs were generated:

1. **Knockout-like candidates (all passing genes)**  
   `project/outputs/tables/knockout_gene_candidates.tsv`

2. **Final knockout gene(s) with key metrics**  
   `project/outputs/tables/final_knockout_genes.tsv`

3. **This concise report**  
   `project/outputs/reports/final_knockout_selection.md`
