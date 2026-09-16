# Identification of the heart RNA-seq sample

## Selected sample
- **Heart sample ID:** `Sample_03`

## Tissue signature evidence

From `tables/sample_tissue_signature_scores.tsv`:

- **Heart scores across samples (mean TPM and z-score)**
  - `Sample_03` has by far the highest heart signature:
    - `heart_mean_TPM` = **1236.1**, the highest of all 12 samples.
    - `heart_zscore` = **2.48**, also the highest heart z-score among all samples.
  - The next highest heart signatures are much lower:
    - `Sample_12`: `heart_mean_TPM` ≈ 780.5, `heart_zscore` ≈ 1.34
    - `Sample_07`: `heart_mean_TPM` ≈ 699.7, `heart_zscore` ≈ 1.14
  - The remaining nine samples all have **negative heart z-scores** and substantially lower heart_mean_TPM (≤ ~60 TPM).

- **Non-heart tissue scores for `Sample_03`**
  - Brain:
    - `brain_mean_TPM` ≈ 7.3, `brain_zscore` ≈ -0.36 (near/below average, not brain-enriched).
  - Liver:
    - `liver_mean_TPM` ≈ 12.2, `liver_zscore` ≈ -0.45 (low, not liver-enriched).
  - Kidney:
    - `kidney_mean_TPM` ≈ 0.51, `kidney_zscore` ≈ -0.49 (very low kidney signal).
  - Intestine:
    - `intestine_mean_TPM` ≈ 61.4, `intestine_zscore` ≈ -0.47 (no intestinal enrichment).
  - Hematopoietic/blood:
    - `hematopoietic_blood_mean_TPM` ≈ 570.9, but `hematopoietic_blood_zscore` ≈ -0.19 (slightly below average relatively to other samples, so not blood-dominated despite a moderate absolute TPM).
  - Skeletal muscle:
    - `skeletal_muscle_mean_TPM` ≈ 425.1 with `skeletal_muscle_zscore` ≈ -0.13.
    - This indicates some absolute skeletal muscle marker expression, but **relative to other samples** (e.g. `Sample_07` with skeletal_muscle_zscore ≈ 2.51 and `Sample_12` with ≈ 1.91), `Sample_03` is **not** the primary skeletal muscle-enriched sample. Some overlap in cardiac and skeletal muscle markers is expected for heart tissue.

- **Comparison to other candidate samples**
  - `Sample_07` and `Sample_12` both have elevated heart scores, but their profiles suggest other dominant tissue types:
    - `Sample_07`:
      - `heart_zscore` ≈ 1.14 (elevated) but
      - `skeletal_muscle_zscore` ≈ 2.51 (strong skeletal muscle enrichment), making this more consistent with skeletal muscle than heart.
    - `Sample_12`:
      - `heart_zscore` ≈ 1.34 (elevated) but
      - `skeletal_muscle_zscore` ≈ 1.91 and `hematopoietic_blood_mean_TPM` ≈ 807.1 (with `hematopoietic_blood_zscore` ≈ -0.04). The strong skeletal muscle signature again suggests a skeletal muscle–rich or mixed sample rather than a cleanly heart-dominated profile.
  - In contrast, `Sample_03` has the **highest and most specific heart signature** with all other tissues either average or below-average in z-score.

## Gene-level confirmation using key heart markers

Using `objects/zebrafish_TPM_annotated.h5ad`, I examined classic cardiac marker genes:
- tnnt2a, myh7bb, myl7, gata4, gata5, gata6, hand2, tbx5a, tbx5b

For these nine markers:
- All are present in the dataset.
- The **per-sample mean expression** across these markers is:
  - `Sample_03`: **~4039 TPM** (by far the highest)
  - Next highest samples are an order of magnitude lower (e.g. `Sample_04` ~22, `Sample_06` ~16, `Sample_02` ~8 TPM).
- For individual key markers (e.g. `myl7`, `tnnt2a`, `myh7bb`, `gata4`, `gata5`, `gata6`, `hand2`, `tbx5a`, `tbx5b`), `Sample_03` shows **dramatically higher expression** than any other sample. For example:
  - `myl7` in `Sample_03` is >30,000 TPM, whereas in other samples it is typically in the 0–40 TPM range.
  - `tnnt2a` and `myh7bb` are also orders of magnitude higher in `Sample_03` compared with the other 11 samples.

This gene-level pattern is strongly indicative of a heart (cardiomyocyte-enriched) sample.

## Conclusion

Based on the combination of:
- The **highest heart_mean_TPM and heart_zscore** of all samples,
- **Relatively low brain, liver, kidney, intestine, and hematopoietic/blood signatures**, and only modest skeletal muscle enrichment relative to strongly muscle-enriched samples,
- And **overwhelmingly higher expression of canonical heart marker genes** in `Sample_03` compared with all other samples,

I conclude with high confidence that **`Sample_03` is the heart RNA-seq sample** in this zebrafish dataset.