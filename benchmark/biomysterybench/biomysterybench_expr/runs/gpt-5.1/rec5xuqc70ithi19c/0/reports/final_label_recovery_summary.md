# Final label recovery summary

This report summarizes the final Sample–Tissue–Sex annotations derived from the upstream mapping and QC steps.

## Tissue mapping overview

- Original `Tissue_Group` labels from the masked metadata were mapped to harmonized `True_Tissue` names using the curated mapping table generated in Step 3 (`tissue_group_to_true_tissue_mapping.tsv`).
- The mapping encodes both organ-level and subregion-level resolution (e.g. brain subregions, ventricular myocardium) and was derived from prior biological knowledge and QC of expression patterns. Detailed rationale is documented in the Step 3 tissue mapping report.

## Sex inference overview

- Sex was inferred per sample using expression of XIST and Y-chromosome marker genes, as described in the Step 4 sex inference QC report (`sample_sex_inference.tsv`).
- Final sex labels in this dataset use the expression-based `Inferred_Sex` calls. In cases where donor metadata sex disagreed with expression, the expression-based call was retained and the discordance is documented in the QC report.

## Final dataset composition

- Total samples: **70**

### Samples per true tissue

| Tissue | N_samples |
|--------|-----------|
| Atrial_Myocardium | 10 |
| Cerebellum | 10 |
| Cerebral_Cortex | 10 |
| Hippocampus | 10 |
| Liver | 10 |
| Peripheral_Whole_Blood | 10 |
| Ventricular_Myocardium | 10 |

### Samples per sex

| Sex | N_samples |
|-----|-----------|
| Female | 28 |
| Male | 42 |

### Samples per (Tissue, Sex) combination

| Tissue | Sex | N_samples |
|--------|-----|-----------|
| Atrial_Myocardium | Female | 3 |
| Atrial_Myocardium | Male | 7 |
| Cerebellum | Female | 5 |
| Cerebellum | Male | 5 |
| Cerebral_Cortex | Female | 4 |
| Cerebral_Cortex | Male | 6 |
| Hippocampus | Female | 3 |
| Hippocampus | Male | 7 |
| Liver | Female | 3 |
| Liver | Male | 7 |
| Peripheral_Whole_Blood | Female | 5 |
| Peripheral_Whole_Blood | Male | 5 |
| Ventricular_Myocardium | Female | 5 |
| Ventricular_Myocardium | Male | 5 |

The authoritative per-sample annotations are provided in `project/outputs/tables/sample_tissue_sex_assignments.tsv`.