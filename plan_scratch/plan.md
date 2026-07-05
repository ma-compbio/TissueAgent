# Plan

```yaml
status: recruited
user_request: Run an ensemble cell-cell communication analysis on dataset_lohoff_et_al_seqhish.h5ad
  and then explain the methods and interpret the results.
current_step_id: 3
provenance:
  template_names:
  - ccc_ensemble
  justification: The plan is directly adapted from the ccc_ensemble template, which
    prescribes LIANA+, COMMOT, and stLearn on a shared preprocessed AnnData and a
    Robust Rank Aggregation–based consensus with specific output tables and figures.
    An additional final step was added to produce the user-requested narrative explanation
    and interpretation.
```

## Step 1 — Prepare dataset for CCC analysis

```yaml
status: done
assigned_agent: coding_agent
assigned_rationale: 'This step is exactly what the ccc-data-prep skill is designed
  for: loading an AnnData object, validating spatial metadata, standardizing cell-type
  labels, and preparing layers for downstream CCC tools, all of which are implemented
  by the coding_agent.'
skills:
- ccc-data-prep
expected_artifacts:
- adata/adata_ccc_prepped.h5ad
- tables/ccc_prep_metadata.tsv
actual_outputs: []
```

**Description:** Load library/datasets/dataset_lohoff_et_al_seqhish.h5ad and prepare a shared AnnData object for CCC methods, ensuring a standardized cell-type column, valid spatial coordinates, and appropriate expression normalization layers.

**Reasoning:** All three CCC methods (LIANA+, COMMOT, stLearn) must run on the same well-prepared object with consistent cell-type labels and spatial information so that downstream aggregation is valid.

## Step 2 — Run LIANA plus CCC analysis

```yaml
status: done
assigned_agent: coding_agent
assigned_rationale: Running LIANA+ on an AnnData object is covered by the ccc-liana
  skill, which is implemented by the coding_agent and produces the required per-(ligand,
  receptor, sender, receiver) CCC table.
skills:
- ccc-liana
expected_artifacts:
- tables/liana_res.csv
- adata/adata_ccc_liana.h5ad
actual_outputs: []
```

**Description:** Apply LIANA+ to the prepared AnnData to infer ligand–receptor interactions between cell types, saving a per-(ligand, receptor, sender, receiver) result table with scores and p-like statistics.

**Reasoning:** LIANA+ provides a robust, non-spatial reference CCC layer that captures transcriptional compatibility of ligand–receptor pairs across cell types, forming one pillar of the ensemble.

## Step 3 — Run COMMOT spatial communication analysis

```yaml
status: running
assigned_agent: coding_agent
assigned_rationale: COMMOT-based spatial communication analysis is handled by the
  ccc-commot skill, which configures ligand–receptor resources and spatial kernels
  within the coding_agent.
skills:
- ccc-commot
expected_artifacts:
- tables/commot_cluster_results.csv
- adata/adata_ccc_commot.h5ad
actual_outputs: []
```

**Description:** Run COMMOT on the same AnnData to model spatially weighted cell–cell communication using appropriate ligand–receptor resources and spatial kernels, and derive cluster-level communication statistics.

**Reasoning:** COMMOT incorporates spatial proximity into ligand–receptor inference, adding a second, explicitly spatial perspective on which cell types are likely communicating.

## Step 4 — Run stLearn ligand–receptor hotspot analysis

```yaml
status: pending
assigned_agent: coding_agent
assigned_rationale: stLearn CCI hotspot and cell-type pair analysis is specifically
  supported by the ccc-stlearn skill, making the coding_agent the appropriate agent
  for this spatial LR hotspot detection step.
skills:
- ccc-stlearn
expected_artifacts:
- tables/stlearn_lr_summary.csv
- tables/stlearn_per_lr_cci.csv
- adata/adata_ccc_stlearn.h5ad
actual_outputs: []
```

**Description:** Use stLearn’s CCI module to detect ligand–receptor hotspots and compute cell-type pair communication scores, exporting summaries per ligand–receptor and per sender–receiver pair.

**Reasoning:** stLearn identifies spatial enrichment of ligand–receptor co-expression, complementing LIANA+ and COMMOT with a hotspot-based view of communication.

## Step 5 — Aggregate CCC methods and generate figures

```yaml
status: pending
assigned_agent: coding_agent
assigned_rationale: Aggregating outputs from multiple CCC methods, performing rank
  aggregation, and generating figures is a general computational analysis task without
  a dedicated specialist skill, so the general-purpose coding_agent is the best fit.
skills: []
expected_artifacts:
- tables/ccc_consensus_ranked.csv
- tables/ccc_high_confidence.csv
- figures/ccc_consensus_dotplot.png
- figures/ccc_method_overlap.png
- figures/ccc_sender_receiver_chord.png
actual_outputs: []
```

**Description:** Combine LIANA+, COMMOT, and stLearn outputs into a long-format table, perform Robust Rank Aggregation across methods for each (ligand, receptor, sender, receiver) triple, define a high-confidence intersection set, and create summary visualizations.

**Reasoning:** Ensemble aggregation mitigates method-specific biases and yields consensus-ranked interactions and clear visual summaries, enabling more reliable biological interpretation.

## Step 6 — Explain methods and interpret CCC results

```yaml
status: pending
assigned_agent: coding_agent
assigned_rationale: Explaining the implemented CCC methods and interpreting the resulting
  interactions relies directly on the computations and artifacts produced in prior
  steps; there is no more specialized interpretation agent, so the coding_agent is
  used as the appropriate fallback.
skills: []
expected_artifacts:
- reports/ccc_methods_and_interpretation.md
actual_outputs: []
```

**Description:** Compile a written report that explains, at a conceptual level, how LIANA+, COMMOT, and stLearn infer cell–cell communication, then interpret the dataset-specific consensus and high-confidence interactions, highlighting key ligands, receptors, sender and receiver cell types, and spatial communication patterns.

**Reasoning:** The user explicitly requested both a methodological explanation and a biological interpretation; a structured report ties together the ensemble results into a clear narrative.
