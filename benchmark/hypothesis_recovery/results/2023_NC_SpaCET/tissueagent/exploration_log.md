# Exploration log — SpaCET tumor spatial transcriptomics dataset

## 1. Dataset structure

- AnnData object loaded from `library/datasets/dataset.h5ad` with **3,798 observations (spots)** and **36,601 variables (genes)**.
- `adata.X` is a `scipy.sparse.csc_matrix` of shape (3798, 36601) with `float32` counts.
- `.obs` columns: `bc_short`, `in_tissue`, `array_row`, `array_col`, `score_CAF`, `score_M2`, `score_malignant`, `score_Tcell`, plus QC columns `n_counts` and `n_genes` computed in this session.
- `.var` columns: `gene_ids`, `feature_types`.
- `.obsm` keys: `spatial` (array of shape (3798, 2), `float64`).
- `.uns` keys: `paper_id`, `sample_id`, `source`.
- No additional `.layers` are present.

## 2. Observation-level metadata

### 2.1 In-tissue flag and array grid structure

- `in_tissue` values: all 3,798 spots have `in_tissue = 1`.
- `array_row` ranges from 0 to 76; `array_col` ranges from 5 to 123.
- A `pandas.crosstab` of `array_row` vs `array_col` shows a grid of shape **(77, 119)**.
- Number of occupied grid positions (spots actually present): **3,798**.
- Total possible grid positions in this row–column range: **9,163**.
- Fraction of occupied positions: **~0.41**.

**OBSERVATION 1.** The Visium-like array grid defined by `array_row` (0–76) and `array_col` (5–123) is only partially occupied: 3,798 observed spots out of 9,163 possible positions (about 41% occupancy), as quantified from the `pandas.crosstab` of `array_row` vs `array_col`.

### 2.2 Precomputed lineage / state scores

- Columns: `score_CAF`, `score_M2`, `score_malignant`, `score_Tcell` (all `float64`).
- Summary statistics (`adata.obs[score_*].describe()`):
  - `score_CAF`: mean ~5.58, median ~2.85, min ~-5.28, max ~180.85.
  - `score_M2`: mean ~0.12, median ~0.03, min ~-1.40, max ~3.99.
  - `score_malignant`: mean ~44.49, median ~32.80, min ~0.16, max ~280.78.
  - `score_Tcell`: mean ~0.009, median ~-0.079, min ~-1.32, max ~6.00.
- Histograms (via `seaborn.histplot` with 30 bins for each score) show:
  - `score_CAF` and `score_malignant` have right-skewed distributions with a tail of high-scoring spots.
  - `score_M2` and `score_Tcell` are more tightly centered around 0 with smaller ranges.

**OBSERVATION 2.** The distributions of `score_CAF` and `score_malignant` are strongly right-skewed, with most spots at low-to-moderate values and a minority of spots forming a high-score tail (as seen in the `describe()` summary and score histograms), whereas `score_M2` and `score_Tcell` are more narrowly distributed around zero.

### 2.3 Per-spot QC metrics (computed)

- Using `adata.X`, per-spot total counts (`n_counts`) and detected genes (`n_genes`) were computed and stored in `.obs`.
- Summary for `n_counts` (`pd.Series(n_counts).describe()`):
  - mean ~21,815; median ~20,762; min 578; max 81,624.
- Summary for `n_genes`:
  - mean ~5,622; median ~6,027; min 430; max 10,153.

**OBSERVATION 3.** The total RNA counts per spot (`n_counts`) and the number of detected genes per spot (`n_genes`) both vary substantially across the array (e.g., approximately 140-fold range in `n_counts` from 578 to 81,624 and over 20-fold range in `n_genes` from 430 to 10,153), based on the computed per-spot QC summaries.

## 3. Variable-level metadata and expression sparsity

- `.var` contains two columns:
  - `gene_ids` (`object`): Ensembl gene identifiers.
  - `feature_types` (`category`): includes at least the category `Gene Expression`.
- Non-zero counts per gene were computed from `adata.X` as `(X > 0).sum(axis=0)`.
- Summary of non-zero counts per gene:
  - median non-zero spots per gene: 19.
  - 25th percentile: 0 spots; 75th percentile: 883 spots.
  - minimum: 0 spots; maximum: 3,798 spots.

**OBSERVATION 4.** Gene detection is highly heterogeneous: half of the genes are detected in at most 19 spots (median), while a subset of genes are expressed broadly (up to all 3,798 spots), as quantified by the distribution of non-zero counts per gene.

## 4. Spatial coordinate structure

- `.obsm['spatial']` is an array of shape (3798, 2) with `float64` values.
- These coordinates were used directly for spatial plotting with `matplotlib.scatter`, with the y-axis inverted for histology-like orientation.

**OBSERVATION 5.** The spatial coordinates in `.obsm['spatial']` form a contiguous 2D arrangement of spots consistent with the underlying grid defined by `array_row`/`array_col`, as seen by overlaying spot positions from `.obsm['spatial']` and confirming that all 3,798 spots have associated 2D coordinates.

## 5. Spatial patterns of lineage / state scores

Using `matplotlib.pyplot.scatter`, spatial maps were generated for `score_CAF`, `score_malignant`, and `score_Tcell`, coloring each spot by its score and plotting at positions from `.obsm['spatial']`.

- `score_CAF` spatial map:
  - Shows clusters of higher CAF scores localized to certain contiguous regions, rather than being uniformly dispersed.
- `score_malignant` spatial map:
  - Exhibits extended regions with elevated malignant scores that form continuous patches of high-intensity spots.
- `score_Tcell` spatial map:
  - Displays localized areas with relatively higher T cell scores, with other regions showing lower or near-zero values.

**OBSERVATION 6.** Spatial scatterplots of `score_CAF`, `score_malignant`, and `score_Tcell` (each spot colored by its respective score at `.obsm['spatial']` coordinates) reveal that high-scoring spots for each score tend to form contiguous patches rather than being randomly interspersed across the tissue.

## 6. Spatial patterns of basic QC metrics

Spatial scatterplots were generated for `n_counts` and `n_genes` using `.obsm['spatial']`.

- `n_counts` spatial map:
  - Shows gradients where certain regions of the array have systematically higher total counts.
- `n_genes` spatial map:
  - Closely parallels `n_counts`, with regions of higher detected gene numbers overlapping with regions of higher counts.

**OBSERVATION 7.** Spatial plots of `n_counts` and `n_genes` show non-uniform coverage: areas of the array with higher total counts generally coincide with areas of higher detected gene numbers, indicating spatial gradients in sequencing depth or capture efficiency.

## 7. Example gene-level spatial expression patterns

To explore basic gene-level patterns, per-gene mean and variance were computed from `adata.X`. Genes expressed in at least 10% of spots were ranked by variance, and three genes (`MGP`, `IGKC`, `COX6C`) with high variance were selected for visualization. For each of these genes, expression values were extracted and plotted over `.obsm['spatial']` coordinates using `matplotlib.scatter`.

- `MGP`:
  - Expression hotspots occur in a subset of contiguous spots, while many spots show lower or zero expression.
- `IGKC`:
  - Expression is concentrated in specific regions with clusters of high values and large areas with little or no expression.
- `COX6C`:
  - More broadly expressed, but still shows spatial variation with areas of relatively higher expression.

**OBSERVATION 8.** Spatial expression maps of the high-variance genes `MGP`, `IGKC`, and `COX6C` (selected by variance among genes expressed in ≥10% of spots) show that each gene has its own distinct spatial pattern: some genes (e.g., `MGP`, `IGKC`) are confined to localized clusters of spots, whereas others (e.g., `COX6C`) are more widespread but still spatially heterogeneous.

## 8. Summary for downstream hypothesis generation

- The dataset comprises a single Visium-like spatial transcriptomics sample with 3,798 in-tissue spots and 36,601 gene features.
- Core structural elements include positional metadata (`array_row`, `array_col`, `.obsm['spatial']`), precomputed lineage/state scores (`score_CAF`, `score_M2`, `score_malignant`, `score_Tcell`), and basic gene annotations (`gene_ids`, `feature_types`).
- Spot-level QC metrics (`n_counts`, `n_genes`) and gene-level detection statistics highlight substantial variability across both spots and genes.
- Spatial visualizations of scores, QC metrics, and selected genes demonstrate clear non-uniform, region-like patterns without specifying biological interpretations at this stage.

These observations provide a structural and spatial overview of the dataset that can be used to anchor more detailed, hypothesis-driven spatial analyses in subsequent steps.