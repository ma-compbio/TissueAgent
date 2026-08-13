# Drug assignment reasoning

## Overview
This analysis used only the probe-level differential expression (DE) tables for Groups A–D versus control, without any valid probe-to-gene mappings or pathway/gene-set resources. As required, no gene- or pathway-level interpretations were made, and no inferred gene identities were used.

## Quantitative summaries of DE profiles

### Distribution of log2 fold-changes per group

| Group | Mean logFC | SD logFC | 5th percentile | Median | 95th percentile | # probes (total) | # FDR<0.05 up | # FDR<0.05 down |
|-------|-----------:|--------:|---------------:|-------:|----------------:|-----------------:|--------------:|----------------:|
| A | 0.023 | 0.411 | -0.606 | -0.003 | 0.739 | 49386 | 13 | 9 |
| B | 0.025 | 0.601 | -0.799 | -0.063 | 1.134 | 49386 | 1172 | 522 |
| C | -0.013 | 0.475 | -0.811 | 0.002 | 0.742 | 49386 | 45 | 35 |
| D | -0.017 | 0.451 | -0.777 | -0.009 | 0.704 | 49386 | 13 | 6 |

### Correlation of logFC profiles between groups

|         |   logFC_A |   logFC_B |   logFC_C |   logFC_D |
|:--------|----------:|----------:|----------:|----------:|
| logFC_A | 1         | 0.435792  | 0.130569  | 0.0579163 |
| logFC_B | 0.435792  | 1         | 0.0848837 | 0.0435243 |
| logFC_C | 0.130569  | 0.0848837 | 1         | 0.378512  |
| logFC_D | 0.0579163 | 0.0435243 | 0.378512  | 1         |

## Comparison to high-level expectations for the four drugs

Only very general, textbook-level expectations can be invoked without referencing specific genes or pathways:

- **Geldanamycin (Hsp90 inhibitor):** typically perturbs stability of many client proteins, often leading to relatively broad transcriptional stress responses and chaperone-related changes, but the precise direction and magnitude at the probe level depends on which genes are targeted.
- **Trichostatin A (HDAC inhibitor):** often produces widespread transcriptional changes via chromatin acetylation, frequently with many genes up-regulated, but again this is defined at the level of specific genes and regulatory programs.
- **Rapamycin (mTOR inhibitor):** classically reduces mTORC1 signaling, affecting protein synthesis and cell growth; transcriptomic effects typically include modulation of metabolic and growth-related gene sets, but these are pathway-level expectations.
- **Doxorubicin (topoisomerase II inhibitor / DNA-damaging anthracycline):** induces DNA damage responses, cell-cycle arrest, and apoptosis-related transcriptional programs, again defined by specific gene sets.

However, without knowing which genes each probe corresponds to, these expectations cannot be translated into testable predictions about particular subsets of probes or pathways. We are limited to global properties such as the overall spread of logFC values and the total number of significantly perturbed probes.

## Assessment of each treatment group

### Group A

- Global DE magnitude: mean logFC ≈ 0.023, SD ≈ 0.411, with median near zero, indicating a roughly symmetric distribution of small changes.
- Extent of DE: 13 probes significantly up-regulated and 9 down-regulated at FDR<0.05 out of 49386 total probes.
- Interpretation under constraints: These numbers tell us how strong and widespread the transcriptional response is at the probe level, but without gene identities or pathways we cannot connect this pattern to any particular mechanism (Hsp90 inhibition, HDAC inhibition, mTOR inhibition, or DNA damage). Different drugs could plausibly produce similar global counts and distributions of DE probes in this experimental context.

### Group B

- Global DE magnitude: mean logFC ≈ 0.025, SD ≈ 0.601, with median near zero, indicating a roughly symmetric distribution of small changes.
- Extent of DE: 1172 probes significantly up-regulated and 522 down-regulated at FDR<0.05 out of 49386 total probes.
- Interpretation under constraints: These numbers tell us how strong and widespread the transcriptional response is at the probe level, but without gene identities or pathways we cannot connect this pattern to any particular mechanism (Hsp90 inhibition, HDAC inhibition, mTOR inhibition, or DNA damage). Different drugs could plausibly produce similar global counts and distributions of DE probes in this experimental context.

### Group C

- Global DE magnitude: mean logFC ≈ -0.013, SD ≈ 0.475, with median near zero, indicating a roughly symmetric distribution of small changes.
- Extent of DE: 45 probes significantly up-regulated and 35 down-regulated at FDR<0.05 out of 49386 total probes.
- Interpretation under constraints: These numbers tell us how strong and widespread the transcriptional response is at the probe level, but without gene identities or pathways we cannot connect this pattern to any particular mechanism (Hsp90 inhibition, HDAC inhibition, mTOR inhibition, or DNA damage). Different drugs could plausibly produce similar global counts and distributions of DE probes in this experimental context.

### Group D

- Global DE magnitude: mean logFC ≈ -0.017, SD ≈ 0.451, with median near zero, indicating a roughly symmetric distribution of small changes.
- Extent of DE: 13 probes significantly up-regulated and 6 down-regulated at FDR<0.05 out of 49386 total probes.
- Interpretation under constraints: These numbers tell us how strong and widespread the transcriptional response is at the probe level, but without gene identities or pathways we cannot connect this pattern to any particular mechanism (Hsp90 inhibition, HDAC inhibition, mTOR inhibition, or DNA damage). Different drugs could plausibly produce similar global counts and distributions of DE probes in this experimental context.

## Can we map groups to drugs in a robust, mechanistically justified way?

The four DE profiles differ in global strength and correlation structure—for example, Group B shows many more significantly changing probes than Groups A, C, or D, and Groups A and B share a moderate correlation of logFC values, while Groups C and D are more correlated with each other. These features indicate that the treatments are not identical and that there are at least two partially related response patterns (A/B and C/D).

However, the textbook-level expectations for Geldanamycin, Trichostatin A, Rapamycin, and Doxorubicin are all formulated in terms of **which genes and pathways** are affected (e.g., chaperone clients, histone acetylation targets, mTOR-regulated metabolic programs, or DNA-damage response genes). Because the probe-to-gene mapping file contains no valid gene symbols and no pathway resources are available, we cannot:

- Identify stress-response, chromatin-regulation, mTOR, or DNA-damage gene sets among the significantly perturbed probes.
- Test whether any group selectively enriches for these mechanism-linked gene sets.
- Even qualitatively check whether canonical marker genes for these mechanisms are up- or down-regulated, since the corresponding probe IDs cannot be reliably linked to gene symbols.

Under these constraints, any attempt to claim that, for example, "the strongest global response corresponds to an HDAC inhibitor" or "a particular pattern of up- versus down-regulation is characteristic of an mTOR inhibitor" would be speculative and not grounded in the available data. There are no widely accepted, mechanism-specific signatures defined purely by **distributional properties** (e.g., number of DE probes, mean logFC, overall correlation) independent of gene identities.

Therefore, no robust, mechanistically justified one-to-one mapping from Groups A–D to the four candidate drugs can be made using only the current probe-level DE tables and general drug knowledge. Any specific assignment of drug identities to groups would require fabricating or implicitly assuming gene–pathway relationships that are not supported by the provided data, which violates the stated constraints.

## Conclusion

- All groups remain **unassigned** to specific drugs in `drug_group_mapping.tsv`.
- This is a deliberate choice to avoid unsupported inference: without valid gene-level annotation or pathway information, and given that only global, probe-level summaries can be computed, mapping treatments to precise drug mechanisms is not defensible.
- The DE tables still document the quantitative effects of each treatment at the probe level and could be revisited if valid probe-to-gene mappings and pathway resources become available in the future.