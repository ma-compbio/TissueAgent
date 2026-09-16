# Enrichment summary by group

This report summarizes over-representation analysis (ORA) for four hand-curated mechanism-of-action (MoA) gene set categories (mTOR, HDAC, HSP90/heat-shock, DNA damage/p53) across groups A–D.

**Ranking metric for gene-level DE lists**: `rank_score = sign(logFC) * -log10(P.Value)`, so strongly up-regulated genes have large positive scores and strongly down-regulated genes have large negative scores.

**Significance thresholds for defining up/down genes**: adj.P.Val < 0.05 and |logFC| ≥ 1.0, applied to gene-collapsed DE results.

**ORA method**: one-sided Fisher’s exact test (alternative="greater") for each gene set against the background of all tested genes in the contrast, performed separately for up- and down-regulated gene lists. Benjamini–Hochberg FDR correction was applied across the eight tests (4 gene sets × 2 directions) within each group.

## Group A


- **Overall pattern**: The gene-level background for Group A contains only three genes (ACTB, GAPDH, STAT1), and none pass the significance threshold (adj.P.Val < 0.05 and |logFC| ≥ 1.0). As a result, there are no significantly over-represented gene sets in either direction. All Fisher tests return p-value = 1 and FDR = 1.0.

- **Nominally strongest MoA signal** (purely by ranking FDR, though not significant): mTOR / mTOR_PI3K_AKT_autophagy in the **up** direction (FDR = 1.000). This ranking is not meaningful given the absence of significant genes.

- **Supporting genes**: Among the three genes represented in the DE + annotation overlap, STAT1 belongs to the HSP90/heat-shock gene signature, but STAT1 itself is not significantly up- or down-regulated under the specified thresholds in Group A. ACTB and GAPDH serve as controls/housekeeping and are not members of the curated MoA sets.

- **Conclusion for Group A**: Within this simplified, annotation-restricted analysis, there is **no clear enrichment** for any of the four hand-curated MoA signatures (mTOR, HDAC/chromatin, HSP90/heat-shock, DNA damage/p53).

## Group B


- **Overall pattern**: The gene-level background for Group B contains only three genes (ACTB, GAPDH, STAT1), and none pass the significance threshold (adj.P.Val < 0.05 and |logFC| ≥ 1.0). As a result, there are no significantly over-represented gene sets in either direction. All Fisher tests return p-value = 1 and FDR = 1.0.

- **Nominally strongest MoA signal** (purely by ranking FDR, though not significant): mTOR / mTOR_PI3K_AKT_autophagy in the **up** direction (FDR = 1.000). This ranking is not meaningful given the absence of significant genes.

- **Supporting genes**: Among the three genes represented in the DE + annotation overlap, STAT1 belongs to the HSP90/heat-shock gene signature, but STAT1 itself is not significantly up- or down-regulated under the specified thresholds in Group B. ACTB and GAPDH serve as controls/housekeeping and are not members of the curated MoA sets.

- **Conclusion for Group B**: Within this simplified, annotation-restricted analysis, there is **no clear enrichment** for any of the four hand-curated MoA signatures (mTOR, HDAC/chromatin, HSP90/heat-shock, DNA damage/p53).

## Group C


- **Overall pattern**: The gene-level background for Group C contains only three genes (ACTB, GAPDH, STAT1), and none pass the significance threshold (adj.P.Val < 0.05 and |logFC| ≥ 1.0). As a result, there are no significantly over-represented gene sets in either direction. All Fisher tests return p-value = 1 and FDR = 1.0.

- **Nominally strongest MoA signal** (purely by ranking FDR, though not significant): mTOR / mTOR_PI3K_AKT_autophagy in the **up** direction (FDR = 1.000). This ranking is not meaningful given the absence of significant genes.

- **Supporting genes**: Among the three genes represented in the DE + annotation overlap, STAT1 belongs to the HSP90/heat-shock gene signature, but STAT1 itself is not significantly up- or down-regulated under the specified thresholds in Group C. ACTB and GAPDH serve as controls/housekeeping and are not members of the curated MoA sets.

- **Conclusion for Group C**: Within this simplified, annotation-restricted analysis, there is **no clear enrichment** for any of the four hand-curated MoA signatures (mTOR, HDAC/chromatin, HSP90/heat-shock, DNA damage/p53).

## Group D


- **Overall pattern**: The gene-level background for Group D contains only three genes (ACTB, GAPDH, STAT1), and none pass the significance threshold (adj.P.Val < 0.05 and |logFC| ≥ 1.0). As a result, there are no significantly over-represented gene sets in either direction. All Fisher tests return p-value = 1 and FDR = 1.0.

- **Nominally strongest MoA signal** (purely by ranking FDR, though not significant): mTOR / mTOR_PI3K_AKT_autophagy in the **up** direction (FDR = 1.000). This ranking is not meaningful given the absence of significant genes.

- **Supporting genes**: Among the three genes represented in the DE + annotation overlap, STAT1 belongs to the HSP90/heat-shock gene signature, but STAT1 itself is not significantly up- or down-regulated under the specified thresholds in Group D. ACTB and GAPDH serve as controls/housekeeping and are not members of the curated MoA sets.

- **Conclusion for Group D**: Within this simplified, annotation-restricted analysis, there is **no clear enrichment** for any of the four hand-curated MoA signatures (mTOR, HDAC/chromatin, HSP90/heat-shock, DNA damage/p53).
