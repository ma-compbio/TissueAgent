# Plan

```yaml
status: done
user_request: Test whether atrial fibroblasts in the AVN/AV ring community follow
  a distinct developmental program compared with atrial fibroblasts in left/right
  atrial communities using the MERFISH dataset, combining differential expression,
  marker-process interpretation, and critical assessment.
current_step_id: 7
provenance:
  template_names:
  - subpopulation_program_analysis
  justification: 'The plan closely follows the subpopulation_program_analysis template:
    subsetting to a target cell type (aFibro), performing DE for a focal community
    (AVN/AV Ring) versus comparison communities (Left/Right Atria), extracting significant
    markers with adjusted P < 0.05, generating a volcano plot, preparing a top-10
    marker list for the GeneAgent, obtaining a verified biological-process narrative,
    having a critic weigh evidence for a distinct program, and finally producing a
    written report with caveats. File paths are adapted to the project/outputs structure
    and to reflect the specific aFibro AVN/AV Ring vs atria comparison requested.'
```

## Step 1 — Subset aFibro cells and define groups

```yaml
status: done
assigned_agent: coding_agent
assigned_rationale: This step requires loading an AnnData .h5ad file, subsetting by
  metadata fields, and writing summary/config tables—tasks best handled by the coding_agent
  with its Python/R and spatial transcriptomics tooling.
skills: []
expected_artifacts:
- tables/aFibro_group_counts.tsv
- configs/aFibro_AVN-AVRing_vs_Atria_config.json
actual_outputs: []
```

**Description:** Load library/datasets/overall_merfish.h5ad; subset to cells with populations == 'aFibro'. Within these, use the communities field to define the focal group (AVN/AV Ring) and comparison groups (Left Atria and Right Atria, pooled as 'Atria'). Compute and save per-group cell counts and a minimal config capturing the comparison design.

**Reasoning:** Restricting to the target cell type and clearly defining focal vs comparison groups ensures the DE directly tests the AVN/AV Ring program within atrial fibroblasts, and allows later steps to check power (e.g., small group sizes).

## Step 2 — Run differential expression for AVN-AVRing

```yaml
status: done
assigned_agent: coding_agent
assigned_rationale: Running normalized differential expression within aFibro cells
  and generating a volcano plot involves statistical testing and plotting in Python/R,
  which falls squarely within the coding_agent’s capabilities.
skills: []
expected_artifacts:
- tables/de_aFibro_AVN-AVRing_vs_Atria_full.tsv
- tables/de_aFibro_AVN-AVRing_markers_adjP_lt0.05.tsv
- figures/volcano_aFibro_AVN-AVRing_vs_Atria.png
actual_outputs: []
```

**Description:** On the aFibro subset, normalize expression (e.g. log-normalization), then run differential expression contrasting AVN/AV Ring aFibro against pooled Left Atria + Right Atria aFibro using a Wilcoxon rank-sum test with Benjamini–Hochberg correction. Save a full DE table for all tested genes and a filtered table of AVN/AV Ring marker genes with adjusted P < 0.05. Generate a volcano plot highlighting significantly up- and down-regulated genes in AVN/AV Ring.

**Reasoning:** Differential expression provides the quantitative basis for defining AVN/AV Ring-specific markers and effect sizes, and the volcano plot gives a quick visual overview of the distinctness and magnitude of the transcriptional program.

## Step 3 — Prepare top marker gene list for GeneAgent

```yaml
status: done
assigned_agent: coding_agent
assigned_rationale: Standardizing gene symbols, ranking markers, and writing ranked
  gene lists/summary tables are data wrangling tasks well suited to the coding_agent.
skills: []
expected_artifacts:
- tables/markers_aFibro_AVN-AVRing_top10_symbols.txt
- tables/markers_aFibro_AVN-AVRing_top10_summary.tsv
actual_outputs: []
```

**Description:** From the significant marker table (adjusted P < 0.05), extract gene symbols, standardize to canonical uppercase symbols, deduplicate, and rank by adjusted P ascending (tie-break by absolute log2 fold-change descending). Keep only the top 10 most significant AVN/AV Ring markers and write them one per line (no header) to a plain-text gene list file; also save a small summary table of these top markers.

**Reasoning:** The GeneAgent expects a short, ranked list of canonical gene symbols provided inline; limiting to the top 10 markers focuses interpretation on the strongest, most reliable signals while meeting the external tool’s input constraints.

## Step 4 — Infer and verify processes via GeneAgent

```yaml
status: done
assigned_agent: gene_agent
assigned_rationale: Interpreting a marker gene list into a verified biological-process
  narrative is exactly the defined role of the gene_agent, which runs the NCBI GeneAgent
  cascade for process-level summaries.
skills: []
expected_artifacts:
- gene_agent/aFibro_AVN-AVRing/process_narrative.md
- gene_agent/aFibro_AVN-AVRing/process_evidence.json
actual_outputs: []
```

**Description:** Provide the top-10 AVN/AV Ring marker genes (from markers_aFibro_AVN-AVRing_top10_symbols.txt, passed inline as a list of symbols) to the GeneAgent. Have it propose and internally verify the biological processes and developmental themes these markers represent, producing a narrative description plus supporting evidence (e.g. literature-backed roles, pathway memberships).

**Reasoning:** A GeneAgent-driven, verification-based narrative links the marker gene set to plausible biological and developmental processes, going beyond raw gene lists or enrichment tables and grounding interpretations in external knowledge.

## Step 5 — Critically assess distinct-program evidence

```yaml
status: done
assigned_agent: critic_agent
assigned_rationale: Evaluating whether the evidence supports a distinct developmental
  program, considering confounders and effect sizes, is the core function of the critic_agent.
skills: []
expected_artifacts:
- reports/criticism_aFibro_AVN-AVRing_vs_Atria.json
actual_outputs: []
```

**Description:** Using the DE results and GeneAgent narrative, have a Critic Agent evaluate whether AVN/AV Ring aFibro exhibit a distinct developmental program compared with atrial aFibro elsewhere. The critic should consider effect sizes, number and coherence of markers, process plausibility, sample sizes per group, and potential confounders (e.g., spatial niche, technical artifacts), and record a structured verdict and caveats.

**Reasoning:** A dedicated critical assessment guards against over-interpreting noisy or confounded DE results and explicitly weighs the strength of evidence for a distinct molecular program in the AVN/AV Ring aFibro.

## Step 6 — Compile integrated subpopulation program report

```yaml
status: done
assigned_agent: coding_agent
assigned_rationale: Synthesizing computational outputs and external narratives into
  a concise written report does not match a more specialized agent, so the general-purpose
  coding_agent is used here as a fallback to assemble and format the final summary.
skills: []
expected_artifacts:
- reports/subpopulation_program_aFibro_AVN-AVRing_vs_Atria_report.md
actual_outputs: []
```

**Description:** Synthesize the analyses into a concise report summarizing: (i) the AVN/AV Ring marker set (including counts and notable top genes; full list referenced via the marker table), (ii) the verified biological processes reported by the GeneAgent for the top markers, and (iii) whether the combined evidence supports a distinct developmental program for AVN/AV Ring aFibro versus atrial aFibro elsewhere. Explicitly note key caveats (e.g., top-10 gene limitation, any small-group issues, potential alternative explanations).

**Reasoning:** An integrated narrative report directly addresses the user’s questions, connects computational outputs to biological interpretation, and documents limitations and uncertainties for downstream use.
