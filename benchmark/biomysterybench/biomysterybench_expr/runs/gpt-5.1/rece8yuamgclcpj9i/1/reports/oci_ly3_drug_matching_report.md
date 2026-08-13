# Title & Objective

**Title:** Mechanism-of-action matching for four drug treatments in OCI-LY3 cells

**Objective:**
Given gene expression profiles from four anonymized drug treatments (Groups A–D) in OCI-LY3 cells, infer which treatment corresponds to each of four candidate compounds — Rapamycin, Trichostatin A, Geldanamycin, and Doxorubicin — and commit to a single one-to-one mapping.

---

# Data & Methods

## Data
- Source file: `library/datasets/anonymized_expression.txt`.
- Content: 49,386 probes × 16 samples.
- Inferred sample groups from column names:
  - Control: Control_1–Control_4 (4 samples)
  - Group A: GroupA_1–GroupA_3 (3 samples)
  - Group B: GroupB_1–GroupB_3 (3 samples)
  - Group C: GroupC_1–GroupC_3 (3 samples)
  - Group D: GroupD_1–GroupD_3 (3 samples)

## Preprocessing & QC
- Orientation: probes as rows (`probe_id`), samples as columns; no transpose required.
- Scale: values in the range ~3–15, consistent with log2 microarray intensities.
- Normalization:
  - Applied between-sample quantile normalization on the log2 matrix.
  - Saved as `project/outputs/data/expression_matrix_processed.tsv`.
- QC metrics:
  - Per-sample mean, median, variance, total intensity, min/max, and z-score-based outlier flags (none detected).
  - Sample–sample Pearson correlation matrix and hierarchical clustering.
  - PCA on all probes.

## Differential Expression
- For each treatment group (A–D) vs Control:
  - Used the quantile-normalized log2 expression matrix.
  - Included 4 controls and 3 treatment samples per contrast.
  - For each probe:
    - Computed logFC = mean(treatment) − mean(control).
    - Pooled-variance two-sample t-statistic (df = 5) and two-sided p-value.
    - AveExpr = mean expression across the 7 samples in that contrast.
  - Adjusted p-values by Benjamini–Hochberg FDR.
- Output tables:
  - Full DE: `tables/de_GroupA_vs_Control.tsv`, `..._GroupB_...`, `..._GroupC_...`, `..._GroupD_...`.
  - Top 50 DE probes: `tables/top_de_genes_GroupA.tsv`, ..., `tables/top_de_genes_GroupD.tsv`.
- Volcano plots (logFC vs −log10(FDR)) with significance thresholds:
  - adj.P.Val < 0.05 and |logFC| ≥ 1.0.
  - Files: `figures/volcano_GroupA.png`, ..., `figures/volcano_GroupD.png`.

## Pathway / Signature Analysis
- Probe-to-gene mapping:
  - Used `tables/GPL570_probe_to_gene_symbol.tsv` (Affymetrix U133 Plus 2.0 style IDs).
  - Retained only the first symbol when multiple symbols were listed (e.g. `MIR4640///DDR1` → `MIR4640`).
  - Dropped probes with missing or `nan` symbols.
- Gene-level DE:
  - For each contrast, DE results were merged with the annotation.
  - When multiple probes mapped to one gene, the probe with the largest |t| was retained.
  - Added a ranking metric: `rank_score = sign(logFC) * -log10(P.Value)`.
  - Due to the restricted annotation subset, only three genes (ACTB, GAPDH, STAT1) overlapped per contrast, and none met adj.P.Val < 0.05 and |logFC| ≥ 1.
- Over-representation analysis (ORA):
  - Defined four hand-curated mechanism-of-action gene sets (mTOR/PI3K/AKT/autophagy, HDAC/chromatin, HSP90/heat-shock, DNA damage/p53/apoptosis).
  - For each group, for up- and down-regulated genes separately (adj.P.Val < 0.05 and |logFC| ≥ 1):
    - Background = all genes in that contrast after collapsing probes.
    - Fisher’s exact test (one-sided, alternative = "greater").
    - BH FDR across the 8 tests (4 sets × 2 directions).
  - Result: no significant enrichment for any MoA set in any group (all p = 1, FDR = 1.0) because no genes were significant in the tiny annotated background.
  - Enrichment tables: `tables/enrichment_GroupA.tsv`, ..., `tables/enrichment_GroupD.tsv`.
  - Dotplots: `figures/enrichment_dotplot_GroupA.png`, ..., `figures/enrichment_dotplot_GroupD.png`.
  - Summary report: `reports/enrichment_summary_by_group.md`.

## Drug Assignment Strategy
- Enrichment results were effectively non-informative.
- Therefore, final mapping relied on:
  - The **scale** of DE (number of significant probes at adj.P.Val < 0.05 and |logFC| ≥ 1).
  - The **balance** of up- vs down-regulation.
  - The **distribution** of effect sizes (e.g., presence of a few very strongly induced probes vs broad moderate shifts).
  - Generic expectations of each drug’s transcriptomic footprint.
- Final assignments and rationale were saved as:
  - `reports/drug_assignment.txt`
  - `reports/drug_assignment_rationale.md`

---

# Results

## Differential Expression Patterns by Group

Using adj.P.Val < 0.05 and |logFC| ≥ 1.0 as the significance threshold:

- **Group A vs Control**
  - Significant probes: 36
    - Up: 19
    - Down: 17
  - Max |logFC|: ~2.4
  - Overall: moderate, fairly symmetric perturbation with balanced up/down changes and modest effect sizes.

- **Group B vs Control**
  - Significant probes: 1,412
    - Up: ~644
    - Down: ~768
  - Max |logFC|: ~4.2
  - Overall: the largest, most symmetric transcriptome-wide reprogramming; many genes both up- and down-regulated, with substantial effect sizes.

- **Group C vs Control**
  - Significant probes: 24
    - Up: 24
    - Down: 0
  - Max |logFC|: ~4.8 (largest single effect of any group)
  - Overall: small number of probes but very strongly induced; signature dominated by strong up-regulation.

- **Group D vs Control**
  - Significant probes: 5
    - Up: 5
    - Down: 0
  - Max |logFC|: ~3.5
  - Overall: a very weak perturbation with only a handful of strongly up-regulated probes.

These global patterns are clearly visible in the volcano plots.

## Enrichment Summary

- Due to the extremely limited probe–gene overlap in the available GPL570 mapping subset:
  - Only ACTB, GAPDH, STAT1 mapped into the gene-level DE.
  - None of these genes were significantly DE in any contrast.
  - All hand-curated MoA gene sets (mTOR, HDAC, HSP90/heat-shock, DNA damage/p53) had FDR = 1.0 in all groups.
- As a result, **no mechanistic pathway assignment could be made from ORA itself**. The enrichment artifacts mainly document this limitation.

## Final Group → Drug Mapping

Based on the DE patterns and generic expectations:

- **Group A → Rapamycin**
  - Rationale: Group A has a modest but clear, balanced response (36 significant probes, roughly half up and half down, moderate |logFC|). This is consistent with a pathway-focused, cytostatic mTOR inhibitor that perturbs a specific signaling/growth network rather than inducing broad histone-level reprogramming or extensive DNA-damage responses. It is stronger than a near-null profile but much less extensive than Group B.

- **Group B → Trichostatin A**
  - Rationale: Group B shows by far the largest and most symmetric signature (1,412 significant probes, both heavily up- and down-regulated). This broad, bidirectional transcriptomic reprogramming is characteristic of an HDAC inhibitor such as Trichostatin A, which globally alters chromatin accessibility and gene expression. The scale and symmetry distinguish B from the other groups and most strongly match an HDAC-inhibition profile.

- **Group C → Doxorubicin**
  - Rationale: Group C has a relatively small number of significant probes, but they are all strongly up-regulated, with the highest maximum logFC (~4.8) among all groups. This pattern—a subset of genes being very strongly induced, with fewer broad changes—is compatible with a stress and DNA-damage response typical of the anthracycline Doxorubicin, where p53 and apoptotic transcriptional programs can drive strong induction of select targets without necessarily causing global reprogramming at this time point.

- **Group D → Geldanamycin**
  - Rationale: Group D displays the smallest overall signature (only 5 significant, all up-regulated probes). After assigning the more distinctive patterns of Groups A–C to Rapamycin, Trichostatin A, and Doxorubicin, Geldanamycin remains as the best match by relative elimination. HSP90 inhibition can exert strong post-transcriptional effects and, depending on timing and context, may produce a more restricted transcriptomic footprint. In the absence of clear heat-shock marker evidence (blocked by limited mapping), Group D’s weak but nonzero response is least inconsistent with Geldanamycin.

---

# Caveats & Warnings

- **Sparse probe–gene annotation:** The available GPL570 mapping overlaps only three genes (ACTB, GAPDH, STAT1) with the DE tables used in gene-level ORA. This prevents direct identification of hallmark markers (e.g., HSPs, histones, canonical p53 targets), severely limiting mechanism-of-action inference.
- **Non-informative enrichment:** All ORA results for hand-curated MoA gene sets are statistically null (FDR = 1.0) in every group. The final mapping does **not** rely on these enrichment statistics; they serve only to document the lack of signal.
- **Simplified DE modeling:** Due to lack of an R/limma environment, DE was performed using equal-variance two-sample t-tests with BH FDR, without empirical Bayes shrinkage. While reasonable for these small contrasts, variance estimates may be noisier than in limma.
- **Pattern-based inference:** Drug assignments are driven by global DE patterns (scale, symmetry, effect sizes) and general expectations of Rapamycin, Trichostatin A, Geldanamycin, and Doxorubicin responses. Especially for Group D, the mapping is speculative and should be treated as a hypothesis.

---

# Next Steps

- If full, accurate probe-to-gene annotation is available, rerun gene-level DE and perform GSEA/ORA against comprehensive gene sets (Hallmark, KEGG/Reactome) to seek mechanistic signatures (mTOR, HDAC, HSP90, DNA damage/p53) directly.
- Validate the proposed mapping against any available external benchmarks (e.g., known reference profiles, connectivity maps, or prior experiments in OCI-LY3).
- If possible, repeat analysis at the gene symbol level using alternative annotation sources or platform manifests to recover more informative markers.
- Consider time-course or dose-response data (if available) to strengthen MoA inference beyond a single endpoint.

---

# References

- Smyth, G. K. (2005). Limma: linear models for microarray data. In *Bioinformatics and Computational Biology Solutions Using R and Bioconductor* (pp. 397–420). Springer. doi:10.1007/0-387-29362-0_23
- Subramanian, A. et al. (2005). Gene set enrichment analysis: a knowledge-based approach for interpreting genome-wide expression profiles. *PNAS*, 102(43), 15545–15550. doi:10.1073/pnas.0506580102
