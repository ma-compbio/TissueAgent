# Inferred organ-of-origin

## Overview of cellular composition

The dataset is dominated by immune and vascular compartments, with substantial frequencies of mature B cells (~16%), inflammatory monocytes (Chil3+), multiple macrophage subsets (resident C1q+, Trem2+), dendritic cells, NK/cytotoxic T cells, neutrophils (including an activated subset), mast/basophils, megakaryocyte/platelet and erythroid populations. There is also a rich stromal and vascular component, including interstitial and adventitial fibroblasts, pericytes/vascular smooth muscle, and several endothelial subtypes (capillary/mixed, arterial, venous/lymphatic, lymphatic endothelial). This repertoire is compatible with many solid organs that host infiltrating immune cells.

Crucially, there is a clear set of organ-defining epithelial populations: `Alveolar type 1 cells`, `Alveolar type 2 cells`, `Club cells (airway epithelial)`, and `Ciliated epithelial cells`. These are hallmark epithelial cell types of the lung and airways and are not typical of liver, kidney, brain, bone marrow, spleen/lymph node, or peripheral blood. Together they comprise a non-trivial fraction of cells (AT1, AT2, club, and ciliated epithelia together ~4–5% of all cells), consistent with a lung tissue sample that includes both parenchymal and immune/stromal compartments.

## Marker gene evidence for organ-defining epithelia

Cluster-level marker genes for these epithelial populations show canonical lung signatures:

- **Alveolar type 2 (AT2) cells**: the AT2 cluster is enriched for surfactant genes **Sftpc, Sftpa1, Sftpb, Sftpd**, together with other AT2-associated markers such as **Slc34a2** and **Ager**. This combination is a defining feature of lung AT2 pneumocytes.
- **Alveolar type 1 (AT1) cells**: the AT1 cluster shows **Cldn18, Ager, Krt7, Hopx, Aqp5-like** expression, matching canonical AT1 pneumocyte markers in lung parenchyma.
- **Club (Clara) cells**: the club cell cluster is marked by **Scgb1a1, Scgb3a2, Cyp2f2, Wfdc2**, plus other detoxification and secretory genes (**Cbr2, Retnla, Hp, Mgst1, Prdx6, Selenbp1**). This pattern is characteristic of airway club cells in bronchiolar epithelium.
- **Ciliated epithelial cells**: the ciliated cluster expresses **Sec14l3, Tppp3, Dynlrb2, Ccdc153, Rsph1, Cfap126, Tubb4b, Fam183b**, a gene set enriched for ciliary structure and motility and known from airway ciliated epithelium.

No hepatocyte markers (e.g. Alb, Ttr, Apoa1, Cyp3a family), kidney proximal tubule/podocyte markers (e.g. Slc34a1, Lrp2, Nphs1), neuronal/astrocytic/oligodendrocyte markers (e.g. Snap25, Syt1, Slc17a7, Gfap, Mbp), or bone marrow-specific progenitor signatures are evident among the major parenchymal clusters. The dominant non-epithelial compartments (immune, endothelial, fibroblasts, pericytes) are generic stromal/vascular lineages that can accompany many tissues, so the lung-specific epithelial markers are the key discriminant.

## Consistency with candidate organs

- **Lung**: Strongly consistent. The presence of distinct AT1, AT2, club, and ciliated epithelial clusters with canonical marker panels (surfactant genes, Scgb1a1/Scgb3a2, Cyp2f2, Wfdc2, Sec14l3, Tppp3, Dynlrb2, Ccdc153, Ager, Cldn18, Hopx, Aqp5) is diagnostic of lung parenchyma and airways. The substantial vascular and immune infiltrate is expected in lung tissue.
- **Liver**: Inconsistent. There are no hepatocyte clusters or hepatocyte markers (Alb, Ttr, Apoa1, Cyp2e1/Cyp3a) and no clear cholangiocyte population. The epithelial cells instead match lung, not liver, gene signatures.
- **Kidney**: Inconsistent. There are no podocyte, proximal/distal tubule, loop of Henle, or collecting duct epithelial clusters, and no kidney-defining markers (Slc34a1, Lrp2, Nphs1, Kcnj1, Umod). The observed epithelia are lung-specific.
- **Brain**: Inconsistent. There are no neuronal, astrocyte, oligodendrocyte, or microglia-like neural parenchymal clusters (no Snap25, Slc17a7, Gad1/2, Gfap, Mbp signatures). Immune and vascular cells are present but the organ-defining epithelial/parenchymal CNS cells are absent.
- **Peripheral blood**: Inconsistent. While many circulating immune lineages are present, there are numerous non-hematopoietic populations (alveolar and airway epithelia, endothelial subtypes, fibroblasts, pericytes), which would not be expected in pure blood.
- **Spleen/lymph node**: Inconsistent. The prominent B/T/myeloid repertoire fits lymphoid organs, but there is no follicular stromal or specialized lymphoid endothelial pattern; instead, there are clear lung-specific epithelial clusters (AT1/AT2/club/ciliated), which are not features of spleen or lymph node.
- **Bone marrow**: Inconsistent. Although megakaryocyte/platelet and erythroid populations are present, there is no broad spectrum of early hematopoietic progenitors and stromal niches characteristic of marrow, and the lung epithelial clusters again argue against marrow origin.

## Conclusion

Integrating the cell-type composition and marker genes, the dataset is best explained as **lung** tissue. The decisive evidence is the presence of multiple well-resolved lung epithelial subtypes—AT1 and AT2 pneumocytes, club cells, and ciliated airway epithelial cells—with canonical marker panels, embedded in a supporting milieu of immune, endothelial, fibroblast, and pericyte populations that are compatible with lung parenchyma.
