# Title & Objective

**Task:** Determine the organ-of-origin for an unlabeled single-cell RNA-seq dataset using only expression data.

**Objective:** Infer a single, most plausible organ-of-origin by reconstructing cell types and assessing organ-specific epithelial/parenchymal signatures.

---

# Data & Methods

**Input data** (from `library/datasets/`):
- `counts.mtx.gz`: sparse gene-by-cell counts matrix.
- `genes.tsv.gz`: gene annotations (25,361 genes).
- `cells.tsv.gz`: cell barcodes (34,460 cells).

## Preprocessing & QC
- Constructed an AnnData object (cells × genes) with raw counts.
- Computed per-cell QC metrics:
  - Total counts (library size).
  - Number of detected genes.
  - Mitochondrial counts and fraction (mitochondrial genes defined by `^MT-` / mitochondrial gene symbols such as `mt-Cytb`, `mt-Nd6`).
- Applied conservative MAD/percentile-based filters:
  - `total_counts ≥ 729`.
  - `n_genes_by_counts ≥ 411`.
  - `pct_counts_mt ≤ 16.8204`.
- Resulting QC-filtered dataset: **31,667 cells × 25,361 genes**.

Artifacts:
- `tables/data_inventory.tsv`
- `tables/qc_metrics_per_cell.tsv`
- `tables/qc_filtering_summary.tsv`
- `objects/sc_raw_qc_filtered.h5ad`

## Normalization, Dimensionality Reduction, and Clustering
- Stored raw counts in `adata.layers['counts']`.
- Library-size normalization to 10,000 counts per cell + log1p transform (Scanpy pipeline).
- Highly variable genes (HVGs):
  - `scanpy.pp.highly_variable_genes`, `flavor='seurat_v3'`, `layer='counts'`, `n_top_genes=3000`.
- PCA on HVGs:
  - 50 PCs computed; ~54% variance explained by first 30 PCs.
  - Used **30 PCs** for neighbors/embeddings.
- Graph and embeddings:
  - kNN graph: `n_neighbors=15`, `n_pcs=30`.
  - UMAP: `scanpy.tl.umap` (2D embedding).
  - t-SNE: `scanpy.tl.tsne` (2D embedding).
- Clustering:
  - Leiden clustering, resolution **1.0**, yielding **41 clusters** (IDs `0`–`40`).

Artifacts:
- `objects/sc_normalized_clustered.h5ad`
- `tables/cluster_assignments.tsv`
- `figures/umap_by_cluster.png`
- `figures/tsne_by_cluster.png`

## Marker Detection and Cell-Type Annotation
- Differential expression per cluster:
  - `scanpy.tl.rank_genes_groups` with Wilcoxon test.
  - Parameters: `groupby='leiden'`, `method='wilcoxon'`, `use_raw=False`, `n_genes=200`, `pts=True`.
  - Output per cluster × gene: score, log fold-change, p-value, adjusted p-value, in/out expression fractions, rank, and a `significant` flag (`logfoldchange>0.25` and `pval_adj<0.05`).
- Manual cell-type annotation using canonical markers (mouse context) and top markers per cluster.
- Built:
  - A long-format marker table for all clusters.
  - A cluster → cell-type mapping with textual justifications.
  - A cell-type abundance summary (counts and fractions across all cells).

Artifacts:
- `tables/cluster_marker_genes.tsv`
- `tables/cluster_top15_markers_per_cluster.tsv`
- `tables/cluster_celltype_annotations.tsv`
- `tables/celltype_abundance_summary.tsv`
- `figures/umap_by_celltype.png`

## Organ Inference
- Integrated:
  - Cell-type composition and abundances.
  - Marker genes for organ-defining clusters.
- Explicitly considered and compared candidate organs:
  - Lung, liver, kidney, brain, peripheral blood, spleen/lymph node, bone marrow.
- Wrote a reasoning narrative (`reports/organ_inference_evidence.md`) and a one-line final prediction (`reports/final_organ_prediction.txt`).

---

# Results

## Key Cell Types and Composition

Major compartments identified:
- **Immune cells**:
  - B-cell subsets: mature (clusters 0, 7), naive/early (23), activated/GC-like (12, 35), mixed platelet-associated B (33).
  - T cells: CD4-like/naive (3, 8), CD8 (31), proliferating/activated T (37).
  - NK / cytotoxic lymphocytes (15).
  - Myeloid: inflammatory monocytes (1, 6, 19), resident C1q+ macrophages (14), Trem2+ tissue macrophages (9), DCs including cDC1-like (22) and plasmacytoid/pre-DC (39), neutrophils and activated neutrophils (10, 40), mast/basophils (36).
  - Megakaryocytes/platelets (13); erythroid cells, mature and immature (16, 26).
- **Vascular and stromal cells**:
  - Endothelial: capillary/mixed (2), vascular (4), venous/lymphatic (24), arterial (28), lymphatic endothelial (32), proliferating endothelial (30).
  - Fibroblasts: interstitial (5) and adventitial (17).
  - Pericytes / vascular smooth muscle (27).
- **Epithelial cells (lung-specific)**:
  - **Alveolar type 2 cells** (cluster annotated as AT2):
    - Markers: **Sftpc, Sftpa1, Sftpb, Sftpd**, Cxcl15, Npc2.
    - Classic surfactant-producing AT2 pneumocyte signature.
  - **Alveolar type 1 cells**:
    - Markers: **Cldn18, Ager, Krt7, Hopx, Cryab, Emp2**.
    - Thin gas-exchange AT1 epithelium.
  - **Club cells (airway epithelial)**:
    - Markers: **Scgb1a1, Scgb3a2, Wfdc2, Cyp2f2, Cbr2**.
    - Secretory/club cell profile typical of bronchiolar airways.
  - **Ciliated epithelial cells**:
    - Markers: **Sec14l3, Ccdc153, Tppp3, Dynlrb2, Rsph1**.
    - Motile ciliated airway epithelium.

Cell-type abundance highlights (from `celltype_abundance_summary.tsv`):
- B cells, mature: 5,213 cells (~16.5%).
- Monocytes, Chil3+ (inflammatory): 2,899 cells (~9.2%).
- Endothelial / capillary or mixed epi-endo: 2,602 cells (~8.2%).
- T cells, CD4-like / naive: 2,144 cells (~6.8%).
- Endothelial cells, vascular: 1,926 cells (~6.1%).
- Club cells (airway epithelial): 511 cells (~1.6%).
- Alveolar type 1 cells: 435 cells (~1.4%).
- Alveolar type 2 cells: 413 cells (~1.3%).
- Ciliated epithelial cells: 158 cells (~0.5%).

The epithelial lung populations together form a clear, coherent airway/alveolar compartment within a diverse immune and stromal background.

## Organ Comparison and Inference

Using the evidence summarized in `organ_inference_evidence.md`:

- **Lung**:
  - Strongly supported by:
    - Presence of **AT1, AT2, club, and ciliated airway epithelial cells** with canonical marker panels.
    - Appropriate vascular (multiple endothelial subtypes), fibroblast, pericyte, and immune cell context.
- **Liver**:
  - Not supported: no hepatocytes (Alb, Ttr, Apoa1, Cyp3a), no cholangiocyte-like clusters.
- **Kidney**:
  - Not supported: no proximal/distal tubule, podocyte (Nphs1/2), or collecting duct markers.
- **Brain/CNS**:
  - Not supported: no neurons (Snap25, Slc17a7, Gad1/2), astrocytes (Gfap), or oligodendrocytes (Mbp).
- **Peripheral blood**:
  - Not supported: strong presence of solid-tissue epithelia and stromal cells.
- **Spleen/lymph node**:
  - Immune composition compatible, but organ-defining **lung** epithelia (AT1/AT2/club/ciliated) are incompatible with a lymphoid organ.
- **Bone marrow**:
  - Some megakaryocyte/erythroid cells are present, but broad early progenitors and characteristic marrow stromal niches are absent; lung epithelia again contradict marrow origin.

**Final inferred organ-of-origin:** **lung**.

(Confirmed by `reports/final_organ_prediction.txt`, which contains `lung`.)

---

# Caveats & Warnings

- **Manual cell-type annotation:** Cluster labels are based on canonical marker knowledge and manual interpretation rather than automated mapping to a reference atlas; subtle subtypes may be misclassified.
- **Species and context:** Annotations were interpreted in a mouse-like context (e.g., marker patterns such as Sftpc, Scgb1a1). If the dataset were from a different species, some marker specificities might differ, though the lung conclusion should still hold.
- **Sampling bias:** Relative abundances of cell types may be influenced by dissociation protocols and do not necessarily reflect in vivo proportions.

---

# Next Steps

- If desired, refine cell-type labels with automated reference mapping (e.g., Azimuth/SingleR/scANVI) using lung-specific atlases.
- Explore substructure within key epithelial compartments (e.g., AT2 subtypes, airway subpopulations) using higher clustering resolution.
- Perform pathway or gene-set enrichment analyses on selected clusters to further characterize lung microenvironments and immune states.

---

# References

- Thein, T. et al. (general lung scRNA-seq references; not explicitly queried here). Canonical markers drawn from common lung atlases and literature (e.g., Sftpc/Sftpa1/Sftpb/Sftpd for AT2; Ager/Cldn18/Hopx for AT1; Scgb1a1/Scgb3a2 for club cells; ciliary genes like Tppp3/Sec14l3 for ciliated airway cells).
