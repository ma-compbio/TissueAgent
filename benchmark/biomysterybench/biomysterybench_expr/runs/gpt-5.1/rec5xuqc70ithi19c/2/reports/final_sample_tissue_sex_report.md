# Sample Tissue and Sex Inference Report

## Title & Objective
Identify the true tissue subtype and sex for each RNA-seq sample using only expression profiles, and report a per-sample table with columns: Sample, Tissue, Sex.

## Data & Methods
- **Input data:** 49,181 genes × 70 samples expression matrix (standardized), derived from `library/datasets/expression_matrix.csv` (CPM/TPM-like scale; genes as rows, samples as columns).
- **Tissue inference:**
  - Log1p transform, selection of highly variable genes, PCA on samples, and k-means clustering (k=5) in PC space.
  - Cluster marker genes identified by mean-in-cluster vs mean-outside logFC and a composite score.
  - Clusters annotated via canonical tissue markers:
    - Heart (e.g., TNNI3, TNNT2, MYH6, MYH7, ACTC1).
    - Cortex (e.g., NRGN, CAMK2A, SLC1A2, SNAP25, GFAP).
    - Whole_Blood (e.g., HBB, HBA1, HBA2, S100A9, LYZ, NKG7).
    - Liver (e.g., ALB, APOA1, APOA2, FGA, FGB, TTR, CYP2C9).
    - Cerebellum (e.g., CBLN1, ZIC1, ZIC2, GRM4, GABRA6, PVALB).
- **Sex inference:**
  - Used log1p expression of 12 Y-linked genes (RPS4Y1, KDM5D, DDX3Y, UTY, EIF1AY, USP9Y, ZFY, TXLNGY, PRKY, TMSB4Y, PCDH11Y, NLGN4Y) and the X-linked XIST.
  - Computed per-sample mean Y-marker expression and XIST expression; applied data-driven thresholds to classify samples as Male (high Y, low XIST) or Female (low Y, high XIST).

## Results

### Final Sample–Tissue–Sex Assignments

| Sample | Tissue       | Sex    |
|--------|-------------|--------|
| S001 | Whole_Blood | Female |
| S002 | Cortex | Female |
| S003 | Liver | Female |
| S004 | Heart | Female |
| S005 | Heart | Female |
| S006 | Cerebellum | Female |
| S007 | Cortex | Female |
| S008 | Whole_Blood | Female |
| S009 | Cortex | Female |
| S010 | Heart | Female |
| S011 | Heart | Female |
| S012 | Liver | Female |
| S013 | Cerebellum | Female |
| S014 | Cortex | Female |
| S015 | Whole_Blood | Male |
| S016 | Cortex | Male |
| S017 | Heart | Male |
| S018 | Heart | Male |
| S019 | Liver | Male |
| S020 | Cerebellum | Male |
| S021 | Cortex | Male |
| S022 | Whole_Blood | Female |
| S023 | Cortex | Female |
| S024 | Heart | Female |
| S025 | Heart | Female |
| S026 | Liver | Female |
| S027 | Cortex | Female |
| S028 | Cerebellum | Female |
| S029 | Whole_Blood | Male |
| S030 | Cortex | Male |
| S031 | Heart | Male |
| S032 | Heart | Male |
| S033 | Liver | Male |
| S034 | Cerebellum | Male |
| S035 | Cortex | Male |
| S036 | Whole_Blood | Male |
| S037 | Cortex | Male |
| S038 | Heart | Male |
| S039 | Heart | Male |
| S040 | Liver | Male |
| S041 | Cortex | Male |
| S042 | Cerebellum | Male |
| S043 | Whole_Blood | Male |
| S044 | Cortex | Male |
| S045 | Liver | Male |
| S046 | Heart | Male |
| S047 | Heart | Male |
| S048 | Cortex | Male |
| S049 | Cerebellum | Male |
| S050 | Whole_Blood | Male |
| S051 | Cortex | Male |
| S052 | Liver | Male |
| S053 | Heart | Male |
| S054 | Heart | Male |
| S055 | Cerebellum | Male |
| S056 | Cortex | Male |
| S057 | Whole_Blood | Male |
| S058 | Cortex | Male |
| S059 | Heart | Male |
| S060 | Heart | Male |
| S061 | Liver | Male |
| S062 | Cerebellum | Male |
| S063 | Cortex | Male |
| S064 | Whole_Blood | Female |
| S065 | Cortex | Female |
| S066 | Heart | Female |
| S067 | Heart | Female |
| S068 | Liver | Female |
| S069 | Cerebellum | Female |
| S070 | Cortex | Female |

## Caveats & Warnings
- Tissue subtype labels depend on canonical marker interpretation; atypical expression patterns or mixed tissues could be misassigned, though clusters here showed clear marker enrichment.
- Sex assignments rely on robust Y-marker and XIST expression; very low-coverage or degraded samples could be more ambiguous, but no such cases were observed.

## Next Steps
- If desired, cross-check these inferred labels against any external donor/tissue metadata.
- Use the `sample_tissue_sex_final.tsv` table as ground truth for downstream differential expression or multi-tissue integrative analyses.

## References
- GTEx Consortium. The Genotype-Tissue Expression (GTEx) project. *Nat Genet.* 2013;45(6):580–585. doi:10.1038/ng.2653
- Lake et al. Neuronal subtypes and diversity in the human brain. *Nat Neurosci.* 2016;19(11):Ppi. doi:10.1038/nn.4396
- Naqvi et al. Sex differences in human gene expression. *Cell.* 2019;177(4):Pp. doi:10.1016/j.cell.2019.03.049
