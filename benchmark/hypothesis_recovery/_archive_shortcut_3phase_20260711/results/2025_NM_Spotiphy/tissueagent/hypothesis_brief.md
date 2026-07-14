# System-level Spatial Hypotheses (Phase 3 testing summary)

Hypotheses are evaluated on Xenium_FAD_1.h5ad with neighbor-graph- and PCA-based summaries.

## H1: Immune cell neighborhoods containing mutually enriched Macrophage–B cell pairs form multicellular immune hubs with increased immune cell diversity and more strongly shared activation programs across immune cell types than immune neighborhoods lacking such Macrophage–B cell adjacency.

**Status:** REFINE

**Narrowing notes:**

Only one mutually adjacent Macrophage–BCell pair and a single Mac–B hub were detected, limiting
power for neighborhood-level comparisons. Immune diversity and program coordination in this hub are
comparable to, but not dramatically distinct from, control Macrophage-centered immune neighborhoods.
Future refinements should relax the mutual-neighbor requirement and/or enlarge the spatial search
radius to capture additional Macrophage–BCell constellations.

**Mechanistic sketch (unchanged):**

Direct spatial coupling between Macrophages and B cells promotes reciprocal signaling and
recruitment of additional immune populations, creating localized immune hubs where multiple immune
cell types are co-activated and share common transcriptional programs. In contrast, immune regions
without Macrophage–B cell contact should display weaker coordination of activation states across
immune cell types.

## H2: Highly clustered hippocampal neuronal populations such as dentate gyrus (DG) and CA neurons are embedded within spatial domains that exhibit sharper spatial gradients in both cell-type composition and dominant expression programs at their boundaries than domains dominated by more intermingled astrocytes.

**Status:** REFINE

**Narrowing notes:**

Distance-to-core profiles could be computed for DG, CA and Astro domains, but the resulting
gradients do not match the original prediction: Astro-centered regions show entropy and program-
score gradients that are at least as steep as, and in PC1 substantially steeper than, those around
DG/CA neuron cores. This suggests that simple distance-to-core metrics do not isolate sharp
hippocampal laminar boundaries in this Xenium field. A refined test should focus on anatomically
restricted hippocampal slabs and/or multi-dimensional program gradients rather than a single global
PC, and incorporate explicit DG–CA anatomical localization instead of treating all DG/CA cells as a
single core.

**Mechanistic sketch (unchanged):**

DG and CA neurons form anatomically compact layers, creating well-defined structural domains with
distinct microenvironments. This laminar organization should produce abrupt transitions in both
surrounding cell-type composition and local transcriptional programs at domain edges. In contrast,
astrocytes tile multiple regions and intermix with diverse cell types, leading to more gradual
spatial transitions in composition and gene expression around astrocyte-rich areas.

## H3: In cortical regions, local neighborhoods with strong cross-type spatial coupling between L5 IT CTX and L5 PT CTX projection neurons exhibit greater convergence of their transcriptional states than neighborhoods where each projection neuron type is more spatially segregated from the other.

**Status:** REFINE

**Narrowing notes:**

In 9 cortical windows with sufficient L5 IT CTX and L5 PT CTX neurons, cross-type neighbor coupling
shows a modest negative association with transcriptomic divergence (Spearman rho≈-0.43 for Euclidean
distance, p≈0.244), but the relationship is not statistically compelling and is essentially absent
when using 1−correlation as the divergence metric. This suggests that any coupling–convergence trend
is weak in this field of view. A refined test should increase the number of windows (e.g., by
adaptive windowing within cortex), stratify by cortical layer/region, and include a null model based
on spatially permuted neuron positions.

**Mechanistic sketch (unchanged):**

Where L5 IT CTX and L5 PT CTX neurons are densely intermingled and strongly co-localized, they are
likely exposed to similar microenvironmental signals and may form shared local circuits, driving
convergence in activity-dependent transcriptional programs. In regions where these projection neuron
types occupy more separate spatial niches, they should maintain more distinct transcriptional
states.
