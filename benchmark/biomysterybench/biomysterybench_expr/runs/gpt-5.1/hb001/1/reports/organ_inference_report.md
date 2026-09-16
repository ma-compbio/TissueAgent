# Organ / Tissue Inference from scRNA-seq Dataset

## Overview

Using global gene statistics and cluster-level marker genes, I inferred the most likely organ or tissue of origin for this single-cell RNA-seq dataset by comparing the observed expression and marker patterns to curated organ-specific gene signatures.

Candidate organs/tissues included: lung, liver, kidney, heart, brain, spleen, bone marrow, thymus, lymph node, intestine, and skin.

## Reference Signatures

For each organ/tissue, I assembled literature-based marker gene signatures (mouse-centric), focusing on genes that are relatively specific or strongly enriched in those organs:

- **Lung**: surfactant-associated and epithelial markers (e.g., Sftpa1, Sftpb, Sftpc, Sftpd, Ager, Pdpn, Scgb1a1, Scgb3a2, Cyp2f2, Wfdc2, Foxj1, Dnah5, Cfap53, Aqp5, Muc1, Krt8, Krt18).
- **Liver**: hepatocyte and secreted plasma proteins (e.g., Alb, Ttr, Apoa1/2, Apoc3, Serpina1a/c, fibrinogen genes Fga/Fgb/Fgg, various Cyp enzymes).
- **Kidney**: tubular and podocyte markers (e.g., Slc34a1, Umod, Aqp2, Nphs1/2, Kcnj1/16, Lrp2, Cdh16, Pax8).
- **Heart**: cardiomyocyte contractile genes (e.g., Tnnt2, Tnni3, Tnnc1, Myh6/7, Actc1, Myl2/3/7, Ryr2, Pln, Mb).
- **Brain**: neuronal and glial markers (e.g., Snap25, Syt1, Rbfox3, Slc17a7/6, Gad1/2, Gfap, Aqp4, Mbp, Plp1, Mog).
- **Spleen**: B- and T-zone and red-pulp markers (e.g., Cd79a, Cd79b, Ms4a1, Cd74, H2-Aa, H2-Ab1, H2-Eb1, Ltb, Ccr7, Cxcr5, Hba-a1, Hbb-bt, Pf4, Ppbp).
- **Bone marrow**: erythroid/megakaryocyte progenitors (e.g., Hba-a1/2, Hbb-bt/bs, Alas2, Klf1, Gata1, Ppbp, Pf4, Itga2b, Mpl, Gfi1b).
- **Thymus**: developing T cells (e.g., Rag1/2, Dntt, Ptcra, Il7r, Ccr9, Ccl25, Cd4, Cd8a/b1, Themis, Bcl11b, Pdia3).
- **Lymph node**: T-zone stromal and lymphocyte markers (e.g., Ccl19, Ccl21a, Cxcl13, Pdpn, Reln, Il7, Ccr7, Cd3d, Cd4, Cd8a, Cd28).
- **Intestine**: epithelial and Paneth/goblet markers (e.g., Muc2, Muc13, Lgr5, Vil1, Alpi, Reg3b/g, Krt20, Fabp2, Apoa1, Apoa4).
- **Skin**: keratinocyte/basal cell markers (e.g., Krt5, Krt14, Krt1, Krt10, Lor, Dsc1, Dmkn, Ppl).

These signatures were compared to:

1. **Global gene statistics** (`global_gene_statistics.tsv`): detection rate and mean log expression across all cells.
2. **Cluster marker genes** (`cluster_marker_genes.tsv`): per-cluster differential markers with scores and log2 fold-changes.

## Scoring Strategy

### 1. Global Expression-Based Scores

For each organ/tissue signature, I computed:

- Number of signature genes present in the dataset and **coverage fraction**.
- **Mean/median detection rate** and **sum of detection rates** for signature genes across all cells.
- Mean log-expression of signature genes.

These metrics quantify how strongly and ubiquitously each organ’s signature is expressed in the dataset as a whole.

### 2. Cluster Marker-Based Scores

Using the top 200 markers per cluster (ranked by the `score` column), I calculated for each organ:

- **Total overlaps across clusters**: total count of signature genes appearing among top cluster markers.
- **Number of clusters with any overlap**: how broadly the signature is represented across distinct cell populations.
- **Best-supporting cluster**: the cluster with the largest overlap between its top markers and the organ signature:
  - Raw overlap count.
  - Fraction of the organ’s signature captured in that cluster.
  - Fraction of that cluster’s top markers accounted for by the signature.
- **Union overlap**: fraction of signature genes that appear in the union of all clusters’ top markers.

### 3. Combined Organ Score and Ranking

To obtain a single rank per organ, I:

1. Standardized (z-scored) the **global mean detection rate** and the **best-cluster overlap count** across organs.
2. Defined a **combined score** as the sum of these two z-scores.
3. Ranked all candidate organs by this combined score.

The resulting table is saved as:

- `project/outputs/tables/organ_signature_scores.tsv`

## Key Observations from the Data

### Immune and Stromal Composition

Cluster-level markers reveal a rich immune and stromal landscape:

- **B cell clusters** (e.g., cluster 0, 11, 17, 23): strongly express **Cd79a, Cd79b, Igkc, Ighm, Ighd, Ms4a1, Cd74, H2-Aa, H2-Ab1, H2-Eb1, Ltb**, all typical of mature B cells and antigen-presenting B cells.
- **T cell clusters** (e.g., cluster 2, 20, 23): markers include **Trbc2, Cd3d, Cd3e, Cd8a, Cd4**, and in cluster 20 also **Rag1, Dntt, Themis, Bcl11b**, consistent with developing T cells.
- **Myeloid/macrophage/DC clusters** (e.g., clusters 1, 5, 6, 18): enriched for **Ctss, Csf1r, C1qa, C1qb, C1qc, Cst3, Aif1, Fc receptor genes, Lst1, Cx3cr1**.
- **Erythroid / megakaryocyte-like clusters** (e.g., clusters 13–14): express **Hba-a1, Hbb-bs, Hbb-bt, Alas2, Pf4, Ppbp**, matching red blood cell/platelet lineages.
- **Lymphoid stromal / endothelial clusters** (e.g., cluster 21): enriched for **Ccl21a, Mmrn1, Stab1, Flt4, Prox1, Reln, Nr2f2, Kdr, Cldn5**, typical of lymphatic endothelial and fibroblastic reticular cells.

### Lung Epithelial and Ciliated Populations

Several clusters show clear **lung epithelial** signatures:

- Clusters 3, 8, 10, 16, 17, 19 have elevated **Sftpc, Sftpa1, Sftpb, Scgb1a1, Scgb3a2, Wfdc2, Cyp2f2, Ager, Pdpn, Krt8, Krt18, Aqp5, Muc1**, indicating alveolar type 2 (AT2), club/secretory, and alveolar type 1 (AT1) cells.
- Cluster 24 strongly expresses **Dnah5, Cfap53, Cfap43/44, Ccdc153, Foxj1**, characteristic of **multiciliated epithelial cells** (airway epithelium).
- These epithelial clusters are relatively abundant (e.g., clusters 3, 8, 10, 16, 19 together contain several thousand cells), consistent with a lung tissue context.

### Cardiac-Like Cluster

- Cluster 25 (small; 19 cells) shows strong expression of **Tnnt2, Myh6, Actc1, Mb, Sln, Myoz2**, indicating a **cardiomyocyte-like** signature. This cluster is rare and likely reflects a minor contaminating tissue or circulating cells, rather than the main organ of origin.

### Global Signature Expression

From global gene statistics:

- **Lung signature genes** (Scgb1a1, Sftpc, Scgb3a2, Wfdc2, Sftpa1, Sftpb, Ager, Pdpn, Cyp2f2, Krt8/18, Aqp5, Muc1, Foxj1, Dnah5, Cfap53, Dnah12) show **high detection rates**, particularly **Scgb1a1 (~98% of cells)** and **Sftpc (>50% of cells)**.
- **Spleen/B cell markers** (Cd79a/b, Ms4a1, Cd74, H2-Aa/Ab1/Eb1, Ltb, Pf4, Ppbp, hemoglobin genes) are strongly detected but are concentrated in specific clusters (B cells, megakaryocytes, erythroid) rather than ubiquitously.

## Organ/Tissue Scoring Results

The integrated scoring table (`organ_signature_scores.tsv`) shows:

- **Spleen** achieved the **highest combined score**, driven by:
  - Full signature coverage (14/14 genes present).
  - High global mean detection among its markers.
  - Strong overlap with top markers, especially in B cell–rich cluster 0 (9 of 14 signature genes present), and representation across 11 clusters.
  - All 14 spleen signature genes appear among the union of top cluster markers.

- **Lung** ranked second overall, with:
  - High coverage of lung markers (18/19 present).
  - High global expression of key epithelial markers (Scgb1a1, Sftpc, Scgb3a2, Wfdc2, Sftpa1, Sftpb, Ager, Pdpn, Cyp2f2, Krt8/18, Aqp5, Muc1).
  - Multiple clusters (3, 8, 10, 16, 19, 24) whose top markers are strongly enriched for lung epithelial and ciliated genes.

Other organs such as **bone marrow, thymus, lymph node, heart, kidney, brain, intestine, skin** show partial support (e.g., specific clusters with matching lineages), but either weaker global expression of their canonical markers or fewer overlaps among top cluster markers.

## Final Inference and Rationale

### Most Likely Organ/Tissue of Origin: **Spleen**

Although there is very strong evidence for lung epithelial populations, the **combined quantitative scoring** and the **immune composition** point slightly more strongly toward a **secondary lymphoid organ rich in B cells, T cells, myeloid cells, and red pulp elements**, consistent with **spleen**.

Key supporting evidence:

1. **Dominant B cell and T cell compartments**:
   - Large B cell clusters (e.g., cluster 0, 11, 17, 23) with high expression of **Cd79a, Cd79b, Ms4a1, Igkc, Ighm, Ighd, Cd74, H2-Aa, H2-Ab1, H2-Eb1, Ltb**.
   - Multiple T cell clusters (2, 20, 23) including naïve/effector and developing T cells (cluster 20: **Satb1, Tcf7, Trbc2, Ccr9, Bcl11b, Rag1, Dntt**).
2. **Red pulp / megakaryocyte / erythroid components**:
   - Clusters 13–14 with **Hba-a1, Hbb-bs/bt, Alas2, Pf4, Ppbp**, matching splenic red pulp erythroid and platelet-associated cells.
3. **Supporting stromal/lymphoid structures**:
   - Cluster 21 with **Ccl21a, Mmrn1, Stab1, Flt4, Prox1, Reln, Nr2f2, Kdr, Cldn5**, compatible with lymphatic endothelial and stromal cells present in spleen and other lymphoid organs.
4. **Quantitative signature match**:
   - The spleen signature has complete coverage (14/14 genes present), the highest global mean detection, and the strongest overlap with cluster-level markers across many clusters, indicating that a large fraction of the dataset’s cellular diversity is well explained by a spleen-like immune and stromal composition.

### Why Not Lung, Despite Strong Lung Epithelial Signals?

There is clear and compelling evidence of **lung epithelial lineages** (AT1, AT2, club, and multiciliated cells) in multiple clusters. In a pure lung tissue sample, however, one would typically expect:

- A higher proportion of epithelial cells relative to lymphocytes.
- Less dominance of highly canonical B cell signatures (Cd79a/b, Ms4a1) across the largest clusters.

In this dataset, the largest cluster is a **B cell cluster (cluster 0; 5751 cells)**, with other large lymphoid/myeloid clusters following, whereas lung epithelial clusters, though numerous, are somewhat less dominant.

Thus, while the presence of lung epithelial signatures is striking and suggests strong lung involvement or sampling near lung tissue, the overall cellular composition and quantitative scoring are more characteristic of a **spleen or spleen-like secondary lymphoid organ**.

## Assumptions and Limitations

- **Species and platform**: The signatures and gene symbols used are mouse-centric (e.g., H2-Aa, Ms4a1). If the dataset is from a different species or platform with different annotation conventions, some markers may behave differently.
- **Signature curation**: Organ signatures are manually curated and not exhaustive; other valid markers may not have been included, and marker specificity can vary with context (e.g., shared immune markers across lymphoid organs).
- **Scoring scheme**: The combined score is a simple linear combination of z-scored metrics; alternative weighting, more sophisticated classifiers, or reference atlases could shift the ranking somewhat.
- **Mixed tissue or contamination**: The dataset clearly includes cell types typical of multiple tissues (e.g., lung epithelium, cardiac-like cells). The inferred organ represents the **most likely dominant tissue source** rather than excluding the possibility of multi-organ sampling or contamination.

## Summary

- **Final predicted organ/tissue**: **Spleen**.
- **Key evidence**: Extensive B cell, T cell, myeloid, erythroid/platelet, and lymphoid stromal populations; complete and highly expressed spleen signature; strong overlap of spleen markers across many clusters.
- **Secondary strong signal**: Lung epithelial and ciliated cells are abundant, consistent with lung tissue involvement but not dominating the overall cellular composition.

The quantitative scores for all candidate organs/tissues are available in `project/outputs/tables/organ_signature_scores.tsv`, and the final prediction is summarized in `project/outputs/tables/final_organ_prediction.tsv`.
