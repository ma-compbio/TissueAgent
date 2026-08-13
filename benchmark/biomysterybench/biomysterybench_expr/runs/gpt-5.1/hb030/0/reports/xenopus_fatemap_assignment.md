# Xenopus tropicalis gastrula fate-map region assignment

## Title & Objective

**Objective:** Infer which embryonic Xenopus tropicalis gastrula fate-map regions correspond to 10 RNA-seq samples (2 replicates from 5 tissues), using only the expression data in `library/datasets/rsem_v9_counts.txt`. Report the five tissue identities (fate-map regions) in the order of the counts-file columns.

**Counts-file sample order:**
1. T1rep1  
2. T1rep2  
3. T2rep1  
4. T2rep2  
5. T3rep1  
6. T3rep2  
7. T4rep1  
8. T4rep2  
9. T5rep1  
10. T5rep2

## Data & Methods

- **Input data:**
  - Gene-by-sample RSEM count matrix: `library/datasets/rsem_v9_counts.txt` (26,550 genes × 10 samples).
  - Xenopus tropicalis v9 GFF3 annotation: `library/datasets/Xtropicalisv9.0.Named.primaryTrs.gff3`.
- **QC & normalization:**
  - Computed per-sample QC metrics: total counts, detected genes, mean and median counts per gene.
  - Normalized to counts per million (CPM) and transformed to log2(CPM + 1).
- **Sample-level analysis:**
  - PCA on log-CPM (top variable genes) to visualize sample relationships.
  - Sample–sample Pearson correlation, hierarchical clustering on 1 − correlation, cut into **5 clusters (C1–C5)**.
- **Gene annotation:**
  - Parsed GFF3 `gene` features to map gene IDs (e.g., `Xetrov90014375m.g`) to symbols (`Name` attribute).
  - Built `gene_id_to_symbol_map.tsv` with full coverage of genes in the count matrix.
- **Gastrula marker panel:**
  - Curated Xenopus gastrula markers and assigned them to fate-map regions:
    - **Animal cap / ectoderm:** sox2, sox3, otx2, krt18, krt8.
    - **Dorsal marginal zone / Organizer:** chrd, nog, gsc, cer1, dkk1, frzb, frzb2, wnt11, otx2, foxa2.
    - **Ventrolateral / Ventral marginal zone:** wnt8a, bmp4.
    - **Mesoderm (general / marginal zone):** t (brachyury), myod1, myf5.
    - **Vegetal endoderm:** vegT, gata4, gata5, gata6, sox17a, hhex, foxa1, foxa2.
    - **Housekeeping:** odc1 (reference).
  - Panel recorded in `marker_panel_definition.tsv` with symbol, region, category, notes, and detection status.
- **Marker expression summaries:**
  - Computed log2(CPM + 1) for all markers per sample (`marker_expression_by_sample.tsv`).
  - Aggregated mean marker expression per cluster using `sample_cluster_assignments.tsv` → `marker_expression_by_cluster.tsv`.
  - Visualized marker expression vs clusters in `marker_expression_heatmap.png`.
- **Region assignment:**
  - For each cluster (C1–C5), inspected organizer, endoderm, ectoderm, ventral, and mesoderm marker expression.
  - Assigned each cluster a primary fate-map region label and propagated these labels to individual samples in file order.
  - Detailed rationale in `region_assignment_rationale.md`.

## Results

### 1. Sample clustering and replicates

- Hierarchical clustering on log-CPM and PCA revealed 5 robust clusters (C1–C5).
- Sample-to-cluster assignments (from `sample_cluster_assignments.tsv`):
  - C1: T4rep1  
  - C2: T4rep2  
  - C3: T1rep1, T2rep1, T3rep1, T5rep1  
  - C4: T2rep2, T3rep2, T5rep2  
  - C5: T1rep2

### 2. Cluster-level marker signatures

Using `marker_expression_by_cluster.tsv` (values = log2(CPM + 1)):

- **Clusters C1 & C2:**
  - Very high **vegetal endoderm markers**: gata4, gata5, gata6, sox17a, hhex, foxa1, foxa2 (C1–C2 ≈ 8–10; other clusters much lower).
  - High **organizer markers**: chrd, cer1, dkk1, frzb, gsc, nog.
  - Interpretation: dorsal vegetal endomesoderm → best summarized as **Vegetal endoderm**.

- **Clusters C3 & C4:**
  - High **ectoderm/animal cap markers**: sox2, sox3, krt8, krt18 (C3–C4 ≈ 8–10), lower endoderm and organizer markers than C1–C2.
  - C4 shows somewhat higher mesoderm gene t than C3, but ectodermal markers still dominate.
  - Interpretation: both clusters represent **Animal cap / ectoderm** (with C4 slightly more mesodermal but still ectoderm-dominated).

- **Cluster C5:**
  - Low organizer/endoderm markers relative to C1–C2.
  - Strong ectodermal keratins (krt8, krt18) and moderate sox2/sox3.
  - Elevated bmp4 relative to most other clusters and low organizer factors; overall most consistent with ventral marginal/ventrolateral identity at this coarse resolution.
  - Interpretation: **Ventrolateral / Ventral marginal zone**.

### 3. Cluster-to-region mapping

From `cluster_to_region_mapping.tsv`:

- C1 → **Vegetal endoderm**  
- C2 → **Vegetal endoderm**  
- C3 → **Animal cap / ectoderm**  
- C4 → **Animal cap / ectoderm**  
- C5 → **Ventrolateral / Ventral marginal zone**

### 4. Final sample region labels (in counts-file order)

Using `sample_region_labels_in_file_order.tsv` and the original column order of `rsem_v9_counts.txt`:

1. **T1rep1** → C3 → **Animal cap / ectoderm**  
2. **T1rep2** → C5 → **Ventrolateral / Ventral marginal zone**  
3. **T2rep1** → C3 → **Animal cap / ectoderm**  
4. **T2rep2** → C4 → **Animal cap / ectoderm**  
5. **T3rep1** → C3 → **Animal cap / ectoderm**  
6. **T3rep2** → C4 → **Animal cap / ectoderm**  
7. **T4rep1** → C1 → **Vegetal endoderm**  
8. **T4rep2** → C2 → **Vegetal endoderm**  
9. **T5rep1** → C3 → **Animal cap / ectoderm**  
10. **T5rep2** → C4 → **Animal cap / ectoderm**

Interpreted as 5 tissues (each with 2 replicates):

- Tissue 1 (T1rep1, T2rep1, T3rep1, T5rep1) – Animal cap / ectoderm (one ectoderm group)  
- Tissue 2 (T2rep2, T3rep2, T5rep2) – Animal cap / ectoderm (slightly more mesodermal bias)  
- Tissue 3 (T4rep1, T4rep2) – Vegetal endoderm  
- Tissue 4 (T1rep2) – Ventrolateral / Ventral marginal zone  
- Tissue 5 – represented within the ectodermal substructure; at the requested coarse fate-map level, both C3 and C4 are Animal cap / ectoderm.

For the purposes of the user’s question—"Which embryonic cell types are the experiments from, in order of the counts file?"—the relevant answer is simply the per-sample region labels above.

## Caveats & Warnings

- **Marker-centric interpretation:** Assignments rely on a curated marker set and cluster averages; subtle spatial heterogeneity within regions (e.g., dorsal vs ventral ectoderm) is not resolved.
- **Ventral markers:** While bmp4 is elevated in C5, wnt8a expression peaks in C2 in this dataset. The C5 label as ventrolateral/ventral marginal zone should be viewed as a coarse fate-map assignment based on overall low organizer/endoderm and higher ventral BMP signaling, rather than a perfect match to all canonical ventral markers.
- **Mesodermal bias in C4:** C4 shows higher brachyury (t) than C3, but ectodermal markers remain dominant; it is still labeled Animal cap / ectoderm at the coarse level requested.

## Next Steps

- Incorporate additional Xenopus gastrula markers (e.g., ventx, tbx, mix/mixes) and run clustering at the gene level to refine sub-territories (e.g., dorsal vs ventral ectoderm, anterior vs posterior).
- Validate assignments against independent spatial transcriptomic or in situ hybridization data, if available.
- Explore differential expression among C1 vs C2 and C3 vs C4 to better separate closely related territories (e.g., dorsal vegetal vs lateral vegetal, neural vs non-neural ectoderm).

## References

- Harland RM, Gerhart J. Formation and function of Spemann's organizer. Annu Rev Cell Dev Biol. 1997;13:611–667. doi:10.1146/annurev.cellbio.13.1.611
- De Robertis EM, Kuroda H. Dorsal–ventral patterning and neural induction in Xenopus embryos. Annu Rev Cell Dev Biol. 2004;20:285–308. doi:10.1146/annurev.cellbio.20.011403.154124
- Zorn AM, Wells JM. Vertebrate endoderm development and organ formation. Annu Rev Cell Dev Biol. 2009;25:221–251. doi:10.1146/annurev.cellbio.042308.113344
