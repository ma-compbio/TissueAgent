# Sex Inference QC Report

## Marker genes used

Y-linked markers (log1p-transformed): RPS4Y1, DDX3Y, EIF1AY, KDM5D, UTY, ZFY, USP9Y
X-inactivation marker: XIST

All listed marker genes were detected in the expression matrix. Expression values were log1p-transformed prior to summarization.

## Thresholds and decision rule

- mean_Y_expression threshold (th_y): 0.743 (identified as the midpoint of the largest gap between 0.230 and 1.255 in the sorted distribution)
- XIST_expression threshold (th_x): 0.664 (midpoint of the largest gap between 0.139 and 1.189)

Sex was inferred for each sample using the following rule (on log1p expression):

1. **Male** if `mean_Y_expression > th_y` **and** `XIST_expression <= th_x`.
2. **Female** if `mean_Y_expression <= th_y` **and** `XIST_expression > th_x`.
3. **Ambiguous cases** (one marker above and the other below its threshold) were resolved by comparing the absolute distance to thresholds; the marker showing the more extreme deviation determined the final call (higher mean_Y favored Male; higher XIST favored Female).

## Concordance with metadata Donor_Sex

- Total samples: **70**
- Concordant samples: **60**
- Discordant samples: **10**
- Overall concordance rate: **85.714%**

## Samples with disagreement between inferred sex and Donor_Sex

The following samples had mismatches; expression-based sex assignment should be preferred:

| Sample | XIST_expression (log1p) | mean_Y_expression (log1p) | Inferred_Sex | Donor_Sex |
|--------|--------------------------|---------------------------|--------------|-----------|
| S004 | 3.891 | 0.077 | Female | Male |
| S013 | 4.443 | 0.053 | Female | Male |
| S015 | 0.035 | 2.902 | Male | Female |
| S026 | 3.202 | 0.023 | Female | Male |
| S027 | 2.954 | 0.026 | Female | Male |
| S035 | 0.022 | 2.294 | Male | Female |
| S045 | 0.012 | 2.053 | Male | Female |
| S051 | 0.011 | 2.536 | Male | Female |
| S060 | 0.014 | 1.255 | Male | Female |
| S068 | 2.737 | 0.045 | Female | Male |
