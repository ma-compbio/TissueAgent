# Zebrafish heart sample identification

## Title & Objective

**Objective:** Determine which of the 12 anonymized zebrafish RNA-seq samples in the TPM matrix corresponds to heart tissue, using only expression patterns and tissue marker genes.

## Data & Methods

**Data:**
- Bulk RNA-seq TPM matrix: `library/datasets/zebrafish_TPM_anonymized.csv` (34,831 genes × 12 samples, `Sample_01`–`Sample_12`).

**Processing and annotation:**
- Loaded the matrix with genes as rows and samples as columns; one row with a missing gene ID was removed, leaving 34,830 genes.
- Annotated ENSDARG gene IDs via an Ensembl/BioMart-style resource for Danio rerio, retrieving:
  - `gene_symbol` (external gene name)
  - `description`
  - `gene_biotype`
- Built an AnnData object (`objects/zebrafish_TPM_annotated.h5ad`) with samples as observations and genes as variables; annotations stored in `.var`.

**Tissue marker definition:**
- Curated marker sets for major tissues: heart, brain, liver, skeletal muscle, kidney, intestine, and hematopoietic/blood.
- Mapped canonical human/mouse markers to zebrafish ortholog-style symbols and intersected with observed gene symbols.
- For each tissue, retained only markers present in the dataset and recorded their gene IDs and gene symbols in `tables/tissue_marker_gene_sets_used.tsv`.

**Tissue signature scoring:**
- For each sample and tissue, computed:
  - `*_mean_TPM`: mean TPM across that tissue’s marker genes.
  - `*_zscore`: z-score of the mean TPM across samples for that tissue.
- Compiled per-sample scores into `tables/sample_tissue_signature_scores.tsv` (rows = samples).
- Generated a clustered heatmap and a sample dendrogram from z-scored tissue signatures:
  - `figures/sample_tissue_signature_heatmap.png`
  - `figures/sample_clustering_dendrogram.png`

**Heart-sample selection:**
- Inspected heart_mean_TPM and heart_zscore across all 12 samples.
- Required the heart sample to:
  - Have the highest heart signature (mean TPM and z-score).
  - Not be strongly enriched for non-heart tissues (brain, liver, intestine, kidney, blood).
  - Allow moderate skeletal muscle co-expression (shared muscle markers).
- Cross-checked expression of canonical cardiac markers (e.g. `tnnt2a`, `myl7`, `myh7bb`, `gata4`, `gata5`, `gata6`, `hand2`, `tbx5a`, `tbx5b`) directly from the annotated expression object.

## Results

- **Heart tissue signature:**
  - **Sample_03** has the strongest heart signature:
    - `heart_mean_TPM` ≈ **1236.1** (highest of all 12 samples).
    - `heart_zscore` ≈ **2.48** (highest heart z-score).
  - Next highest heart signatures are much lower:
    - Sample_12: `heart_mean_TPM` ≈ 780.5, `heart_zscore` ≈ 1.34.
    - Sample_07: `heart_mean_TPM` ≈ 699.7, `heart_zscore` ≈ 1.14.
  - The remaining nine samples all show negative heart z-scores and much lower heart_mean_TPM (≤ ~60 TPM).

- **Other tissue signatures for Sample_03:**
  - Brain: `brain_mean_TPM` ≈ 7.3, `brain_zscore` ≈ -0.36 → no brain enrichment.
  - Liver: `liver_mean_TPM` ≈ 12.2, `liver_zscore` ≈ -0.45 → low liver signal.
  - Kidney: `kidney_mean_TPM` ≈ 0.51, `kidney_zscore` ≈ -0.49 → very low kidney signal.
  - Intestine: `intestine_mean_TPM` ≈ 61.4, `intestine_zscore` ≈ -0.47 → no intestinal enrichment.
  - Hematopoietic/blood: `hematopoietic_blood_mean_TPM` ≈ 570.9, `hematopoietic_blood_zscore` ≈ -0.19 → not blood-dominated relative to other samples.
  - Skeletal muscle: `skeletal_muscle_mean_TPM` ≈ 425.1, `skeletal_muscle_zscore` ≈ -0.13 → only mildly elevated versus strongly muscle-enriched samples (e.g. Sample_07 and Sample_12), consistent with cardiac muscle overlap rather than a pure skeletal muscle sample.

- **Comparative tissue context:**
  - Brain: Sample_01 has a very high brain signature (`brain_mean_TPM` ≈ 875.0, `brain_zscore` ≈ 3.22), clearly distinct from Sample_03.
  - Liver and blood: Sample_05 is strongly liver- and blood-enriched (`liver_mean_TPM` ≈ 3217.1, `liver_zscore` ≈ 2.54; very high hematopoietic/blood z-score), unlike Sample_03.
  - Intestine: Sample_04 shows a strong intestinal signal (`intestine_mean_TPM` ≈ 1488.2, `intestine_zscore` ≈ 2.23), again unlike Sample_03.
  - Skeletal muscle: Samples_07 and 12 have extremely high skeletal muscle signatures and only moderately elevated heart scores, indicating they are more consistent with skeletal muscle than heart.

- **Gene-level heart marker evidence:**
  - Evaluated canonical cardiac markers: `tnnt2a`, `myl7`, `myh7bb`, `gata4`, `gata5`, `gata6`, `hand2`, `tbx5a`, `tbx5b`.
  - All are present in the dataset.
  - Mean TPM across these nine markers:
    - Sample_03: ~**4039 TPM**.
    - Next highest samples: on the order of 10–20 TPM (e.g. Sample_04 ~22, Sample_06 ~16, Sample_02 ~8).
  - For key genes like `myl7`, `tnnt2a`, and `myh7bb`, Sample_03 has orders-of-magnitude higher expression than any other sample (e.g., `myl7` >30,000 TPM in Sample_03 vs. mostly 0–40 TPM elsewhere).
  - This pattern is characteristic of a cardiomyocyte-rich (heart) sample.

**Final call:** The heart tissue sample is **Sample_03**.

## Caveats & Warnings
- Marker sets are curated from general vertebrate cardiac and other tissue markers and mapped to zebrafish by symbol/orthology; some tissue-specific nuances may not be fully captured.
- Scores are based on bulk TPM and mean expression over marker sets; no adjustment was made for potential compositional differences within tissues (e.g., varying stromal vs. parenchymal content).
- Despite these limitations, the heart signal in Sample_03 is so strong and specific (both in aggregate signatures and individual marker genes) that misclassification is unlikely.

## Next Steps
- If additional tissues or conditions exist in related datasets, apply the same marker-based scoring to cross-validate tissue assignments.
- Optionally refine marker panels using zebrafish-specific resources (ZFIN, zebrafish atlases) to confirm and potentially sharpen tissue discrimination.

## References
- Ensembl / BioMart: Kinsella et al., Database (Oxford). 2011;2011:bar030. doi:10.1093/database/bar030.
- General cardiac markers and biology: Olson EN. Development. 2006;133(23):4479–4490. doi:10.1242/dev.02607.