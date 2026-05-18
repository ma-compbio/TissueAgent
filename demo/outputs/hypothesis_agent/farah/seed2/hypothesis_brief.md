# Hypothesis Brief: Farah Heart MERFISH Dataset

- Total cells: 228635
- Genes in panel: 238
- Populations (Populations labels): 27
- Samples (Sample_ID counts): R78_4C15: 79891, R78_4C12: 75782, R77_4C4: 72962

## H1 (REFINE) – Conduction-associated cardiomyocyte microdomains

Refined hypothesis: Conduction-associated cardiomyocyte populations (ncCM-IFT-like, ncCM-AVC-like, vCM-His-Purkinje) form spatially segregated, strongly self-associated microdomains that are modestly enriched for neuronal neighbors compared with working ventricular cardiomyocytes and exhibit a shared developmental and conduction-related gene program distinct from the surrounding ventricular myocardium.

Key evidence:
- Conduction-like cells (n=9,748) vs working ventricular cardiomyocytes (n=73,963) showed slightly lower mean fractions of fibroblast neighbors (0.101 vs 0.121; p≈2×10⁻²⁴⁷) and endothelial neighbors (0.083 vs 0.107; p<10⁻³⁰⁰), but higher neuronal neighbor fraction (0.010 vs ≈0.000; p<10⁻³⁰⁰). Thus broad stromal enrichment is not supported, but modest neuronal enrichment is.
- Differential expression between conduction-like and working ventricular cardiomyocytes identified 72/238 genes with log₂ fold-change>0.5 and 36>1.0. Top conduction-enriched genes include BMP2, ISL1, NR2F1, TBX3, RSPO3, IRX1, IRX2, JAG1, TRPM3, and FBLN2, indicating a coordinated developmental/conduction program.
- Rare-but-tight and pairwise co-localization analyses (from the exploration phase) showed very strong self-association of ncCM-IFT-like, ncCM-AVC-like, and vCM-His-Purkinje labels, consistent with discrete conduction microdomains.

Status: **REFINE** – spatial self-organization and a distinct gene program are supported; the original prediction of stronger fibroblast/endothelial enrichment was not supported and has been removed from the statement.

## H2 (KEEP) – Lymphatic–adipogenic fibroblast–epicardial niche

Hypothesis: Lymphatic endothelial cells, adipogenic fibroblasts, and epicardial/epicardial-derived cells form a spatially co-localized niche in which adipogenic fibroblasts display a transcriptional program distinct from ventricular fibroblasts, characterized by coordinated upregulation of extracellular-matrix, remodeling-associated, and signaling-related genes, with additional modulation in adipogenic fibroblasts located directly within the niche.

Key evidence:
- Strong spatial co-localization: adFibro cells (n=1,562) vs vFibro (n=16,624) have much higher mean neighbor fractions for LEC (0.109 vs 0.001), Epicardial (0.043 vs 0.001), EPDC (0.055 vs 0.013), and Any(LEC/Epicardial/EPDC) (0.208 vs 0.015), all with Mann–Whitney p<10⁻²⁷⁰.
- At least one niche neighbor: 46.1% of adFibro vs 1.5% of vFibro have a LEC neighbor; 32.2% vs 1.1% an Epicardial neighbor; 36.2% vs 7.6% an EPDC neighbor; and 62.7% vs 8.0% have at least one of these niche neighbors.
- Differential expression (adFibro vs vFibro) revealed 99/238 genes with log₂ fold-change>0.5 and 54>1.0. Top adFibro-enriched genes include PIEZO2, OSR1, MFAP5, NR2F1, MYH11, CRABP2, NPR3, FNDC1, LYVE1, FBLN5, HOXA5, F13A1, and COL14A1, encompassing extracellular-matrix and remodeling/guidance-related factors.
- Within adFibro, niche vs non-niche cells (979 vs 583) showed 40 genes with log₂ fold-change>0.5 and 8>1.0; top niche-enriched genes such as CLDN5, PENK, NKD2, LYVE1, WT1, NRP2, F13A1, and GJA1 suggest further tuning of the program linked to direct lymphatic/epicardial contact.

Status: **KEEP** – both the spatial niche and a distinct, niche-sensitive adFibro gene program are strongly supported by the data.