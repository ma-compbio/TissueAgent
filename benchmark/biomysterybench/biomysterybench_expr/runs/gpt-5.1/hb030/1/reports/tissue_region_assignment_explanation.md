# Tissue-to-gastrula-region assignments

This report summarizes how each tissue (T1–T5) was mapped to a Xenopus tropicalis gastrula fate-map region using the gastrula-region marker enrichment summary (`tissue_region_enrichment_summary.tsv`) and the combined top marker list (`top_markers_summary.tsv`). Where possible, assignments are linked to well-characterized gastrula-stage markers.

## Overview of region enrichment

From the enrichment table:

- **T1**
  - Only non-zero enrichment: **MarginalZone (1 marker: _trim29_)**.
  - No markers annotated for Organizer, AnimalEctoderm, Mesoderm, or EndodermVegetal.
- **T2, T3, T5**
  - No annotated region markers (all n_markers = 0 across regions).
- **T4**
  - Organizer: 1 marker (**_foxa1_**)
  - MarginalZone: 5 markers (**_csrnp1; dkk1; fgfr4; foxa1; sia1_**)
  - AnimalEctoderm: 2 markers (**_fgfr4; tbx2_**)
  - Mesoderm: 7 markers (**_dkk1; fgfr4; foxa1; hhex; six1; sulf1; tbx2_**)
  - EndodermVegetal: 9 markers (**_dkk1; foxa1; gata4; gata6; hhex; hnf1b; otx1; six1; sox17a_**)

Thus, T4 shows the strongest and broadest enrichment for endoderm/vegetal and organizer/marginal-zone markers, whereas T1–T3 and T5 have little or no region annotation support.

## Tissue-specific interpretations

### T4 – Vegetal endoderm / organizer-enriched tissue

**Enrichment evidence**

- Strong enrichment in **EndodermVegetal (9 markers)** and substantial overlap with **Mesoderm** and **MarginalZone**.
- Key markers from the enrichment table and top-marker list include:
  - **_foxa1_**: forkhead transcription factor expressed in endodermal and organizer-associated endoderm at gastrula stages.
  - **_gata4, gata6_**: classic **vegetal endoderm** transcription factors involved in early endoderm specification.
  - **_hnf1b_**: associated with endodermal derivatives and early gut/liver primordia, fitting a vegetal endoderm program.
  - **_sox17a_**: canonical **endoderm/vegetal pole marker** in Xenopus gastrula.
  - **_otx1_**: expressed in anterior neural/forebrain and in anterior endomesoderm; its presence alongside strong endoderm markers fits an anterior endoderm or organizer-associated endoderm identity.
  - **_dkk1_**: secreted Wnt antagonist, a well-known **dorsal organizer** and anterior endomesoderm marker.
  - **_fgfr4_**: FGF receptor enriched in organizer/anterior mesendoderm territories.
  - **_sia1_**: dorsal organizer transcription factor (Siamois) induced by Wnt/β-catenin.
  - **_six1, sulf1_**: genes associated with mesodermal and somitic/cranial domains; here they likely reflect mesendodermal overlap rather than pure ectoderm.

**Biological interpretation**

The co-enrichment of classic **vegetal endoderm markers** (_gata4, gata6, sox17a, hnf1b_) together with **organizer/anterior mesendoderm markers** (_dkk1, fgfr4, sia1, otx1, foxa1_) indicates that T4 corresponds to **vegetal endoderm with strong organizer/anterior mesendoderm character**, rather than pure mesoderm or ectoderm.

Among the available fate-map labels, the best single descriptor is:

- **Assigned region for T4: VegetalEndoderm (High confidence)**

This captures the dominant endoderm/vegetal identity, with the understanding that it likely corresponds to dorsal/anterior vegetal endoderm (organizer-associated endoderm).

### T1 – Animal cap / animal ectoderm–like tissue

**Enrichment evidence**

- Region enrichment table: only one annotated marker, **_trim29_**, associated with **MarginalZone** (1 marker). No AnimalEctoderm markers were annotated.
- However, the **top markers for T1** show strong enrichment for classic **animal cap / ectodermal** transcription factors:
  - **_foxi1_** and **_foxi4.1_**: I-fox family transcription factors enriched in **non-neural ectoderm / animal cap** at blastula–gastrula stages; widely used as markers of epidermal/placodal ectoderm in Xenopus.
  - **_klf2_**, **_pdgfa_**, and others (_erbb3_, cell-surface/secreted factors) are compatible with a proliferative, non-vegetal, non-mesodermal territory, but are less specific.

**Biological interpretation**

Although the formal enrichment table only connects T1 to the MarginalZone via _trim29_, the presence of **highly specific animal-cap markers (_foxi1, foxi4.1_)** is strong evidence that T1 corresponds to **animal ectoderm / animal cap** rather than marginal or vegetal tissues. The single marginal-zone annotation (via _trim29_) is weak and may reflect either limited annotation coverage or low-level expression rather than true positional identity.

- **Assigned region for T1: AnimalCap (High confidence)**

### T2 – Uncharacterized (no region-enriched markers)

**Enrichment evidence**

- The tissue–region enrichment table lists **zero markers for all regions** (Organizer, MarginalZone, AnimalEctoderm, Mesoderm, EndodermVegetal).
- The combined top-marker summary contains **no entries for T2**, indicating that either T2 has few or no robustly differential markers or did not meet the thresholds used to build the summary.

**Biological interpretation**

With no region-enriched markers and no top-marker list to interpret, there is **insufficient evidence** to confidently assign T2 to a specific gastrula region. Any assignment would be essentially speculative.

- **Assigned region for T2: Unknown (Low confidence)**

### T3 – Uncharacterized (no region-enriched markers)

**Enrichment evidence**

- As with T2, **all region counts are zero** in the enrichment summary.
- The top-marker summary also contains **no T3 entries**, so there are no clearly tissue-specific genes to interpret.

**Biological interpretation**

Given the complete absence of region annotations and informative markers, T3 cannot be reliably mapped to animal cap, marginal zone, organizer, mesoderm, or vegetal endoderm.

- **Assigned region for T3: Unknown (Low confidence)**

### T5 – Uncharacterized (no region-enriched markers)

**Enrichment evidence**

- The enrichment table shows **zero markers** across all regions for T5.
- The top-marker summary similarly has **no T5 entries**, leaving no strong gene-level clues.

**Biological interpretation**

Like T2 and T3, T5 lacks clear gastrula-region marker signatures in the available data. Without recognizable domain-specific markers, any fate-map assignment would be speculative.

- **Assigned region for T5: Unknown (Low confidence)**

## Final mapping table

The final tissue-to-region assignments (in the order of T1–T5, matching the counts matrix columns) are:

| tissue | assigned_region   | confidence |
|--------|-------------------|------------|
| T1     | AnimalCap         | High       |
| T2     | Unknown           | Low        |
| T3     | Unknown           | Low        |
| T4     | VegetalEndoderm   | High       |
| T5     | Unknown           | Low        |

This mapping prioritizes strong, domain-specific marker evidence where available (T1, T4) and explicitly flags uncertainty where the data lack informative markers (T2, T3, T5).
