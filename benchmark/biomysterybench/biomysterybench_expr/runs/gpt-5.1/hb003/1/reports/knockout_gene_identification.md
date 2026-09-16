# Knockout Gene Identification

## Data
- Raw counts: `library/datasets/raw_counts.tsv` (genes × 5 samples).
- Sample groups: `project/outputs/tables/sample_group_assignments.tsv` (3 controls, 2 inferred knockouts).

## Methods (summary)
- Computed library-size–normalized counts per million (CPM) per gene and sample.
- Transformed CPM to log2(CPM + 1) and calculated, for each gene:
  - Mean logCPM in controls and in KO-inferred samples.
  - Log2 fold-change (KO vs control).
- Used a Mann–Whitney U test on logCPM values (2 KO vs 3 controls) to obtain a p-value per gene,
  with Benjamini–Hochberg FDR correction (q-values).
- Prioritized genes with:
  - Zero total raw counts across KO-inferred samples, and
  - Substantial expression in controls (high total control counts), and
  - Large negative log2 fold-change.

## Results
The top candidate gene exhibiting complete loss of expression in KO-inferred samples while being clearly expressed in controls is:

- **Called knockout gene:** `LOC105374110`
- Gene ID: `105374110`
- Mean control logCPM: 0.657
- Mean KO logCPM: 0.000
- Log2 fold-change (KO vs control): -0.657
- Total control counts: 45
- Total KO counts: 0
- p-value: 0.333
- q-value: 1

Based on these criteria, **LOC105374110** is the most plausible knocked-out gene in the experimental samples.
