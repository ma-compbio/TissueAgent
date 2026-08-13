# Title & Objective

**Objective:** Recover the true tissue subtype and sex for each RNA-seq sample in the masked multi-tissue dataset, using expression patterns alone, and provide a final table with columns: Sample, Tissue, Sex.

# Data & Methods

**Data sources**
- Expression: `library/datasets/expression_matrix.csv` (54,592 genes × 70 samples; genes in rows, samples in columns).
- Metadata: `library/datasets/sample_metadata_masked.csv` with columns:
  - `Sample_ID` (S001–S070)
  - `Tissue_Group` (Whole_Blood, Liver, Brain_Region_A/B/C, Heart_Region_X/Y)
  - `Donor_ID`, `Donor_Sex` (used only for comparison/QC).

**Overview of analysis workflow**
1. **QC and PCA**
   - Confirmed that expression columns match `Sample_ID` order.
   - Computed sample-level metrics (library size, detected genes, mean/median expression, fraction of counts in top 100 genes) and gene-level metrics (mean, variance, detection rate).
   - Applied log1p transform and gene-wise standardization, then PCA on samples. PC1–PC2 clearly separated major tissue groups.

2. **Group-level expression and marker discovery**
   - For each `Tissue_Group`, computed mean expression per gene across that group’s samples.
   - Defined markers per group by contrasting mean expression in that group vs the mean across all other groups, using log2 fold-change (with a small pseudocount) and a minimum in-group expression filter.
   - Selected the top 100 markers per group (by log2 fold-change and absolute difference) and visualized union marker sets in heatmaps.

3. **Mapping masked tissue groups to true tissues**
   - Examined canonical tissue markers in the group-mean profiles and top markers to map each `Tissue_Group` to an anatomically meaningful label:
     - Blood/immune: HBB, HBA1, HBA2, HBD, PTPRC, LST1, MS4A1, CD3D, CD8A.
     - Liver: ALB, APOA1, APOB, TTR, HP, FGA, FGB, FGG, CYP3A4, CPS1, TAT.
     - Brain (neuronal / glial and regional markers): RBFOX3, SLC17A7, GAD1/2, SYN1, MAP2, SNAP25, GFAP, AQP4, MBP, OLIG2, SLC1A2, SLC1A3, RORB, CUX1/2, TBR1, GRID2, PCP4, CALB1/2, PROX1, ZBTB20, RELN.
     - Heart: MYH6, MYH7, TNNT2, ACTC1, TNNI3, TTN, NPPA, NPPB, MYL2, MYL7, MYL4, SLN.
   - Used these signatures plus clustering/heatmaps to assign specific brain and heart subregions.

4. **Sex inference from expression**
   - Used X-/Y-linked markers:
     - Y: RPS4Y1, DDX3Y, EIF1AY, KDM5D, UTY, ZFY, USP9Y.
     - X-inactivation: XIST.
   - Log1p-transformed expression and summarized per sample:
     - `mean_Y_expression` = mean log1p across Y markers.
     - `XIST_expression` = log1p(XIST).
   - Derived thresholds from gaps in marker distributions:
     - `th_y ≈ 0.743` for mean_Y_expression; `th_x ≈ 0.664` for XIST.
   - Classification rule (log1p scale):
     - Male if `mean_Y_expression > th_y` and `XIST_expression <= th_x`.
     - Female if `mean_Y_expression <= th_y` and `XIST_expression > th_x`.
     - Ambiguous cases resolved by whichever marker (Y vs XIST) deviated more strongly from its threshold.
   - Compared `Inferred_Sex` to metadata `Donor_Sex` for QC; expression-based sex calls were used for final labels.

5. **Final label assembly**
   - Mapped each `Tissue_Group` to `True_Tissue` via the mapping table.
   - Joined `Inferred_Sex` to each sample.
   - Produced `sample_tissue_sex_assignments.tsv` with columns: Sample, Tissue, Sex.

# Results

## 1. Mapping of masked tissue groups

The seven `Tissue_Group` levels were mapped as follows (from `tissue_group_to_true_tissue_mapping.tsv`):

| Tissue_Group      | True_Tissue            |
|-------------------|------------------------|
| Whole_Blood       | Peripheral_Whole_Blood |
| Liver             | Liver                  |
| Brain_Region_A    | Cerebral_Cortex        |
| Brain_Region_B    | Hippocampus            |
| Brain_Region_C    | Cerebellum             |
| Heart_Region_X    | Ventricular_Myocardium |
| Heart_Region_Y    | Atrial_Myocardium      |

**Key supporting patterns (brief):**
- **Peripheral_Whole_Blood:** Very high erythrocyte (HBB, HBA1/2, HBD) and leukocyte (PTPRC, LST1, MS4A1, CD3D/CD8A) expression, absent/low in non-blood groups.
- **Liver:** Strong enrichment of ALB, APOA1, APOB, TTR, HP, FGA/B/G, CYP3A4, CPS1, TAT.
- **Cerebral_Cortex (Brain_Region_A):** High neuronal markers (SLC17A7, RBFOX3, SYN1, MAP2, SNAP25) plus cortical layer markers (RORB, CUX1/2, TBR1), lower cerebellar/hippocampal signatures.
- **Hippocampus (Brain_Region_B):** Enrichment of hippocampal markers PROX1, ZBTB20, RELN alongside neuronal markers.
- **Cerebellum (Brain_Region_C):** Strong cerebellar marker pattern including GRID2, PCP4, CALB1, CALB2 and distinct clustering in brain-focused heatmaps.
- **Ventricular_Myocardium (Heart_Region_X):** High MYH7, MYL2, MYL3, TNNI3—classic ventricular myocardial profile; lower NPPA/NPPB.
- **Atrial_Myocardium (Heart_Region_Y):** High NPPA, NPPB, MYH6, MYL4, SLN—canonical atrial signature.

## 2. Sex inference

From `sample_sex_inference.tsv` and the QC report:
- All 8 primary markers (XIST plus 7 Y-linked genes) were detected.
- Expression was clearly bimodal:
  - One mode: high XIST and low Y → Female.
  - Other mode: low XIST and high Y → Male.
- Applying the decision rule:
  - **Inferred Female:** 28 samples.
  - **Inferred Male:** 42 samples.
- Concordance with metadata `Donor_Sex`:
  - **60/70** samples concordant (~85.7%).
  - **10/70** discordant, where expression strongly contradicts metadata; expression-based calls were adopted as final.

## 3. Final Sample–Tissue–Sex assignments

The authoritative per-sample labels are in:
- `project/outputs/tables/sample_tissue_sex_assignments.tsv`

This table contains 70 rows (S001–S070) and three columns:
- **Sample:** S001–S070
- **Tissue:** one of {Peripheral_Whole_Blood, Liver, Cerebral_Cortex, Hippocampus, Cerebellum, Ventricular_Myocardium, Atrial_Myocardium}
- **Sex:** Male or Female (expression-based).

Summary of final composition (from `final_label_recovery_summary.md`):

- **Total samples:** 70

**Samples per true tissue:**
- Atrial_Myocardium: 10
- Cerebellum: 10
- Cerebral_Cortex: 10
- Hippocampus: 10
- Liver: 10
- Peripheral_Whole_Blood: 10
- Ventricular_Myocardium: 10

**Samples per sex:**
- Female: 28
- Male: 42

**Samples per (Tissue, Sex) combination:**
- Atrial_Myocardium: 3 Female, 7 Male
- Cerebellum: 5 Female, 5 Male
- Cerebral_Cortex: 4 Female, 6 Male
- Hippocampus: 3 Female, 7 Male
- Liver: 3 Female, 7 Male
- Peripheral_Whole_Blood: 5 Female, 5 Male
- Ventricular_Myocardium: 5 Female, 5 Male

# Caveats & Warnings

- **Marker-based mapping (no external reference atlas):** Tissue and subregion assignments rely on canonical marker genes and within-dataset contrasts, not on direct alignment to an external reference atlas. While strongly supported by known biology, very fine-grained anatomical distinctions (e.g., specific cortical Brodmann areas, left vs right ventricle) were not resolved.
- **Sex inference thresholds are data-driven:** XIST and Y-marker thresholds were chosen from the largest gaps in their distributions. The resulting calls are robust and consistent with biology but could differ slightly if an alternative thresholding strategy were chosen.
- **Metadata discrepancies:** Ten samples show disagreement between expression-based sex and metadata Donor_Sex. These are most likely metadata mislabels, but only molecular evidence was used here; any downstream interpretation should treat metadata sex with caution and prefer expression-based calls.

# Next Steps

- If you plan downstream analyses (e.g., differential expression, donor-level comparisons), use `sample_tissue_sex_assignments.tsv` as the authoritative annotation.
- For full transparency, consult the detailed rationale reports:
  - Tissue mapping markers and reasoning: `project/outputs/reports/tissue_mapping_rationale.md`.
  - Sex inference thresholds, markers, and discordant samples: `project/outputs/reports/sex_inference_qc.md`.
- Optionally validate a subset of assignments against any external metadata you may possess (e.g., histology, clinical notes) to further confirm tissue and sex labels.

# References

- Carithers et al., "A Novel Approach to High-Quality Postmortem Tissue Procurement: The GTEx Project," Biopreserv Biobank. 2015. doi:10.1089/bio.2014.0032
- GTEx Consortium, "The GTEx Consortium atlas of genetic regulatory effects across human tissues," Science. 2020. doi:10.1126/science.aaz1776
- Oliva et al., "The impact of sex on gene expression across human tissues," Science. 2020. doi:10.1126/science.aba3066
