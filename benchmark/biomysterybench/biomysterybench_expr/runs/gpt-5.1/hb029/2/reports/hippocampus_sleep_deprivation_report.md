# Title & Objective

**Title:** Inference of sleep-deprived vs control hippocampus RNA-seq samples

**Objective:**
Identify which of eight bulk hippocampal RNA-seq samples (sample1–sample8), provided without labels, were obtained from sleep-deprived mice, using only their gene-expression profiles.

---

## Data & Methods

**Data:**
- Counts matrix `hb029_counts_cleaned.csv` (51,826 genes × 8 samples; samples named sample1–sample8).
- No additional metadata (no labels or covariates) were provided.

**Pre-processing & QC:**
- Interpreted matrix as genes in rows and samples in columns.
- Computed per-sample QC metrics:
  - Total counts (library size).
  - Number of detected genes (count > 0).
  - Percent of counts in the top 100 most expressed genes.
- Filtered out very lowly expressed genes: kept genes with raw count ≥ 1 in at least 2 samples (34,361 genes retained).

**Normalization & transformation:**
- Library-size normalization to counts per million (CPM).
- Log-transformation: log2(CPM + 1).
- Saved normalized matrix as `project/outputs/tables/expression_normalized.tsv`.

**Unsupervised sample analysis:**
- Computed sample–sample Pearson correlation on log2(CPM+1) and visualized as a clustered heatmap.
- Performed PCA on samples (using all filtered genes), visualizing the first two PCs.
- Performed hierarchical clustering of samples using correlation distance (1 − Pearson r) and average linkage.
- Cut the dendrogram at 2 clusters, yielding:
  - **cluster1:** sample1, sample2, sample5, sample6
  - **cluster2:** sample3, sample4, sample7, sample8

**Differential expression (DE):**
- Worked on log2(CPM+1) expression.
- For each gene, compared cluster1 (n=4) vs cluster2 (n=4) using Wilcoxon rank-sum (Mann–Whitney U) tests.
- Computed:
  - log2FC = mean(cluster1) − mean(cluster2) (on log2 scale).
  - Raw p-values from Wilcoxon tests.
  - Benjamini–Hochberg FDR-adjusted p-values (padj).
- Saved full DE table as `project/outputs/tables/de_results_all_contrasts.tsv`.
- Note: No genes reached padj < 0.05, reflecting limited power (4 vs 4 samples).

**Gene-set and pathway analysis (exploratory):**
- Constructed lenient gene signatures per cluster from the DE table:
  - `cluster1_up`: genes with positive log2FC and among the 1,000 most cluster1-biased genes by padj and effect size.
  - `cluster2_up`: genes with negative log2FC and among the 1,000 most cluster2-biased genes.
- These relaxed signatures (padj ≲ 0.151) are stored in
  `project/outputs/tables/go_enrichment_by_group_input_genes.tsv`.
- Performed GO Biological Process enrichment (GO_Biological_Process_2021) separately for `cluster1_up` and `cluster2_up` using over-representation analysis.
- Summarized results in `project/outputs/tables/go_enrichment_by_group.tsv` and visualized top terms as a dot plot (`project/outputs/figures/go_dotplot_by_group.png`).

**Sleep-deprivation / wake-activity marker panel:**
- Assembled a curated marker list typical of sleep deprivation and neuronal activity:
  - Fos, Fosb, Arc, Egr1, Egr2, Egr3, Homer1 (Homer1a), Npas4, Nr4a1, Nr4a2, Nr4a3,
    Bdnf, Dusp1, Dusp4, Dusp5, Dusp6, Jun, Junb, Atf3.
- Mapped these to mouse Ensembl IDs present in the matrix (19 markers resolved; Jund could not be confidently mapped and was excluded).
- Extracted normalized expression across all samples and summarized per cluster (mean in cluster1, mean in cluster2, and delta = cluster1 − cluster2).
- Saved as `project/outputs/tables/sleep_deprivation_marker_expression.tsv` and visualized in `project/outputs/figures/sleep_deprivation_marker_heatmap.png`.

**Cluster-to-condition interpretation:**
- Integrated:
  - DE-based signatures and GO enrichment.
  - Marker panel expression differences between clusters.
- Concluded which unsupervised cluster corresponds to a sleep-deprived hippocampal state.
- Full interpretation documented in `project/outputs/reports/sd_vs_control_interpretation.md`.

---

## Results

- **Unsupervised clustering:**
  - Samples segregated robustly into two clusters:
    - **cluster1:** sample1, sample2, sample5, sample6.
    - **cluster2:** sample3, sample4, sample7, sample8.

- **Pathway signatures (GO enrichment):**
  - **cluster1_up** genes were enriched for:
    - Synaptic and neuronal processes: *synapse organization*, *regulation of synaptic plasticity*, *axonogenesis* and related neurite remodeling terms.
    - Activity/stress-related pathways: hormone/steroid and stress-response signaling and regulation of transcription/translation.
  - **cluster2_up** genes were enriched for:
    - Translation and ribosome biogenesis: multiple *translation*, *ribosome biogenesis*, and *rRNA metabolic process* terms.
    - Mitochondrial and energy metabolism: *mitochondrial ATP synthesis coupled electron transport*, *mitochondrial translation*.
  - Overall, cluster1 shows an activity- and plasticity-focused profile; cluster2 shows increased biosynthetic and metabolic machinery with less clear activity dependence.

- **Sleep-deprivation / wake-activity marker expression:**
  - Canonical immediate-early and activity-dependent genes were generally **higher in cluster1** than in cluster2:
    - Fos, Fosb, Arc, Egr1, Egr3, Homer1/Homer1a, Npas4, Nr4a1, Nr4a2, Nr4a3, Dusp5, Dusp6, Jun, Junb all had positive (cluster1 − cluster2) log2 expression differences.
    - A few markers (e.g., Atf3, Bdnf) were slightly higher in cluster2, but with small effect sizes compared to the broad elevation pattern in cluster1.
  - The marker heatmap (`sleep_deprivation_marker_heatmap.png`) shows coherent upregulation of this panel across **sample1, sample2, sample5, sample6** relative to **sample3, sample4, sample7, sample8**.

- **Cluster-to-condition mapping:**
  - The combination of:
    - Elevated immediate-early and activity-dependent markers.
    - Enrichment for synaptic plasticity, neurite remodeling, and stress/hormone-responsive pathways.
  - strongly supports **cluster1** as a wake-activated, sleep-deprived hippocampal state.
  - Conversely, cluster2’s emphasis on ribosomal and mitochondrial functions, with lower activation of canonical wake/sleep-deprivation markers, is more consistent with a non-deprived (baseline/rested) state.

- **Final sample assignments:**
  - **Sleep-deprived hippocampus (cluster1):**
    - sample1
    - sample2
    - sample5
    - sample6
  - **Control (non-deprived) hippocampus (cluster2):**
    - sample3
    - sample4
    - sample7
    - sample8

These assignments are recorded in `project/outputs/tables/sample_condition_assignments.tsv` and summarized in `project/outputs/reports/final_answer.md`.

---

## Caveats & Warnings

- **Small sample size:** Only 4 samples per cluster (8 total). Statistical power for DE is low; no genes reached FDR < 0.05, so results rely on lenient, exploratory thresholds and multi-gene patterns.
- **Exploratory enrichment:** The gene signatures used for GO analysis were defined with a relaxed adjusted p-value cutoff (padj ≲ 0.151) and top-N selection; individual gene-level associations should be treated as hypothesis-generating.
- **No external labels or covariates:** The cluster interpretation rests entirely on expression-based patterns and known biology of sleep deprivation and neuronal activation, without behavioral or physiological metadata for validation.
- **Single dataset:** Findings are specific to this dataset and may not generalize to other hippocampal sleep-deprivation experiments without replication.

---

## Next Steps

- **Independent validation:**
  - Validate the inferred labels against any available experimental metadata (if it becomes available) or in independent hippocampal sleep-deprivation datasets.
- **Richer modeling:**
  - Re-run DE with more sophisticated methods (e.g., limma-voom or edgeR/DESeq2 using raw counts) and incorporate covariates if future metadata are provided.
- **Targeted gene panels:**
  - Design targeted qPCR or in situ experiments focusing on the key immediate-early and plasticity markers that distinguish cluster1 from cluster2 to biologically confirm the assignments.

---

## References

- Cirelli C, Tononi G. Is sleep essential? *PLoS Biol.* 2008;6(8):e216. doi:10.1371/journal.pbio.0060216.
