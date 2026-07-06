# Plan

```yaml
status: recruited
user_request: Determine whether atrial fibroblasts in the AVN/AV ring community follow
  a distinct developmental program compared with atrial fibroblasts in left and right
  atrial communities, using the provided MERFISH dataset.
current_step_id: 3
provenance:
  template_names:
  - subpopulation_program_analysis
  justification: 'The task exactly matches the subpopulation_program_analysis use
    case: testing whether a target cell type (aFibro) within a focal community (AVN/AV
    Ring, defined in the communities field) follows a distinct molecular/developmental
    program compared with the same cell type in other communities (Left and Right
    Atria). The template’s steps—DE to derive markers, volcano plot, GeneAgent process
    narrative, and critic review—were adapted with concrete dataset paths, field names
    (populations, communities), and output filenames specific to the user’s request.'
```

## Step 1 — Subset aFibro and define groups

```yaml
status: done
assigned_agent: coding_agent
assigned_rationale: This step requires loading and subsetting an AnnData (.h5ad) MERFISH
  dataset, defining groups, and generating QC summaries, which fits the coding_agent’s
  expertise in spatial transcriptomics data handling and preprocessing.
skills: []
expected_artifacts:
- tables/aFibro_group_counts.tsv
- tables/aFibro_subset_qc.tsv
- anndata/aFibro_subset.h5ad
actual_outputs: []
```

**Description:** Load library/datasets/overall_merfish.h5ad, subset cells with populations == 'aFibro', and within these define a focal group (communities == 'AVN/AV Ring') and comparison groups (communities in ['Left Atria', 'Right Atria']). Compute and save per-group cell counts and basic QC summaries.

**Reasoning:** We must isolate the target cell type and ensure that the focal and comparison communities are well-defined with adequate cell numbers before running differential expression or interpreting any differences as a distinct program.

## Step 2 — Run differential expression and volcano plot

```yaml
status: done
assigned_agent: coding_agent
assigned_rationale: Running differential expression on the aFibro subset, computing
  statistics, adjusting p-values, saving DE tables, and generating a volcano plot
  are standard scanpy/Python/R analysis tasks well suited to the coding_agent.
skills: []
expected_artifacts:
- tables/de_aFibro_AVN-AVRing_vs_LA-RA_full.tsv
- tables/markers_aFibro_AVN-AVRing_adjP_lt_0.05.tsv
- figures/volcano_aFibro_AVN-AVRing_vs_LA-RA.png
actual_outputs: []
```

**Description:** On the aFibro subset, perform differential expression comparing AVN/AV Ring aFibro against Left and Right Atria aFibro (combined), using log-normalized data and a non-parametric method (e.g. Wilcoxon). Compute log2 fold changes and adjusted P values (Benjamini–Hochberg), saving the full DE table and the AVN/AV Ring marker set (adjusted P < 0.05). Generate and save a volcano plot visualizing all tested genes, highlighting significant AVN/AV Ring markers.

**Reasoning:** Differential expression provides the quantitative basis for defining AVN/AV Ring-specific markers and visualizing their effect sizes and significance, which is necessary for subsequent biological-process interpretation.

## Step 3 — Interpret AVN/AV Ring marker genes with GeneAgent

```yaml
status: running
assigned_agent: gene_agent
assigned_rationale: Interpreting a marker gene list into a verified biological-process
  narrative is exactly the defined role of the gene_agent, which produces process
  summaries and verification logs rather than enrichment tables.
skills: []
expected_artifacts:
- workspace/gene_agent/aFibro_AVN-AVRing/marker_gene_input.tsv
- workspace/gene_agent/aFibro_AVN-AVRing/process_narrative.md
- workspace/gene_agent/aFibro_AVN-AVRing/verification_log.json
actual_outputs: []
```

**Description:** Provide the full AVN/AV Ring marker gene list (adjusted P < 0.05, using canonical gene symbols) to the GeneAgent to infer, propose, and internally verify the biological processes and developmental programs these markers represent, producing a narrative-style interpretation rather than enrichment tables.

**Reasoning:** A verified process narrative from the marker genes is needed to move from a statistical gene list to biologically meaningful statements about putative developmental programs in AVN/AV Ring aFibro.

## Step 4 — Critically assess evidence for distinct program

```yaml
status: pending
assigned_agent: critic_agent
assigned_rationale: Assessing whether the evidence supports a distinct developmental
  program, and identifying confounders and alternative explanations, matches the critic_agent’s
  remit for hypothesis evaluation and falsification-style critique.
skills: []
expected_artifacts:
- reports/aFibro_AVN-AVRing_criticism.json
actual_outputs: []
```

**Description:** Using the DE results, marker characteristics, and the GeneAgent’s verified process narrative, have a Critic-style agent evaluate whether the data support a distinct molecular/developmental program in AVN/AV Ring aFibro versus atrial aFibro elsewhere, explicitly noting strengths, potential confounders (e.g. cell numbers, batch, spatial context), and alternative explanations.

**Reasoning:** A critical synthesis step is required to judge whether observed differences constitute a genuine distinct program or could be explained by technical or contextual factors.

## Step 5 — Compile final summary report

```yaml
status: pending
assigned_agent: coding_agent
assigned_rationale: Compiling an integrated written report that synthesizes computational
  results and interpretive outputs has no dedicated specialist; here the coding_agent
  is used as a general-purpose fallback to collate artifacts and produce the final
  summary.
skills: []
expected_artifacts:
- reports/aFibro_AVN-AVRing_distinct_program_report.md
actual_outputs: []
```

**Description:** Integrate the marker set overview, key genes and patterns, the GeneAgent’s verified biological-process narrative, and the Critic’s assessment into a concise written report addressing whether AVN/AV Ring aFibro follow a distinct developmental program, including explicit caveats and limitations.

**Reasoning:** The user requested an integrated summary interpreting the marker set and biological processes in the context of a distinct developmental program, which is best provided as a single, coherent report.
