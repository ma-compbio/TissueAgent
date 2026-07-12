# Tested Novel Hypotheses (Grounded in OBSERVATION ids)

Paper findings are withheld; hypotheses are derived from exploratory OBSERVATION entries and dataset structure.

## Dataset Overview

- Cells: 3798
- Genes: 36601
- Spatial coordinates available: True
- Annotations: bc_short, in_tissue, array_row, array_col, score_CAF, score_M2, score_malignant, score_Tcell

---

## Hypothesis H1

**Grounded in OBSERVATION ids**: OBSERVATION_1, OBSERVATION_2

**Statement**:
Spatially co-localized immune and stromal compartments exhibit coordinated activation of
inflammatory and extracellular-matrix remodeling programs relative to regions where these
compartments are spatially segregated.

**Proposed Mechanism**:
Building on OBSERVATION_1, OBSERVATION_2 indicating spatial gradients in immune activity and
distinct stromal transcriptional programs, this hypothesis proposes that physical proximity between
immune-enriched and stromal-enriched regions induces a coupled inflammatory–fibrotic transcriptional
state in both compartments. In regions of close immune–stromal apposition, immune cells would
upregulate chemokines and cytokines while nearby stromal cells would simultaneously upregulate
extracellular-matrix, matrix-remodeling, and fibrosis-associated gene modules, leading to a
spatially localized inflammatory–fibrotic niche.

**Status after testing (phase 3)**:
- Status: SUPPORTED
- Narrowing notes: Partial but strong support focused on stromal compartment: extracellular-matrix/fibrosis scores are significantly elevated at stromal spots contacting immune-high neighbors compared with isolated stromal spots (p=3.14e-08). Immune inflammatory scores do not increase at interfaces (p=6.93e-02), so the immune side of the coupled inflammatory–fibrotic response is not clearly detected under this simple scoring scheme.

**Test Plan (high-level)**:
- Define immune-, stromal-, and epithelial-like compartments using existing cell-type or cluster annotations if available; otherwise infer compartments using expression of canonical immune (e.g., PTPRC/CD45, LYZ, HLA genes), stromal (e.g., COL1A1, DCN, LUM), and epithelial markers (e.g., EPCAM, KRT genes) restricted to genes present in the dataset.
- Compute spatial proximity metrics between immune and stromal spots or cells (e.g., minimum inter-spot distance, shared neighborhood membership on a k-nearest-neighbor graph in physical space). Define ‘proximal immune–stromal interfaces’ versus ‘immune-isolated’ and ‘stromal-isolated’ regions by thresholding proximity metrics.
- Construct gene-set scores for inflammation (e.g., cytokines, chemokines, antigen-presentation genes) and extracellular-matrix / fibrosis programs (e.g., collagens, matrix metalloproteinases, matricellular proteins) using only genes confirmed in the data inventory or feasibility file.
- For each compartment (immune, stromal), compare program scores between interface regions and isolated regions using appropriate statistical tests (e.g., Wilcoxon rank-sum test), controlling for overall cell-type composition if possible.
- Perform a spatial permutation test: randomly shuffle spatial coordinates or region labels while preserving cell-type identity to generate a null distribution of interface-associated program enrichment. Assess whether observed co-activation of inflammatory and ECM programs at interfaces exceeds the null.
- Visualize spatial maps of program scores and overlay the locations of immune–stromal interfaces to demonstrate co-localization patterns (e.g., heatmaps on tissue coordinates, neighborhood-level averages).

**Predicted Outcome**:
Immune and stromal compartments located at immune–stromal interfaces will show significantly higher
inflammatory program scores in immune cells and higher extracellular-matrix/fibrosis program scores
in stromal cells compared with the same cell classes in spatially isolated regions. Spatial
permutation analysis will indicate that this coordinated activation is unlikely under a null model
of random spatial arrangement, supporting a model where spatial immune–stromal interactions
contribute to localized inflammatory–fibrotic niches in the diseased tissue.

**Quality Scores (1–10)**:
- Derivable: 8
- Novel: 8
- Feasible: 8
- Specific: 8
- Falsifiable: 8

---

## Hypothesis H2

**Grounded in OBSERVATION ids**: OBSERVATION_2, OBSERVATION_3

**Statement**:
Transcriptional programs related to cellular metabolism and stress responses form coordinated
spatial gradients across tissue regions, such that regions enriched for extracellular-matrix and
structural remodeling programs display a shift toward stress- and glycolysis-associated gene
expression and away from oxidative metabolism compared to structurally intact regions.

**Proposed Mechanism**:
Based on OBSERVATION_2, OBSERVATION_3, which indicate distinct transcriptional programs between
structural compartments and localized enrichment of extracellular-matrix and fibrosis-like
signatures, this hypothesis posits that tissue zones undergoing active remodeling adopt a shared
metabolic and stress-response state. Specifically, regions with high ECM-remodeling activity are
expected to show coordinated upregulation of hypoxia, unfolded protein response, and glycolytic
pathways, with relative downregulation of oxidative phosphorylation and mitochondrial programs,
reflecting metabolic reprogramming imposed by the diseased microenvironment.

**Status after testing (phase 3)**:
- Status: DROPPED
- Narrowing notes: Contrary to prediction, ECM-rich regions show lower glycolysis and stress-associated module scores and higher oxidative-phosphorylation scores relative to ECM-poor regions (perfect negative Spearman correlations between ECM and glycolysis/UPR and positive correlation with ROS). With only four spatial regions this pattern is strong but opposite in sign to the hypothesized glycolytic/stress-shift, so the hypothesis is not supported in this dataset.

**Test Plan (high-level)**:
- Use available region/layer/zone annotations to define spatial compartments (e.g., lesion core vs periphery, fibrotic vs non-fibrotic regions). If such labels are absent, derive data-driven regions by clustering spots in spatial coordinates combined with expression of ECM/fibrosis markers identified in the exploration log.
- Compute module scores for metabolic and stress-related pathways using curated gene sets restricted to genes present in the dataset: glycolysis, oxidative phosphorylation, hypoxia-response, unfolded protein response, and reactive-oxygen-species handling. Use data_feasibility to confirm genes’ presence where possible.
- For each annotated region (or spatial cluster), quantify average ECM/fibrosis program scores and metabolic program scores. Test for associations between ECM/fibrosis scores and metabolic/stress modules using correlation analyses (e.g., Spearman rank correlation across regions or spatial bins).
- Assess whether there is a significant monotonic trend in metabolic program scores along spatial gradients from intact to remodelled regions (e.g., core-to-periphery or distal-to-proximal), by ordering regions according to ECM/fibrosis scores and fitting trend models (e.g., Kendall trend test or linear regression).
- Perform spot-level mixed-effects modeling or generalized additive modeling incorporating region identity and spatial coordinates to test whether association between ECM and metabolic programs is robust to local spatial context and cell-type composition, when cell-type annotations are available.
- Visualize spatial maps of ECM/fibrosis and metabolic program scores and their residuals after adjusting for cell-type composition to qualitatively validate the presence of coordinated metabolic reprogramming in ECM-enriched zones.

**Predicted Outcome**:
Regions with high extracellular-matrix/fibrosis program scores will show significantly higher levels
of stress-response and glycolytic pathway activity and lower oxidative-phosphorylation scores
relative to structurally intact regions. A positive correlation between ECM and stress/glycolytic
modules and a negative correlation between ECM and oxidative metabolism across spatial regions will
support the presence of zonal metabolic reprogramming accompanying structural remodeling in the
diseased tissue.

**Quality Scores (1–10)**:
- Derivable: 8
- Novel: 9
- Feasible: 7
- Specific: 8
- Falsifiable: 8

---

## Hypothesis H3

**Grounded in OBSERVATION ids**: OBSERVATION_1, OBSERVATION_3

**Statement**:
Tissue interfaces where epithelial-like and stromal or immune compartments directly abut exhibit
convergent upregulation of barrier-disruption, cell-adhesion remodeling, and chemotactic signaling
programs compared with epithelial regions that remain insulated from stromal and immune cells.

**Proposed Mechanism**:
Given OBSERVATION_1, OBSERVATION_3, which highlight spatial gradients in immune activity and
localized extracellular-matrix remodeling, this hypothesis proposes that loss of normal
compartmental segregation at epithelial–stromal interfaces triggers a coordinated transcriptional
state. At these interfaces, epithelial cells downregulate barrier-maintenance and polarity-
associated programs while upregulating adhesion-remodeling and chemokine/adhesion ligand genes, and
adjacent stromal/immune cells upregulate complementary adhesion receptors and chemokine receptors,
collectively reflecting a breakdown and reconfiguration of the barrier.

**Status after testing (phase 3)**:
- Status: SUPPORTED
- Narrowing notes: Strong partial support: epithelial interface spots have significantly reduced barrier/polarity scores relative to insulated epithelia (p=1.06e-02) and adjacent stromal/immune spots show significantly increased adhesion-remodeling scores (p=3.33e-23). However, chemotaxis-module scores are actually lower in interface-adjacent stromal/immune neighbors than in the background, suggesting that barrier disruption and adhesion remodeling are decoupled from chemokine upregulation in this sample.

**Test Plan (high-level)**:
- Identify epithelial-like, stromal-like, and immune-like populations using existing annotations or by constructing marker-based scores (epithelial markers such as EPCAM and keratins; stromal markers such as collagens and decorin; immune markers such as PTPRC and HLA genes, restricted to genes present in the dataset).
- Define epithelial regions that are ‘insulated’ (no stromal/immune neighbors within a specified spatial radius) versus ‘interface’ regions (epithelial spots whose k-nearest neighbors in physical space include stromal and/or immune spots). Use multiple radii or k to confirm robustness.
- Construct gene-set scores for barrier/polarity maintenance (tight junction, adherens junction, epithelial polarity complexes), adhesion remodeling (integrins, cadherin switching, matrix receptors), and chemotactic signaling (chemokines and their receptors) using genes available in the dataset.
- Compare these program scores between insulated and interface epithelial cells using appropriate statistical tests (e.g., Wilcoxon rank-sum), correcting for multiple testing across modules.
- In stromal and immune neighbors adjacent to epithelial interface regions, quantify complementary adhesion and chemokine-receptor program scores and assess whether these are elevated relative to stromal/immune cells distant from epithelia.
- Perform spatial co-variation analysis: within local neighborhoods centered on epithelial interface spots, measure correlations between epithelial barrier-disruption/adhesion-remodeling scores and stromal/immune adhesion/chemotaxis scores. Compare these correlations to those observed in neighborhoods centered on insulated epithelial regions, using permutation tests over neighborhood labels.
- Visualize interface vs insulated epithelial regions and overlay program scores to qualitatively illustrate barrier-disruption and adhesion-remodeling concentrated at epithelial–stromal/immune contact zones.

**Predicted Outcome**:
Epithelial cells at stromal/immune interfaces will show significantly lower barrier/polarity program
scores and higher adhesion-remodeling and chemotactic signaling scores compared with insulated
epithelial cells. Adjacent stromal and immune cells will display complementary increases in adhesion
and chemokine-receptor programs, leading to stronger local co-variation of these programs around
interfaces than around insulated epithelial regions. Failure to detect such patterns would argue
against widespread transcriptional reprogramming at epithelial–stromal/immune interfaces in this
dataset.

**Quality Scores (1–10)**:
- Derivable: 8
- Novel: 9
- Feasible: 7
- Specific: 9
- Falsifiable: 9

---
