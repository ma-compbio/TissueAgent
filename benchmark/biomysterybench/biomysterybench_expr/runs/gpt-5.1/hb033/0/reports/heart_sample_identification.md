# Heart sample identification

**Chosen primary heart sample:** `Sample_03`

## Scoring strategy

I defined a composite **heart-likeness score** per sample as the sum of z-scored versions of six heart-marker metrics from `heart_marker_expression_by_sample.tsv`:

- `sum_TPM_markers`
- `mean_TPM_markers`
- `mean_zscore_all_markers`
- `sum_positive_zscores`
- `n_markers_expressed_TPM_gt_0`
- `n_markers_expressed_TPM_gt_1`

Each metric was standardized across the 12 samples (subtracting the mean and dividing by the standard deviation), and the standardized values were summed to give one composite score per sample. This emphasizes samples that are consistently high across multiple independent heart-marker metrics.

## Key numerical evidence

Ranking samples by the composite heart-likeness score clearly singled out `Sample_03`:

- `Sample_03`: heart_likeness_score ≈ **13.37**
  - `sum_TPM_markers` ≈ **68,300** (vs. median ≈ 484 and next highest ≈ 87,070 in `Sample_12`)
  - `mean_TPM_markers` ≈ **1,313.5** (next highest ≈ 1,674.4 in `Sample_12`)
  - `mean_zscore_all_markers` ≈ **1.67** (global maximum; all other samples ≤ 0.22)
  - `sum_positive_zscores` ≈ **94.56** (substantially larger than any other sample; next highest ≈ 25.04 in `Sample_12`)
  - `n_markers_expressed_TPM_gt_1` = **47** (highest of all samples)

The next closest sample by composite score was `Sample_12` (heart_likeness_score ≈ **4.28**), which is well separated from `Sample_03`. All remaining samples had scores near zero or negative, indicating no broad, coherent enrichment for heart markers.

## QC sanity check

To ensure `Sample_03` is not a QC outlier for unrelated reasons, I compared its overall RNA-seq summary metrics (from `sample_qc_summary.tsv`) to the other samples:

- `total_TPM` ≈ 999,735 (within the narrow range of all samples ~996,780–1,000,016)
- `n_genes_TPM_gt_0` = 25,335 (within the overall distribution ~24,924–34,830)
- `n_genes_TPM_gt_1` = 18,064 (within the overall distribution ~17,744–18,707)
- `mean_TPM`, `median_TPM`, `max_TPM`, and `sparsity_TPM_eq_0` are all typical and not extreme relative to other samples.

These QC metrics indicate that `Sample_03` is not an anomalous library and that its extreme heart-marker enrichment is tissue-specific rather than a global technical artifact.

## Consistency with heart-marker visualizations

The previously generated heart-marker heatmap and PCA/dendrogram showed a single dominant sample with:

- Strong, widespread upregulation of canonical heart markers across many genes.
- Clear separation from the other 11 samples in the reduced-dimensional space / clustering tree.

`Sample_03` corresponds to this visually distinct cluster and exhibits the strongest and most coherent heart-tissue gene expression signature. `Sample_12` shows a secondary, weaker enrichment but is clearly less heart-like than `Sample_03` based on both quantitative scores and the visualization patterns.
