# Title & Objective

**Title:** Cell line identification for RNA-seq sample A

**Objective:**
Determine which of 24 candidate human cell lines best matches the gene expression profile of RNA-seq sample A, using only its bulk gene-level expression data.

---

# Data & Methods

## Data
- Input expression file: `library/datasets/sample_A_gene_quantifications.tsv` (bulk RNA-seq quantifications).
- Derived sample vector: `project/outputs/tables/sample_A_tpm_vector.tsv` (columns: `gene_id`, `TPM`).
- Marker signatures for candidate cell lines: `project/outputs/tables/cell_line_marker_signatures.tsv`.

## Candidate cell lines (24)
K562, HL-60, GM12878 (not explicitly modeled; see caveats), DND-41 (not explicitly modeled; see caveats), THP-1, HepG2, A549, IMR-90, MCF-7, MDA-MB-231, HCT116, Caco-2, SW620, SK-N-SH, SH-SY5Y, BE2C, PC-3, DU145, Panc1, HEK293, H1, H9, BJ, HFFc6.

## Processing and ID harmonization
- Used the `TPM` column from the original quantification table as the primary expression measure.
- Total genes in the raw table: 59,429; detected genes (TPM > 0): 23,088.
- Harmonization of gene identifiers:
  - Treated IDs starting with `ENSG` as Ensembl gene IDs with version (e.g. `ENSG00000000419.12`).
  - Stripped version suffixes (e.g. `ENSG00000000419.12 → ENSG00000000419`).
  - Mapped Ensembl IDs to HGNC symbols using **mygene.info** (`mygene` Python package) with `scopes='ensembl.gene'`, `fields='symbol'`, `species='human'` (GRCh38-based).
  - For non-`ENSG` IDs, used the raw `gene_id` as a putative symbol.
  - Dropped rows with no resolvable symbol; aggregated TPM by `gene_symbol` (sum).
- Result: 44,555 unique gene symbols with TPM values.

## Marker signatures and scoring
- Marker signatures (20–30 HGNC symbols per line, with integer weights 2–3) were curated from CCLE/DepMap patterns, ATCC datasheets, Human Protein Atlas, and lineage-specific literature.
- Lineages encoded include: erythroid, myeloid (granulocytic and monocytic), hepatocyte, lung epithelial, breast epithelial (luminal and EMT-like), colon epithelial (primary, enterocyte-like, metastatic), neural/neuroblastoma, prostate epithelial, pancreatic ductal, kidney/embryonic, pluripotent stem cell (hESC, hiPSC), fibroblast, and generic epithelial.

### Expression transform and metrics
- To stabilize scores and avoid domination by zeros:
  - Applied a floor TPM value: `TPM_capped = max(TPM, 0.01)`.
  - Computed `log2_TPM_plus1 = log2(TPM_capped + 1)` for each gene.
- Also computed a rank-based metric:
  - Ranked genes by TPM (descending); for each gene with rank *r* among *N* genes:
    - `rank_frac = 1 - (r - 1)/N` → top gene has 1.0; lowest-ranked gene approaches 0.0; genes not found get 0.

### Similarity scores per cell line
For each cell line *c* with marker set *M_c* and weights *w_g*:
- **Primary score (reported):** weighted mean log2(TPM+1)
  \[
  S_{primary}(c) = \frac{\sum_{g \in M_c} w_g \cdot \log_2(\text{TPM}_g^{capped} + 1)}{\sum_{g \in M_c} w_g}
  \]
- **Secondary metrics:**
  - Fraction of markers with TPM ≥ 1:
    \[
    f_{\ge 1}(c) = \frac{\#\{g \in M_c : \text{TPM}_g \ge 1\}}{|M_c|}
    \]
  - Weighted mean rank fraction:
    \[
    R_{wmean}(c) = \frac{\sum_{g \in M_c} w_g \cdot \text{rank\_frac}_g}{\sum_{g \in M_c} w_g}
    \]

Scores and methods are detailed in `project/outputs/reports/cell_line_identity_prediction.md`.

---

# Results

## 1. Global expression summary
- TPM distribution (all genes):
  - min: 0.0
  - max: 41,889.23
  - mean: 16.59
  - median: 0.0
  - Q1: 0.0
  - Q3: 0.54
  - standard deviation: 373.58
  - total genes: 59,429
  - zero-TPM genes: 36,341
  - nonzero-TPM genes: 23,088
- Distribution is highly right-skewed, with a small subset of genes extremely highly expressed.

## 2. Cell line similarity scores

Top candidates, sorted by **primary score (weighted mean log2(TPM+1) over markers)**:

- **K562**
  - Primary score: **5.61**
  - Fraction of markers with TPM ≥ 1: **0.86**
  - Weighted mean rank fraction: **0.88**
  - n_markers: 28; sum_weight: 71
- **PC-3**
  - Primary score: 2.55; frac_markers_TPM≥1: 0.48; rank_frac_wmean: 0.61
- **A549**
  - Primary score: 2.45; frac_markers_TPM≥1: 0.48; rank_frac_wmean: 0.67
- **HEK293**
  - Primary score: 2.42; frac_markers_TPM≥1: 0.48; rank_frac_wmean: 0.65
- **MCF-7**
  - Primary score: 2.38; frac_markers_TPM≥1: 0.48; rank_frac_wmean: 0.72
- **DU145**
  - Primary score: 2.34; frac_markers_TPM≥1: 0.44; rank_frac_wmean: 0.60
- **Epithelial_generic**
  - Primary score: 2.32; frac_markers_TPM≥1: 0.44; rank_frac_wmean: 0.65
- **MDA-MB-231**
  - Primary score: 2.26; frac_markers_TPM≥1: 0.48; rank_frac_wmean: 0.73
- Remaining lines (SW620, HCT116, Panc1, HFFc6, BJ, HepG2, IMR-90, H1, H9, hiPSC, Caco-2, HL-60, THP-1, BE2C, SH-SY5Y, SK-N-SH) have primary scores between ~0.48 and 2.06, all well below K562’s 5.61.

**Conclusion from scoring:**
- K562’s primary score is more than **double** that of any other candidate cell line, and its secondary metrics indicate that most of its markers are both highly expressed and rank among the top-expressed genes in the sample.

## 3. Lineage-specific marker evidence for K562

The sample shows a classic **erythroid / erythroleukemia** expression program:

- **Hemoglobins and erythroid structural genes (very high TPM):**
  - HBG2 (γ-globin): 1,638.6 TPM
  - HBG1 (γ-globin): 1,394.8 TPM
  - HBA1 (α-globin): 1,373.2 TPM
  - HBA2 (α-globin): 337.2 TPM
  - GYPA (glycophorin A): 264.0 TPM
  - GYPB (glycophorin B): 154.8 TPM
  - ALAS2 (erythroid ALA synthase): 38.4 TPM
  - AHSP (α-hemoglobin stabilizing protein): 30.7 TPM

- **Erythroid transcription factors and regulators (high TPM):**
  - GATA1: 141.5 TPM
  - NFE2: 138.5 TPM
  - TAL1: 79.7 TPM
  - KLF1: 36.1 TPM
  - LMO2: 28.7 TPM
  - HEMGN: 163.9 TPM

- **Leukemia-defining fusion partners (supporting CML/K562):**
  - BCR: 50.4 TPM
  - ABL1: 51.1 TPM

This combination of strong erythroid globin expression, lineage-defining TFs, and BCR/ABL1 expression is characteristic of **K562**, a BCR–ABL1–positive chronic myelogenous leukemia blast crisis line with erythroid features.

By contrast:
- **HL-60 / THP-1 (myeloid lines)** show some myeloid markers but lack hemoglobin expression and score much lower (~1.0–1.1 primary).
- **HepG2 (hepatoma)** exhibits some liver markers but cannot explain the dominant erythroid signature.
- **Epithelial carcinomas** (A549, MCF-7, PC-3, DU145, etc.) show epithelial and carcinoma marker enrichment but not erythroid genes.
- **Pluripotent, fibroblast, and neuronal lines** have low scores and lack an erythroid program.

**Final prediction:**
- The RNA-seq sample is best explained as originating from **K562**.

---

# Caveats & Warnings

- **Incomplete explicit modeling of two candidate lines:**
  - The user’s candidate list includes **GM12878** (B-lymphoblastoid) and **DND-41** (T-ALL), which were not given dedicated marker signatures in the curated table. Instead, only generic lymphoid-related markers are indirectly represented through the existing marker sets.
  - However, the sample’s overwhelmingly erythroid transcriptional program and extremely high K562 score make B- or T-lymphoid identities highly implausible for this dataset.
- **Reliance on external annotation service:**
  - Ensembl-to-HGNC mapping used the mygene.info service; discrepancies or missing mappings could, in principle, slightly alter scores. Marker coverage was very high (293/295 markers mapped), so impact is minimal.
- **Single-sample, signature-based classification:**
  - The method uses curated marker sets and does not rely on direct comparison to matched RNA-seq profiles from each line. While this is appropriate for this task, extremely atypical or perturbed samples could, in other contexts, require more nuanced modeling.

---

# Next Steps

- If desired, augment this analysis by:
  - Comparing the sample to CCLE/DepMap RNA-seq profiles quantitatively (e.g., correlation across all genes) to confirm the K562 match.
  - Incorporating explicit marker sets for GM12878 and DND-41 to fully cover all 24 listed candidates, even though they are not competitive given the erythroid profile.
  - Repeating the scoring on any additional blinded samples to identify their likely cell line of origin using the same pipeline.
