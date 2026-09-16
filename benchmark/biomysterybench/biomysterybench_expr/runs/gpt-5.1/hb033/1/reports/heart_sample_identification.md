# Identification of the Heart Tissue Sample

## Data and scoring overview

We used the per-sample tissue marker scores from `tissue_marker_scores_per_sample.tsv`. Each score is the mean z-score of a curated tissue-specific marker gene set in a given sample (0 ≈ cohort average; positive = enrichment; negative = depletion). Higher values therefore indicate stronger evidence that the sample derives from that tissue.

For each of the 12 anonymized samples, we:

1. Took all tissue scores (blood_hematopoietic, brain, endothelium_vasculature, gut, heart, kidney, liver, skeletal_muscle).
2. Identified the tissue with the highest score as the primary tissue call.
3. Recorded the second-highest score and computed a margin: `top_score − second_best_score`.
4. Assigned a qualitative confidence:
   - **high**: top_score ≥ 1.5 and margin ≥ 0.75
   - **medium**: top_score ≥ 1.0 and margin ≥ 0.5
   - **low**: otherwise

These assignments were saved to `project/outputs/tables/sample_tissue_assignments.tsv`.

## Tissue assignments

The resulting primary calls and score margins are:

| sample_id | assigned_tissue         | top_score | second_best_tissue        | second_best_score | score_margin | confidence |
|-----------|-------------------------|----------:|---------------------------|------------------:|-------------:|-----------|
| Sample_01 | brain                   |  2.714195 | heart                     |        -0.064229 |     2.778424 | high      |
| Sample_02 | gut                     |  0.473489 | kidney                    |        -0.155336 |     0.628825 | low       |
| Sample_03 | heart                   |  2.994196 | endothelium_vasculature   |         1.606579 |     1.387617 | high      |
| Sample_04 | gut                     |  2.233223 | liver                     |         0.293895 |     1.939328 | high      |
| Sample_05 | kidney                  |  1.909688 | blood_hematopoietic       |         1.400493 |     0.509195 | medium    |
| Sample_06 | liver                   |  2.778828 | kidney                    |         0.183581 |     2.595247 | high      |
| Sample_07 | skeletal_muscle         |  0.953398 | endothelium_vasculature   |         0.330626 |     0.622773 | low       |
| Sample_08 | kidney                  | -0.242710 | gut                       |        -0.267658 |     0.024948 | low       |
| Sample_09 | endothelium_vasculature |  1.969535 | blood_hematopoietic       |         1.108748 |     0.860787 | high      |
| Sample_10 | gut                     | -0.003942 | blood_hematopoietic       |        -0.096987 |     0.093045 | low       |
| Sample_11 | brain                   |  0.628262 | skeletal_muscle           |        -0.313530 |     0.941792 | low       |
| Sample_12 | skeletal_muscle         |  2.561674 | blood_hematopoietic       |         0.312535 |     2.249139 | high      |

Under this scheme, **Sample_03** is uniquely assigned as **heart** with high confidence.

## Tissue score profile of the heart-assigned sample

The full tissue marker score profile for **Sample_03** is:

| tissue                   | score   |
|--------------------------|--------:|
| blood_hematopoietic      | -0.3521 |
| brain                    | -0.3824 |
| endothelium_vasculature  |  1.6066 |
| gut                      |  0.0447 |
| **heart**                | **2.9942** |
| kidney                   | -0.2083 |
| liver                    | -0.3291 |
| skeletal_muscle          |  0.1453 |

Key points:

- The **heart** marker program has the highest score (≈3.0), indicating that heart markers are ~3 standard deviations above the cohort mean in Sample_03.
- The second-best tissue is **endothelium_vasculature** with score ≈1.61, still enriched but substantially lower than heart.
- The **margin** between heart and the runner-up (≈1.39 z-score units) is large, supporting a clear separation.
- Most non-cardiac tissues show near-zero or negative scores, consistent with a specific heart identity rather than a mixed or ambiguous tissue.

No other sample has a positive heart score; all other samples have heart scores between approximately -0.06 and -0.34, further reinforcing that only Sample_03 carries a strong cardiac signature.

## Heart marker gene expression across samples

To independently validate the tissue-score–based assignment, we examined expression of canonical heart marker genes using:

- Marker definitions from `tissue_marker_gene_sets.tsv` (tissue = heart).
- The anonymized expression matrix `zebrafish_TPM_anonymized.csv`.

The heart marker set includes core and auxiliary markers such as:

- **Contractile and sarcomeric markers**: *myl7, tnnt2a, myh6, myh7ba*
- **Cardiac transcription factors**: *hand2, gata4, gata5, tbx5a*
- **Chamber/heart failure markers**: *nppa, nppb*
- **Calcium-handling genes**: *ryr2a, ryr2b*

### TPM expression of canonical heart markers

For each heart marker gene, we inspected its TPM expression across the 12 samples. Illustrative values (TPM) include:

- **myl7**:
  - Sample_01: ~3.10
  - Sample_02: ~1.05
  - **Sample_03: ~30,910**
  - Other samples: typically ~0–39
- **tnnt2a**:
  - Sample_01: ~3.12
  - Sample_02: ~0.001
  - **Sample_03: ~4,447**
  - Others: ≲2
- **tbx5a**:
  - **Sample_03: ~103.2**
  - All other samples: ≈0–0.7
- **nppa**:
  - **Sample_03: ~1,577.5**
  - Other samples: ≲0.33
- **nppb**:
  - **Sample_03: ~197.4**
  - Others: ≲3.2 (and often near zero)
- **hand2, gata4, gata5**:
  - All show pronounced elevation in Sample_03 relative to other samples, which have low or modest expression.

This pattern shows a **massive, coherent up-regulation of multiple independent cardiac markers specifically in Sample_03**. Other samples may have low-level expression of some cardiac markers (e.g., low *myl7* or *hand2* in several tissues, or high *ryr2a* in Sample_01 reflecting non-cardiac excitable tissue), but none displays a globally elevated heart marker program.

### Heart marker program z-scores

We also computed gene-wise z-scores (across samples) for the heart marker genes and then averaged per sample. The resulting mean heart-marker z-scores per sample are:

| sample_id | mean heart-marker z-score |
|-----------|---------------------------:|
| Sample_01 | -0.0642 |
| Sample_02 | -0.2987 |
| **Sample_03** | **2.9942** |
| Sample_04 | -0.1534 |
| Sample_05 | -0.3371 |
| Sample_06 | -0.1907 |
| Sample_07 | -0.3207 |
| Sample_08 | -0.3413 |
| Sample_09 | -0.3308 |
| Sample_10 | -0.3015 |
| Sample_11 | -0.3300 |
| Sample_12 | -0.3259 |

These values match the heart column of the tissue marker score matrix and underscore that **only Sample_03 has a strongly positive heart marker z-score**, close to 3 standard deviations above the mean.

## Final heart sample identification

Putting the evidence together:

- **Tissue marker scores**:
  - Sample_03 has the highest heart score in the dataset (≈2.99), with a large margin over all other tissues in the same sample and over heart scores in all other samples.
  - No other sample has a positive heart marker score.
- **Gene-level expression patterns**:
  - Sample_03 uniquely exhibits extremely high expression of multiple independent canonical heart markers (*myl7, tnnt2a, tbx5a, nppa, nppb, hand2, gata4, gata5, myh6, myh7ba*), in contrast to consistently low levels in other samples.
  - The concordant elevation across structural, transcriptional, and signalling markers is exactly what is expected for bona fide heart tissue.

**Most likely heart tissue sample:**

> **Sample_03** is the clear and uniquely supported heart tissue sample.

Both the aggregate tissue marker scores and the underlying canonical heart marker expression profiles independently and strongly support this assignment, with no plausible competing sample.
