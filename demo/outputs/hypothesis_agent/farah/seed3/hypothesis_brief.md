# Hypothesis Brief — Farah heart MERFISH spatial dataset

## Retained hypotheses (KEEP/REFINE)

### H1
**Status:** REFINE

**Statement:** A subset of spatially rare but highly self-associated cell communities captured by high-clustering-ratio leiden clusters exhibits coordinated enrichment of extracellular-matrix and cell-adhesion gene programs relative to more spatially dispersed clusters belonging to the same major population, while other rare clusters do not show this pattern.

**Grounded in:** OBSERVATION 2

**Narrowing notes:**

Cluster 20 (dominant population VSMC, n_cluster=3131, n_background=1542) had ECM score median 0.9442 vs 0.7266 in background (diff 0.2175, p=2.51e-142 if computed). Cluster 31 (dominant population VSMC, n_cluster=1542, n_background=3131) had ECM score median 0.7266 vs 0.9442 in background (diff -0.2175, p=2.51e-142 if computed). Across 2 rare-but-tight clusters with evaluable comparisons, 1 showed significantly higher ECM scores (p<0.05), 1 showed significantly lower ECM scores, and 0 were not significant. The data show mixed effects (some clusters higher, some lower); hypothesis refined to focus on the clusters with higher ECM scores.

### H2
**Status:** KEEP

**Statement:** Lymphatic and vascular endothelial cells that reside in strongly co-localized interfaces with adventitial fibroblasts or epicardial-derived cells exhibit enhanced expression of vascular-interface and barrier-related gene programs compared to endothelial cells located in regions lacking these fibroblast- and epicardial-rich neighborhoods.

**Grounded in:** OBSERVATION 3

**Narrowing notes:**

Identified 5018 endothelial cells (Populations in ['LEC', 'VEC']). Using neighbor fractions of adFibro/EPDC/Epicardial, defined 1324 'interface-associated' endothelial cells (>=75th percentile, threshold 0.100) and 3694 'non-interface' cells (<=25th percentile, threshold 0.000). Vascular-interface program (genes ['PECAM1']) had median score 1.1431 in interface-associated endothelial cells vs 0.6538 in non-interface cells (diff 0.4893, p=6.91e-46 if computed). Interface-associated endothelial cells show significantly higher vascular-interface program scores; hypothesis retained.

## Dropped hypotheses

- **H3** (status DROP): Cardiomyocytes classified as ncCM-IFT-like that reside in neuron-enriched microenvironments display coordinated upregulation of conduction and ion-handling gene programs relative to ncCM-IFT-like cells located away from neuronal neighbors, consistent with specialized neuro-cardiac interface niches during heart development.
  - Notes: Identified 2027 ncCM-IFT-like cells and 1027 Neuronal cells. Defined 534 'neuron-proximal' ncCM-IFT-like cells (>=75th percentile Neuronal-neighbor fraction, threshold 0.100) and 1493 'neuron-distant' cells (<=25th percentile, threshold 0.000). Conduction/ion-handling program (genes ['GJA1', 'GJA5', 'KCNH2', 'KCNJ8', 'SCN5A', 'SCN7A', 'RYR2', 'CACNA1C', 'HCN4']) had median score 0.6357 in neuron-proximal ncCM-IFT-like cells vs 0.6526 in neuron-distant cells (diff -0.0168, p=3.41e-02 if computed). Neuron-proximal ncCM-IFT-like cells show significantly lower conduction program scores; hypothesis contradicted and dropped.

