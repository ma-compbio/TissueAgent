# Tissue Classification Report

## Predicted tissue

- **Predicted tissue:** Prostate  
- **tissue_score (mean Pearson correlation):** 0.9797  
- **pearson_correlation_max:** 0.9905  
- **spearman_correlation_mean:** 0.9202  
- **spearman_correlation_max:** 0.9322  
- **cosine_similarity_mean:** 0.9850  
- **cosine_similarity_max:** 0.9930  
- **Number of matched reference samples (n_samples):** 52

These values indicate a very strong and consistent similarity signal between the unknown sample and Prostate reference profiles, across Pearson, Spearman, and cosine similarity metrics.

## Ranked tissue summary (top 5)

Based on `tissue_score` (mean Pearson correlation):

1. **Prostate** — tissue_score: 0.9797; n_samples: 52
2. **Bladder** — tissue_score: 0.9506; n_samples: 43
3. **Cervix - Endocervix** — tissue_score: 0.9496; n_samples: 23
4. **Thyroid** — tissue_score: 0.9479; n_samples: 52
5. **Colon - Transverse - Muscularis** — tissue_score: 0.9479; n_samples: 9

Prostate shows a clearly higher mean Pearson correlation than all alternatives, with a margin of ~0.029 over the second-ranked tissue (Bladder). All top-ranked tissues have high correlations, but Prostate is distinctly strongest.

## Evidence from top per-sample matches

- Among the **top 10, 25, 50, and 100** per-sample reference matches ranked by Pearson correlation, **all** matches are annotated as **Prostate**.
- The overall `top_reference_matches.tsv` table (top 50 by Pearson) contains only Prostate samples.

This indicates that the highest-similarity individual reference profiles are exclusively from Prostate, further reinforcing the tissue-level summary.

## Caveats and assumptions

- Similarity scores for several non-Prostate tissues (e.g., Bladder, Cervix - Endocervix, Thyroid) are also high (>0.94 mean Pearson), which reflects biological and technical similarities across some tissues and the generally high signal-to-noise of the data. However, none of these tissues approach the Prostate tissue_score or per-sample dominance.
- The classification relies primarily on **mean Pearson correlation (tissue_score)**, supplemented by Spearman and cosine metrics and the distribution of top per-sample matches. All three similarity measures consistently favor Prostate.
- The analysis assumes that log1p-CPM normalized expression profiles and Pearson-based similarity are appropriate for this dataset and that the reference annotations are accurate.

**Conclusion:** The unknown sample is best classified as **Prostate**, with high confidence given the strong, consistent similarity metrics and exclusive dominance of Prostate among the top individual reference matches.
