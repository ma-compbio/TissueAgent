# Hypothesis Brief

- Dataset: 228635 cells × 238 genes, spatial transcriptomics with 'leiden' clusters.
- Phase 1 observations: 3 entries logged to exploration_log.md.

## Retained hypotheses (KEEP/REFINE)
- **H1** (REFINE):
  - **Statement:** Within the rare, spatially compact clusters that form strongly enriched mutual neighbor pairs (especially clusters '15' and '30' in the leiden labeling), cells located at inter-cluster interfaces (i.e. with many neighbors from the partner cluster) exhibit coordinated shifts in multi-gene expression programs relative to same-cluster cells embedded within homogeneous neighborhoods, indicating microenvironment-dependent sub-states inside these small communities.
  - **Grounded in:** OBSERVATION 2, OBSERVATION 3
  - **Narrowing notes:** Differential expression between interface and interior subsets was only feasible for cluster 15 (interface=438, interior=297), while the partner cluster lacked enough cells in one of the groups (<10). In cluster 15, interface vs interior comparison yielded 70 genes with FDR < 0.05 and |log fold-change| > 0.25, compared with 0 significant genes in a size-matched random split. This supports the existence of interface-associated sub-states within cluster 15, but we cannot generalize this to a shared program across both clusters 15 and 30.
  - **Quality scores:** Derivable=7, Novel=6, Feasible=8, Specific=8, Falsifiable=8.

- **H2** (REFINE):
  - **Statement:** Rare clusters with extremely high same-label spatial concentration scores (such as leiden clusters '28', '15', '20', '29' and '31') occupy restricted regions along tissue coordinates and correspond to extremes of low-dimensional gene-expression gradients, so that the gene programs defining major spatial axes of variation are disproportionately loaded onto these tightly localized communities compared with more diffuse clusters.
  - **Grounded in:** OBSERVATION 1, OBSERVATION 2
  - **Narrowing notes:** At least one principal component was moderately correlated with spatial coordinates, but the difference in extremeness between rare concentrated and diffuse clusters was mixed rather than uniformly strong. For example, PC1 (r_x=0.02, r_y=-0.35) with mean |z_mean| 0.93 for rare vs 0.54 for diffuse clusters; PC2 (r_x=-0.17, r_y=0.68) with mean |z_mean| 0.73 for rare vs 1.09 for diffuse clusters. The average ratio of mean |z_mean| for rare versus diffuse clusters across spatial PCs was about 1.19, indicating that some rare clusters lie toward spatial PC tails while others do not. Thus, rare concentrated clusters are linked to extremes of spatial gene-expression gradients only for a subset of PCs and clusters, and the hypothesis is partially supported.
  - **Quality scores:** Derivable=6, Novel=7, Feasible=8, Specific=7, Falsifiable=7.
