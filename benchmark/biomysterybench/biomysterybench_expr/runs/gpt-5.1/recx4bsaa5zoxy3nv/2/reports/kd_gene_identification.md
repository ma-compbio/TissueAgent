# Knocked-down Gene Identification

## Inferred sample conditions

The following sample-to-condition mapping was used (from `sample_condition_inference.tsv`):


sample	inferred_condition
ctrl1	control
ctrl2	control
kd1	knockdown
kd2	knockdown

## Most likely knocked-down gene

Based on differential expression between inferred control and knockdown samples, the most likely knocked-down gene is **RF01956**.

### Expression summary for the knocked-down gene

Per-sample TPMs:

| Sample | Condition | TPM |
|--------|-----------|-----|
| ctrl1 | control | 9.1511 |
| ctrl2 | control | 77.0718 |
| kd1 | knockdown | 0.0000 |
| kd2 | knockdown | 0.0000 |

Group means and log2 fold-change (KD vs control):

| Group | Mean TPM | SD (between samples) |
|-------|----------|----------------------|
| Control (n=2) | 43.1114 | 48.0272 |
| Knockdown (n=2) | 0.0000 | 0.0000 |

Using a pseudocount of 0.1, the log2 fold-change of knockdown vs control is **-8.755**. A large negative value indicates strong downregulation in knockdown samples.

## Comparison to other candidate genes

Across all candidate genes, this gene has one of the most extreme negative log2 fold-changes while having substantial expression in control samples and near-absent expression in knockdown samples. This pattern is consistent across both control replicates and both knockdown replicates, supporting its identification as the primary knocked-down target.
