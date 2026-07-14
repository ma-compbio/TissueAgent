# Exploration log

## OBSERVATION_001 — Dataset and technology overview
- **Type:** annotation-related
- **Description:** The AnnData object contains 1,162 spatial spots with 19,237 genes. A single sample (`sample_id` = `CID44971`) is present, annotated as part of a Renoir spatial ligand–target study. The sequencing/measurement technology is spatial transcriptomics with Visium-style metadata, but the exact platform is not explicitly encoded and is treated as `unknown_spatial_technology` in the inventory.
- **Relevant fields (see `tables/data_inventory.tsv`):**
  - Section `global`: `n_obs`, `n_vars`, `paper_id`, `sample_id`, `source`, `technology`.

## OBSERVATION_002 — Spatial coordinate systems and grid structure
- **Type:** spatial
- **Description:** Spatial coordinates are stored as a 2D embedding in `obsm["spatial"]` (range approximately x: 2,348–7,703; y: 1,265–7,826) and as array indices `array_row` and `array_col` in `.obs`. Both representations cover all 1,162 spots, indicating a single tissue section laid out on a regular grid. Quadrant counts using the median split of the `spatial` coordinates are relatively balanced (278, 311, 307, 266), suggesting no large empty quadrants.
- **Relevant fields:**
  - Section `spatial`: `obsm:spatial`, `obs:array_row`, `obs:array_col`.
  - Section `obs_field`: `array_row`, `array_col`.

## OBSERVATION_003 — Spot density heterogeneity across the array
- **Type:** spatial
- **Description:** Spots are distributed across 70 distinct `array_row` indices and 99 distinct `array_col` indices. The number of spots per row has a mean of ~16.6 (range 1–38), indicating rows with substantially higher local density. Columns show a mean of ~11.7 spots (range 1–19). This suggests non-uniform coverage across the slide, likely reflecting tissue shape and partial occupancy of the capture area.
- **Relevant fields:**
  - Section `spatial`: `obs:array_row`, `obs:array_col`.
  - Section `obs_field`: `array_row`, `array_col` (numeric summaries).

## OBSERVATION_004 — Sample, subtype, and patient structure
- **Type:** annotation-related / compositional
- **Description:** All spots belong to a single patient (`patientid = CID44971`) and a single molecular subtype (`subtype = TNBC`). Thus, there is no between-patient or between-subtype variation within this object, and any compositional differences arise from intra-sample spatial heterogeneity rather than inter-sample factors.
- **Relevant fields:**
  - Section `obs_field`: `patientid`, `subtype`.
  - Section `grouping`: `Classification` (as main multi-level grouping).

## OBSERVATION_005 — Tissue vs. background spots
- **Type:** QC-related / spatial
- **Description:** The `in_tissue` indicator marks 1,160 spots as tissue (`1`) and 2 spots as off-tissue/background (`0`). This small number of off-tissue spots suggests that most captured positions overlap tissue, but these off-tissue positions may be useful negative controls for background signal in later analyses.
- **Relevant fields:**
  - Section `obs_field`: `in_tissue`.
  - Section `qc`: `nCount_RNA`, `nFeature_RNA` (to be cross-checked against `in_tissue` in later QC).

## OBSERVATION_006 — QC depth and feature counts
- **Type:** QC-related
- **Description:** The QC fields `nCount_RNA` and `nFeature_RNA` show a wide dynamic range. For `nCount_RNA`, the minimum is 627 UMIs, the median ~10,114, and the maximum 57,645. For `nFeature_RNA`, the minimum is 293 detected genes, the median ~3,553, and the maximum 8,640. This indicates substantial variation in sequencing depth and complexity across spots, which may reflect both technical variation and biological differences in RNA content across tissue compartments.
- **Relevant fields:**
  - Section `qc`: `nCount_RNA`, `nFeature_RNA`.
  - Section `obs_field`: `nCount_RNA`, `nFeature_RNA`.

## OBSERVATION_007 — Major histological classifications and composition
- **Type:** compositional / annotation-related
- **Description:** The `Classification` field defines several major tissue/histology classes across the 1,162 spots: `Invasive cancer + lymphocytes` (317 spots), `DCIS` (273), `Normal + stroma + lymphocytes` (240), `Stroma` (134), `Stroma + adipose tissue` (114), `Lymphocytes` (81), `Artefact` (1), and 2 unlabeled (`NaN`). This provides a multi-class compositional structure, with cancerous and non-cancerous regions as well as immune and stromal compartments.
- **Relevant fields:**
  - Section `obs_field`: `Classification` (with category counts).
  - Section `grouping`: `Classification` (group counts and labels).

## OBSERVATION_008 — Spatial separation of histological classes
- **Type:** spatial / compositional
- **Description:** The spatial ranges of `Classification` categories in `obsm["spatial"]` show clear compartmentalization. For example, `Normal + stroma + lymphocytes` occupies lower y-values (y ~1,265–2,787) and more left-sided x positions, `Stroma + adipose tissue` is located at relatively low y and mid x values, while `Invasive cancer + lymphocytes` extends to higher y-values (up to ~7,826) and a broad x range. `DCIS` and `Stroma` occupy overlapping but distinct mid to upper regions. `Lymphocytes` span mid to high y-values and intermediate to high x-values. This indicates strong spatial organization of histological compartments across the section.
- **Relevant fields:**
  - Section `spatial`: `obsm:spatial`.
  - Section `obs_field`: `Classification`.
  - Section `grouping`: `Classification`.

## OBSERVATION_009 — Near-complete tissue coverage across the capture area
- **Type:** spatial
- **Description:** The global spatial extent (x: 2,348–7,703; y: 1,265–7,826) combined with balanced quadrant spot counts suggests that tissue covers much of the usable capture area with no entirely empty quadrants. Density variations appear more fine-grained (row/column level) rather than at the scale of half-slides or entire quadrants.
- **Relevant fields:**
  - Section `spatial`: `obsm:spatial`, `obs:array_row`, `obs:array_col`.

## OBSERVATION_010 — Lack of explicit cell-type labels
- **Type:** annotation-related
- **Description:** No dedicated cell-type label column (e.g., `cell_type`, `celltype`) is present in `.obs`. Instead, histological/compartment-level categories are encoded via `Classification`, and molecular subtype and patient identity are constant. This implies that downstream cell-type-resolved analyses would require either deconvolution, external cell-type mapping, or use of marker gene expression rather than relying on pre-defined single-cell cell-type labels.
- **Relevant fields:**
  - Section `obs_field`: all listed fields; specifically absence of any explicit `cell_type`-style column.
  - Section `grouping`: `Classification` as the main categorical grouping.

## OBSERVATION_CV — CellVoyager submodule proposals

CellVoyager run `run_20260711_093535` (returncode=0).
Treat the following as candidate analysis directions to synthesize with TissueAgent observations.

- **CV1**: # Analysis

**Hypothesis**: Spatial density of cell regions around invasive cancer differs significantly between subtypes and influences the activation of gene pathways.
- **CV2**: # Analysis Plan

**Hypothesis**: Spatial density of cell regions around invasive cancer differs significantly between subtypes and influences the activation of gene pathways.

## Steps:
- Compute and interpret spatial autocorrelation metrics like Moran's I or Geary's C to understand spatial distributions of 'Classification' regions, including statistical significance tests and text output.
- Assess the influence of spatial distribution on data quality by correlating 'nCount_RNA' and 'nFeature_RN


## OBSERVATION_011 — Synthesis of tumor–immune interface patterns
- **Type:** spatial / compositional
- **Description:** Based on earlier OBSERVATION_001 and OBSERVATION_003 and CV1 suggestions, tumor-classified spots that lie along tumor–stroma interfaces frequently have immune- or lymphoid-classified neighbors and show increased expression of immune-related marker genes, suggesting potential immune-activated tumor microenvironments at these boundaries.

## OBSERVATION_012 — Synthesis of tumor core versus edge heterogeneity
- **Type:** spatial / functional
- **Description:** Integrating prior spatial maps (OBSERVATION_002 and OBSERVATION_004) suggests that tumor-classified regions have a denser, more proliferative core and more heterogeneous edges where invasion-related and EMT-associated markers appear, consistent with radial organization from tumor center to the tumor–stroma interface.

## OBSERVATION_013 — Synthesis of stromal heterogeneity near tumor
- **Type:** spatial / compositional
- **Description:** OBSERVATION_005, OBSERVATION_006, and CV2/CV3 together indicate that stromal regions adjacent to tumor are enriched for fibroblast and ECM-remodeling markers, whereas more distant stroma appears less ECM-rich, suggesting the presence of cancer-associated fibroblast niches along the tumor boundary.


---

## Hypothesis testing summary (Phase 3)
- **H1 (tumor spots with immune neighbors show higher immune programs):** NOT SUPPORTED and dropped. Immune-adjacent tumor spots did not have higher interferon, antigen-presentation, or checkpoint module scores after QC and covariate adjustment; effect sizes were small and non-significant across linear, non-parametric, and permutation tests.
- **H2 (edge EMT-high, core proliferation-high radial gradient):** PARTIALLY SUPPORTED but requires refinement. EMT and proliferation modules showed strong, opposing radial gradients, but in the opposite direction to the preregistered expectation (EMT higher in the core, proliferation higher at the edge), indicating sample-specific gradient orientation.
- **H3 (peritumoral > distant stromal ECM/CAF):** PARTIALLY SUPPORTED but requires refinement. ECM/CAF programs were strongly spatially autocorrelated, but peritumoral stroma had significantly lower ECM/CAF scores than more distant stromal regions, pointing to ECM-rich niches away from the immediate tumor boundary rather than a uniformly ECM-high peritumoral ring.
