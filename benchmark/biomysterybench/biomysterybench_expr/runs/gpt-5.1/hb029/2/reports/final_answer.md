# Final assignment of sleep-deprived vs control samples

## Sample-level condition assignments

Based on the unsupervised clustering and downstream biological interpretation (see `sd_vs_control_interpretation.md`), **cluster1** is inferred to correspond to **sleep-deprived hippocampus**, and **cluster2** to **non-deprived (control) hippocampus**. Applying this mapping to the sample–cluster assignments yields:

- **Sleep-deprived samples (cluster1 → sleep_deprived):** sample1, sample2, sample5, sample6
- **Control samples (cluster2 → control):** sample3, sample4, sample7, sample8

These assignments are saved in tabular form in `project/outputs/tables/sample_condition_assignments.tsv` with columns `sample_id`, `cluster_label`, and `condition_label`.

## Rationale

The key evidence supporting this mapping comes from comparing the transcriptional signatures of the two unsupervised clusters against known features of sleep-deprived vs rested hippocampus. The cluster1-up gene set shows broad upregulation of immediate-early and activity-dependent genes, enrichment for synaptic plasticity and neurite remodeling pathways, and involvement of stress/hormone-responsive and translational control processes—hallmarks of a wake-activated, sleep-deprived hippocampal state. In contrast, genes elevated in cluster2 are predominantly associated with ribosomal function, translation, and mitochondrial energy metabolism, with comparatively lower activation of canonical sleep-deprivation markers, consistent with a more baseline, non-deprived (control) state. The convergence of these independent markers and pathway signatures strongly supports assigning cluster1 as sleep-deprived and cluster2 as control, and thus the sample-level condition labels listed above.