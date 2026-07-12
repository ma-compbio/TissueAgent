# Spatial Transcriptomics Hypotheses (Finalized After Critic Review)

These hypotheses are derived from generic properties of the available spatial transcriptomics dataset (`library/datasets/dataset.h5ad`), including:
- Per-spot scores: `score_malignant`, `score_Tcell`, `score_CAF`, `score_M2`
- Spatial coordinates and the `in_tissue` mask
- CellVoyager-derived prompt scores or latent dimensions (CV1–CV3)

They are formulated and refined using only these generic features and do not assume any withheld, paper-specific results. The critic’s feedback has been incorporated to clarify statements, sharpen background/control definitions, pre-specify thresholds and neighborhood rules where appropriate, and elevate confounder checks into the test plans.


## HYP_001

**Biological / Spatial Pattern and Rationale**

High T-cell score regions form spatially clustered ‘immune rims’ that preferentially border, rather than overlap with, malignant-score-rich tumor cores.

Rationale: The exploration log (DATASET_OVERVIEW) indicates that each spot has both spatial coordinates and continuous scores for malignant and T-cell enrichment, and OBSERVATION_CV / CV1–CV2 emphasize that spatially structured variation in these phenotypes may underlie tissue heterogeneity. A plausible spatial pattern in a tumor microenvironment is that T-cell–enriched regions accumulate around, but do not fully penetrate, malignant cores, forming ‘immune rims’ at tumor borders.

**Planned Tests and Interpretation**

The analysis plan specifies:
- Restricting to `in_tissue` spots and defining `MAL_CORE` as the top quartile of `score_malignant`.
- Building a spatial k-NN graph on `obsm['spatial']`, defining `RIM` as non-core spots that are immediate neighbors of any core spot, and `FAR` as remaining in-tissue spots.
- Comparing `score_Tcell` across MAL_CORE, RIM, and FAR with global (Kruskal–Wallis) and pairwise (Wilcoxon/Mann–Whitney) tests, plus standardized effect sizes.
- Quantifying neighbor-based T-cell enrichment around malignant cores using permutation-based nulls.

Evidence for the hypothesis would be a pattern where T-cell scores are significantly higher in RIM than in MAL_CORE, comparable between RIM and FAR, and with elevated neighbor T-cell scores immediately around malignant cores relative to the global mean, together indicating a rim of T-cell enrichment at tumor borders.

**Executed Tests and Outcomes (Phase 3)**

Status: **REFINE**

- Using all in-tissue spots, MAL_CORE was defined as the top 25% of `score_malignant`, RIM as immediate k-NN neighbors of cores that were not themselves cores, and FAR as remaining in-tissue spots.
- `score_Tcell` distributions differed strongly across MAL_CORE, RIM, and FAR (Kruskal–Wallis p ≈ 1.8×10⁻¹⁵⁰).
- RIM spots had substantially higher T-cell scores than MAL_CORE (mean difference ≈ 0.37, Cohen’s d ≈ 0.78, FDR-adjusted p ≈ 4.1×10⁻⁵⁷), indicating robust T-cell depletion within malignant cores relative to their immediate surroundings.
- However, RIM spots were modestly depleted relative to FAR (mean difference ≈ −0.07, d ≈ −0.12, FDR-adjusted p ≈ 1.9×10⁻⁷), suggesting that the highest T-cell scores occur in more distant regions rather than in a narrow rim.
- Neighbor-based analysis around MAL_CORE spots showed that the mean T-cell score among spatial neighbors was **lower** than the global mean (difference ≈ −0.26), with an empirical one-sided permutation p-value of ≈ 1.0 for the test of neighbor > global, indicating no evidence for local T-cell enrichment immediately adjacent to cores.

**Interpretation:**

These results strongly support T-cell depletion within malignant-rich cores and higher T-cell scores outside them, but they do not show a clear, narrow band of locally enriched T-cell scores hugging the core boundaries. Instead, T-cell enrichment appears more diffuse, with the highest values in more distant regions. Because the global group differences and MAL_CORE vs RIM contrast are strong but the rim vs far pattern and neighbor-based enrichment are not aligned with the pre-specified expectations, the hypothesis is best classified as **REFINE**. Future refinements could adjust the malignant-core threshold or explore alternative neighborhood radii to better isolate potential border-localized T-cell rims.


## HYP_002

**Biological / Spatial Pattern and Rationale**

Spatially coherent regions with concurrently high cancer-associated fibroblast and M2-like myeloid scores act as immunosuppressive niches characterized by locally reduced T-cell scores.

Rationale: The dataset includes per-spot `score_CAF`, `score_M2`, and `score_Tcell`, allowing definition of putative CAF/M2-rich niches and comparison of local T-cell context. Spatially clustered CAF/M2-high regions with depleted T-cell scores would be consistent with immunosuppressive niches.

**Planned Tests and Interpretation**

The analysis plan specifies:
- Restricting to `in_tissue` spots and defining `CAF_high` and `M2_high` as top-quartile values of `score_CAF` and `score_M2`.
- Defining `CAF_M2_niche` spots as the intersection of CAF_high and M2_high, and `CAF_M2_background` as all other in-tissue spots.
- Building a spatial k-NN graph on `obsm['spatial']`.
- For each niche and matched background spot, computing the mean `score_Tcell` among spatial neighbors and comparing these distributions using non-parametric tests and standardized effect sizes.
- Quantifying spatial coherence of CAF_M2_niche labels via the fraction of neighbors that are also niche spots, with permutation-based empirical p-values.

Support for the hypothesis would require that CAF_M2_niche spots are spatially clustered and have **lower** neighbor T-cell scores than matched background spots (with statistically significant differences and at least moderate effect sizes).

**Executed Tests and Outcomes (Phase 3)**

Status: **REFINE**

- Using all in-tissue spots, CAF_high and M2_high were defined by the top 25% of `score_CAF` and `score_M2` respectively. Their intersection yielded 372 `CAF_M2_niche` spots, with the remaining 3426 spots as `CAF_M2_background`.
- A shared spatial k-NN graph (k = 8) was used for all hypotheses.
- For each niche spot, the mean T-cell score among its neighbors was computed and compared to an equal-sized random sample of background spots. Contrary to the immunosuppressive niche expectation, neighbor mean T-cell scores were **higher** around CAF_M2_niche centers than around background controls (mean difference ≈ +0.18, Cohen’s d ≈ 0.43, p ≈ 6.8×10⁻⁷).
- CAF_M2_niche labels were strongly spatially coherent: the observed fraction of neighbors of niche spots that were also niche was ≈ 0.24, with an empirical permutation p ≈ 0.001 (one-sided test for greater-than-random), indicating robust clustering of CAF/M2-high regions.

**Interpretation:**

The data clearly support the existence of spatially coherent CAF/M2-enriched regions, but these regions are associated with local **T-cell enrichment** rather than depletion under the pre-specified top-quartile thresholds and neighborhood definition. Because one core component of the hypothesis (CAF/M2 clustering) is supported while the key prediction of local T-cell suppression is reversed, the hypothesis is classified as **REFINE**. Refinement could involve exploring alternative cutoffs (e.g., higher quantiles, joint CAF/M2 score thresholds) or different spatial scales to test whether a subset of CAF/M2-rich regions are genuinely T-cell–poor.


## HYP_003

**Biological / Spatial Pattern and Rationale**

Unsupervised transcriptomic clusters define spatially coherent tumor microenvironment ‘ecosystem’ states with distinct malignant, fibroblast, myeloid, and T-cell score profiles.

Rationale: The dataset contains a full gene-expression matrix with per-spot summary scores for malignant, CAF, M2, and T-cell states. Dimensionality reduction and graph-based clustering can reveal data-driven groups of spots, which may correspond to spatially organized microenvironment “ecosystems” with characteristic combinations of these scores.

**Planned Tests and Interpretation**

The analysis plan specifies:
- Restricting to `in_tissue` spots and performing standard preprocessing (library-size normalization, log1p transform) on the expression matrix.
- Running PCA and constructing a k-NN graph in PCA space.
- Applying Leiden clustering at predefined resolutions (0.4–0.8) and selecting a primary resolution (e.g., ~0.6) for downstream analysis.
- For the chosen clustering, computing per-cluster means and variances of `score_malignant`, `score_CAF`, `score_M2`, and `score_Tcell`.
- Testing, for each score, whether its distribution differs across clusters (global ANOVA/Kruskal–Wallis) and, where relevant, examining pairwise contrasts and standardized effect sizes.
- Quantifying spatial coherence by measuring, for each cluster, the fraction of spatial neighbor edges that connect spots within the same cluster, and comparing this to permutation-based label nulls.

Support for the hypothesis requires that (i) at least two of the four scores show significant between-cluster variation with substantial effect sizes, and (ii) at least two reasonably large clusters exhibit spatial coherence beyond random expectation.

**Executed Tests and Outcomes (Phase 3)**

Status: **SUPPORTED**

- Standard scanpy preprocessing (normalize_total, log1p, highly variable gene selection, scaling, PCA) was applied to all in-tissue spots, followed by a PCA-based k-NN graph and Leiden clustering at resolution 0.6, yielding 11 clusters (9 of which contained ≥5% of spots).
- Cluster-level summaries showed diverse score profiles: some clusters were malignant-dominant with relatively low T-cell scores, others were more immune-enriched, fibroblast-high, or myeloid-high, indicating distinct ecosystem-like states.
- Global Kruskal–Wallis tests confirmed very strong between-cluster differences for all four scores (FDR-adjusted p-values < 1×10⁻¹⁰⁰ for malignant, CAF, M2, and T-cell scores). Maximum standardized pairwise differences (using global SD) were substantial: roughly 2.5 SD for malignant scores, 1.3 SD for CAF, 1.5 SD for M2, and 1.6 SD for T-cell scores.
- Spatial coherence analysis using the shared spatial k-NN graph showed that all sizable clusters had within-cluster neighbor fractions far above those expected under permutation-based null models (empirical p ≈ 0.001 for clusters 0–8), consistent with spatially organized ecosystems rather than spatially mixed labels.

**Interpretation:**

The combination of large, statistically robust differences in malignant, stromal, myeloid, and T-cell scores across unsupervised clusters and strong spatial coherence of those clusters supports the view that data-driven transcriptomic clusters correspond to distinct, spatially organized tumor microenvironment ecosystems. While additional differential expression analyses could further characterize the underlying gene programs, the pre-specified criteria are clearly met, and the hypothesis is classified as **SUPPORTED**.
