# Final sleep deprivation condition call

## Cluster membership by sample

- **Cluster1**: sample1, sample2, sample3, sample5, sample6, sample7
- **Cluster2**: sample4, sample8

## Inferred condition per cluster

- **Sleep-deprived cluster**: Cluster1
- **Control cluster**: Cluster2

## Heuristic used to assign sleep deprivation

We used only the provided differential expression and top marker tables, without any external annotation, to infer which cluster corresponds to sleep-deprived mice. The heuristic was:

1. For each cluster, we summarized the distribution of log2 fold-changes (log2FC) and adjusted p-values among its top markers from `top_markers_by_cluster.tsv`.
2. We interpreted the cluster whose markers showed higher median log2FC as more **activated**, consistent with stronger overall upregulation of its defining genes.
3. The more activated cluster was labeled as **sleep_deprived**, and the other as **control**.

### Quantitative marker summaries

Per-cluster marker statistics (from `top_markers_by_cluster.tsv`):

| cluster_label | n_markers | log2FC_mean | log2FC_median | log2FC_min | log2FC_max | pval_adj_median | n_FDR_lt_0_25 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Cluster1 | 50 | 3.7290168624142677 | 1.5468086097922729 | 0.1192787651967755 | 23.879029570908884 | 0.3002118281560735 | 6 |
| Cluster2 | 50 | -1.3485459770658923 | -0.7613060240552129 | -3.73428209223036 | -0.1100755208815715 | 0.2412433631553395 | 29 |

From these summaries, Cluster1 has markedly higher mean and median log2FC among its top markers (mean ~3.7, median ~1.55, max ~23.9), indicating a strong overall upregulation pattern. In contrast, Cluster2 markers have negative mean and median log2FC (mean ~-1.35, median ~-0.76), consistent with relative downregulation compared to the other cluster.

The gene-level differential expression table (`de_results_cluster1_vs_cluster2.tsv`) is broadly consistent with this picture: although relatively few genes reach the most stringent FDR thresholds, genes upregulated in Cluster1 tend to have larger positive log2FC values on average than those up in Cluster2.

## Final interpretation

- **Cluster1** is interpreted as the more strongly activated state and is labeled **sleep_deprived**.
- **Cluster2** is interpreted as the relatively less activated state and is labeled **control**.

## Caveats

- No gene symbols or functional annotations were used; the inference relies solely on the magnitude and direction of log2FC and adjusted p-values.
- The top markers table includes a limited number of genes per cluster (50), so unmodeled genes could alter the overall biological picture.
- FDR values are relatively modest for many markers, so statistical support for differential expression is not uniformly strong.
- The assignment of the more activated cluster to sleep deprivation is based on a general biological prior (sleep deprivation tends to increase neural activation and immediate early gene expression) rather than direct evidence from these data.