# Predicted organ of origin for Sample_X

**Final call:** `heart`

---

## Evidence supporting a heart origin

1. **Top tissue/organ similarity scores**
   - In the ranked candidate organ analysis (`sample_X_ranked_candidate_organs.tsv`), **heart** is the **top-scoring organ**:
     - Heart similarity score: **3.27** (enriched_markers_mean_z)
     - Blood_or_bone_marrow is second: **3.24** (also enriched_markers_mean_z)
   - In the broader tissue similarity table (`sample_X_tissue_similarity_scores.tsv`), heart again has the **highest similarity score** among all tissues/organs profiled, slightly above blood_or_bone_marrow and clearly above all other tissues (adipose, skeletal_muscle, liver, etc.).
   - Thus, across independent views of the reference marker panel, Sample_X is most similar to a heart-specific marker profile.

2. **Organ marker support and coherence**
   - The organ-level marker summary (`sample_X_organ_marker_support_summary.tsv`) shows:
     - **Heart**:
       - mean_marker_z_score ≈ **3.20**, median_marker_z_score ≈ **3.27**
       - **100%** of detected heart markers are in the top 10% of expression, and **100%** are in the top 5% of expression.
       - **100%** of detected heart markers are also tissue-enriched candidate markers in Sample_X.
       - qualitative_support = **"strong"**.
     - **Blood_or_bone_marrow**:
       - mean_marker_z_score ≈ **1.48**, median_marker_z_score ≈ **1.66** (substantially lower than heart).
       - ~**64%** of detected markers in the top 10% and ~**45%** in the top 5% of expression.
       - ~**36%** of markers overlapping tissue-enriched candidates.
       - qualitative_support = **"strong"**, but numerically weaker and less coherent than heart.
     - **Adipose**:
       - mean_marker_z_score ≈ **1.22**, median_marker_z_score ≈ **1.35**.
       - 50% of markers in the top 10% and top 5%; only ~17% overlap with tissue-enriched candidates.
       - qualitative_support = **"strong"**, but clearly below heart and blood_or_bone_marrow.
   - Heart markers show **both the highest average overexpression and the most coherent, uniformly high expression pattern** among all organs.

3. **Individual marker gene patterns**
   - The per-marker expression table (`sample_X_organ_marker_expression.tsv`) reveals classic **cardiac contractile and natriuretic markers** that are extremely high and uniformly upregulated:
     - Structural/contractile genes: **Tnnt2, Tnni3, Actc1, Myl2, Myl3, Myh6, Myh7, Mybpc3**.
     - Hormone/peptide markers: **Nppa, Nppb**.
   - These heart markers:
     - Have **z-scores ~2.6–3.6** (strongly above background).
     - Sit at **>99th percentile** of expression for the sample.
     - Are annotated as both **top-expressed** and **tissue-enriched markers**.
   - By contrast, blood_or_bone_marrow and adipose markers, while upregulated, show **lower z-scores and less complete/coherent coverage** of their respective marker sets.

4. **Resolving the heart vs blood/immune ambiguity**
   - Heart and blood_or_bone_marrow have **very similar enriched-marker similarity scores** (~3.27 vs ~3.24). If considering only those scores, the distinction would be modest.
   - However, deeper marker-level evidence strongly favors heart:
     - Heart has **higher mean and median marker z-scores**, indicating a more robust and uniform organ-specific signature.
     - Heart shows **complete enrichment** of its marker set in the top expression percentiles and within the tissue-enriched candidates, while blood_or_bone_marrow shows only partial enrichment.
     - The presence of **multiple canonical cardiomyocyte structural genes and natriuretic peptides** at extremely high expression is more consistent with myocardium than with circulating blood or bone marrow.
   - Taken together, this breaks the tie in favor of **heart** as the primary organ of origin.

---

## Caveats and limitations

- **Blood/immune contribution:**
  - The strong blood_or_bone_marrow similarity signal suggests that Sample_X may have a **substantial blood/immune cell component** (e.g., infiltrating or contaminating leukocytes), or that immune-related genes are particularly active in this sample.
  - While this does not change the primary organ call, it indicates that the sample is unlikely to be a purely parenchymal cardiomyocyte population.

- **Reference panel constraints:**
  - The analyses rely on a **hand-curated mouse tissue/organ marker panel** (not a full transcriptomic atlas). Some organs or cell types may be underrepresented, and overlapping markers could blur distinctions among related tissues.
  - Quantitative similarity scores are **relative within this marker set** and should not be interpreted as absolute probabilities.

- **Tissue heterogeneity and sampling context:**
  - The sample may come from a **specific cardiac region or mixed cell population** (e.g., myocardium with vascular and immune components), which is not explicitly modeled here.
  - If Sample_X is derived from a tumor or engineered tissue, marker expression may deviate from normal organ profiles.

Despite these caveats, the convergence of the highest similarity scores, the strongest and most coherent marker support, and the presence of multiple classical heart-specific genes at the top of the expression distribution all support **heart** as the most plausible organ of origin for Sample_X.
