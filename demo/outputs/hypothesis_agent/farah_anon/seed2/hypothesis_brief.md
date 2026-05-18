## Hypothesis Narrowing Summary

Total draft hypotheses: 3.
Retained (KEEP/REFINE): 2.
Dropped: 1.

### H2 (REFINE)
**Statement:** Spatial neighborhoods composed of leiden clusters 29, 31 and their enriched partners (14, 23, 10, 18) show higher extracellular-matrix gene program activity than the same labels in less interconnected regions, although this enrichment is not fully specific relative to contractile programs.
**Grounded in:** OBSERVATION 2, OBSERVATION 3, OBSERVATION 4
**Narrowing notes (abridged):**
H2 label-set cells total: 28956.
Neighborhood cells (>= 0.30 neighbors from H2 label-set)=18127, context-matched controls=10829.
ECM module scores: mean(neighborhood)=0.075, mean(control)=-0.126, p=1.58e-301.
Contractile module scores: mean(neighborhood)=-0.038, mean(control)=0.064, p=1.23e-148.

### H3 (REFINE)
**Statement:** Rare, spatially tight leiden clusters 28, 15, 20, 29, and 31 are closer to the tissue boundary than more abundant diffuse clusters and show modest enrichment for selected proliferation or progenitor transcription-factor programs, rather than a uniformly stronger immature profile across all metrics.
**Grounded in:** OBSERVATION 1, OBSERVATION 2, OBSERVATION 3
**Narrowing notes (abridged):**
Tight-cluster cells=10554, other cells=218081.
Boundary distance: median(tight)=1527.6, median(other)=1921.0, p=0.00e+00 (lower median implies closer to edge).
Top-5 abundant (non-tight) cluster codes used for comparison: ['0', '1', '3', '2', '4'] with total cells=85401.
Cell-cycle module: mean(tight)=-0.060, mean(top5)=0.007, p=8.48e-48.
Progenitor TF module: mean(tight)=0.011, mean(top5)=-0.001, p=3.81e-11.

### Dropped Hypotheses
- H1: Spatially tight microcommunities built around rare leiden clusters 28 and 15 and their strongly enriched neighbor labels (including 33, 14, 30, and 32) exhibit coordinated upregulation of developmental signaling and transcription-factor gene programs compared to cells of the same clusters that reside outside these enriched neighbor contexts elsewhere in the tissue.  
  Reason: Cluster 28: total cells=2027, interface (>= 0.30 partner neighbors)=329, non-interface=1698.
