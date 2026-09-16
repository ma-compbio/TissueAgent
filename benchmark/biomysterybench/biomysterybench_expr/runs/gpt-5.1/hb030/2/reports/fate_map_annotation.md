# Xenopus tropicalis gastrula fate-map annotation

## 1. Fate-map marker panel

We constructed a literature-based panel of Xenopus tropicalis gastrula fate-map markers and mapped them to v9 gene IDs using the Xtropicalis v9.0 GFF3 annotation. The panel focuses on major gastrula territories expected in this experiment (five tissues, two replicates each):

- **Animal ectoderm / animal cap**
  - Neural and non-neural ectoderm markers: *sox2* (Xetrov90014375m.g), *sox3* (Xetrov90020478m.g), *foxi1* (Xetrov90007506m.g), *foxi2* (Xetrov90017599m.g), *tfap2a* (Xetrov90016561m.g), *tfap2c* (Xetrov90025902m.g), *dlx3* (Xetrov90024886m.g), *zic1* (Xetrov90014780m.g), *zic3* (Xetrov90020675m.g).
  - Epidermal keratins: *krt12* (Xetrov90028525m.g), *krt18* (Xetrov90006540m.g).

- **Marginal zone / mesoderm**
  - Pan-mesoderm and marginal zone: *tbxt / T / brachyury* (here Xetrov90013794m.g, annotated as "t"), *eomes* (Xetrov90016435m.g), *wnt8a* (Xetrov90007482m.g), *msgn1/tbx6-like* (Xetrov90015181m.g).
  - Gastrulation and EMT-associated: *snai1* (Xetrov90025269m.g), *snai2* (Xetrov90016785m.g).

- **Organizer / dorsal lip (Spemann organizer and axial mesendoderm)**
  - Classic secreted antagonists: *gsc* (Xetrov90021259m.g), *chrd* (Xetrov90014683m.g), *nog* (Xetrov90025090m.g), *cer1* (Xetrov90002179m.g), *dkk1* (Xetrov90017466m.g), *frzb* (Xetrov90024159m.g).
  - Axial mesendoderm / anterior organizer factors: *foxa2* (Xetrov90013306m.g), *otx2* (Xetrov90021558m.g).

- **Vegetal endoderm (deep vegetal cells / definitive endoderm)**
  - Endoderm TFs: *sox17a* (Xetrov90016800m.g), *sox17b.1* (Xetrov90016802m.g), *sox17b.2* (Xetrov90016803m.g).
  - Nodal targets and vegetal determinants: *mixer* (Xetrov90012972m.g), *mix1* (Xetrov90012973m.g), *vegt* (Xetrov90002928m.g).
  - GATA factors: *gata4* (Xetrov90026121m.g), *gata5* (Xetrov90028957m.g), *gata6* (Xetrov90016691m.g).
  - Anterior endoderm: *hhex* (Xetrov90017618m.g).

This panel is saved as:

- `project/outputs/tables/fate_map_marker_panel.tsv`

Columns include `gene_id`, `gene_symbol`, `fate_region`, and `notes` describing literature-based expression domains and roles (organizer, marginal zone, endoderm, or animal ectoderm). All markers in the panel are present in the normalized expression matrix.

## 2. Cluster-level marker enrichment

Using `project/outputs/tables/normalized_expression.tsv` and sample-to-cluster assignments from `project/outputs/tables/sample_clusters.tsv`, we computed, for each marker gene and cluster:

- Mean expression within the cluster (averaged over samples in that cluster).
- Mean expression across all *other* clusters.
- A simple enrichment score: `log2FC_in_vs_others = log2((mean_in_cluster + 1e-6) / (mean_other_clusters + 1e-6))`.

Results are saved in:

- `project/outputs/tables/cluster_marker_enrichment.tsv`

with columns: `fate_region`, `gene_id`, `gene_symbol`, `cluster_id`, `mean_expression_in_cluster`, `mean_expression_other_clusters`, and `log2FC_in_vs_others`.

### Fate-region summary by cluster

Averaging log2FC over markers within each fate-region gives the following pattern (values approximate):

- **Animal ectoderm markers**
  - Cluster 0: mildly enriched (~+0.05)
  - Cluster 1: strongly depleted (~−1.9)
  - Cluster 2: mildly enriched (~+0.11)
  - Cluster 3: strongly depleted (~−2.2)
  - Cluster 4: clearly enriched (~+0.48)

- **Marginal zone / mesoderm markers**
  - Cluster 0: moderately depleted (~−0.37)
  - Cluster 1: enriched (~+0.61)
  - Cluster 2: slightly depleted (~−0.12)
  - Cluster 3: enriched (~+0.57)
  - Cluster 4: strongly depleted (~−1.97)

- **Organizer markers**
  - Cluster 0: mildly depleted (~−0.25)
  - Cluster 1: enriched (~+0.76)
  - Cluster 2: slightly depleted (~−0.10)
  - Cluster 3: enriched (~+0.79)
  - Cluster 4: clearly depleted (~−2.18)

- **Vegetal endoderm markers**
  - Cluster 0: mildly depleted (~−0.20)
  - Cluster 1: enriched (~+0.65)
  - Cluster 2: near-neutral (~+0.03)
  - Cluster 3: enriched (~+0.59)
  - Cluster 4: depleted (~−1.80)

Together with individual marker-level patterns (below), these provide the basis for fate-map assignments.

## 3. Fate-map assignments for clusters 0–4

### Cluster 4 — Animal ectoderm / animal cap

**Evidence:**
- Strong, consistent enrichment of animal ectoderm markers:
  - *krt12* (epidermal keratin) log2FC >> 0 and one of the top markers in cluster 4.
  - *dlx3*, *foxi1*, *tfap2a*, *tfap2c*, *foxi2* all show positive log2FC in cluster 4 vs other clusters.
  - Neural plate/ectoderm factors *sox2*, *sox3*, *zic1*, *zic3* are also modestly enriched.
- Strong depletion of organizer, mesoderm, and endoderm markers (negative mean log2FC for Organizer, Marginal_zone_mesoderm, Vegetal_endoderm).

**Interpretation:**
- This expression profile is characteristic of **animal cap / animal ectoderm**, with robust non-neural epidermal signatures and some neural ectoderm markers.
- **Assigned fate-map region:** `Animal_ectoderm` (animal cap–derived tissue).

### Cluster 1 — Dorsal organizer-enriched marginal zone / axial mesendoderm

**Evidence:**
- Organizer and endoderm markers are strongly enriched:
  - Classic organizer genes *snai2* (2.1 log2FC), *dkk1*, *gsc*, *chrd*, *frzb*, and *foxa2* all show positive enrichment.
  - Endoderm markers *gata4*, *gata5*, *gata6*, *sox17a*, *sox17b.1*, *sox17b.2*, and *hhex* are up-regulated.
- Mesoderm markers are also enriched but somewhat less strongly than cluster 3:
  - *snai2* is the single most enriched mesoderm marker here.
- Animal ectoderm markers are markedly depleted (global negative log2FC for Animal_ectoderm in this cluster).

**Interpretation:**
- This combination of strong organizer (gsc/chrd/nog/cer1/dkk1/frzb) and endoderm (sox17/gata4/5/6, hhex) marks **dorsal axial mesendoderm and Spemann organizer** at the interface of marginal and vegetal zones.
- Compared with cluster 3 (below), cluster 1 appears somewhat more endoderm-leaning (strong Gata/Sox17/Hhex) and slightly less mesoderm-heavy.
- **Assigned fate-map region:** `Organizer` / dorsal axial mesendoderm (dorsal lip and adjacent dorsal marginal/vegetal tissue).

### Cluster 3 — Organizer–mesoderm with strong marginal zone signature

**Evidence:**
- Strong enrichment of marginal zone / mesoderm markers:
  - *snai2* is even more enriched than in cluster 1 (log2FC > 2.5), indicating robust involuting mesoderm.
  - *eomes* and the T-box / paraxial mesoderm marker *tbx6/msgn1* are positively enriched.
- Classic organizer genes are also clearly enriched:
  - *dkk1*, *foxa2*, *nog*, *cer1*, and *gsc* all show positive log2FC.
- Endoderm markers remain enriched:
  - *gata4*, *gata5*, *gata6*, *sox17a/b.1/b.2*, *hhex* all have positive log2FC in cluster 3.
- Animal ectoderm markers are depleted on average.

**Interpretation:**
- Cluster 3 represents a more **mesodermally biased organizer/marginal zone territory**, with strong mesoderm and organizer signatures and substantial, but slightly less dominant, endoderm.
- This is compatible with **dorsal marginal zone mesoderm / organizer mesoderm** (including the dorsal lip region and immediate mesodermal descendants).
- **Assigned fate-map region:** `Marginal_zone_mesoderm` with organizer influence (dorsal marginal zone / organizer mesoderm).

### Cluster 2 — Intermediate / ventrolateral marginal zone (mixed mesoderm)

**Evidence:**
- Marginal zone mesoderm markers are near neutral or modestly positive overall (mean log2FC slightly negative, but individual markers like *eomes* and *wnt8a* have positive log2FC).
- Organizer markers show weak or slightly negative enrichment overall; no strong organizer signature.
- Endoderm markers are near-neutral (mean log2FC ~ 0.03), indicating low but non-zero expression.
- Animal ectoderm markers show mild enrichment (~+0.11), but far weaker than cluster 4.

**Interpretation:**
- Cluster 2 lacks a strong, pure signature for either animal ectoderm, organizer, or deep vegetal endoderm.
- The presence of mesoderm-associated genes (e.g. *eomes*, *wnt8a*) with modest enrichment suggests **ventrolateral marginal zone / general mesoderm** that is less organizer-biased than clusters 1 and 3.
- **Assigned fate-map region:** `Marginal_zone_mesoderm` (ventrolateral / intermediate mesoderm).
- **Ambiguity:** Because marker enrichment is relatively modest and mixed, this cluster could encompass a heterogeneous mixture of ventrolateral mesoderm and adjacent ectoderm; additional markers (e.g. more vent-specific Wnt/Bmp targets) would refine this assignment.

### Cluster 0 — Mixed ectoderm with weak mesoderm/organizer signals

**Evidence:**
- Animal ectoderm markers are mildly enriched on average (+0.05), with specific markers (*krt12*, *foxi1*, *sox2*, *sox3*, *tfap2a*, *tfap2c*, *zic1*) showing modest positive log2FC.
- Mesoderm markers are overall slightly depleted, but some (e.g. *tbxt*, *snai1*) show small positive enrichment.
- Organizer and endoderm markers are mildly depleted, and classic organizer genes (*gsc*, *chrd*, *cer1*, *dkk1*) are not strongly elevated.

**Interpretation:**
- The profile is dominated by ectodermal markers but with weaker, diffuse mesoderm/organizer signatures than clusters 1 and 3.
- In the context of five experimental tissues, this is consistent with an **animal cap / ectoderm-derived territory that is less enriched for epidermal keratins than cluster 4** and may represent more neural-leaning ectoderm or partially induced ectoderm.
- **Assigned fate-map region:** `Animal_ectoderm` (with a more neural or less committed profile than cluster 4).
- **Ambiguity:** The small positive enrichment of some mesoderm-associated markers suggests possible contamination or partial induction (e.g., marginal-zone-contaminated animal caps). Finer-grained markers (e.g., neural plate vs epidermis vs placodes) would help resolve this.

## 4. Summary of cluster-to-fate assignments

Based on the marker-enrichment analysis and classical Xenopus gastrula fate-map literature, we propose the following assignments:

- **Cluster 0:** Animal ectoderm (moderately ectodermal, possibly more neural/less keratinized).
- **Cluster 1:** Dorsal organizer / axial mesendoderm (strong organizer and endoderm signatures).
- **Cluster 2:** Ventrolateral/intermediate marginal zone mesoderm (mixed mesoderm with modest organizer and endoderm influence).
- **Cluster 3:** Dorsal marginal zone / organizer mesoderm (strong mesoderm and organizer markers, plus endoderm factors).
- **Cluster 4:** Animal ectoderm (animal cap / epidermal ectoderm; strong epidermal and ectodermal markers).

## 5. Key assumptions and limitations

- Marker selection is based on well-established Xenopus laevis and Xenopus tropicalis gastrula literature (e.g. gsc, chrd, nog, cer1, dkk1/frzb as organizer; sox17/gata4/5/6, vegt, mixer/mix1 as endoderm; tbxt/eomes/wnt8a/snai1/2 as mesoderm; sox2/3, foxi1/2, tfap2a/c, dlx3, zic1/3, krt12/18 as ectoderm).
- Mapping from gene symbols to v9 gene IDs uses the Name field of Xtropicalisv9.0.Named.primaryTrs.gff3 and assumes those names correspond to standard gene symbols.
- Enrichment metrics use bulk-like averages across a small number of samples per cluster (2 replicates per tissue), so estimates may be noisy for lowly expressed markers.
- Clusters are treated as homogeneous representations of anatomical territories, but in reality they may contain mixtures of neighboring fate-map regions.
- Additional spatial or lineage tracing data, or a larger panel of region-specific markers (e.g., ventral-specific bmp/wnt targets, more refined neural vs non-neural markers), could further refine or adjust these assignments.
