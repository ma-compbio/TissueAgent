# Knockdown gene inference

## Cluster mapping

Sample cluster assignments confirm that cluster 0 contains ctrl1/ctrl2 and cluster 1 contains kd1/kd2, so cluster 0 was treated as control and cluster 1 as knockdown throughout.

## Ranking of candidate genes

Genes were ranked primarily by TPM-based log2 fold change between knockdown and control (log2FC_KD_vs_CTRL_TPM), with more negative values indicating lower expression in knockdown, and by the contrast in per-sample TPM z-scores between kd and control (zscore_contrast_KD_minus_CTRL).

The top three knockdown-like candidates were:

- **QKI**: log2FC_KD_vs_CTRL_TPM = -0.402, zscore_contrast_KD_minus_CTRL = -1.999
- **ADD3**: log2FC_KD_vs_CTRL_TPM = -0.346, zscore_contrast_KD_minus_CTRL = -1.955
- **SRSF1**: log2FC_KD_vs_CTRL_TPM ≈ -0.254, zscore_contrast_KD_minus_CTRL ≈ -1.576 (from support metrics)

Other candidates either showed weaker or positive log2FC (higher expression in knockdown), making them inconsistent with a knockdown signature.

## Evidence supporting QKI as the knocked-down gene

1. **Effect size on TPM scale**  
   QKI shows the most negative log2FC_KD_vs_CTRL_TPM among all candidates (≈ -0.402), corresponding to a substantial reduction in TPM (mean_TPM_CTRL = 144.4 vs mean_TPM_KD = 109.3). This effect size is clearly larger than that of ADD3 (log2FC ≈ -0.346) and SRSF1 (log2FC ≈ -0.254).

2. **Effect size on log2(TPM+1) scale**  
   The group-wise mean log2(TPM+1) for QKI decreases from 7.184 in controls to 6.785 in knockdown, a difference of -0.399 log2 units. This is the strongest negative shift among the candidates and is slightly larger in magnitude than for ADD3 (delta ≈ -0.342).

3. **Consistency across replicates and within-group variability**  
   QKI has very low within-group variance on the log2(TPM+1) scale (var_log2TPM_plus1_CTRL = 0.000108, var_log2TPM_plus1_KD = 0.000054), indicating tight agreement between replicates in both control and knockdown groups. The across-sample variance remains small (var_log2TPM_plus1_across_samples ≈ 0.03986), supporting a coherent shift rather than noisy fluctuations. ADD3 shows somewhat larger within-group variance, particularly in the knockdown group (var_log2TPM_plus1_KD ≈ 0.005333).

4. **Z-score contrast between groups**  
   On TPM z-scores, QKI has mean_ctrl_z_TPM ≈ 0.999 and mean_kd_z_TPM ≈ -0.999, giving a zscore_contrast_KD_minus_CTRL of -1.999. This is the strongest negative contrast among all candidates, indicating that both kd1 and kd2 consistently sit well below the control samples. ADD3 also shows a strong negative contrast (≈ -1.955), but its magnitude is slightly smaller than for QKI. SRSF1 has a weaker contrast and substantially higher knockdown variance (sd_kd_z_TPM ≈ 0.853), suggesting more heterogeneous behavior across kd replicates.

5. **Exclusion of alternative candidates**  
   Several genes (e.g. RBM39, GADD45A, PTBP1, HNRNPA1, SF3B1, HSP90AB1, EGR1, RBFOX1) have positive log2FC_KD_vs_CTRL_TPM values, indicating higher expression in knockdown than in controls, which is inconsistent with a knockdown target. VEGFA and HBB show either small effect sizes or higher relative variability, and their z-score contrasts are weaker or less interpretable as a clean knockdown. Overall, no other candidate matches the combination of strongest negative fold-change, coherent per-sample z-score pattern, and low within-group variability observed for QKI.

## Conclusion

Considering TPM-level log2 fold-changes, group-wise mean differences on the log2(TPM+1) scale, per-sample z-score contrasts, and within-group variability, **QKI** is the single best-supported candidate displaying a clear knockdown-like signature between cluster 0 (control) and cluster 1 (knockdown). QKI is therefore inferred to be the knocked-down gene in this experiment.
