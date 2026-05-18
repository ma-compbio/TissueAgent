## Hypothesis Brief

Dataset: developing human heart MERFISH (Farah et al. 2024, anonymized Populations labels).

Retained hypotheses (KEEP/REFINE): 3

- **H1** (KEEP)
  - Statement: Spatially co-localized PX–PY micro-environments form a specialized interface niche where PX and PY cells share a coordinated multi-gene expression program that is distinct from PX and PY cells located in regions without direct PX–PY contact.
  - Grounded in: OBSERVATION 2, OBSERVATION 3
  - Narrowing notes: H1 supported: PX and PY interface cells are abundant (PX_interface=640, PX_non_interface=922; PY_interface=396, PY_non_interface=896). Differential expression reveals 123 interface-up genes in PX and 94 in PY, with a shared module of 51 genes upregulated in both. Example shared genes: ADGRL1, APOE, CA4, CACNA1C, CBLN2. PCA on this shared set yields clear separation of interface vs non-interface cells within each label (PX PC1 separation=1.577; PY PC1 separation=-0.278), indicating a coordinated PX–PY interface program.
  - Quality scores: Derivable=8, Novel=7, Feasible=9, Specific=8, Falsifiable=9

- **H2** (REFINE)
  - Statement: PW–PAA–PM micro-communities form spatially distinct stromal niches that differ transcriptionally from diffuse PM regions, but the enrichment for extracellular-matrix–associated genes is modest in this panel.
  - Grounded in: OBSERVATION 2
  - Narrowing notes: H2 partially supported: niche-core vs distant PM comparison yields 98 niche-upregulated genes, of which 2 match a broad ECM-like set (e.g., ADAMTS6, COL9A2). This indicates that PW–PAA–PM regions have a distinct program relative to diffuse PM, but the evidence for a strongly ECM-dominated signature is limited by the available gene panel.
  - Quality scores: Derivable=7, Novel=7, Feasible=8, Specific=8, Falsifiable=8

- **H3** (KEEP)
  - Statement: Spatially tight PV micro-communities that are enriched for PM and PF neighbors deploy a distinct, multi-gene stress or signaling program compared with PV cells that are not embedded in such PV–PM–PF neighborhoods.
  - Grounded in: OBSERVATION 2, OBSERVATION 3
  - Narrowing notes: H3 supported: PV cells embedded in PV–PM–PF micro-communities (n=681) differ transcriptionally from isolated PV cells (n=461). Embedded PV cells upregulate 169 genes at FDR<0.05, including 6 genes with signaling/stress-associated annotation in this panel (e.g., ADM, ANGPT1, FGF12, NOTCH1, PDGFRA). This indicates a distinct multi-gene program activated when PV cells are in close contact with PM and PF neighbors.
  - Quality scores: Derivable=7, Novel=6, Feasible=8, Specific=8, Falsifiable=9

