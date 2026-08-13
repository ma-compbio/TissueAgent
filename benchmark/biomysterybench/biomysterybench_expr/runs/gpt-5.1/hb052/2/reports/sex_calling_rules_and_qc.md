# Sex calling based on sex-marker expression

## Marker expression distributions and thresholds

We used the following marker genes: Y-linked (DDX3Y, EIF1AY, KDM5D, RPS4Y1, USP9Y, UTY, ZFY) and the X-linked inactivation marker XIST. TSIX was entirely missing (all values NaN) in this dataset and was therefore not used.

### Raw expression summary (log-scale units as provided)

- DDX3Y: mean=4.765, sd=1.017, min=4.351, 25%=4.400, 50%=4.418, 75%=4.442, max=8.589
- EIF1AY: mean=9.309, sd=1.567, min=7.177, 25%=8.293, 50%=9.081, 75%=9.696, max=13.766
- KDM5D: mean=4.985, sd=1.241, min=4.418, 25%=4.509, 50%=4.557, 75%=4.613, max=9.349
- RPS4Y1: mean=5.243, sd=2.707, min=4.351, 25%=4.376, 50%=4.400, 75%=4.445, max=15.007
- USP9Y: mean=4.668, sd=0.475, min=4.429, 25%=4.477, 50%=4.509, 75%=4.622, max=7.128
- UTY: mean=4.577, sd=0.258, min=4.406, 25%=4.458, 50%=4.512, 75%=4.558, max=5.797
- ZFY: mean=5.356, sd=0.870, min=4.549, 25%=4.844, 50%=5.072, 75%=5.493, max=8.582
- XIST: mean=8.539, sd=4.703, min=4.966, 25%=5.108, 50%=6.073, 75%=12.492, max=14.704

### Z-score summary (per-gene, across samples)

For each marker we computed a per-gene z-score (value minus gene mean, divided by gene standard deviation) across all samples.

- DDX3Y_z: mean=0.000, sd=1.000, min=-0.407, 25%=-0.359, 50%=-0.341, 75%=-0.317, max=3.762
- EIF1AY_z: mean=0.000, sd=1.000, min=-1.360, 25%=-0.648, 50%=-0.145, 75%=0.247, max=2.844
- KDM5D_z: mean=0.000, sd=1.000, min=-0.457, 25%=-0.383, 50%=-0.344, 75%=-0.299, max=3.515
- RPS4Y1_z: mean=0.000, sd=1.000, min=-0.329, 25%=-0.320, 50%=-0.311, 75%=-0.295, max=3.606
- USP9Y_z: mean=0.000, sd=1.000, min=-0.503, 25%=-0.403, 50%=-0.334, 75%=-0.097, max=5.181
- UTY_z: mean=0.000, sd=1.000, min=-0.666, 25%=-0.464, 50%=-0.254, 75%=-0.075, max=4.729
- ZFY_z: mean=-0.000, sd=1.000, min=-0.927, 25%=-0.588, 50%=-0.326, 75%=0.157, max=3.708
- XIST_z: mean=0.000, sd=1.000, min=-0.760, 25%=-0.730, 50%=-0.524, 75%=0.841, max=1.311

From these z-scores we defined composite Y-scores per sample:

- **Y_mean_z**: mean z-score across the seven Y-linked genes. In this dataset, most samples cluster around Y_mean_z ≈ -0.3, while a small subset shows **Y_mean_z > 1.5**, representing very strong Y expression across markers.

- **Y_max_z**: maximum z-score among the Y-linked genes. This captures a single very high Y marker even if others are more modest.

- **Y_high_genes_z1.5**: count of Y markers with z > 1.5, used to require concordance across multiple Y genes. In this dataset, three samples have all seven Y markers with z > 1.5; most other samples have zero such markers.

For **XIST**, only 6/49 samples had non-missing values. Within those, XIST_z ranged from approximately -0.76 to 1.31, with the top two samples (SampleID 2 and 3) showing XIST_z > 1.2 and raw expression around 14.4–14.7 (far above the dataset median of ~6.1).

## Decision rules for sex calling

Sex was assigned solely from marker patterns using the following rules, evaluated per sample on the z-transformed values:

1. **Confident male ("very_strong_Y_lowXIST")**\

   - Y_mean_z > 1.5 (Y expression well above the gene-wise means), **and**\

   - At least 5 of 7 Y-linked markers have z > 1.5 (Y_high_genes_z1.5 ≥ 5), ensuring concordant elevation across multiple Y markers, **and**\

   - XIST_z < 0.5 or XIST is missing (no strong XIST signal).\

   - If Y_mean_z > 1.5 and ≥5 high Y markers but XIST_z ≥ 0.5 (strong XIST), the sample would instead be labelled **unknown** as a conflicting pattern, but no such sample was observed here.

2. **Male ("strong_Y_multi_markers_verylow_XIST")**\

   - Y_mean_z > 1.0 (strong but slightly weaker than the above), **and**\

   - At least 4 Y markers have z > 1.5 (Y_high_genes_z1.5 ≥ 4), **and**\

   - XIST_z < 0.0 or missing (XIST at or below the dataset mean).\

   - In this dataset, the three confident males already satisfy the stricter rule above; no additional males were added by this second rule.

3. **Confident female ("high_XIST_uniformly_lowY")**\

   - XIST_z > 0.8 (strong XIST up-regulation relative to other samples with XIST measured), **and**\

   - Y_mean_z < 0.5 (no overall Y up-regulation), **and**\

   - Y_max_z < 1.0 (no individual Y gene strongly elevated).

4. **Female (weaker evidence, "moderate_XIST_noY")**\

   - XIST_z > 0.5 (moderately high XIST), **and**\

   - Y_mean_z < 0.8, **and**\

   - Y_max_z < 1.5 (no clearly elevated Y markers).

5. **Unknown**\

   - Any sample not meeting the above male or female criteria is classified as **unknown**. This explicitly includes cases with moderate Y and moderate XIST, or with overall low signal and missing XIST.

## QC results and interpretation

### Sex category counts

- unknown: 46 samples
- male: 3 samples

In this dataset, three samples (SampleID 1, 4, 6) show very strong, concordant Y expression across all seven Y-linked markers (Y_mean_z ≈ 2.9–3.7 with all seven Y markers having z > 1.5) and low XIST_z (< 0). These are confidently called **male**.

Two samples (SampleID 2 and 3) show both elevated Y (Y_mean_z ≈ 0.93–1.38 with 3 Y markers having z > 1.5) and very strong XIST (XIST_z > 1.2). Because of this conflicting pattern, they do not satisfy either male or female rules and are conservatively labelled **unknown**.

All remaining 44 samples have uniformly low Y expression (Y_mean_z < 0.5, typically < 0) and no XIST measurement (XIST is missing). Without a positive XIST signal, these cannot be confidently assigned as female; they are therefore also classified as **unknown** rather than being forced into either sex category.

### Marker informativeness

- All seven Y-linked markers show a clear bimodal-like separation between a small cluster of Y-high samples and a majority of Y-low samples, supporting their use for detecting males.\

- XIST is informative where present, but it is missing for the majority of samples (43/49), limiting confident female calling.\

- TSIX is entirely missing (0 non-NaN values) and was not used.

### Summary

The rule set above gives high-confidence **male** calls for a small set of samples with strong, concordant Y-marker expression and low XIST, while avoiding over-calling **female** status in the absence of robust XIST signal. Most samples fall into an **unknown** category due to either missing XIST or conflicting Y/XIST patterns.
