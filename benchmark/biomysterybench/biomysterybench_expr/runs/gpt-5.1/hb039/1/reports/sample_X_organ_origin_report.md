# Title & Objective

**Objective:** Determine the organ of origin for **Sample_X** (Mus musculus) based solely on its Affymetrix Mouse Genome 430 2.0 (GPL1261) gene expression profile, and commit to a single organ label.

# Data & Methods

## Data
- Platform: Affymetrix Mouse Genome 430 2.0 (GPL1261).
- Input file: `library/datasets/sample_X.CEL.gz` (single microarray sample, Sample_X).
- No external metadata or labels were provided; tissue identity was inferred from expression alone.

## Preprocessing & Normalization
- The CEL file was decompressed to `project/outputs/intermediate/sample_X.CEL`.
- Normalization: **MAS5 single-array normalization** (Affymetrix MAS 5.0 algorithm) via the R `affy` package.
- Expression scale: MAS5 signal intensities were **log2-transformed**.
- Probeset-to-gene mapping:
  - Bioconductor annotation package: **`mouse4302.db`**.
  - Probeset ID (`PROBEID`) mapped to Mus musculus gene symbols (`SYMBOL`).
  - Additional fields: `GENENAME` and `ENTREZID`.
- Gene-level summarization:
  - Control probes and probes without valid gene symbols were removed.
  - When multiple probesets mapped to the same gene symbol, values were **collapsed by median** of log2 expression.
  - Resulting matrix: **22,006 genes** with columns `gene_symbol`, `expression` (log2 MAS5), `n_probes`, `entrez_ids`, `gene_names`.

## Feature Derivation
- **Global high-expression genes** (`sample_X_top_expressed_genes.tsv`):
  - Expression percentiles computed across all 22,006 genes.
  - High-expression rule: `expression ≥ 10.391` (≈ 90th percentile; top ~10%).
  - Output: 2,201 genes ranked by expression with additional columns:
    - `expression_percentile`, `is_housekeeping`, `n_probes`, `entrez_ids`, `gene_names`.
- **Tissue-enriched candidate markers** (`sample_X_tissue_enriched_candidate_markers.tsv`):
  - Cutoff: `expression ≥ 12.492` (≈ 97.5th percentile; top ~2.5%) and **not** in a hard-coded housekeeping list (Actb, Gapdh, Rplp0, Hprt1, Ppia, B2m, etc.).
  - Output: 541 genes with same fields plus `selection_reason`.

## Tissue/Organ Reference and Similarity Scoring
- No prebuilt mouse tissue atlas was available, so a **hand-curated marker panel** was constructed:
  - Organs/tissues considered: `heart`, `blood_or_bone_marrow`, `adipose`, `skeletal_muscle`, `liver`, `kidney`, `lung`, `spleen`, `brain_cortex`, `cerebellum`, `pancreas`, `thymus`, `ovary`, `testis`, `small_intestine`, `colon`, `stomach`, `skin_epidermis`.
  - Each organ had a list of canonical mouse markers (e.g., Myh6/Myh7/Tnnt2/Actc1 for heart; Alb/Ttr/Cyp genes for liver; Sftpc/Scgb1a1 for lung; Ins1/Ins2/Pdx1 for pancreas; Prm1/Prm2 for testis; Krt5/Krt14 for skin, etc.).
  - Reference label: **`hand_curated_mouse_tissue_markers_v1`**.
- Expression standardization:
  - For each gene: `z_expression = (expression − mean_all_genes) / sd_all_genes`.
- Tissue similarity scores (`sample_X_tissue_similarity_scores.tsv`):
  - For each organ:
    - Collected marker genes present in Sample_X.
    - Computed `mean_z_expression_all_markers`.
    - Identified overlap with Sample_X tissue-enriched candidates; if ≥3 enriched markers were present, computed `mean_z_expression_enriched_markers`.
  - **Similarity score:**
    - `enriched_markers_mean_z` if ≥3 enriched markers were available.
    - Otherwise `all_markers_mean_z`.
  - Output fields: `tissue_or_organ`, `similarity_score`, `scoring_method`, `n_markers_defined`, `n_markers_present_in_sample`, `n_markers_used_for_score`, `n_markers_enriched_present`, `mean_z_expression_all_markers`, `mean_z_expression_enriched_markers`, `mean_expression_all_markers`, `reference_panel`.
- Ranked candidate organs (`sample_X_ranked_candidate_organs.tsv`):
  - Same metrics as above, plus `rank`, `organ`, and a brief `notes` field.

## Organ Marker Cross-check (Coherence Analysis)
- A more focused organ marker set (**`curated_mouse_organ_markers_step4_v1`**) was defined for:
  - heart, blood_or_bone_marrow, skeletal_muscle, liver, kidney, lung, spleen, brain_cortex, small_intestine, colon, adipose.
- For each `(organ, marker_gene)` (`sample_X_organ_marker_expression.tsv`):
  - Extracted log2 MAS5 expression, z-score, expression percentile, and flags:
    - `is_top_expressed` (top 10% by expression),
    - `is_tissue_enriched_marker` (in the 97.5th percentile, non-housekeeping set),
    - `is_above_top10pct_expr`, `is_above_top5pct_expr`.
- Organ-level summary (`sample_X_organ_marker_support_summary.tsv`):
  - Metrics per organ: number of markers, mean/median expression and z-scores, fractions of markers above 90th/95th percentile, fraction overlapping tissue-enriched markers, coefficient of variation of marker z-scores, and a heuristic `qualitative_support` category (`strong`, `moderate`, `weak`, `none`).

# Results

## 1. Tissue Similarity Rankings
From `sample_X_ranked_candidate_organs.tsv`:
- **Rank 1 – heart**
  - similarity_score ≈ **3.27**
  - scoring_method: `enriched_markers_mean_z`
  - n_markers_defined/present: 16/16; 11 enriched markers used.
  - Heart markers show very high standardized expression relative to global distribution.
- **Rank 2 – blood_or_bone_marrow**
  - similarity_score ≈ **3.24**
  - scoring_method: `enriched_markers_mean_z`
  - n_markers_defined/present: 12/12; 6 enriched markers used.
- **Rank 3 – adipose**
  - similarity_score ≈ **1.37**
  - scoring_method: `all_markers_mean_z`.
- **Rank 4–5 – skeletal_muscle, liver**
  - similarity_score ≈ **0.44** for each (all_markers_mean_z).
- All other organs (kidney, lung, brain_cortex, cerebellum, pancreas, thymus, spleen, ovary, stomach, small_intestine, colon, skin_epidermis, testis) have **similarity_score ≤ 0**, indicating their markers are not consistently overexpressed in Sample_X.

**Key point:** Within this marker-based framework, **heart** is the top candidate and slightly outperforms blood_or_bone_marrow, with all other organs trailing clearly behind.

## 2. Organ Marker Support & Coherence
From `sample_X_organ_marker_support_summary.tsv` (selected organs):

- **Heart**
  - n_markers_defined/detected: **10 / 10**.
  - mean_marker_z_score ≈ **3.20**, median_marker_z_score ≈ **3.27**.
  - fraction_markers_top10pct_expr: **1.00**.
  - fraction_markers_top5pct_expr: **1.00**.
  - fraction_markers_tissue_enriched_candidate: **1.00**.
  - qualitative_support: **strong**.
  - Interpretation: All heart markers are strongly and coherently overexpressed; every heart marker lies in the very top of the global expression distribution and is also flagged as tissue-enriched.

- **Blood_or_bone_marrow**
  - n_markers_defined/detected: **11 / 11**.
  - mean_marker_z_score ≈ **1.48**, median_marker_z_score ≈ **1.66**.
  - fraction_markers_top10pct_expr: ~**0.73**.
  - fraction_markers_top5pct_expr: ~**0.36**.
  - fraction_markers_tissue_enriched_candidate: ~**0.36**.
  - qualitative_support: **strong**.
  - Interpretation: Clear signal from hemoglobin and immune markers but weaker and less uniform than heart.

- **Adipose**
  - n_markers_defined/detected: **6 / 6**.
  - mean_marker_z_score ≈ **1.26**, median_marker_z_score ≈ **1.45**.
  - fraction_markers_top10pct_expr: ~**0.83**.
  - fraction_markers_top5pct_expr: ~**0.33**.
  - fraction_markers_tissue_enriched_candidate: ~**0.17**.
  - qualitative_support: **strong** but based on a smaller marker set and lower overall z-scores than heart.

- **Liver**
  - mean_marker_z_score ≈ **0.60**, median ≈ **0.47**.
  - fraction_markers_top10pct_expr: ~**0.21**; top5%: **0.0**.
  - fraction_markers_tissue_enriched_candidate: **0.0**.
  - qualitative_support: **weak**.

- **Skeletal_muscle**
  - mean_marker_z_score ≈ **0.54**, median ≈ **0.02** (driven by a subset of high markers such as Myh7, Ckm).
  - qualitative_support: **weak**.

- **Other organs (kidney, lung, spleen, colon, brain_cortex, small_intestine)**
  - mean_marker_z_score ≤ ~0.1; modest or negative.
  - fraction of markers in top expression percentiles low; qualitative_support: **none**.

**Key point:** The **heart** marker set stands out by having every marker extremely high and tissue-enriched, a pattern not matched by any other organ.

## 3. Gene-level Patterns (Illustrative Markers)
Examples of highly expressed heart markers (from `sample_X_top_expressed_genes.tsv` and `sample_X_tissue_enriched_candidate_markers.tsv`):
- **mt-Nd5** (mitochondrial respiratory chain; high in energy-demanding tissues including heart).
- **Myl2** – myosin light chain 2, regulatory, cardiac.
- **Actc1** – alpha-cardiac actin.
- **Tnnt2** – troponin T2, cardiac.
- **Myh6 / Myh7** – alpha/beta-myosin heavy chains.
- **Nppa, Nppb** – atrial and B-type natriuretic peptides, classic cardiac hormone genes.
- **Mybpc3** – myosin binding protein C, cardiac.

These genes appear near the very top of the expression ranking and are all in the tissue-enriched marker set, collectively forming a classic **cardiac contractile and natriuretic signature** that is hard to reconcile with non-cardiac tissues.

# Caveats & Warnings

- **Blood/immune contribution:**
  - Blood_or_bone_marrow also shows a strong similarity score and “strong” marker support, with high hemoglobin and leukocyte markers (e.g., Hba-a1/2, Hbb variants, Ptprc, Cd3e).
  - This suggests Sample_X likely contains **substantial blood/immune components** (e.g., infiltrating leukocytes or residual blood), so it is unlikely to represent purely isolated cardiomyocytes.

- **Reference panel limitations:**
  - The analysis uses a **hand-curated marker panel**, not a full transcriptomic atlas like BioGPS or ENCODE.
  - Marker sets per organ are finite and may not cover all relevant genes or substructures; some markers are shared across tissues (e.g., immune genes in multiple organs).
  - Similarity scores are **relative within this panel** and should not be treated as calibrated probabilities.

- **Normalization choice:**
  - MAS5 single-array normalization was used instead of multi-array RMA due to environment constraints.
  - While acceptable for within-sample ranking and z-scoring, MAS5 differs from RMA in dynamic range and background handling; direct comparison to RMA-based references is not made here.

- **Biological context unknown:**
  - The sample could derive from diseased, tumor, engineered, or region-specific tissue. Such contexts may distort expression relative to normal organ references.

# Next Steps

- If available, compare Sample_X against a **full mouse tissue expression atlas** (e.g., BioGPS/GNF or Mouse ENCODE) to validate the heart call using genome-wide correlation rather than only curated markers.
- Perform **cell-type deconvolution** (if a suitable reference exists) to quantify contributions from cardiomyocytes, fibroblasts, endothelial cells, and immune cells.
- If replicate samples or other tissues from the same study exist, perform **multi-sample normalization (e.g., RMA)** and clustering to see if Sample_X clusters with known heart samples.
- Use targeted visualization (e.g., heatmaps of marker expression) to communicate the cardiac vs blood/immune marker patterns more intuitively.

# References

- Dai M et al. Evolving gene/transcript definitions significantly alter the interpretation of GeneChip data. *Nucleic Acids Res.* 2005;33(20):e175. doi:10.1093/nar/gni179.
- Gautier L et al. affy—analysis of Affymetrix GeneChip data at the probe level. *Bioinformatics.* 2004;20(3):307–315. doi:10.1093/bioinformatics/btg405.
- Lein ES et al. Genome-wide atlas of gene expression in the adult mouse brain. *Nature.* 2007;445:168–176. doi:10.1038/nature05453. (Reference for tissue/brain markers conceptually.)
- General cardiac marker usage informed by standard mouse cardiac biology literature (e.g., Myh6/Myh7, Tnnt2, Nppa/Nppb as canonical markers).
