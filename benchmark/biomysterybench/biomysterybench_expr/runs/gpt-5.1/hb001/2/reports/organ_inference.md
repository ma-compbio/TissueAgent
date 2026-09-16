# Organ of origin inference

## Final organ call

**spleen**

## Dataset overview

- **Species:** mouse (from species_inference.txt: high mouse-like gene name fraction and canonical mouse markers such as Actb, Alb, Cd14, Cd3d, Epcam, Pecam1).
- **Cells:** 34,460 cells; 25,361 genes detected (qc_metrics.tsv).
- **High-level composition:**
  - Multiple large lymphoid clusters (B and T cells) with canonical markers.
  - Several macrophage / monocyte / dendritic clusters.
  - Prominent endothelial and stromal clusters.
  - A lung-like epithelial/AT2 cluster is present but not dominant in cell number.

## Evidence from organ signature scores

### Global organ scores

From organ_signature_scores.tsv (rows with `cluster_id == "all"`):

- **spleen:** mean_signature_score = 0.722, fraction_cells_signature_positive = 0.917, mean_fraction_genes_detected = 0.328
- **blood_immune:** score = 0.524, fraction_cells_signature_positive = 0.948
- **lung:** score = 0.178, fraction_cells_signature_positive = 0.715
- All other organs (kidney, liver, brain, intestine, pancreas, skin, heart) have substantially lower mean_signature_score (< 0.1) and lower fractions of signature-positive cells.

Interpretation: Across all cells, spleen signatures are the strongest and most coherent, with a high fraction of cells expressing multiple spleen signature genes. A generic blood_immune program is also very strong, consistent with a lymphoid organ.

### Top organ per cluster

Using organ_signature_scores.tsv for each cluster_id (excluding the global "all" row), the top-scoring organ per cluster shows:

- **Top organ counts across clusters:**
  - spleen: 16 clusters
  - blood_immune: 15 clusters
  - kidney: 4 clusters
  - liver: 3 clusters
  - lung: 3 clusters
  - heart: 1 cluster
- Among the largest clusters by n_cells_in_cluster (0–7):
  - Cluster 0 (4042 cells): top spleen (score 1.86), second blood_immune (0.72).
  - Cluster 1 (2207 cells): top blood_immune (0.76), second spleen (0.32).
  - Cluster 2 (2054 cells): top spleen (0.30), second kidney (0.28).
  - Cluster 3 (2049 cells): top blood_immune (0.54), second spleen (0.13).
  - Cluster 4 (2039 cells): top kidney (0.53), second spleen (0.49) – a kidney-associated myeloid cluster.
  - Cluster 5 (2020 cells): top spleen (1.80), second blood_immune (0.76).
  - Cluster 6 (1804 cells): top blood_immune (0.82), second spleen (0.69).
  - Cluster 7 (1139 cells): top liver (0.26), second spleen (0.24) – likely generic stromal cells.

Interpretation: Most major clusters are best explained by spleen or blood_immune signatures, indicating that the dominant cell states are hematopoietic / lymphoid and that spleen-specific genes are strongly and repeatedly enriched.

## Evidence from cluster markers (cluster_markers_top50_per_cluster.tsv)

### Major clusters and canonical cell types

Among the largest clusters (0–7), the top marker genes clearly correspond to classic splenic and immune cell populations:

- **Cluster 0 (B cells; 4042 cells):**
  - Top markers: Ighm, Cd79a, Cd79b, Ebf1, Igkc, Iglc2, Ms4a1, Ighd, Cd37, Cd74, H2-Aa.
  - Interpretation: Strong B cell receptor and MHC-II expression, consistent with splenic B cells / germinal center-like B cells.

- **Cluster 1 (T cells; 2207 cells):**
  - Top markers: Trbc2, Cd3d, Cd3g, Cd3e, Il7r, Bcl11b, Trac, Tcf7.
  - Interpretation: Canonical T cell receptor and T cell differentiation markers, consistent with naive/activated T cells in spleen.

- **Cluster 2 (monocyte / macrophage-like; 2054 cells):**
  - Top markers: Atp6v0d2, Ctsd, Chil3, Lpl, Mrc1, Mpeg1, Pld3.
  - Interpretation: Phagocytic and macrophage activation genes, consistent with splenic red pulp macrophages or monocyte-derived cells.

- **Cluster 3 (endothelial cells; 2049 cells):**
  - Top markers: Calcrl, Ptprb, Cdh5, Ramp2, Cd93, Egfl7, Pecam1, Clec14a, Aqp1, Cldn5.
  - Interpretation: Vascular endothelial cells, expected in spleen vasculature.

- **Cluster 4 (C1q+/Lyz2+ macrophages; 2039 cells):**
  - Top markers: C1qb, C1qa, C1qc, Ctss, Lyz2, Wfdc17, Apoe, Trem2, C3ar1, Csf1r.
  - Interpretation: Classic macrophage / monocyte signature including complement, lysozyme, and CSF1 receptor; fits splenic macrophages.

- **Cluster 5 (endothelial / lung-associated; 2020 cells):**
  - Top markers: Epas1, Adgrf5, Ly6a, Ly6c1, Calcrl, Slco2a1, Egfl7, Ifitm3, **Scgb1a1**.
  - Interpretation: Mix of endothelial/vascular and club cell (Scgb1a1) markers; suggests a subset of pulmonary or vascular endothelium with airway-associated contamination.

- **Cluster 6 (monocytes / dendritic / myeloid; 1804 cells):**
  - Top markers: Lst1, Csf1r, Clec4a3, Cybb, Clec4a1, Coro1a, Ms4a6c, Cebpb, Ifitm6, Cx3cr1, Ptprc.
  - Interpretation: Myeloid and antigen-presenting cells; common in spleen and blood.

- **Cluster 7 (stromal / fibroblasts; 1139 cells):**
  - Top markers: Mgp, Bgn, Sparc, Col3a1, Col1a2, Col1a1, Mfap4, Dpt, Pcolce2, Eln.
  - Interpretation: Collagen-rich stromal fibroblasts; compatible with splenic capsule and trabeculae.

Across all clusters, canonical immune markers (Cd3d/e, Cd79a, Ms4a1, Ptprc, Lyz2, S100a8, S100a9), endothelial marker Pecam1, and stromal collagens (Col1a1/Col3a1) are abundant. Lung-specific epithelial markers (**Scgb1a1, Sftpc, Sftpa1**) and proliferative marker **Top2a** are present but confined to smaller subsets/clusters.

## Global top expressed genes (global_top_expressed_genes.tsv)

Among the top ~200 globally expressed genes:

- **Spleen signature overlap:** Cd74, H2-Aa, H2-Ab1 are among the most highly expressed, matching organ_signature_definitions for spleen.
- **Blood_immune signature overlap:** Lyz2 and Ptprc are in the global top 200.
- **Lung signature overlap:** Only a single lung signature gene (Sftpc) appears among the top 200, and it is restricted to a subset of cells.

This pattern reinforces that splenic and generic immune programs dominate the dataset-wide expression landscape.

## Integrating the evidence to choose a single organ

1. **Organ signatures:** Spleen has the highest global signature score and the largest fraction of signature-positive cells. It is also the most frequent top organ across clusters, including the largest B cell, macrophage, and mixed immune clusters.
2. **Cell-type composition:** The dataset is dominated by B cells, T cells, and multiple macrophage/monocyte/dendritic clusters, plus supporting endothelial and stromal populations. This composition is characteristic of a secondary lymphoid organ, particularly spleen, which harbors large B and T zones, red pulp macrophages, and vascular/stromal infrastructure.
3. **Marker genes:** Cluster markers highlight classic splenic immune cell markers (Ighm, Cd79a/b, Ms4a1, Cd74, H2-Aa/H2-Ab1 in B cells; Cd3d/e, Trbc2, Il7r, Tcf7 in T cells; C1qa/b/c, Lyz2, Csf1r in macrophages) as major drivers of cluster identity. These are more consistent with spleen than with a primary hematopoietic organ like bone marrow or a peripheral tissue with resident immune cells.
4. **Alternative organ signatures:** Lung, kidney, and liver signatures are detectable in some clusters (e.g., Scgb1a1/Sftpc-positive lung-like cells; kidney-like myeloid cluster; generic liver/stromal signatures), but their global signature scores are much lower than spleen, and they are confined to relatively small subpopulations.

Taken together, the quantitative organ scores and the biological interpretation of cluster markers strongly support **spleen** as the single best-fitting organ of origin for this mouse scRNA-seq dataset.

## Alternative possibilities and why they are less consistent

- **blood_immune (peripheral blood or generic immune compartment):**
  - Pros: Strong global blood_immune signature; many clusters are T cells, B cells, and myeloid cells typical of circulating or lymphoid immune populations.
  - Cons: The presence of robust spleen-specific signature enrichment across many clusters (including high expression of MHC-II and splenic signature genes such as Cd74, H2-Aa, H2-Ab1) and the strong global spleen score argue for an organized secondary lymphoid tissue rather than peripheral blood, which would lack structured stromal and endothelial niches to this extent.

- **lung:**
  - Pros: Clear lung-related markers (Scgb1a1, Sftpc, Sftpa1) are present in specific clusters, and lung has a non-zero global signature score.
  - Cons: Lung is not the dominant signature globally; lung-specific markers are confined to a minority of cells. The majority of cells show lymphoid and splenic signatures rather than a typical mixture of airway/alveolar epithelial, endothelial, and interstitial cells expected in a primary lung dataset.

- **kidney or liver:**
  - Pros: Some clusters show kidney or liver as the top organ by score, mostly in stromal or myeloid compartments.
  - Cons: Global kidney and liver scores are low, and key parenchymal markers (e.g., Alb for hepatocytes, classic nephron segment markers) are absent from the dominant clusters. These organs are therefore unlikely to be the source tissue.

Overall, while there is evidence for a mixture of immune and some tissue-resident cells (including lung-like epithelium), the strongest and most coherent signal across the dataset is that of a **mouse spleen** sample.
