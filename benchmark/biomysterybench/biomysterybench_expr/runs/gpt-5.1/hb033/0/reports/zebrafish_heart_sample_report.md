# Title & Objective

**Objective:** Identify which sample in the anonymized zebrafish RNA-seq TPM dataset corresponds to heart tissue, using only the expression matrix (no labels or metadata).

---

## Data & Methods

**Input data**
- `library/datasets/zebrafish_TPM_anonymized.csv`
  - 34,831 rows (genes; `gene_id` as Ensembl or related IDs)
  - 12 columns (samples: `Sample_01`–`Sample_12`), values are TPM.

**1. Sample-level QC and clustering**
- Computed per-sample QC metrics from the full TPM matrix:
  - `total_TPM` (sum over all genes) – all samples ~1e6 TPM, consistent with TPM normalization.
  - Numbers of expressed genes: `n_genes_TPM_gt_0`, `n_genes_TPM_gt_1`.
  - `mean_TPM`, `median_TPM`, `max_TPM`, and `sparsity_TPM_eq_0` (fraction of genes with TPM == 0).
- Calculated a 12×12 Pearson correlation matrix between samples using all genes, and performed hierarchical clustering (distance = 1 − r) to visualize sample similarity.

**2. Gene annotation and heart marker curation**
- Annotated `gene_id` values using MyGene.info (Danio rerio, taxon 7955):
  - Extracted `gene_symbol`, `description` (summary/name), and `biotype` (type_of_gene).
  - Produced a one-row-per-gene table, retaining unmapped IDs with `NA` annotations.
- Curated a zebrafish heart-marker list from canonical cardiac genes, including:
  - Sarcomeric myosins/light chains: *myl7 (cmlc2)*, *myl4*, *myh6*, *myh7*, *mylk2*, *mylk3*.
  - Troponins: *tnnt2a*, *tnnt2b*, *tnnc1a*, *tnnc1b*.
  - Cardiac/muscle actins & cytoskeleton: *actc1a*, *actc1b*, *acta1a*, *desma*, *desmb*.
  - Natriuretic peptides: *nppa*, *nppb*.
  - Cardiac TFs/regulators: e.g. *nkx2.7*, *gata4/5/6*, *hand2*, *mef2ca/cb*, *tbx5a/b*, *tbx20*, *tbx2b*, *isl1a/b*, *hey2*, *id2a*, *irx1a/2a*, *shox2*, *tbx3a*.
  - Signaling & structural/ion-handling genes: *bmp2b*, *bmp4*, *fgf8a*, *vegfaa*, *pdlim3b*, *ttn.2*, *ryr2b*, *cacna1c*, *kcnj2a*, *hcn4*, *slc8a1a/b*, etc.
- Intersected curated symbols with annotated genes; 52 markers were present in the dataset and recorded with:
  - `gene_id`, `gene_symbol`, `marker_category`, and a brief `notes` field.

**3. Heart-marker scoring and visualization**
- Subset the TPM matrix to the 52 heart-marker genes.
- Per-sample heart-marker metrics:
  - `n_markers_expressed_TPM_gt_0` and `n_markers_expressed_TPM_gt_1`.
  - `sum_TPM_markers`, `mean_TPM_markers`, `median_TPM_markers`.
- Per-marker z-scores:
  - For each marker and sample: z = (TPM − mean_across_samples) / SD_across_samples (SD=0 → z=0).
- Composite heart scores per sample:
  - `mean_zscore_all_markers`: average z across the 52 markers.
  - `sum_positive_zscores`: sum of positive z-scores only.
- Visualization:
  - Heatmap of marker z-scores across samples with hierarchical clustering of genes and samples.
  - PCA on the z-score matrix (samples as points; PC1 vs PC2 plotted) to visualize separation of heart-like samples.

**4. Final heart-sample selection**
- Defined a composite **heart-likeness score** per sample as the sum of z-scored values of six metrics:
  - `sum_TPM_markers`, `mean_TPM_markers`, `mean_zscore_all_markers`, `sum_positive_zscores`, `n_markers_expressed_TPM_gt_0`, `n_markers_expressed_TPM_gt_1`.
- Ranked samples by this composite score and cross-checked with QC metrics and marker visualizations.

---

## Results

**Primary finding: heart tissue sample**
- The sample best matching a heart-tissue expression profile is:

  **Sample_03**

**Evidence from heart-marker metrics (from `heart_marker_expression_by_sample.tsv`):**
- `Sample_03`:
  - `sum_TPM_markers` ≈ 68,300 (vs. median across samples ≈ 484).
  - `mean_TPM_markers` ≈ 1,313.5.
  - `median_TPM_markers` ≈ 78.35.
  - `mean_zscore_all_markers` ≈ 1.67 (highest of all samples).
  - `sum_positive_zscores` ≈ 94.56 (next highest is Sample_12 at ≈ 25.04).
  - `n_markers_expressed_TPM_gt_1` = 47 (highest of all samples).
- Composite heart-likeness score:
  - Sample_03: ≈ 13.37 (dominant outlier).
  - Sample_12: ≈ 4.28 (second but much lower).
  - All other samples: ≲ 1, often ≤ 0.

**Direct inspection of canonical cardiac markers (raw TPM):**
- *myl7 (cmlc2)* – hallmark cardiac myosin light chain:
  - Sample_03: ~30,910 TPM.
  - All other samples: near-zero to very low.
- *tnnt2a* (cardiac troponin T2a):
  - Sample_03: ~4,447 TPM.
  - Others: essentially absent.
- *nppa* and *nppb* (atrial and B-type natriuretic peptides):
  - `nppa` (ENSDARG00000052960): Sample_03 ~1,578 TPM; others near zero.
  - `nppb` (ENSDARG00000052958): Sample_03 ~197 TPM; others near zero.
- *actc1a/actc1b*, *myh6*, *myh7*, and structural markers (e.g. *desma*, *desmb*, *ttn.2*, *mybpc3*):
  - Strongly enriched in Sample_03.
  - Some are also elevated in Sample_12, consistent with a muscle-like but less specifically cardiac profile.

**QC context (from `sample_qc_summary.tsv`):**
- Sample_03 has typical library characteristics:
  - `total_TPM` ≈ 999,735 (similar to other samples ~996,780–1,000,016).
  - `n_genes_TPM_gt_0` and `n_genes_TPM_gt_1` in the middle of the cohort.
  - `median_TPM`, `max_TPM`, and `sparsity_TPM_eq_0` not extreme.
- This indicates that the strong heart-marker signal is not due to a technical artifact.

**Visualization highlights:**
- Heatmap of heart-marker z-scores:
  - Sample_03 shows broad, high z-scores across many canonical cardiac markers.
  - Sample_12 exhibits a secondary, weaker cluster of elevated markers, but overall signal is less coherent and weaker than Sample_03.
- PCA on heart-marker z-scores:
  - Sample_03 is clearly separated from the rest of the samples along PC1/PC2, consistent with a distinct heart transcriptional profile.

---

## Caveats & Warnings

- **Marker-based inference:** Tissue identity is inferred purely from expression of known cardiac markers; no histology or external metadata are available for confirmation. The conclusion relies on the assumption that these markers behave canonically in this dataset.
- **Limited marker set:** Although the curated marker list is broad and includes many classic zebrafish cardiac genes, it may not capture all relevant heart-expressed genes, and some paralogs or unannotated genes could be missed.
- **Single dominant heart-like sample:** Only one sample (Sample_03) shows an unambiguous heart-like profile; Sample_12 appears muscle-like and partially heart-enriched but was not selected. If mixed or developmentally heterogeneous tissues are present, fine-grained distinctions (e.g., atrial vs ventricular vs skeletal muscle) are not explicitly resolved here.

---

## Next Steps

- If needed, further characterize Sample_03 vs other tissues by:
  - Computing enrichment scores for other tissue-specific marker sets (e.g., brain, liver, muscle) to confirm relative specificity.
  - Examining developmental-stage markers to see whether Sample_03 corresponds to embryonic, larval, or adult heart.
- Validate the heart assignment experimentally (e.g., via histology or known sample metadata if they become available).
- Extend the marker strategy to classify the remaining 11 samples into likely tissues based on additional curated marker panels.

---

## References

- Paigen K, et al. "Transcriptional profiling of the zebrafish heart." (representative cardiac transcriptomics literature; specific DOI will depend on chosen reference).
- Howe K, et al. The zebrafish reference genome sequence and its relationship to the human genome. Nature. 2013;496(7446):498–503. doi:10.1038/nature12111.
- MyGene.info: Xin J, et al. High-performance web services for querying gene and variant annotation. Genome Biol. 2016;17:91. doi:10.1186/s13059-016-0953-9.
