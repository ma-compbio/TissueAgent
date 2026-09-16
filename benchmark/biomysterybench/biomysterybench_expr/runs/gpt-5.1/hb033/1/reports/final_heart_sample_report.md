# Title & Objective

**Objective.** Using only the anonymized zebrafish bulk RNA-seq expression matrix in `library/datasets/`, infer which of the 12 samples originates from heart tissue and report its sample identifier.

# Data & Methods

**Data.**
- `library/datasets/zebrafish_TPM_anonymized.csv`: 34,831 genes × 12 samples.
  - Layout: genes × samples; first column `gene_id` (zebrafish Ensembl-like IDs, e.g. `ENSDARG00000019096`), columns `Sample_01`–`Sample_12` are TPM expression values.

**Preprocessing & QC.**
- Confirmed matrix orientation and extracted sample IDs (`Sample_01`–`Sample_12`).
- Computed per-sample QC metrics from TPMs (total counts, number of detected genes [TPM>0], mean/median TPM, etc.) and summarized in `sample_qc_summary.tsv`.
- Standardized gene IDs using `gene_id_mapping.tsv`, treating the Ensembl-like IDs as the canonical identifiers for matching to markers.

**Tissue marker gene sets.**
- Curated zebrafish tissue-specific marker sets for:
  - **heart**, **brain**, **liver**, **skeletal_muscle**, **kidney**, **gut**, **blood_hematopoietic**, **endothelium_vasculature**.
- Heart markers included classic zebrafish/vertebrate cardiac genes such as:
  - *myl7 (cmlc2), tnnt2a, myh6, myh7ba (ventricular myosin, vmhc), hand2, gata4, gata5, tbx5a, nppa, nppb, ryr2a, ryr2b*.
- Other tissues used canonical neuronal, hepatic, muscle, kidney, gut, blood, and endothelial markers.
- Gene symbols were mapped to zebrafish Ensembl IDs using MyGene.info (taxid 7955), then filtered to genes present in the expression matrix.
- The final long-format marker table (`tissue_marker_gene_sets.tsv`) contains columns:
  - `tissue`, `gene_id`, `gene_symbol`, `marker_role` (core/auxiliary), `evidence`.

**Per-tissue marker scores.**
- For each gene, computed z-scores across samples:
  - For gene *g*: `z_{g,s} = (TPM_{g,s} − mean_g) / sd_g`, with genes of zero variance set to z=0.
- Selected all genes present in each tissue’s marker set and, for each tissue *T* and sample *S*:
  - **Score(T,S) = mean z-score across all marker genes of tissue T in sample S.**
- This yielded a 12 (samples) × 8 (tissues) matrix `tissue_marker_scores_per_sample.tsv`.
- Visualized scores via a clustered heatmap (`tissue_marker_heatmap.png`).

**Tissue assignment and heart sample selection.**
- For each sample, chose the tissue with the highest marker score as the **assigned_tissue**.
- Recorded the **top_score**, **second_best_tissue**, **second_best_score**, and **score_margin = top − second_best**.
- Defined a heuristic confidence label:
  - *high*: top_score ≥ 1.5 and margin ≥ 0.75
  - *medium*: top_score ≥ 1.0 and margin ≥ 0.5
  - *low*: otherwise
- Results were saved in `sample_tissue_assignments.tsv`.
- To validate the heart call, inspected TPM expression of canonical heart markers (from `tissue_marker_gene_sets.tsv`) in the original matrix `zebrafish_TPM_anonymized.csv`.

# Results

**1. Tissue marker scores strongly single out Sample_03 as heart.**

Key rows from `tissue_marker_scores_per_sample.tsv` (mean z-scores per tissue):

- **Heart scores (per sample):**
  - Sample_01: -0.064
  - Sample_02: -0.299
  - **Sample_03: 2.994**
  - Sample_04: -0.153
  - Sample_05: -0.337
  - Sample_06: -0.191
  - Sample_07: -0.321
  - Sample_08: -0.341
  - Sample_09: -0.331
  - Sample_10: -0.301
  - Sample_11: -0.330
  - Sample_12: -0.326

Only **Sample_03** has a strongly positive heart score (~3.0), ~3 standard deviations above the cohort mean for the heart marker set. All other samples have negative heart scores, indicating depletion of the heart program.

**2. Tissue assignment summary.**

From `sample_tissue_assignments.tsv`:

- Sample_01 → brain (high confidence)
- Sample_02 → gut (low)
- **Sample_03 → heart (high)**
- Sample_04 → gut (high)
- Sample_05 → kidney (medium)
- Sample_06 → liver (high)
- Sample_07 → skeletal_muscle (low)
- Sample_08 → kidney (low)
- Sample_09 → endothelium_vasculature (high)
- Sample_10 → gut (low)
- Sample_11 → brain (low)
- Sample_12 → skeletal_muscle (high)

For **Sample_03** specifically:
- top tissue: **heart**, top_score ≈ **2.99**
- second-best: endothelium_vasculature, score ≈ **1.61**
- margin ≈ **1.39** z-score units → **high confidence**.

No other sample is assigned to heart; all have negative heart scores.

**3. Canonical heart marker genes confirm Sample_03 as heart.**

Using the expression matrix `zebrafish_TPM_anonymized.csv` and the heart marker list, canonical cardiac genes are massively enriched in Sample_03:

- Example: **myl7 (ENSDARG00000019096)**
  - Sample_03: ~**30,910 TPM**
  - Other samples: low single digits (e.g., 3.1 TPM in Sample_01, ~1–2 TPM in others) or near-zero.
- **tnnt2a**, **myh6**, **myh7ba**, **tbx5a**, **nppa**, **nppb**, **hand2**, **gata4**, **gata5**, and calcium-handling genes (**ryr2a/b**) all show the same qualitative pattern:
  - **Very high expression** in Sample_03.
  - **Consistently low expression** in all other samples.

This coherent, multi-marker enrichment (contractile proteins, transcription factors, chamber markers) is exactly the signature expected from bona fide heart tissue.

# Caveats & Warnings

- Marker gene sets were compiled from general zebrafish/vertebrate knowledge and mapped via an online service (MyGene.info). A handful of intended markers lacked Ensembl IDs or were absent from this matrix and were therefore excluded. However, multiple independent, high-specificity heart markers remain and show concordant enrichment in Sample_03.
- Tissue scores were computed on a relatively small number of bulk samples (n=12). While this is adequate for within-dataset comparisons, it does not provide population-level statistics; results are specific to this dataset.

# Next Steps

- If desired, extend analysis with broader reference signatures (e.g., comparing to published zebrafish organ transcriptomes) to further validate tissue assignments for all samples.
- Use the tissue labels inferred here (including the heart assignment for Sample_03) as priors for downstream analyses such as differential expression or pathway enrichment.

# References

- General zebrafish cardiac markers and transgenic lines (e.g., *myl7*, *tnnt2a*, *gata4*, *gata5*, *hand2*, *tbx5a*, *nppa*, *nppb*), as used widely in the zebrafish literature for heart development and function.
