# Label Recovery Report

## Title & Objective

**Objective:** Recover the true tissue subtype and sex for each RNA-seq sample using only expression data, under the assumption that provided metadata labels are masked/untrusted. Output the final labels as a table with columns: Sample, Tissue, Sex.

## Data & Methods

**Data used**
- Expression matrix: `library/datasets/expression_matrix.csv` (54,592 genes × 70 samples), normalized to CPM-like values and log1p-transformed, then filtered to 20,198 informative genes.
- Masked metadata (not used for training): `library/datasets/sample_metadata_masked.csv`.

**Broad tissue inference**
- Performed PCA → kNN graph → UMAP and Leiden clustering on the normalized data.
- Scored samples with curated marker panels for major tissues (Brain, Liver, Heart, Skeletal_muscle, Blood_Immune, etc.) using known markers (e.g., ALB, APOB for Liver; MYH6, TNNT2 for Heart; PTPRC/CD45, MS4A1 for Blood_Immune; MYH1, ACTN3 for Skeletal_muscle; GAD1, GFAP, MBP, SLC17A7 for Brain).
- Assigned each cluster, then each sample, a broad tissue class based on marker scores and cluster purity.

**Brain subtype resolution**
- Subset samples with broad tissue == Brain.
- Re-ran HVG selection, PCA, neighbors, UMAP, and Leiden clustering on brain-only data.
- Scored clusters with canonical region markers (from GTEx/Allen-style references):
  - Cortex: SLC17A7, NEUROD6, RCAN2.
  - Hippocampus: PROX1, RELN.
  - Basal_ganglia: PDE1A, PPP1R1B, RGS9.
  - Cerebellum markers (PCP4, GABRA6, CALB1) were present but did not define a dominant cluster.
- Labeled brain clusters as Brain_Cortex, Brain_Hippocampus, or Brain_Basal_ganglia based on highest region score.

**Sex inference**
- Used expression of sex-linked genes:
  - X: XIST.
  - Y: KDM5D, RPS4Y1, DDX3Y, UTY, EIF1AY, ZFY.
- Computed per-sample XIST_score and mean Y_score.
- Fit a 2D Gaussian Mixture Model (2 components) on standardized (XIST_score, Y_score).
- Interpreted clusters as Female (high XIST, low Y) vs Male (low XIST, high Y) and used posterior probabilities as confidence.

**Donor inference (QC only)**
- Centered expression within each Tissue_subtype to remove tissue effects and computed a sample–sample Pearson correlation matrix on residuals.
- Performed hierarchical clustering on 1 − correlation and cut into 20 clusters, assigning inferred donor IDs (D01–D20).
- Used these donor-like groups only as internal QC; they did not alter tissue or sex labels.

**Final label assembly**
- Merged refined tissue subtypes and sex calls by Sample ID.
- Constructed `project/outputs/tables/sample_tissue_sex.tsv` with exactly three columns: Sample, Tissue (Tissue_subtype), Sex.

## Results

**Final Sample–Tissue–Sex assignments**

| Sample | Tissue              | Sex    |
|--------|---------------------|--------|
| S001   | Blood_Immune        | Female |
| S002   | Brain_Basal_ganglia | Female |
| S003   | Liver               | Female |
| S004   | Heart               | Female |
| S005   | Skeletal_muscle     | Female |
| S006   | Brain_Hippocampus   | Female |
| S007   | Brain_Cortex        | Female |
| S008   | Blood_Immune        | Female |
| S009   | Brain_Basal_ganglia | Female |
| S010   | Skeletal_muscle     | Female |
| S011   | Heart               | Female |
| S012   | Liver               | Female |
| S013   | Brain_Hippocampus   | Female |
| S014   | Brain_Cortex        | Female |
| S015   | Blood_Immune        | Male   |
| S016   | Brain_Basal_ganglia | Male   |
| S017   | Heart               | Male   |
| S018   | Skeletal_muscle     | Male   |
| S019   | Liver               | Male   |
| S020   | Brain_Hippocampus   | Male   |
| S021   | Brain_Cortex        | Male   |
| S022   | Blood_Immune        | Female |
| S023   | Brain_Basal_ganglia | Female |
| S024   | Heart               | Female |
| S025   | Skeletal_muscle     | Female |
| S026   | Liver               | Female |
| S027   | Brain_Cortex        | Female |
| S028   | Brain_Hippocampus   | Female |
| S029   | Blood_Immune        | Male   |
| S030   | Brain_Basal_ganglia | Male   |
| S031   | Heart               | Male   |
| S032   | Skeletal_muscle     | Male   |
| S033   | Liver               | Male   |
| S034   | Brain_Hippocampus   | Male   |
| S035   | Brain_Cortex        | Male   |
| S036   | Blood_Immune        | Male   |
| S037   | Brain_Basal_ganglia | Male   |
| S038   | Heart               | Male   |
| S039   | Skeletal_muscle     | Male   |
| S040   | Liver               | Male   |
| S041   | Brain_Cortex        | Male   |
| S042   | Brain_Hippocampus   | Male   |
| S043   | Blood_Immune        | Male   |
| S044   | Brain_Basal_ganglia | Male   |
| S045   | Liver               | Male   |
| S046   | Skeletal_muscle     | Male   |
| S047   | Heart               | Male   |
| S048   | Brain_Cortex        | Male   |
| S049   | Brain_Hippocampus   | Male   |
| S050   | Blood_Immune        | Male   |
| S051   | Brain_Basal_ganglia | Male   |
| S052   | Liver               | Male   |
| S053   | Heart               | Male   |
| S054   | Skeletal_muscle     | Male   |
| S055   | Brain_Hippocampus   | Male   |
| S056   | Brain_Cortex        | Male   |
| S057   | Blood_Immune        | Male   |
| S058   | Brain_Basal_ganglia | Male   |
| S059   | Heart               | Male   |
| S060   | Skeletal_muscle     | Male   |
| S061   | Liver               | Male   |
| S062   | Brain_Hippocampus   | Male   |
| S063   | Brain_Cortex        | Male   |
| S064   | Blood_Immune        | Female |
| S065   | Brain_Basal_ganglia | Female |
| S066   | Heart               | Female |
| S067   | Skeletal_muscle     | Female |
| S068   | Liver               | Female |
| S069   | Brain_Hippocampus   | Female |
| S070   | Brain_Cortex        | Female |

(The same table is available as a machine-readable TSV at `project/outputs/tables/sample_tissue_sex.tsv`.)

## Caveats & Warnings

- Broad and brain-region tissue labels are based on curated marker panels and unsupervised clustering; while they match expected patterns, they are not validated against external ground truth and could miss rare or atypical tissues.
- Brain region resolution distinguishes Cortex, Hippocampus, and Basal_ganglia but did not identify a clear Cerebellum cluster; true cerebellar samples, if any, may be absorbed into nearby brain subtypes.
- Some Skeletal_muscle and Heart samples show partial overlap in muscle-related markers; assignments in these classes rely on overall patterns and clustering structure rather than a single definitive marker.
- Donor_inferred groups were used only as internal QC and are not guaranteed to equal true donor IDs.

## Next Steps

- If ground-truth metadata are available, compare the inferred labels to true tissues and sexes to quantify accuracy per class.
- Refine brain-region annotation using richer reference atlases or supervised classifiers trained on GTEx/Allen data.
- Use inferred donor groups alongside tissue and sex labels for downstream differential expression or eQTL analyses.

## References

- GTEx Consortium. "The Genotype-Tissue Expression (GTEx) project." *Nat Genet* 45, 580–585 (2013). doi:10.1038/ng.2653.
- Hawrylycz et al. "An anatomically comprehensive atlas of the adult human brain transcriptome." *Nature* 489, 391–399 (2012). doi:10.1038/nature11405.
- Tukiainen et al. "Landscape of X chromosome inactivation across human tissues." *Nature* 550, 244–248 (2017). doi:10.1038/nature24265.
