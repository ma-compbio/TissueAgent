# Tissue and region assignment for rnaseqSampleID_2

## Overview

This report integrates per-sample tissue signature scores, cluster-level context, and marker genes to assign a tissue and, where possible, a sub-region for **rnaseqSampleID_2**.

**Final assignment (summary):
- Tissue call: **Brain**
- Region call: **Global brain (neural tissue, mixed neuronal/glial features)**
- Cluster ID: **3**

---

## 1. Cluster context for rnaseqSampleID_2

### Cluster assignment
- From `sample_cluster_assignments.tsv`, **rnaseqSampleID_2 is assigned to cluster 3**.

### Cluster 3 tissue signature scores
From `cluster_tissue_signature_scores.tsv`, restricting to `cluster_id == 3` and ranking by `score_mean_expr`:

Top tissue/region scores for cluster 3:
- **Brain – Global**: score_mean_expr ≈ **4.99** (12/15 markers used)
- **Brain – Hippocampus**: score_mean_expr ≈ **3.07** (1/7 markers used)
- **Brain – Cerebellum**: score_mean_expr ≈ **2.93** (5/7 markers used)
- **Brain – Cortex**: score_mean_expr ≈ **2.56** (2/10 markers used)
- **Kidney – Cortex**: score_mean_expr ≈ **2.71** (4/14 markers used)
- **Kidney – Medulla**: score_mean_expr ≈ **1.87** (3/9 markers used)
- **Blood_Immune – Myeloid/B_cell/PBMC/T_cell**: score_mean_expr ≈ **0.96–1.39** (7–11 markers used)
- Heart and Gut show lower scores (~0.6–1.1).

**Interpretation:**
- Cluster 3 is **strongly enriched for brain markers**, with the **Brain–Global signature clearly dominant**.
- Kidney and blood/immune scores are modest and likely reflect low-level expression of shared genes or background, not a primary tissue identity.

### Cluster 3 marker genes
From `cluster_marker_genes.tsv` for `cluster_id == 3`, top markers (by fold_change) include:
- **Myelin/oligodendrocyte / astrocyte / pan-neuronal markers:**
  - MOG, MOBP, OLIG1, MBP, PLP1
  - GFAP, AQP4, SLC1A2, ETNPPL, MLC1
  - SNAP25, NEFL, NEFM, STMN2, GRIN1, UCHL1, KIF5A, GAP43, GPM6A
- Additional neuronal/glial-associated genes: ELAVL3, HPCA, TAGLN3, BCAN, PMP2, PACSIN1, TMEM59L, FAIM2, ATP1A3, MT3, etc.

These genes are **canonical central nervous system markers** spanning neurons, oligodendrocytes, and astrocytes.

### Overlap with defined brain marker sets
Using `tissue_marker_gene_sets_used.tsv` restricted to Brain markers:
- Brain Global markers (15 genes): include RBFOX3, MAP2, MAPT, SNAP25, SYT1, SYN1, SLC17A7, GAD1, GAD2, GFAP, SLC1A2, SLC1A3, MBP, PLP1, OLIG2.
- Overlap of cluster 3 markers with Brain Global markers:
  - **GFAP, MBP, PLP1, SLC1A2, SNAP25** (5/15 global brain markers are highly enriched in cluster 3).
- Overlap with Brain Cortex, Cerebellum, Hippocampus marker sets: **0 markers each** from the curated region-specific lists.

**Interpretation:**
- Cluster 3 clearly represents **central nervous system (brain) tissue with strong global brain signatures**.
- The prominent myelin/oligodendrocyte and astrocyte markers, together with pan-neuronal genes, suggest a **mixed neuronal and glial brain sample** rather than a cleanly defined sub-region.
- Lack of overlap with cortex/cerebellum/hippocampus marker sets argues against making a confident fine-grained anatomical sub-region call.

---

## 2. Per-sample tissue scores for rnaseqSampleID_2

From `sampleID_2_tissue_signature_scores.tsv` sorted by `normalized_score_z`:

Top tissue/region combinations for rnaseqSampleID_2:
- **Brain – Global**
  - normalized_score_z ≈ **4.17** (15/15 markers present)
  - raw_score_mean ≈ 299.5
- **Brain – Cortex**
  - normalized_score_z ≈ **0.35** (10/10 markers)  
- **Kidney – Medulla**
  - normalized_score_z ≈ **0.08** (9/9 markers)
- **Heart – Cardiac_muscle**
  - normalized_score_z ≈ **0.04** (15/15 markers)
- **Brain – Hippocampus / Cerebellum**
  - normalized_score_z slightly negative (all markers present)
- Kidney Cortex, Blood_Immune subsets, Lung, Adipose, Pancreas, Skeletal_muscle, Skin, etc. all have **negative or near-zero** normalized z-scores.

**Interpretation:**
- The **Brain Global signature is a clear outlier**, with a much higher normalized z-score than any other tissue/region.
- Within brain, **no sub-region (cortex, cerebellum, hippocampus) displays a comparably strong or distinct enrichment**.
- Non-brain tissues do not show compelling evidence of being the primary tissue of origin.

---

## 3. Expression profile for additional qualitative support

From `sampleID_2_top_genes.tsv`, top expressed genes include:
- Numerous **mitochondrial genes** (MT-RNR2, MT-CO1/2/3, MT-ND1/2/3/4/5/6, MT-ATP6/8, MT-CYB), consistent with high metabolic activity.
- Canonical **brain-associated genes** among the top expressed nuclear-encoded genes:
  - **MBP**, **KIF5A**, **NRGN**, **UCHL1**, **ALDOC**, **SPARCL1**, **CLU**, **PTGDS**, **TSPAN7**, **ITM2C**, **MT3**, etc.

These genes are strongly associated with neurons and glial cells, consistent with the cluster-level brain identity.

---

## 4. Concordance and discordance between sample and cluster

### Concordant signals
- Both **per-sample scores** and **cluster-level scores** identify **Brain – Global** as the **dominant tissue signal**.
- The **cluster’s marker genes** are classical central nervous system markers, supporting a brain assignment.
- The **sample’s top expressed genes** include several neuronal and glial markers that match the cluster 3 marker profile (e.g., MBP, KIF5A, UCHL1, MT3), providing qualitative consistency.

### Minor discordant/secondary signals
- Kidney and blood/immune tissues show **modest, secondary scores** at the cluster level and weak/negative z-scores at the sample level.
- These are plausibly explained by shared housekeeping genes, low-level contamination, or generic stress/immune response genes rather than indicating a different primary tissue.
- There is no strong, structurally coherent marker pattern for a non-brain tissue.

**Resolution:**
- Given the magnitude and specificity of the **brain global signal** at both the sample and cluster levels, and the presence of many canonical CNS marker genes, the modest renal and immune scores are interpreted as **background** and do not alter the primary tissue call.

---

## 5. Final tissue and region assignment

**Tissue call:** **Brain**

**Region/compartment call:** **Global brain / mixed neuronal and glial CNS tissue**

Rationale:
- rnaseqSampleID_2 is assigned to **cluster 3**, which shows **strong enrichment for global brain markers** (highest score_mean_expr across all tissues, multiple overlapping global brain marker genes).
- The **per-sample tissue scores** for rnaseqSampleID_2 show a **dominant Brain–Global signature** (normalized z ≈ 4.17), with no other tissue or brain sub-region approaching this level of evidence.
- The **cluster marker gene profile** (e.g., MOG, MOBP, MBP, PLP1, OLIG1, GFAP, SLC1A2, SNAP25, NEFL, NEFM, UCHL1, KIF5A, GRIN1) and **sample top genes** (e.g., MBP, NRGN, UCHL1, KIF5A, SPARCL1, MT3) are characteristic of central nervous system tissue.
- Lack of convincing cortex/cerebellum/hippocampus-specific marker enrichment suggests that **a precise anatomical sub-region cannot be reliably determined** from these data.

**Final recommended label:**
- **Tissue:** Brain
- **Region:** Global brain (mixed neuronal/glial CNS sample)
