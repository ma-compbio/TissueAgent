# Knockout Gene Inference Report

## Title & Objective

**Objective:** Infer which gene(s) were knocked out in samples 1–3 (Group A) compared with samples 4–6 (Group B) using only the anonymized RNA‑seq count matrix, and commit to a specific gene‑level answer.

Final biological question: *Which genes were knocked out in samples 1,2,3 versus 4,5,6?*

---

## Data & Methods

### Data
- **Raw counts:** `library/datasets/anonyomized_rnaseq_count.tsv.gz`
  - 58,721 rows × 7 columns.
  - Column 1: `GeneID` (Ensembl gene IDs with version, e.g., `ENSG00000086289.11`).
  - Columns 2–7: `sample_rnaseq1` … `sample_rnaseq6` (integer RNA‑seq counts).
- **Sample grouping (inferred):**
  - **KO / Group A:** samples 1–3 → `sample_rnaseq1`, `sample_rnaseq2`, `sample_rnaseq3`.
  - **WT / Group B:** samples 4–6 → `sample_rnaseq4`, `sample_rnaseq5`, `sample_rnaseq6`.

Orientation was confirmed from dimensions and headers: genes are rows, samples are columns.

### Differential Expression (Step 2)

- **Tool:** PyDESeq2 (DESeq2‑style analysis).
- **Normalization:** Median‑of‑ratios size‑factor normalization.
- **Model:** Negative binomial GLM with dispersion shrinkage and Wald test.
- **Contrast:** `condition KO` vs `condition WT` so that:
  - `log2FoldChange = log2(KO / WT)`.
- **Outputs:**
  - `de_design.tsv`: sample IDs, group labels (A/KO vs B/WT), library sizes, method description.
  - `de_results.tsv`: for each gene, `GeneID`, `baseMean`, `log2FoldChange`, `stat`, `pvalue`, `padj` (BH‑FDR).
  - `de_volcano.png`: volcano plot of log2FC vs –log10(p/FDR), with FDR<0.05 highlighted.

### KO‑pattern Scoring (Step 3)

Using the raw counts and per‑sample library sizes, counts‑per‑million (CPM) were computed for each gene and sample. For each gene, the following metrics were derived:

- **Expression metrics:**
  - `ko_mean_cpm`, `wt_mean_cpm` – mean CPM in KO (samples 1–3) and WT (4–6).
  - `ko_max_cpm`, `wt_max_cpm` – maximum CPM within KO and WT.
  - `ko_zero_fraction`, `wt_zero_fraction` – fraction of samples in the group with **raw count = 0**.
  - `wt_over_ko_mean_fc_cpm` – fold change based on group means:
    - `(wt_mean_cpm + 0.1) / (ko_mean_cpm + 0.1)` (0.1 CPM pseudocount for stability).

- **DE statistics (from DESeq2‑style results):**
  - `baseMean`, `log2FoldChange` (KO/WT), `stat`, `pvalue`, `padj`.

These were merged into `ko_pattern_scores.tsv`.

#### Composite KO Pattern Score

For each gene, a composite score was defined (higher = more KO‑like: low in KO, high in WT, strong statistics):

- `fc_term = max(0, log2(wt_over_ko_mean_fc_cpm))`
- `zero_term = 0.5 * (ko_zero_fraction + (1 - wt_zero_fraction))`  (range [0,1])
- `lfc_term = max(0, -log2FoldChange)`  (large when KO ≪ WT)
- `padj_term` based on adjusted p‑value:
  - Replace missing/NaN `padj` with 1.0.
  - Clamp `padj` to [1e-300, ∞) and set `padj_term = -log10(padj)`.
  - If `padj ≥ 1`, force `padj_term = 0`; clip `padj_term` to [0,10].

Then:

> `ko_pattern_score = fc_term + zero_term + 0.5 * lfc_term + 0.2 * padj_term`

The full table of these metrics is stored in `ko_pattern_scores.tsv`. A coarse top‑20 list by score is recorded in `ko_top_candidates.tsv`.

### Final KO Gene Selection (Step 4)

A strict decision rule was applied to **all** 58,721 genes in `ko_pattern_scores.tsv` to define primary KO calls.

**Primary KO criteria (very stringent):**

1. **Very low expression in KO (Group A):**
   - `ko_zero_fraction ≥ 2/3` (at least 2 out of 3 KO samples have zero raw counts).
   - `ko_mean_cpm < 0.5` CPM.
2. **Robust expression in WT (Group B):**
   - `wt_zero_fraction == 0` (all 3 WT samples non‑zero).
   - `wt_mean_cpm ≥ 5` CPM.
3. **Strong WT ≫ KO contrast:**
   - `wt_over_ko_mean_fc_cpm ≥ 20`.
   - `log2FoldChange ≤ -4.0` (log2(KO/WT) strongly negative).
4. **Strong statistical support:**
   - `padj < 1e-5` (Benjamini–Hochberg FDR).

Applying these filters yielded **exactly one gene**.

To optionally identify additional, clearly KO‑like but less extreme genes, a *secondary* relaxed filter was also defined (used only for interpretation, not to change the primary call):

- KO: `ko_zero_fraction ≥ 1/3`, `ko_mean_cpm < 1.0`.
- WT: `wt_zero_fraction ≤ 1/3`, `wt_mean_cpm ≥ 3.0`.
- Contrast: `wt_over_ko_mean_fc_cpm ≥ 10.0`, `log2FoldChange ≤ -3.5`.
- Statistics: `padj < 1e-5`.

Genes passing these relaxed criteria (excluding the primary gene) were considered **secondary candidates**.

Ensembl IDs (version‑stripped) were mapped to official human gene symbols via the `mygene` service (`scopes='ensembl.gene'`, `fields='symbol,name'`, `species='human'`).

---

## Results

### Primary knockout gene (strict criteria)

Exactly one gene satisfied all strict primary KO criteria:

**EPDR1 – ENSG00000086289.11**

Key metrics (from `ko_pattern_scores.tsv` and `de_results.tsv`):

- `GeneID` (Ensembl): **ENSG00000086289.11**
- Official symbol: **EPDR1**
- `ko_mean_cpm` = **0.162951**
- `wt_mean_cpm` = **17.182977**
- `ko_zero_fraction` = **0.666667** (2 of 3 KO samples zero)
- `wt_zero_fraction` = **0.0** (all WT samples non‑zero)
- `wt_over_ko_mean_fc_cpm` = **65.7269**
- `log2FoldChange (KO/WT)` = **–6.7898**
- `padj` = **4.67×10⁻¹⁴**
- `ko_pattern_score` = **12.27** (highest observed)

**Raw counts (sanity check):**

- KO (samples 1–3: `sample_rnaseq1–3`): **[0, 0, 3]**
- WT (samples 4–6: `sample_rnaseq4–6`): **[126, 124, 102]**

This pattern is exactly what is expected for a gene knocked out in samples 1–3 and intact in 4–6: near‑complete absence (two zeros, one very low count) in KO and strong, consistent expression in all WT samples, with a very large fold‑change and extremely significant DE statistics.

### Secondary candidate (relaxed criteria)

Under the relaxed, secondary criteria (used only to flag additional KO‑like behavior), one additional gene emerged:

**CAV3 – ENSG00000182533.6**

- `GeneID` (Ensembl): **ENSG00000182533.6**
- Official symbol: **CAV3**
- `ko_mean_cpm` = **0.221183**
- `wt_mean_cpm` = **3.678504**
- `ko_zero_fraction` = **0.333333** (1 of 3 KO samples zero)
- `wt_zero_fraction` = **0.0** (all WT samples non‑zero)
- `wt_over_ko_mean_fc_cpm` = **11.7643**
- `log2FoldChange (KO/WT)` = **–4.1452**
- `padj` = **4.43×10⁻⁶**
- `ko_pattern_score` = **7.37**

**Raw counts:**

- KO samples 1–3: **[2, 0, 2]**
- WT samples 4–6: **[25, 27, 23]**

CAV3 clearly shows lower expression in KO and robust expression in all WT samples, with strong statistical support, but does not meet the very strict primary thresholds (fewer zeros in KO, lower WT expression, smaller fold‑change, lower KO‑pattern score). It is therefore treated as a **secondary candidate**, not the primary knockout.

### Answer in requested format

Given the requirement to commit to a specific answer and the stringent decision rule, the gene that was knocked out in samples 1–3 versus 4–6 is:

> **EPDR1**

(Secondary candidate with a KO‑like pattern: **CAV3**, but EPDR1 is the clear primary knockout under strict criteria.)

---

## Caveats & Warnings

- **Sample size:** Only 3 KO and 3 WT samples were available; although DESeq2‑style shrinkage mitigates small‑n issues, subtle effects could be underpowered. The EPDR1 signal, however, is extreme.
- **Single‑dataset inference:** The knockout inference is purely observational from this one dataset; no experimental validation is available here.
- **Annotation dependence:** Gene symbol mapping used `mygene` and Ensembl IDs; if future annotation versions change, mappings should be re‑checked, though EPDR1 and CAV3 are standard, stable symbols.

---

## Next Steps

- **Biological follow‑up:**
  - Validate the EPDR1 knockout in samples 1–3 using orthogonal methods (e.g., PCR, Western blot, or targeted re‑sequencing) if experimental work is possible.
- **Robustness checks:**
  - Re‑run the analysis with an independent DE tool (e.g., edgeR, limma‑voom) to confirm the EPDR1 signal.
- **Functional interpretation:**
  - Explore known functions and pathways associated with EPDR1 (and CAV3 as a secondary candidate) to interpret the phenotypic consequences of the knockout.

---

## References

- Love MI, Huber W, Anders S. *Moderated estimation of fold change and dispersion for RNA‑seq data with DESeq2.* Genome Biol. 2014;15(12):550. doi:10.1186/s13059-014-0550-8
- Robinson MD, McCarthy DJ, Smyth GK. *edgeR: a Bioconductor package for differential expression analysis of digital gene expression data.* Bioinformatics. 2010;26(1):139–140. doi:10.1093/bioinformatics/btp616
- Ritchie ME, et al. *limma powers differential expression analyses for RNA-sequencing and microarray studies.* Nucleic Acids Res. 2015;43(7):e47. doi:10.1093/nar/gkv007
