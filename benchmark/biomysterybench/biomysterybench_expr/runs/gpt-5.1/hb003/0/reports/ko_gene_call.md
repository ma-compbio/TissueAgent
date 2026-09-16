# Final Knocked-Out Gene Call

**Final KO gene:** LOC105374110 (GeneID 105374110)

## Evidence supporting KO call

Using the ranked KO candidate list and raw per-sample counts, LOC105374110 was selected as the most consistent with a true knockout pattern.

### Per-group summary statistics (raw counts)

- **Control group (Control_1, Control_2, Control_3)**
  - Mean: 15.0 counts
  - Median: 22.0 counts
  - Zero fraction: 0.33 (1/3 samples with zero counts)
- **KO group (KO_1, KO2)**
  - Mean: 0.0 counts
  - Median: 0.0 counts
  - Zero fraction: 1.0 (2/2 samples with zero counts)

These values match the summary statistics in the ranked candidate table and were independently recomputed from the raw count matrix.

### Per-sample expression pattern

For LOC105374110, the raw counts by sample are:

- Control_1: 23
- Control_2: 0
- Control_3: 22
- KO_1: 0
- KO2: 0

On the log2(count+1) scale used for visualization:

- Control samples show high expression in 2/3 replicates and a clear non-zero signal overall.
- KO samples show complete loss of detectable expression (both samples at zero counts).

The accompanying barplot (`figures/final_ko_gene_expression_by_sample.png`) shows strong separation between control and KO groups, with KO samples clustered at the baseline while control samples reach substantially higher log2(count+1) values.

### Comparison to other top candidates

Other high-ranking candidates inspected:

1. **GSX2 (GeneID 170825)**
   - Control mean/median (raw): 17.3 / 19
   - KO mean/median (raw): 3.5 / 3.5
   - KO zero fraction: 0.5
   - Interpretation: Expression is clearly reduced in KO but not abolished; one KO sample retains appreciable expression, making this more consistent with a partial knockdown or incomplete KO rather than a true knockout.

2. **LINC01638 (GeneID 105372978)**
   - Control mean/median (raw): 12.0 / 10
   - KO mean/median (raw): 2.0 / 2
   - KO zero fraction: 0.5
   - Interpretation: Similar to GSX2, KO samples retain non-zero expression, again suggesting downregulation rather than complete loss.

In contrast, **LOC105374110** shows **complete loss of expression in all KO samples** with relatively robust expression in controls, matching the expected pattern for the directly targeted knockout gene.

## Caveats

- One control sample (Control_2) shows zero counts for LOC105374110, increasing the control zero fraction to 0.33. This may reflect biological variability or limited sequencing depth for that sample. However, the remaining two controls show strong expression, and the KO group exhibits a clean, complete loss.
- GSX2 and LINC01638 remain plausible downstream or co-regulated targets affected by the perturbation, but their residual expression in KO samples is inconsistent with them being the primary, directly knocked-out gene.

## Conclusion

Based on per-group statistics, per-sample raw counts, and visual inspection of expression patterns, **LOC105374110 (GeneID 105374110)** is the best-supported call for the knocked-out gene in this dataset.