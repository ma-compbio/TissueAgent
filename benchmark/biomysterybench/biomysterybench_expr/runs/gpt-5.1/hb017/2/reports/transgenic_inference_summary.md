# Transgenic Group Inference Summary

## Data limitations

- The primary expression matrix (`library/datasets/cleaned_counts.csv`) has **no gene identifiers**; genes are indexed only by implicit integer row positions.

- Because of the missing gene IDs, **Bmp4/BMP4 and other BMP/TGF-β pathway genes cannot be located** in the matrix.

- As a consequence, the files `bmp4_expression_by_sample.tsv` and `bmp4_group_summary.tsv` contain only schema (no rows), and **no direct gene-level BMP4 expression evidence is available**.

## Surrogate BMP pathway activity analysis

- A curated BMP/TGF-β gene set was defined, but none of its gene symbols could be mapped to the unlabeled expression matrix.

- As a surrogate, a `bmp_pathway_score` was computed as the **mean expression across all 36,572 genes per sample**, which is effectively a global expression intensity measure, not a true pathway score.

- This surrogate score was summarized by group (Group1 vs Group2):

  - Group1 mean surrogate score: **514.051** (n = 9)

  - Group2 mean surrogate score: **498.764** (n = 12)

  - Two-sample t-test (surrogate scores): t = 0.785, p = 0.445.

- The p-value (~0.445) indicates **no statistically significant difference** in the surrogate score between Group1 and Group2.

- Biologically, a small difference in global mean expression is difficult to interpret and **cannot be confidently linked to BMP4 transgene activity**.

## Inference about the NSE-BMP4 transgenic group

- Because we lack **gene-level BMP4 expression** and **cannot quantify BMP/TGF-β pathway genes**, there is no direct evidence to identify which group corresponds to NSE-BMP4 transgenic mice.

- The only available quantitative comparison (global mean expression) shows **no significant difference** between Group1 and Group2.

- Given these limitations, **no statistically or biologically compelling case** can be made that either Group1 or Group2 has higher BMP4-related activity.

- Any assignment of a specific group as "transgenic" based solely on these data would be speculative and is therefore **not performed**.

## Final decision and outputs

- The transgenic status for all samples is labeled as **`UNKNOWN`** in the final assignment table, reflecting that the transgenic group is not inferable from the available expression data.

- Output files generated in this step:

  - `project/outputs/tables/transgenic_group_assignment.tsv`: per-sample table with `sample_id`, `group_label`, `is_transgenic` (all `UNKNOWN`), and a note explaining the limitation.

  - `project/outputs/tables/transgenic_sample_ids.txt`: contains a single comment line stating that no transgenic group could be inferred.



In summary, **the available data are insufficient to assign the NSE-BMP4 transgenic group based on expression alone**. Any further inference would require either gene-level identifiers for the expression matrix or independent experimental metadata linking groups to genotype.
