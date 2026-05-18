# Hypothesis Brief — Farah developing human heart MERFISH

Total cells: 228635, genes: 238, Populations: 27.

## Retained hypotheses

### H2: Fibroblast subtypes that form spatially concentrated niches and preferentially neighbor specific cardiomyocyte or endothelial populations exhibit distinct extracellular matrix and remodeling gene programs compared to fibroblasts residing in more compositionally mixed neighborhoods.

- Grounded in: OBSERVATION 2, OBSERVATION 3
- Status after narrowing: KEEP
- Quality scores: Derivable=8, Novel=7, Feasible=8, Specific=8, Falsifiable=9.
- Evidence notes: H2 ECM program (genes=['COL14A1', 'DCN', 'FN1', 'POSTN', 'TNC', 'VCAN'], n=6); main neighbor categories with >=50 fibro cells: ['CM_enriched', 'Endothelium_enriched', 'Fibro_dominated']. H2 Kruskal-Wallis across neighbor categories ['CM_enriched', 'Endothelium_enriched', 'Fibro_dominated', 'Other', 'Vascular_support_enriched']: H=2341.41, p=0.00e+00. H2 ECM CM_enriched vs Fibro_dominated: mean_CM=1.325, mean_Fibro=1.813, U=9481197.5, p=0.00e+00.

### H3: Endothelial microdomains dominated by lymphatic endothelial cells (LEC) in the developing heart exhibit coordinated enrichment of lymphangiogenic and vascular signaling gene programs relative to generic vascular endothelial clusters (VEC) that are less spatially restricted.

- Grounded in: OBSERVATION 2, OBSERVATION 4
- Status after narrowing: KEEP
- Quality scores: Derivable=7, Novel=7, Feasible=7, Specific=8, Falsifiable=8.
- Evidence notes: H3 vascular program (genes=['ANGPT1', 'CXCL12', 'NRP2', 'PROX1'], n=4): LEC mean=1.164, VEC mean=0.618. H3 LEC vs VEC Mann–Whitney U=4134369.5, p=0.00e+00. H3 DE overlap with vascular program genes in top 20: ['NRP2', 'PROX1'].

## Dropped hypotheses

- H1: Specialized non-chamber and conduction-associated cardiomyocyte microdomains (e.g. ncCM-IFT-like, ncCM-AVC-like, vCM-His-Purkinje, vCM-RV-AV) that form highly self-clustered spatial islands exhibit coordinated enrichment of conduction and stress-response gene programs, compared to bulk ventricular compact and trabecular cardiomyocytes that occupy more mixed regions. (status=DROP).
  Notes: H1 conduction program (genes=['CACNA1C', 'CASQ2', 'CKMT2', 'GJA1', 'GJA5', 'HCN4', 'ISL1', 'KCNH2', 'KCNJ8', 'NKX2-5', 'PLN', 'RYR2', 'SCN5A', 'TBX18', 'TBX3', 'TBX5'], n=16): specialized mean=0.754, bulk mean=0.939. H1 stress program (genes=['EGR1'], n=1): specialized mean=0.126, bulk mean=0.101. H1 conduction Mann–Whitney U=262134294.0, p=0.00e+00. H1 stress Mann–Whitney U=510129096.0, p=1.34e-06. H1 DE overlap: conduction genes in top 20=['HCN4', 'TBX3'], stress genes in top 20=[].

