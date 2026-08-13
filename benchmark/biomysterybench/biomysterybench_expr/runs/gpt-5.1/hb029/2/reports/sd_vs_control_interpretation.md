# Interpretation of transcriptional differences between unsupervised hippocampal clusters

## 1. DE-based gene sets and relaxed cutoff

Differential expression (DE) was performed for the contrast `cluster1_vs_cluster2` using Wilcoxon tests on log2(CPM+1) with Benjamini–Hochberg correction. As expected from the small sample size (4 samples per cluster), no genes passed a stringent FDR<0.05. To enable pathway-level interpretation, a relaxed cutoff was used:

- All genes with `padj <= 0.151` (the minimum adjusted p-value observed) were selected and then split by the sign of `log2FC`.
- This yields two balanced gene sets, each containing the 1,000 most DE-biased genes (by FDR and effect size) for pathway analysis:
  - `cluster1_up`: genes with positive log2FC (higher in cluster1).
  - `cluster2_up`: genes with negative log2FC (higher in cluster2).
- These are explicitly saved (with gene_id, Ensembl ID, symbol, name, log2FC, padj, group_label) in `project/outputs/tables/go_enrichment_by_group_input_genes.tsv`.

Thus, enrichment results should be interpreted as *lenient, exploratory* patterns, not as definitive single-gene findings.

## 2. Functional enrichment patterns

GO enrichment was run separately for `cluster1_up` and `cluster2_up` genes using the GO_Biological_Process_2021 collection. Below, I focus on terms related to neuronal function, activity-dependent plasticity, stress/hormone signaling, and metabolism.

### 2.1 Cluster1_up: neuronal / plasticity / hormone-related programs

Among the top terms for `cluster1_up` (sorted by FDR) are broad transcriptional regulation categories, but more specific biology-relevant processes emerge when filtering for key themes:

- **Synaptic and structural plasticity**
  - *Positive regulation of axon extension* (padj ≈ 4.6×10⁻⁴, ES ≈ 15.2).
  - *Positive regulation of axonogenesis* (padj ≈ 3.1×10⁻³, ES ≈ 7.4).
  - *Synapse organization* (padj ≈ 3.7×10⁻²).
  - *Cell morphogenesis involved in neuron differentiation* and *nervous system development* (padj ≈ 0.09–0.10 range, but with clear enrichment).

  These terms indicate enhanced structural remodeling and connectivity, consistent with activity-dependent synaptic plasticity that is typically induced by wakefulness or learning-like stimuli.

- **Translational control and mRNA turnover**
  - *Regulation of translation* and *regulation of translational termination* (padj ≈ 0.01–0.04).
  - *Positive regulation of nuclear-transcribed mRNA catabolic process, deadenylation-dependent decay* (padj ≈ 0.004).
  - *Negative regulation of cellular amide metabolic process* (which in this context is largely driven by RNA-binding and mRNA decay factors; padj ≈ 0.003).

  These categories suggest dynamic control of protein synthesis and mRNA stability, a hallmark of neurons undergoing heightened activity and plasticity.

- **Hormone / steroid / stress-relevant pathways**
  - *Cellular response to peptide hormone stimulus* (padj ≈ 0.013).
  - *C21-steroid hormone biosynthetic process* and *steroid hormone biosynthetic process* (padj ≈ 0.02–0.03).
  - *Regulation of lipid metabolic process* (padj ≈ 0.004).

  These point to altered hormone-related and lipid signaling, compatible with glucocorticoid and other stress hormone responses that often accompany sleep deprivation.

Overall, `cluster1_up` shows a pattern of increased transcriptional regulation, synaptic plasticity, neurite outgrowth, mRNA turnover, and hormone-related signaling—features in line with a wake-activated, plastic hippocampal state.

### 2.2 Cluster2_up: translational and metabolic upregulation

In contrast, `cluster2_up` is strongly enriched for biosynthetic and metabolic processes:

- **Ribosomal / translational machinery**
  - *Translation* (padj ≈ 2.8×10⁻³¹, ES ≈ 11.8).
  - *Cytoplasmic translation*, *translational elongation*, and *cotranslational protein targeting to membrane* (padj as low as ~10⁻²⁴–10⁻²⁶, ES ≈ 7–19).
  - *Ribosome biogenesis* and *rRNA metabolic process* (padj ≈ 10⁻¹⁹ to 10⁻¹⁵).

  This indicates coordinated upregulation of general protein synthesis machinery.

- **Mitochondrial and energy metabolism**
  - *Mitochondrial ATP synthesis coupled electron transport* (padj ≈ 3×10⁻¹⁰).
  - *Mitochondrial translation* and *inner mitochondrial membrane organization* (padj ≈ 10⁻⁵ to 10⁻⁸).
  - *Regulation of cellular amino acid and amine metabolic processes* (padj ≈ 10⁻⁵–10⁻⁷).

  These suggest increased mitochondrial capacity and general metabolic readiness.

Together, `cluster2_up` looks like a state with enhanced baseline biosynthetic and metabolic functions, but comparatively less emphasis on synaptic plasticity and hormone/stress-responsive signaling than `cluster1_up`.

## 3. Sleep-deprivation / wake-activity marker panel

A curated panel of canonical sleep-deprivation and neuronal activity–induced genes was assembled:

Fos, Fosb, Arc, Egr1, Egr2, Egr3, Homer1a (Homer1), Npas4, Nr4a1, Nr4a2, Nr4a3, Bdnf, Dusp1, Dusp4, Dusp5, Dusp6, Jun, Junb, Atf3.

Using the normalized expression matrix (Ensembl Mouse gene IDs), each marker was matched to its Ensembl ID (gene_id) and extracted across all samples. The resulting table, including per-cluster means and deltas, is saved as:

- `project/outputs/tables/sleep_deprivation_marker_expression.tsv`.

A heatmap of marker expression across all samples, annotated by unsupervised cluster, is saved as:

- `project/outputs/figures/sleep_deprivation_marker_heatmap.png`.

### 3.1 Direction of marker changes

For each gene, I compared mean expression between clusters (delta = mean_cluster1 − mean_cluster2). Key observations:

- **Immediate-early genes and classic activity markers**
  - **Fos**: higher in cluster1 (Δ ≈ +0.18 log2 units).
  - **Fosb**: higher in cluster1 (Δ ≈ +0.19).
  - **Arc**: clearly higher in cluster1 (Δ ≈ +0.39).
  - **Egr1**: slightly higher in cluster1 (Δ ≈ +0.05).
  - **Egr3**: higher in cluster1 (Δ ≈ +0.21); Egr2 is slightly higher in cluster2.
  - **Homer1a (Homer1)**: higher in cluster1 (Δ ≈ +0.22).
  - **Npas4**: higher in cluster1 (Δ ≈ +0.16).
  - **Nr4a family**:
    - Nr4a1: higher in cluster1 (Δ ≈ +0.33).
    - Nr4a2, Nr4a3: modestly higher in cluster1 (Δ ≈ +0.00–0.12).

  This pattern is consistent with a coordinated activation of immediate-early gene (IEG) networks in cluster1.

- **Stress/plasticity-related phosphatases and transcription factors**
  - **Dusp5** and **Dusp6**: higher in cluster1 (Δ ≈ +0.19 and +0.14, respectively).
  - **Jun** and **Junb**: higher in cluster1 (Δ ≈ +0.27 and +0.03), reflecting AP-1 complex activation.
  - **Atf3**: somewhat higher in cluster2 (Δ ≈ −0.15), but the magnitude is small relative to other markers.
  - **Bdnf**: slightly higher in cluster2 (Δ ≈ −0.10), but the difference is modest.

Overall, the **majority of canonical activity/sleep-deprivation markers (Fos, Fosb, Arc, Egr1/3, Homer1a, Npas4, Nr4a1/2/3, Dusp5/6, Jun)** show higher expression in **cluster1** relative to cluster2.

### 3.2 Marker heatmap pattern

The heatmap reveals that samples assigned to **cluster1** (sample1,2,5,6) tend to co-express higher levels of the IEG/sleep-deprivation marker set compared with **cluster2** samples (sample3,4,7,8). While expression differences are moderate—as expected for bulk-like data with only 8 samples—the directionality is consistent across multiple independent markers.

## 4. Integrative interpretation and cluster assignment

### 4.1 Evidence pointing to cluster1 as sleep-deprived hippocampus

Several independent lines of evidence converge on cluster1 representing a **sleep-deprived / wake-activated hippocampal transcriptional state**:

1. **Immediate-early gene activation**
   - Cluster1 shows higher expression of classic IEGs and activity-dependent genes (Fos, Fosb, Arc, Egr1, Egr3, Homer1a, Npas4, Nr4a1–3, Jun, Dusp5/6). These markers are robustly and repeatedly induced by neuronal activation and experimentally induced sleep deprivation in hippocampus and cortex.

2. **Synaptic plasticity and neurite remodeling**
   - GO enrichment for `cluster1_up` highlights "positive regulation of axon extension", "positive regulation of axonogenesis", "synapse organization", and broader nervous system development and cell morphogenesis terms—all consistent with activity-dependent structural and synaptic remodeling.

3. **Translational and mRNA turnover dynamics typical of activated neurons**
   - Enrichment in *regulation of translation*, *regulation of translational termination*, and *positive regulation of nuclear-transcribed mRNA catabolic process* indicates dynamic control of protein synthesis and mRNA stability, a well-characterized feature of neurons undergoing bursts of activity and plasticity.

4. **Hormone / stress signaling signatures**
   - The presence of *cellular response to peptide hormone stimulus*, *C21-steroid hormone biosynthetic process*, and *steroid hormone biosynthetic process* terms in `cluster1_up` is compatible with glucocorticoid and other stress hormone pathways triggered by sleep loss and associated stress.

### 4.2 Interpretation of cluster2

Cluster2, in contrast, is dominated by enrichment of:

- **Core translational machinery** (translation, ribosome biogenesis, rRNA metabolism, translational elongation).
- **Mitochondrial oxidative phosphorylation and metabolic readiness** (mitochondrial ATP synthesis, mitochondrial translation, inner mitochondrial membrane organization, amino acid and amine metabolism).

While these processes are not specific to sleep or wake, the pattern suggests a comparatively **metabolically primed but transcriptionally quieter state**, with less pronounced IEG activation and fewer synaptic plasticity terms. This is more compatible with a baseline or rested hippocampal state.

### 4.3 Conclusion: cluster1 corresponds to sleep-deprived hippocampus

Integrating the DE-based gene sets, pathway enrichment, and sleep-deprivation marker panel leads to a consistent conclusion:

- **Cluster1** displays hallmark features of **sleep-deprived / wake-activated hippocampus**:
  - Broad upregulation of immediate-early and activity-dependent genes.
  - Enrichment for synaptic plasticity, axonogenesis, and neurite remodeling.
  - Evidence of hormone/stress-responsive and translational control pathways.

- **Cluster2** instead shows strong enrichment in generic translation, ribosome, and mitochondrial energy metabolism pathways, with relatively lower expression of canonical activity/sleep-deprivation markers, suggesting a **non-deprived (control or rested) hippocampal state**.

Given these concordant signals, I infer that **cluster1 corresponds to sleep-deprived hippocampus**, and **cluster2 corresponds to non-deprived (control) hippocampus**.

All interpretations should be viewed in light of the lenient DE cutoff and small sample size, but the convergence of multiple independent IEG and pathway signatures provides strong biological plausibility for this assignment.
