# Spatial Hypotheses for SpaCET Tumor Dataset

## H1: Enrichment of immune-lineage scores at tumor edge versus interior

**Hypothesis statement.** In this single human tumor section, spatial spots located near the outer tissue boundary show higher T cell lineage scores and related immune-activation module scores than interior spots, even after accounting for variation in total counts and detected genes.

**Referenced observations.** OBSERVATION_2.2_spatial_pattern_lineage_scores, OBSERVATION_3.1_spatial_gradients_and_edge_definition.

**Why interesting here.** Tests whether immune-lineage enrichment at the tumor edge, a common pattern in solid tumors, is recapitulated in this single-section spatial dataset, using only existing T cell scores and data-derived immune modules.

**Main planned tests.** Define a robust edge vs interior classification from spatial coordinates; derive an immune-activation gene module from genes correlated with score_Tcell; compare immune scores between edge and interior spots using regression with n_counts and n_genes covariates and a spatial permutation null; and examine gradients with distance to the tissue edge.

**Strengths and limitations.** Strengths include explicit control for QC covariates, a clearly defined edge metric, and a dataset-derived gene set. Limitations include sensitivity to the chosen edge threshold and the reliance on correlation-based gene-set construction flagged by the critic.


---

## H2: Higher domain-level heterogeneity and lineage mixing at tumor boundaries

**Hypothesis statement.** Tissue regions near the tumor boundary exhibit greater diversity of transcriptomic domains and stronger co-localization of immune and stromal lineage scores than interior regions, when domains are defined in an unsupervised manner from spatially smoothed expression patterns.

**Referenced observations.** OBSERVATION_2.2_spatial_pattern_lineage_scores, OBSERVATION_3.2_spatial_autocorrelation_domains.

**Why interesting here.** Explores whether the tumor boundary harbors more diverse and lineage-mixed microenvironmental domains than the interior, going beyond single-spot scores to domain-level structure.

**Main planned tests.** Construct unsupervised spatial domains (domain_label) from smoothed expression or lineage-score representations; classify domains as boundary or interior based on edge-status of member spots; compare domain richness, lineage-score diversity, and immune–stromal co-localization between boundary and interior domains using permutation-based nulls.

**Strengths and limitations.** Strengths are the explicit domain-label construction, clear boundary vs interior contrasts, and specified null models. Limitations flagged by the critic include sensitivity to clustering choices and the need to adjust for QC covariates when comparing domain-level diversity.


---

## H3: Spatial segregation of proliferation-like and inflammation-like programs within the tumor

**Hypothesis statement.** Within this tumor section, spots with high proliferation-associated gene expression programs are spatially segregated from spots with high inflammation-associated programs, such that local neighborhoods tend to be dominated by one program or the other rather than a balanced mixture.

**Referenced observations.** OBSERVATION_2.3_QC_and_highly_variable_genes, OBSERVATION_2.2_spatial_pattern_lineage_scores.

**Why interesting here.** Addresses whether proliferative and inflammatory transcriptional programs occupy distinct spatial niches within the same tumor, a key question for understanding mutually exclusive versus co-existing tumor states using only this spatial dataset.

**Main planned tests.** Derive proliferation and inflammation gene programs via unsupervised factorization and correlation with lineage scores; compute corresponding module scores; test global and covariate-adjusted correlations between the programs; quantify local spatial segregation using neighborhood-based metrics and permutation nulls; and relate program dominance to domain_label from H2.

**Strengths and limitations.** Strengths include a fully data-driven definition of programs and explicit local versus global segregation tests. Limitations noted by the critic involve potential ambiguity in program gene-set definition, dependence on chosen neighborhood parameters, and the need for carefully specified null models.


---
