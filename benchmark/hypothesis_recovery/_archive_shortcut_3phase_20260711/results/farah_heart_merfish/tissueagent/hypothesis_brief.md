# Hypotheses – Farah et al. MERFISH heart (Phase 3 status)

## Dataset overview

- Cells (n_obs): 228635
- Genes (n_vars): 238
- obs columns: Sample_ID, Batch, UMI Count, leiden, Complexity, Populations, Purity
- spatial key: spatial

## H1 – Status: SUPPORTED

**Statement**

Within ventricular myocardium, proliferating ventricular cardiomyocytes preferentially occupy spatial boundary zones between compact cardiomyocytes and ventricular fibroblasts, forming pro-growth microdomains with distinct developmental signaling activity compared to proliferating cardiomyocytes in more homogeneous neighborhoods.

**Mechanistic rationale**

If ventricular growth is coordinated by interactions between compact cardiomyocytes, proliferating cardiomyocytes, and ventricular fibroblasts, then proliferating ventricular cardiomyocytes should be spatially concentrated at interfaces where compact myocardium interdigitates with fibroblast-rich stroma. In these boundary zones, paracrine signals and matrix cues provided by fibroblasts are expected to sustain a distinct developmental gene-expression program in neighboring proliferating cardiomyocytes relative to cells embedded deep within compact muscle.

**Test plan (summary)**

- 1. Use spatial coordinates and cell-type labels to identify ventricular regions dominated by compact cardiomyocytes (vCM-LV-Compact and related ventricular compact CM labels) and ventricular fibroblasts (vFibro and closely related ventricular stromal populations).
- 2. For each proliferating ventricular cardiomyocyte, compute the composition of its spatial neighbors within a fixed-radius or k-nearest-neighbor window, recording fractions of compact cardiomyocytes and ventricular fibroblasts.
- 3. Define 'boundary proliferating cardiomyocytes' as those whose local neighborhoods contain substantial proportions of both compact cardiomyocytes and ventricular fibroblasts, and 'interior proliferating cardiomyocytes' as those surrounded predominantly by compact cardiomyocytes with minimal fibroblast neighbors.
- 4. Compare spatial metrics (e.g., distance to fibroblast-rich clusters, thickness of mixed zones) between boundary and interior proliferating cardiomyocytes using permutation tests that shuffle cell-type labels while preserving spatial structure.
- 5. Within the MERFISH gene panel, construct scores for developmental and cell-cycle–adjacent signaling programs (e.g., growth factor signaling, morphogen pathways, generic proliferation markers) using aggregated expression of the relevant genes present in the panel.
- 6. Compare these program scores between boundary and interior proliferating cardiomyocytes, controlling for overall expression level and sample/batch, and assess statistical significance with appropriate regression or nonparametric tests.
- 7. As a spatial validation, visualize program scores overlaid on tissue maps, testing whether high-score proliferating cardiomyocytes align along compact–fibroblast interfaces more often than expected by spatial permutation.

**Predicted outcome**

Proliferating ventricular cardiomyocytes will be enriched at compact–fibroblast interfaces, forming visible bands or clusters at boundaries rather than being uniformly scattered within compact myocardium. Boundary proliferating cardiomyocytes will show higher scores for developmental signaling programs relative to interior proliferating cardiomyocytes, even after accounting for cell-cycle activity. Spatial permutation tests will indicate that the coincidence of high signaling scores with compact–fibroblast boundaries exceeds expectations from randomized cell-type assignments.

**Phase 3 status and narrowing notes**

Boundary proliferating vCM defined by compact>=0.3 and fibro>=0.15 neighbors account for ~25% of proliferating vCM and show markedly higher fibro-like neighbor fractions (Δ≈0.13, p≈0.005) and slightly elevated developmental signaling scores (Δ≈0.005, p≈0.035) compared to interior proliferating vCM, while generic proliferation scores do not differ. This supports the existence of fibroblast-associated boundary microdomains with distinct signaling rather than globally elevated proliferation. Future refinements should tighten boundary definitions and test additional signaling pathways as more genes become available.

## H2 – Status: SUPPORTED

**Statement**

Lymphatic–fibroblast microdomains defined by co-localized lymphatic endothelial cells and adventitial/valve fibroblasts constitute specialized extracellular-matrix remodeling and immune-modulatory niches, exhibiting distinct gene-expression programs in both lineages compared to lymphatic endothelial cells and fibroblasts located outside these paired regions.

**Mechanistic rationale**

The strong bidirectional enrichment of adFibro–LEC and EPDC–LEC neighbors suggests stable microenvironments where lymphatic endothelium and stromal fibroblast-like cells interact. If these microdomains are functionally specialized, lymphatic endothelial cells and nearby fibroblasts in such regions should co-activate extracellular-matrix remodeling and immune-associated transcriptional programs distinct from the programs active in the same cell types located away from lymphatic–fibroblast interfaces.

**Test plan (summary)**

- 1. Using the spatial neighbor graph, formally define 'lymphatic–fibroblast niches' as connected sets of cells enriched for mutual nearest-neighbor relationships between lymphatic endothelial cells (LEC) and fibroblast-like populations that show adFibro/EPDC identity.
- 2. For each LEC, compute the fraction of neighbors that are adFibro/EPDC; classify LEC as 'niche LEC' when this fraction exceeds a defined enrichment threshold derived from the global neighbor distribution, and 'non-niche LEC' otherwise.
- 3. Analogously, classify fibroblast-like cells (adFibro/EPDC) into 'niche fibroblasts' if they are surrounded by an enriched fraction of LEC neighbors, using symmetric or complementary thresholds.
- 4. From the MERFISH gene panel, define gene sets representing extracellular-matrix components, matrix-processing enzymes, and generic immune-modulatory or inflammatory mediators, using all available genes in these categories.
- 5. Compute module scores for these matrix and immune programs for each LEC and fibroblast-like cell, and compare niche versus non-niche groups within each cell type using appropriate statistical tests while controlling for sample effects.
- 6. Map module scores back onto the tissue to assess whether high matrix/immune scores form coherent spatial domains coinciding with LEC–fibroblast co-localized regions.
- 7. Perform spatial permutation tests that shuffle cell-type labels or niche assignments while keeping coordinates fixed to confirm that any observed enrichment of matrix or immune programs in niches cannot be explained by generic spatial trends.

**Predicted outcome**

Lymphatic–fibroblast niches will be apparent as compact spatial regions where niche LEC and niche fibroblasts co-cluster. In these regions, both LEC and fibroblast-like cells will show higher extracellular-matrix remodeling and immune-modulatory program scores compared to their counterparts outside the niches. Spatial permutation will indicate that the co-occurrence of high matrix/immune activity with LEC–fibroblast co-localization is unlikely under randomized cell-type configurations.

**Phase 3 status and narrowing notes**

Top-20% LEC by fibro-like neighbor fraction (niche LEC, n≈270) and top-20% adFibro/EPDC by LEC neighbors (niche fibro-like, n≈2200) define compact lymphatic–fibroblast niches with high mutual connectivity. Niche LEC have substantially higher fibro-like neighbor fractions (Δ≈0.34, p≈0.005) and are closer to fibro-like cells, and niche fibro-like cells show significantly elevated immune-module scores (Δ≈0.06, p≈0.005) relative to non-niche fibroblasts. ECM-module scores are similar or slightly lower in niches. Overall this supports specialized immune-modulatory lymphatic–fibroblast microdomains but suggests that ECM remodeling is not uniquely upregulated in these niches under the current MERFISH panel.

## H3 – Status: SUPPORTED

**Statement**

Multilineage hub regions, such as epicardial and valve/vascular zones where multiple cell types intermingle, act as high-diversity signaling centers with elevated ligand–receptor interaction potential compared to more homogeneous myocardial or endothelial territories.

**Mechanistic rationale**

If epicardial and valve/vascular compartments function as organizing hubs for cardiac growth and remodeling, we expect spatial subregions where cardiomyocytes, fibroblast/EPDC, and endothelial/valve lineages co-occur at high diversity and density. In these hubs, a rich repertoire of secreted ligands and cognate receptors should be co-expressed across lineages, yielding higher local interaction potential than in relatively homogeneous regions dominated by a single population.

**Test plan (summary)**

- 1. Partition the tissue into overlapping spatial windows (e.g., discs of fixed radius or neighborhoods derived from the spatial kNN graph) and, for each window, compute the local cell-type composition and a lineage-diversity index (e.g., Shannon entropy over cardiomyocyte, fibroblast/EPDC, and endothelial/valve compartments).
- 2. Identify 'hub windows' as those with high cell-type diversity and substantial representation of at least three major lineages (e.g., cardiomyocytes, fibroblast/EPDC, and endothelial/ valve-associated cells), and 'homogeneous windows' as those dominated by a single compartment.
- 3. From the MERFISH panel, assemble sets of genes annotated as secreted factors and receptors (ligand–receptor candidates supported by the panel), and compute ligand program scores, receptor program scores, and a combined 'interaction potential' score for each cell.
- 4. Aggregate these program scores within each spatial window (e.g., mean or upper quantiles) to obtain window-level measures of ligand, receptor, and interaction potential activity.
- 5. Compare these measures between hub and homogeneous windows using statistical tests that adjust for overall cell density and sample-level differences.
- 6. Perform spatial permutation controls by randomly reassigning cell-type labels among coordinates or randomly shifting window positions to test whether any enrichment of interaction potential in hubs exceeds expectations from chance mixing.
- 7. Visualize maps of cell-type diversity and interaction potential scores across the tissue sections to qualitatively confirm that high-diversity, high-interaction windows coincide with epicardial and valve/vascular regions highlighted by the neighbor-composition analyses.

**Predicted outcome**

Spatial windows classified as hubs will show significantly higher cell-type diversity and elevated ligand–receptor program activity compared to homogeneous windows composed primarily of a single population such as compact ventricular cardiomyocytes, lymphatic endothelial cells, or conduction cells. This difference will remain robust after spatial permutation, supporting the existence of discrete multilineage signaling hubs in the developing heart.

**Phase 3 status and narrowing notes**

High-diversity spatial windows (top-20% lineage entropy with ≥2 CM, fibro/EPDC, and endo/valve cells) form ≈9k hub windows. Compared to low-entropy homogeneous windows, hubs have similar ligand program activity but substantially higher receptor and combined interaction-potential scores (p≈0.005), consistent with enriched multilineage signaling capacity in epicardial/valve/vascular-like regions. The current definition is coarse and should be refined with more anatomically targeted windows and curated ligand–receptor gene sets.
