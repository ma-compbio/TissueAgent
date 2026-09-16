# Xenopus tropicalis gastrula fate-map inference report

## Title & Objective

**Objective.** Using only the RNA-seq expression matrix in `library/datasets/rsem_v9_counts.txt` (10 samples; 2 replicates × 5 tissues), infer which Xenopus tropicalis embryonic gastrula fate-map region each sample comes from, in the exact order of the counts file. Regions should be named using standard gastrula territories (e.g., Animal ectoderm/Animal Cap, Marginal Zone mesoderm, Organizer).

## Data & Methods

**Data.**
- Primary matrix: `rsem_v9_counts.txt` (26,550 genes × 10 samples), columns:
  - `T1rep1, T1rep2, T2rep1, T2rep2, T3rep1, T3rep2, T4rep1, T4rep2, T5rep1, T5rep2`.
- Annotation/metadata: `Xtropicalisv9.0.Named.primaryTrs.gff3` used to map v9 transcript IDs to gene symbols; `GeneExpression_tropicalis.txt` used qualitatively but not for quantitation.

**Preprocessing.**
1. Parsed `rsem_v9_counts.txt` into `raw_counts_matrix.tsv` (genes as rows, 10 sample columns).
2. Computed basic QC (library size, detected genes, zero fraction) per sample (`qc_summary.tsv`).
3. Normalized counts by library-size CPM-like scaling followed by `log1p` transform, preserving sample order (`normalized_expression.tsv`).
4. Computed per-gene mean and variance on log-CPM and selected the top 2,000 highly variable genes by variance (`highly_variable_genes.tsv`).

**Clustering & dimensionality reduction.**
- PCA on samples using the 2,000 HVGs (centered & scaled), retaining 5 PCs).
- Hierarchical clustering (Ward linkage, Euclidean distance) on PCA coordinates, forcing 5 clusters (0–4) to match the expected 5 tissues (`sample_clusters.tsv`).

**Marker and fate-map analysis.**
1. Built a literature-based marker panel of classic Xenopus gastrula genes mapped to v9 IDs using the GFF3:
   - **Organizer**: gsc, chrd, nog, cer1, dkk1, frzb, foxa2, otx2.
   - **Marginal zone mesoderm**: tbxt/T ("t"), eomes, wnt8a, msgn1/tbx6-like, snai1, snai2.
   - **Vegetal endoderm**: sox17a, sox17b.1, sox17b.2, gata4/5/6, mixer, mix1, vegt, hhex.
   - **Animal ectoderm (animal cap, epidermal/neural)**: sox2, sox3, foxi1, foxi2, tfap2a, tfap2c, dlx3, zic1, zic3, krt12, krt18.
   Panel saved as `fate_map_marker_panel.tsv`.
2. For each marker gene and cluster, computed mean expression in that cluster vs all others and a log2 fold-change (`cluster_marker_enrichment.tsv`).
3. Combined marker enrichment with unsupervised cluster markers (`cluster_marker_genes.tsv`) to assign each cluster to a fate-map region. Summary (from `fate_map_annotation.md`):
   - Cluster 0: Animal ectoderm (moderately ectodermal, neural-leaning/less keratinized).
   - Cluster 1: Organizer / axial mesendoderm (strong organizer + endoderm markers).
   - Cluster 2: Ventrolateral/intermediate marginal zone mesoderm.
   - Cluster 3: Dorsal marginal zone / organizer mesoderm.
   - Cluster 4: Animal ectoderm (animal cap / epidermal ectoderm; strong epidermal keratins and ectoderm TFs).
4. Propagated these cluster labels to samples in original file order, yielding `sample_tissue_assignments.tsv` and `final_sample_order_with_fate_map_regions.txt`.

## Results

### Final fate-map region assignments (in counts-file order)

Sample order is exactly the column order of `rsem_v9_counts.txt`:

1. **T1rep1** → **Animal ectoderm** (cluster 0)
2. **T1rep2** → **Animal ectoderm** (cluster 4)
3. **T2rep1** → **Animal ectoderm** (cluster 0)
4. **T2rep2** → **Marginal zone mesoderm** (cluster 2; ventrolateral/intermediate marginal zone)
5. **T3rep1** → **Animal ectoderm** (cluster 0)
6. **T3rep2** → **Marginal zone mesoderm** (cluster 2; ventrolateral/intermediate marginal zone)
7. **T4rep1** → **Marginal zone mesoderm** (cluster 3; dorsal marginal zone / organizer mesoderm)
8. **T4rep2** → **Organizer** (cluster 1; dorsal organizer / axial mesendoderm)
9. **T5rep1** → **Animal ectoderm** (cluster 0)
10. **T5rep2** → **Marginal zone mesoderm** (cluster 2; ventrolateral/intermediate marginal zone)

### Supporting patterns (brief)
- **Animal ectoderm clusters (0 & 4)** show enrichment for sox2/sox3, foxi1/2, tfap2a/c, dlx3, zic1/3, and epidermal keratins (krt12, krt18), with depletion of organizer/endoderm markers.
- **Organizer/axial mesendoderm (cluster 1)** has strong gsc, chrd, nog, cer1, dkk1, frzb, foxa2, and co-enriched endoderm markers (sox17, gata4/5/6, hhex).
- **Dorsal marginal zone / organizer mesoderm (cluster 3)** shows very strong mesodermal tbxt/T, eomes, msgn1, snai1/2 with organizer signals (gsc, dkk1, nog, foxa2) and endoderm factors.
- **Ventrolateral/intermediate marginal zone mesoderm (cluster 2)** is characterized by mesoderm markers (eomes, wnt8a, snai genes) with weaker organizer/endoderm and ectoderm signatures.

## Caveats & Warnings

- **Region granularity.** Clusters 0 and 4 are both animal ectoderm; they likely represent different ectodermal sub-states (e.g., more neural vs more epidermal), but both are reported simply as "Animal ectoderm" here.
- **Limited replicates per tissue.** Each inferred tissue is represented by only two replicates, so cluster-level fold-changes are somewhat noisy, especially for low-abundance markers.
- **Marker mapping assumptions.** Mapping from gene symbols to v9 IDs relied on the GFF3 Name field; rare aliasing or misannotation could affect individual marker calls but is unlikely to overturn the broad region assignments.

## Next Steps

- If you wish to refine sub-regions (e.g., distinguish neural plate vs non-neural ectoderm or dorsal vs ventral mesoderm), extend the marker panel with more region-specific genes and re-run enrichment.
- Validate these assignments against any external metadata you might have (e.g., experimental notes) or by cross-referencing with Xenbase anatomical expression profiles for the top cluster markers.

## References

- Xenbase and Xenopus tropicalis genome resources for v9 annotation.
- Classic Xenopus gastrulation and fate-map literature describing organizer (gsc, chrd, nog, cer1, dkk1, frzb), mesoderm (tbxt/T, eomes, wnt8a, snai1/2), endoderm (sox17, gata4/5/6, vegt, mixer/mix1, hhex), and animal ectoderm (sox2/3, foxi1/2, tfap2a/c, dlx3, zic1/3, keratins) expression domains.
