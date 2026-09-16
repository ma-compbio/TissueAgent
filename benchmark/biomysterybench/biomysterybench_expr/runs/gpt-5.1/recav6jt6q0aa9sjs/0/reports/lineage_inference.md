# Lineage / Tissue-of-Origin Inference for sample_A

## Data and methods

- Input: gene-level RNA-seq quantifications from `library/datasets/sample_A_gene_quantifications.tsv`.
- Expression measure: TPM from the `TPM` column.
- Gene IDs: Ensembl (some with version suffixes). For scoring, Ensembl IDs from a curated marker list were matched after stripping any version suffix from the expression matrix.
- Marker sets: curated panels (10–15 genes each) for 13 broad lineages/tissues:
  - B cell
  - T cell
  - Myeloid (monocyte/granulocyte)
  - Hepatocyte / liver
  - Lung epithelium
  - Colon / intestinal epithelium
  - Breast epithelium
  - Prostate epithelium
  - Pancreas (exocrine/endocrine)
  - Neural / neuronal / glial
  - Pluripotent stem cell (ESC/iPSC-like)
  - Fibroblast / mesenchymal
  - Kidney proximal tubule / epithelium

Markers were initially specified as HGNC symbols and mapped to Ensembl gene IDs using a hard-coded mapping dictionary for common, well-established markers. Any symbols that could not be mapped, or mapped to Ensembl IDs not present in the quantification table, were recorded as such and ignored in scoring.

Lineage scores were computed as:

- **Primary score:** mean log2(TPM + 1) across all mapped markers for the lineage.
- **Secondary metrics:**
  - Fraction of markers with TPM > 1.
  - Fraction of markers with TPM > 10.

These metrics are directly comparable across lineages because they use the same expression transformation and thresholds.

## Overview of lineage scores

Summary of scores (sorted by primary score; higher means stronger marker expression):

- Colon / intestinal epithelium: mean log2(TPM+1) ≈ 2.69; ~40% of markers TPM>1 and ~40% TPM>10.
- Fibroblast / mesenchymal: mean log2(TPM+1) ≈ 2.40; ~38% TPM>1 and ~31% TPM>10.
- Lung epithelium: mean log2(TPM+1) ≈ 1.95; 50% TPM>1 and ~29% TPM>10.
- Breast epithelium: mean log2(TPM+1) ≈ 1.80.
- Myeloid: mean log2(TPM+1) ≈ 1.76.
- Neural / neuronal / glial: mean log2(TPM+1) ≈ 1.68.
- Pancreas: mean log2(TPM+1) ≈ 1.66.
- B cell: mean log2(TPM+1) ≈ 1.35.
- T cell: mean log2(TPM+1) ≈ 1.34.
- Kidney proximal tubule: mean log2(TPM+1) ≈ 1.13.
- Hepatocyte / liver: mean log2(TPM+1) ≈ 0.96.
- Pluripotent stem cell: mean log2(TPM+1) ≈ 0.86.
- Prostate: mean log2(TPM+1) ≈ 0.82.

A heatmap of the primary scores is saved as `project/outputs/figures/lineage_marker_heatmap.png`.

## Likely tissue-of-origin

### 1. Strongest signal: Colon / intestinal epithelium

The **colon / intestinal epithelium** marker set shows the highest overall enrichment and contains several classic intestinal epithelial markers with high TPM values:

- **MS4A12** (colon-specific surface marker): TPM ~1350 — extremely high, strongly indicative of colon epithelium.
- **EPCAM** (epithelial cell adhesion molecule): TPM ~50.
- **CA1** (carbonic anhydrase 1, typical of colon enterocytes): TPM ~30.
- **SI** (sucrase-isomaltase, brush-border enzyme): TPM ~25.
- **CA2**: TPM ~0.7.

Other canonical colon markers like **MUC2**, **KRT20**, **ALPI**, and **CDX1** were present in the marker list but had low or undetectable TPM in this sample, which may reflect the exact sublineage or differentiation state (e.g. more absorptive than goblet-cell-like).

Taken together, the high expression of MS4A12, CA1, SI, and EPCAM is strongly consistent with an **intestinal / colorectal epithelial** origin.

### 2. Secondary signal: Fibroblast / mesenchymal

The **fibroblast / mesenchymal** lineage scores second-highest, driven by extracellular matrix and mesenchymal markers:

- **COL1A2**: TPM ~343.
- **VIM** (vimentin): TPM ~227.
- **ITGB1**: TPM ~162.
- **COL5A2**: TPM ~34.

Such markers are often upregulated in epithelial cancer cell lines undergoing partial epithelial–mesenchymal transition (EMT) or with stromal-like features. Given the very strong epithelial and colon-specific signals noted above, these mesenchymal markers likely reflect EMT or a mixed epithelial–mesenchymal phenotype of a colorectal-derived line, rather than a primary fibroblast origin.

### 3. Additional epithelial signal: Lung / breast

Lung and breast epithelial marker sets show intermediate scores:

- **Lung epithelium**: high expression of generic epithelial markers and some lung-associated genes:
  - **KRT8**: TPM ~140.
  - **EPCAM**: TPM ~50 (shared with colon epithelium).
  - **SFTPA1**: TPM ~37.
  - **MUC1**: TPM ~15.
  - **SCGB1A1**: TPM ~2.8.
- **Breast epithelium**: expression of common epithelial markers (KRT8/18/19, EPCAM, MUC1) but relatively weak hormone receptor and ERBB2 signals.

These results support an epithelial carcinoma-like expression pattern, but the presence of strongly colon-restricted markers (e.g. MS4A12, CA1, SI) points more specifically to **intestinal/colorectal** rather than lung or breast.

## Lineages with weak or absent support

Several marker sets show relatively low scores and/or lack of hallmark lineage-defining genes, arguing against these tissues as the major origin:

- **Hepatocyte / liver:** modest expression of some liver-associated genes, but classic hepatocyte markers (e.g. very high **ALB**, **TTR**, **CYP3A4**) are not strongly expressed overall.
- **Kidney proximal tubule:** kidney-specific transporters (e.g. **SLC34A1**, **LRP2**, **CUBN**) do not show a dominant signal.
- **Pancreas:** endocrine markers (**INS**, **GCG**, **SST**, **PPY**) and key exocrine enzymes (**PRSS1**, **CPA1**, **CTRB1/2**) are not strongly expressed.
- **Neural / neuronal / glial:** neuronal markers (**MAP2**, **TUBB3**, **RBFOX3**) and glial markers (**GFAP**, **MBP**, **MOG**) are generally low.
- **Pluripotent stem cell (ESC/iPSC):** core pluripotency factors (**POU5F1/OCT4**, **SOX2**, **NANOG**) are low, arguing against a stem-cell-like line as the primary identity.
- **Prostate:** typical prostate markers (**KLK3/PSA**, **KLK2**, **NKX3-1**, **TMPRSS2**) are weak overall.
- **B cell / T cell / myeloid:** while some immune markers are detectable, there is no coherent pattern of strong B-, T-, or myeloid-specific receptor and transcription factor expression to suggest a primary hematopoietic origin.

## Conclusion

Based on the curated marker scoring and expression patterns in this sample:

- The **most strongly supported tissue-of-origin** is **colon / intestinal epithelium**, driven by very high expression of classic intestinal markers such as **MS4A12**, **CA1**, **SI**, and **EPCAM**.
- A **secondary fibroblast/mesenchymal signature** (e.g. **COL1A2**, **VIM**, **ITGB1**) is present, consistent with epithelial–mesenchymal features often seen in carcinoma cell lines rather than indicating a true fibroblast lineage.
- Other epithelial lineages (lung, breast) show some overlapping epithelial marker expression but lack the strong colon-restricted markers observed here.
- Hematopoietic, neural, hepatocyte, pancreatic, pluripotent, kidney, and prostate signatures are comparatively weak and can be reasonably **ruled out as primary tissues-of-origin** for this sample, given the available expression data.

Overall, the expression profile is most consistent with a **colorectal/intestinal epithelial cancer cell line** or a closely related intestinal epithelial derivative.
