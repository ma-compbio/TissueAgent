# Title & Objective

**Title:** Tissue-of-origin inference for rnaseqSampleID_2 from an anonymized bulk RNA-seq matrix

**Objective:**
Infer the tissue of origin for sample `rnaseqSampleID_2` (corresponding to the user’s `sampleID_2`) using only its RNA-seq expression profile in a multi-tissue dataset, and commit to one specific tissue label including anatomical region.

---

## Data & Methods

**Input data**
- File: `library/datasets/anonymizedGeneExp.tsv.gz`
- Structure: 55,600 genes × 1,802 samples.
  - Rows: genes (first column `Gene` with symbols such as DDX11L1, WASH7P, etc.).
  - Columns: samples (`rnaseqSampleID_1` … `rnaseqSampleID_1802`).
- Values: continuous expression measures (TPM/FPKM-like; total per-sample sums ~1e6), reasonably uniform library sizes across samples.

**Step 1 – QC and data inventory**
- Confirmed orientation (genes as rows, samples as columns) from header patterns and data types.
- Computed per-sample QC metrics:
  - Library size (sum of expression across genes).
  - Number of expressed genes (>0 expression).
  - Mean, median, and selected quantiles of expression.
- Stored summaries in:
  - `project/outputs/tables/data_inventory.tsv`
  - `project/outputs/tables/sample_qc_summary.tsv`

**Step 2 – Tissue marker panels and scoring**
- Constructed knowledge-based marker panels for 23 tissues / regions:
  - Brain: `brain_cortex`, `brain_cerebellum`
  - Others: `heart`, `skeletal_muscle`, `liver`, `kidney`, `lung`, `blood_immune`, `small_intestine`, `colon`, `pancreas`, `stomach`, `adipose`, `skin`, `testis`, `ovary`, `uterus_endometrium`, `prostate`, `thyroid`, `salivary_gland`, `pituitary`, `placenta`, `spleen_lymphoid`.
- For each tissue:
  - Started from canonical human marker genes (e.g., ALB for liver, SFTPC for lung, PRM1/2 for testis, KLK3 for prostate, TG/TPO for thyroid, neuronal markers like RBFOX3, NRGN, SLC17A7, MAP2, SNAP25, etc.).
  - Restricted to markers present in the matrix.
  - Ensured each tissue retained ≥3 markers after filtering; mild variance filtering was applied but relaxed if it would reduce a tissue below this minimum.
- Computed tissue scores per sample (`project/outputs/tables/tissue_scores_by_sample.tsv`):
  - For each tissue T and sample S, raw mean:
    - `rawmean_T(S)` = mean(expression of all marker genes for T in sample S).
  - Within each sample S, across tissues:
    - Z-score the vector of raw means to get `score_T(S)`:
      - subtract per-sample mean across tissues, divide by per-sample SD.
  - The `score_*` columns are the primary signals for tissue calling; `rawmean_*` columns provide absolute expression context.

**Step 3 – Tissue calling**
- For each sample, including `rnaseqSampleID_2`, used the following rule:
  - Identify `top_tissue` as argmax over `score_*` z-scores.
  - Identify `second_best_tissue` as the next-highest score.
  - Record `score_top`, `score_second`, and `score_gap = score_top − score_second`.
  - Assign `predicted_tissue = top_tissue`.
  - Define a confidence label:
    - High: `score_top ≥ 4` and `score_gap ≥ 2`.
    - Medium: `score_top ≥ 3` or `score_gap ≥ 1` (if not high).
    - Low: all other cases.
- Stored sample-level predictions in:
  - `project/outputs/tables/predicted_tissues.tsv`
- For `rnaseqSampleID_2`, additionally inspected its expression profile directly:
  - Extracted its expression vector and ranked genes by expression.
  - Examined the top ~50 genes, focusing on canonical CNS vs non-CNS markers.
- Summarized the detailed reasoning for rnaseqSampleID_2 in:
  - `project/outputs/reports/sampleID_2_tissue_call.md`

---

## Results

### Global tissue assignments
- The argmax-z-score rule produced one predicted tissue per sample (no unassigned samples).
- Example predominant tissue counts (out of 1,802 samples):
  - `skeletal_muscle`: 423
  - `spleen_lymphoid`: 295
  - `brain_cortex`: 269
  - `adipose`: 148
  - `skin`: 140
  - `heart`: 94
  - `thyroid`: 63
  - `blood_immune`: 61
  - `testis`: 43
  - `pituitary`: 42
  - `brain_cerebellum`: 40
  - plus smaller groups for liver, lung, pancreas, prostate, stomach, small_intestine, colon, kidney, uterus_endometrium, etc.

These distributions resemble a plausible multi-tissue atlas and serve as context for the specific call on rnaseqSampleID_2.

### Tissue-of-origin for rnaseqSampleID_2

- **Sample ID:** `rnaseqSampleID_2` (user’s `sampleID_2`)
- **Predicted tissue:** **brain_cortex (cerebral cortex)**
- **Confidence:** **High**

**Score-based evidence**
- From `tissue_scores_by_sample.tsv` for rnaseqSampleID_2:
  - `score_brain_cortex` ≈ **4.57** (z-score within sample)
  - Runner-up tissues:
    - `score_brain_cerebellum` ≈ **0.03**
    - `score_spleen_lymphoid` ≈ **0.01**
  - All other tissues have scores around **−0.18 to −0.26**.
- Score gap:
  - `score_gap` (cortex − second best) ≈ **4.54**.
  - Across all samples, the median gap is ≈ 3.62 and the 75th percentile ≈ 4.39, so rnaseqSampleID_2 is in the upper tail of separation between first and second tissues.

**Absolute marker expression (raw means)**
- For rnaseqSampleID_2:
  - `rawmean_brain_cortex` ≈ **247.2**
  - Next highest raw means:
    - `rawmean_brain_cerebellum` ≈ **15.3**
    - `rawmean_spleen_lymphoid` ≈ **14.2**
    - Most other tissues: roughly **0–4.5**.
- Interpretation:
  - Cortex markers are expressed at levels roughly **10–20× higher** than any other tissue’s marker panel.
  - Both the relative (z-score) and absolute (`rawmean_*`) signals uniquely favor **brain_cortex**.

**Top expressed genes in rnaseqSampleID_2**
- Among the highest-expressed genes (excluding ubiquitous mitochondrial and housekeeping genes), many are canonical CNS / cortical neuronal or glial markers, e.g.:
  - **NRGN (Neurogranin)** – postsynaptic protein enriched in excitatory neurons, especially in cerebral cortex.
  - **UCHL1 (PGP9.5)** – neuron-specific deubiquitinase, widely used neuron marker.
  - **SPARCL1** – astrocyte/brain vascular associated, enriched in brain, especially cortex.
  - **MT3** – metallothionein isoform with brain-enriched expression.
  - **KIF5A** – neuron-specific kinesin heavy chain involved in axonal transport.
  - **ALDOC, ITM2C, CPE, NDRG2, TSPAN7, PSAP, CKB, CALM1/2/3**, and similar genes characteristic of neuronal/glial expression.
- Notably **absent** among top-expressed genes are strong markers of other tissues:
  - Liver (e.g., **ALB**, **TTR**),
  - Kidney (e.g., **UMOD**, **SLC5A2**),
  - Heart/skeletal muscle (e.g., **MYH7**, **TNNT2**, **ACTN2**),
  - Skin (keratins such as **KRT1**, **KRT10**, **KRT14**),
  - Classic endocrine markers from thyroid, testis, prostate, etc.

**Comparison with other cortex samples**
- Among samples predicted as `brain_cortex`:
  - Median `score_brain_cortex` ≈ **4.27** (IQR ~3.76–4.55).
- Among non-cortex samples:
  - Median `score_brain_cortex` ≈ **−0.24**, maximum ≈ **3.07**.
- rnaseqSampleID_2 has `score_brain_cortex` ≈ **4.57**, placing it in the **upper range of cortex-predicted samples** and clearly above the non-cortex range.
- Its profile therefore matches well with other samples inferred as cortical brain tissue.

**Ruling out alternatives**
- **brain_cerebellum:**
  - Z-score only ~0.03 and rawmean ~15.3, far below cortex (247.2).
  - Some shared neuron markers exist, but the magnitude and specific set of top markers strongly favor cortex.
- **Immune/lymphoid (blood_immune, spleen_lymphoid):**
  - Slightly positive or near-zero z-scores, but rawmeans (~14) are modest, and the top genes are neuron/glia, not immune markers.
- **Muscle, heart, liver, kidney, skin, and other solid organs:**
  - All have **negative z-scores** (~−0.18 to −0.26) for rnaseqSampleID_2.
  - Their canonical markers are neither strongly expressed nor enriched among the top genes.

**Final interpretation:**
- The combination of:
  - a **very high cortex-specific z-score**,
  - a **large gap** to the next tissue,
  - **very high absolute expression** of cortex markers,
  - and a **top-gene list dominated by well-known neuronal and glial markers**

  makes **brain_cortex (cerebral cortex)** the only tissue assignment consistent with the data.

---

## Caveats & Warnings

- Marker panels were assembled from general biological knowledge rather than a formally curated atlas; while they rely on well-established markers, subtle subregion distinctions within cortex (e.g., specific Brodmann areas) cannot be resolved.
- Tissue scores are z-scored within each sample; they are optimized for **within-sample** tissue ranking, not absolute cross-sample comparisons of tissue abundance.
- The analysis assumes each sample is dominated by a single tissue; mixed or highly heterogeneous samples (e.g., tissue with large infiltrates) might be simplified to one label.

---

## Next Steps

- If available, compare these inferred tissues against any external metadata or known labels for validation.
- Extend marker panels or incorporate reference-based deconvolution if finer distinctions within brain (e.g., cortical layers or specific neuronal subtypes) are desired.
- Apply similar tissue-calling logic to other samples of interest using `predicted_tissues.tsv` and `tissue_scores_by_sample.tsv`.

---

## References

- Uhlén M et al., "Tissue-based map of the human proteome." *Science* 2015;347(6220):1260419. doi:10.1126/science.1260419.
- GTEx Consortium, "The GTEx Consortium atlas of genetic regulatory effects across human tissues." *Science* 2020;369(6509):1318–1330. doi:10.1126/science.aaz1776.
- Lein ES et al., "Genome-wide atlas of gene expression in the adult mouse brain." *Nature* 2007;445(7124):168–176. doi:10.1038/nature05453 (for canonical CNS marker context).
