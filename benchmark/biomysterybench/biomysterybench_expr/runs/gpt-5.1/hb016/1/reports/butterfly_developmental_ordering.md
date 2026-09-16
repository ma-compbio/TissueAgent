# Title & Objective

**Objective:** Infer the correct developmental chronology across five time points in a Bicyclus anynana RNA-seq dataset using only the expression matrix (no labels), and group replicate samples for each stage. The end goal is an ordered list of developmental stages from earliest to latest, each with its replicate sample IDs.

# Data & Methods

**Data sources**
- `library/datasets/butterfly_data.csv`: Gene-by-sample RNA-seq expression matrix for 15 samples and 16,420 genes.

**Pre-processing and QC**
- Loaded `butterfly_data.csv` as an AnnData object, oriented as samples × genes (15 × 16,420).
- Computed per-sample QC metrics:
  - Total expression (sum over all genes).
  - Number of detected genes (expression > 0).
  - Mitochondrial fraction left as missing (no annotation available).

**Normalization & feature selection**
- Library-size normalization to 10,000 counts per sample followed by log1p transform:
  - Implemented via `normalize_total(target_sum=1e4)` and `log1p` on the main expression matrix.
  - Stored original library sizes in `obs['lib_size']` and normalization metadata in `uns['normalization']`.
- Filtered lowly expressed genes, retaining genes expressed in at least 3 samples:
  - Reduced genes from 16,420 to 14,517.
- Selected 2,000 highly variable genes (HVGs) using a Seurat-style method:
  - Marked in `var['highly_variable']`.

**Dimensionality reduction & clustering**
- Scaled HVGs and performed PCA:
  - 10 principal components (PCs) computed on HVGs.
  - Stored PC scores in `obsm['X_pca']`; PC1 and PC2 also stored in `obs['PC1']`, `obs['PC2']`.
- Clustered samples into 5 groups using k-means on 10D PCA space:
  - `k = 5`, `random_state = 0`, `n_init = 50`.
  - Cluster labels stored as:
    - `obs['cluster_numeric']` ∈ {0,…,4}.
    - `obs['cluster_id']` ∈ {C1,…,C5}.

**Trajectory inference and stage ordering**
- Used PC1 as a one-dimensional pseudotime proxy:
  - `obs['pseudotime'] = obs['PC1']`.
- For each cluster (C1–C5), computed mean and SD of pseudotime and number of samples.
- Ordered clusters by increasing mean pseudotime and mapped them to developmental stages:
  - Stage_1 → earliest; Stage_5 → latest.
- Merged stage ordering with sample–cluster assignments to obtain final stage → sample mapping.

# Results

**Cluster-level pseudotime (from earliest to latest)**
- Stage_1 → C3 (cluster_numeric 2): mean_pseudotime ≈ -36.43 (n = 3)
- Stage_2 → C1 (cluster_numeric 0): mean_pseudotime ≈ -8.78 (n = 3)
- Stage_3 → C4 (cluster_numeric 3): mean_pseudotime ≈ 1.29 (n = 3)
- Stage_4 → C2 (cluster_numeric 1): mean_pseudotime ≈ 11.57 (n = 4)
- Stage_5 → C5 (cluster_numeric 4): mean_pseudotime ≈ 42.73 (n = 2)

**Final developmental stage assignment (earliest → latest)**
- Stage_1: Sample_13, Sample_14, Sample_15 (cluster_id = C3)
- Stage_2: Sample_7, Sample_8, Sample_9 (cluster_id = C1)
- Stage_3: Sample_4, Sample_5, Sample_6 (cluster_id = C4)
- Stage_4: Sample_1, Sample_2, Sample_3, Sample_11 (cluster_id = C2)
- Stage_5: Sample_10, Sample_12 (cluster_id = C5)

# Caveats & Warnings
- **PC1 as pseudotime proxy:** Developmental ordering is inferred purely from PC1 of the HVG-based PCA. While PC1 often captures the dominant biological gradient (here interpreted as development), no external validation or gene-set enrichment was available to confirm directionality.
- **Small sample size:** With only 15 samples and unsupervised clustering, fine-grained stage boundaries cannot be assessed; stages represent 5 coarse groups.
- **No external labels or annotations:** The inferred stages are relative (Stage_1–Stage_5) and not directly mapped to named biological time points (e.g., embryo/larva/pupa), since no such metadata were provided.

# Next Steps
- Validate the inferred stage ordering using known developmental marker genes (if such annotations become available) to confirm that PC1 aligns with biological time.
- Explore alternative trajectory methods (e.g., principal curves along PCA space) to test robustness of the inferred ordering.
- Perform differential expression analyses between adjacent stages (Stage_1 vs Stage_2, etc.) to identify genes driving developmental transitions.

# References
- Luecken MD, Theis FJ. Current best practices in single-cell RNA-seq analysis: a tutorial. Mol Syst Biol. 2019;15(6):e8746. doi:10.15252/msb.20188746.
- Stuart T, et al. Comprehensive integration of single-cell data. Cell. 2019;177(7):1888-1902.e21. doi:10.1016/j.cell.2019.05.031.
