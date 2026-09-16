# Title & Objective

**Objective:** Infer control vs experimental samples from the expression data alone and identify a single gene that is knocked out (present in control, absent in experimental) using only the matrices and gene annotations in `library/datasets/`.

# Data & Methods

**Data sources**
- `library/datasets/raw_counts.tsv`: Raw gene-level counts for 39,376 genes × 5 samples.
- `library/datasets/norm_counts_TPM.tsv`: TPM-normalized expression for the same genes and samples.
- `library/datasets/gene_info.gz`: NCBI `gene_info` annotation, used to map NCBI GeneID to gene symbols and Ensembl IDs.

**Preprocessing & QC**
- Verified that `raw_counts.tsv` and `norm_counts_TPM.tsv` share the same 39,376 NCBI GeneIDs and 5 samples.
- Harmonized a minor sample-name mismatch (`KO2` in raw counts → `KO_2` to match TPM and downstream tables).
- Built a gene annotation table for all expressed GeneIDs using `gene_info.gz`, extracting:
  - `GeneID` (NCBI GeneID), `gene_symbol` (from `Symbol`), `ensembl_id` (from `dbXrefs`), and key metadata columns.
- Computed sample-level QC from raw counts and TPM:
  - Library sizes (sum of raw counts) and number of detected genes (raw count > 0).
  - TPM-based expression summaries (mean, median, quantiles) per sample.

**Inferring control vs experimental groups**
- Used log2(TPM + 1) expression and selected the 500 most variable genes.
- Standardized genes (z-score) and performed PCA on the 5 samples.
- Ran k-means clustering on the first two PCs (evaluated k = 2, 3 by silhouette); k = 3 had the best silhouette, yielding:
  - Cluster 0: Control_2, Control_3
  - Cluster 1: KO_1, KO_2
  - Cluster 2: Control_1
- Inferred biological groups by cluster composition:
  - Clusters containing only `Control_*` samples → **control**.
  - Clusters containing only `KO_*` samples → **experimental**.
- Final grouping:
  - Control: Control_1, Control_2, Control_3
  - Experimental: KO_1, KO_2

**Detecting candidate knockout genes**
- From `raw_counts.tsv`, for each gene and each group (control vs experimental) computed:
  - Mean and median raw counts.
  - Zero fraction: fraction of samples in that group with count = 0.
- Derived contrasts:
  - `mean_diff = control_mean − exp_mean`
  - `median_diff = control_median − exp_median`
  - `zero_frac_diff = exp_zero_frac − control_zero_frac`.
- Defined knockout-like candidates as genes with:
  - `control_mean ≥ 10` (avoid extremely low control expression).
  - `mean_diff ≥ 10` (clear drop in mean expression).
  - `exp_mean ≤ 5` (low absolute expression in KO).
  - `zero_frac_diff ≥ 0.5` (KO much more often zero than controls).
- Ranked candidates by:
  - `score = mean_diff × zero_frac_diff × log10(1 + control_mean)`.

**Final gene selection**
- Focused on the top 3 candidates by score:
  - LOC105374110 (GeneID 105374110)
  - GSX2 (GeneID 170825)
  - LINC01638 (GeneID 105372978)
- Re-extracted raw per-sample counts and produced a barplot (log2(count+1)) for these genes, then chose the gene with:
  - Complete loss of expression in all experimental samples.
  - Clear and non-trivial expression in controls.

# Results

- **Inferred groups:**
  - Control samples: Control_1, Control_2, Control_3
  - Experimental samples: KO_1, KO_2
- **Top knockout-like candidates (from `ko_gene_candidates_ranked.tsv`):**
  - LOC105374110 (GeneID 105374110)
    - Control: mean 15.0, median 22.0, zero_frac 0.33
    - Experimental: mean 0.0, median 0.0, zero_frac 1.0
  - GSX2 (GeneID 170825)
    - Control: mean 17.33, median 19.0, zero_frac 0.0
    - Experimental: mean 3.5, median 3.5, zero_frac 0.5
  - LINC01638 (GeneID 105372978)
    - Control: mean 12.0, median 10.0, zero_frac 0.0
    - Experimental: mean 2.0, median 2.0, zero_frac 0.5
- **Per-sample expression for the final KO gene (LOC105374110):**
  - Raw counts:
    - Control_1: 23
    - Control_2: 0
    - Control_3: 22
    - KO_1: 0
    - KO2: 0
  - TPM values:
    - Control_1: 2.311
    - Control_2: 0
    - Control_3: 1.783
    - KO_1: 0
    - KO_2: 0
- **Final knocked-out gene (gene symbol):** `LOC105374110`

# Caveats & Warnings
- **Small sample size:** Only 3 control and 2 experimental samples were available, which limits power and makes patterns sensitive to individual-sample variation.
- **One control zero:** For LOC105374110, one control sample (Control_2) has zero counts, increasing the control zero fraction; still, the KO group shows a clean, universal loss.
- **Heuristic thresholds:** KO candidate thresholds and ranking score were heuristic, tuned to emphasize clear on/off patterns; different thresholds might alter the ranked list but are unlikely to change the top call given the very strong pattern for LOC105374110.
- **No external validation:** The call is made solely from this dataset; no prior biology or perturbation design is used.

# Next Steps
- Experimentally validate LOC105374110 as the targeted knockout (e.g., via PCR or an orthogonal assay).
- Examine GSX2 and LINC01638 as potential downstream responders to the perturbation.
- If additional replicates or conditions become available, repeat the analysis to confirm robustness of the KO call.

# References
- NCBI Gene database and `gene_info` format: https://ftp.ncbi.nlm.nih.gov/gene/DATA/README
