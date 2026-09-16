# Tissue and Anatomical Region Call for rnaseqSampleID_2 (sampleID_2)

## 1. Summary Call

**Primary tissue identity:** Central nervous system **brain**.

**Most likely anatomical region:** **Forebrain**, most consistent with **cerebral cortex and/or hippocampus**, with substantial **white-matter / glial** content (mixed neurons, astrocytes, and oligodendrocytes).

This call is supported independently by (i) strong brain-related tissue scores for rnaseqSampleID_2 relative to the full cohort, and (ii) the cluster identity and marker-gene profile of its assigned cluster (cluster 2).

---

## 2. Tissue-Score Evidence for rnaseqSampleID_2

Tissue scores were taken from `sample_by_tissue_scores.tsv` and summarized relative to all 1,802 samples. For each tissue, we computed the sample’s raw score, its z-score, and its percentile within the distribution of that tissue’s scores across samples.

### 2.1 Key quantitative results

For rnaseqSampleID_2, the brain-related tissues are clear outliers:

- **Whole_brain**: raw score **1.36**, z-score **~2.08**, **93rd percentile** among all samples.
- **Cerebral_cortex**: raw score **0.97**, z-score **~2.32**, **96th percentile**.
- **Hippocampus**: raw score **0.86**, z-score **~1.31**, **90th percentile**.
- **Cerebellum**: raw score **0.42**, z-score **~0.62**, **90th percentile**.

Non-brain tissues show modestly negative scores, generally near or below the median of their respective distributions (z-scores ~0 to −0.5, percentiles from ~15–55%), for example:

- **Liver**: raw score ~−0.14, z ≈ −0.17, ~29th percentile.
- **Kidney**: raw score ~−0.11, z ≈ −0.25, ~45th percentile.
- **Heart**: raw score ~−0.17, z ≈ −0.30, ~54th percentile.
- **Whole_blood_immune**: raw score ~−0.28, z ≈ −0.46, ~18th percentile.
- **Spleen**: raw score ~−0.32, z ≈ −0.48, ~16th percentile.

Overall, rnaseqSampleID_2 is **strongly enriched for brain-like expression** and **depleted or neutral for non-brain tissues**, based purely on tissue scores.

A compact table of these statistics is saved as:

- `project/outputs/tables/sampleID_2_tissue_scores.tsv`

This table includes, for each tissue: `tissue`, `raw_score`, `z_score_within_tissue`, `percentile_within_tissue`, and distributional summaries across all samples.

---

## 3. Cluster-Based Evidence

### 3.1 Cluster assignment

From `sample_cluster_assignments.tsv`, rnaseqSampleID_2 is assigned to:

- **Cluster label:** **2**

Cluster 2 contains 379 samples and, based on the clustering report, represents a **CNS brain cluster**.

### 3.2 Marker genes and functional themes for Cluster 2

Using `cluster_markers.tsv` and the cluster summary in `cluster_annotation_summary.md`, Cluster 2 is characterized by:

- **Astrocyte markers:** **GFAP**, **KCNJ10**, **KCNJ9**, **MT3**.
- **Oligodendrocyte / myelin markers:** **OPALIN**, **OLIG1**, **OLIG2**, **MOG**, **PLP1**, **MOBP**, **PMP2**, **BCAS1**.
- **Neuronal / synaptic markers:** **GRM3**, **ELAVL3**, **KIF5A**, **VSTM2B**, **NTSR2**, **CEND1**, **TAGLN3**, **CTNND2**, **CPNE6**.

These genes are all strongly overexpressed in Cluster 2 relative to other clusters (large log2 fold-changes and extremely significant p-values), and they are canonically associated with **central nervous system tissue**, particularly **brain gray and white matter**.

### 3.3 Anatomical interpretation from cluster context

The cluster-level report interprets Cluster 2 as:

- A **central nervous system (CNS) brain cluster** with mixed **astrocytic, oligodendrocytic, and neuronal** signatures.
- Showing strong myelin-related expression, suggesting appreciable **white-matter** representation.
- Displaying high **Whole_brain**, **Cerebral_cortex**, **Hippocampus**, and **Cerebellum** tissue scores across its member samples.

Within this context, rnaseqSampleID_2 shows:

- Very high scores for **Whole_brain**, **Cerebral_cortex**, **Hippocampus**, and **Cerebellum**, and
- No strong enrichment for any non-brain tissue.

This places rnaseqSampleID_2 firmly within a **brain-dominant gene-expression neighborhood**.

---

## 4. Integrated Tissue and Anatomical-Region Call

### 4.1 Primary call

Integrating the tissue scores and the cluster interpretation, the most consistent assignment for rnaseqSampleID_2 is:

- **Tissue:** **Brain (central nervous system)**.
- **Likely anatomical region:** **Forebrain**, most consistent with **cerebral cortex and/or hippocampus**, with substantial **white-matter / glial** content.

Rationale:

1. **Quantitative tissue scores:** All four brain-related tissue scores (Whole_brain, Cerebral_cortex, Hippocampus, Cerebellum) are in the **top ~90–96th percentiles** of their respective distributions, while non-brain tissues are not enriched.
2. **Cluster membership:** rnaseqSampleID_2 resides in a cluster whose marker genes and mean tissue scores are unambiguously CNS-brain–like.
3. **Cell-type composition signals:** The co-expression of classic astrocyte, oligodendrocyte, and neuronal markers is typical of bulk or near-bulk brain samples from cortex/hippocampus (gray matter plus adjacent white matter).

On this basis, a **non-brain** interpretation would require much stronger evidence than is present here.

### 4.2 Alternative plausible tissues (ranked)

Although the evidence is strongly brain-biased, we can list alternative interpretations and explain why they are less favored.

1. **Cerebellar brain tissue** (alternative brain sub-region)
   - **Support:** rnaseqSampleID_2 has a **Cerebellum** score near the 90th percentile, consistent with robust cerebellar-like expression in the cohort, and myelin-related genes (MOG, PLP1, MOBP, PMP2, OPALIN) are also expressed in cerebellar white matter.
   - **Why less favored:** The overall marker set (e.g., GRM3, ELAVL3, NTSR2, CTNND2) and the particularly high **Cerebral_cortex** and **Hippocampus** scores argue more strongly for **forebrain** than for cerebellum. The cerebellar interpretation likely reflects that Cluster 2 aggregates multiple brain subregions, some of which are cerebellum-enriched, but rnaseqSampleID_2 itself shows stronger cortex/hippocampus signals.

2. **General mixed or unspecific brain tissue ("Whole brain")**
   - **Support:** The **Whole_brain** score is extremely high (z ~2.1; 93rd percentile), and the cluster is broadly CNS-like. A generic “brain” label is safe and clearly supported.
   - **Why less favored than the specific forebrain call:** The combination of elevated **Cerebral_cortex** and **Hippocampus** scores and forebrain-associated neuronal markers suggests that rnaseqSampleID_2 is **not just any brain region** but is more likely to come from **cortex/hippocampus-rich samples**.

3. **Peripheral nervous system or non-classical CNS-adjacent tissue** (e.g., spinal cord, nerve)
   - **Support:** Some myelin/oligodendrocyte genes have broader roles in myelinating cells.
   - **Why much less favored:** The strong presence of canonical **brain** neuronal markers (e.g., GRM3, ELAVL3, NTSR2, KIF5A) and high scores for **Cerebral_cortex/Hippocampus/Cerebellum** are much more typical of brain parenchyma than peripheral nerve or spinal cord; moreover, there are no specific peripheral nerve markers or non-CNS tissue scores elevated.

4. **Non-brain tissues (e.g., liver, kidney, heart, blood/immune)**
   - **Support:** Essentially none from the score or cluster context. Most non-brain scores are negative and sit around the median or lower percentiles.
   - **Why not plausible:** Non-brain clusters in the dataset (e.g., immune/blood, muscle, epithelial, liver-like) have entirely different marker profiles (e.g., immune receptors, keratins, smooth muscle genes) that are **absent** from Cluster 2’s marker list. The quantitative tissue scores also do not support any non-brain tissue.

---

## 5. Caveats and Limitations

- **Sub-regional resolution:** The tissue-score panel includes only a limited set of brain subregions (Cerebral_cortex, Hippocampus, Cerebellum, Whole_brain). While rnaseqSampleID_2 is strongly forebrain-like, finer distinctions (e.g., specific cortical layers, hippocampal subfields, or other limbic areas) cannot be resolved from these data.
- **Cluster heterogeneity:** Cluster 2 contains multiple brain subregions, as suggested by elevated Cortex, Hippocampus, and Cerebellum scores across its samples. rnaseqSampleID_2 likely reflects one part of this spectrum; a more granular clustering focused only on brain samples might split cortex, hippocampus, and cerebellum into distinct subclusters.
- **Tissue-score model assumptions:** The tissue scores themselves are derived from reference marker sets and may be influenced by sample quality, sequencing depth, or partial-volume effects (e.g., varying proportions of white vs gray matter). However, the consistency between scores and cluster markers provides cross-validation.

### Potential ways to reduce uncertainty

- Incorporate additional **brain-region–specific marker panels** (e.g., layer-specific cortical genes, dentate gyrus vs CA-region markers) to refine the subregional call.
- Restrict clustering to **brain-only samples** and perform higher-resolution clustering and marker analysis to separate cortex, hippocampus, and cerebellum more clearly.
- If available, integrate **metadata** (e.g., known anatomical source, dissection notes) or **spatial transcriptomics/imaging** data to relate the expression profile to anatomical landmarks.

---

## 6. Final Interpretation

Taking all evidence together, rnaseqSampleID_2 (sampleID_2) is best interpreted as a **central nervous system brain sample**, most likely derived from **forebrain regions such as cerebral cortex and/or hippocampus**, with significant representation of **glial (astrocyte and oligodendrocyte) and neuronal** cell types and appreciable **white-matter content**.
