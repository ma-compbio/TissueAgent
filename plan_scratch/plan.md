# Plan

```yaml
status: recruited
user_request: Test whether atrial fibroblasts in the AVN/AV Ring community follow
  a distinct developmental program compared with atrial fibroblasts in the Left and
  Right Atria communities, using the developing human heart MERFISH dataset.
current_step_id: 1
provenance:
  template_names:
  - subpopulation_program_analysis
  justification: 'The task exactly matches the subpopulation_program_analysis template:
    testing whether a target cell type (aFibro) in a focal community (AVN/AV Ring)
    follows a distinct program compared with the same cell type in other communities
    (Left and Right Atria). The template’s steps (DE, marker extraction, GeneAgent
    process narrative, critical evaluation, and final report) were retained, with
    field names, groups, file names, and report focus adapted to the specific MERFISH
    dataset and user requirements.'
```

## Step 1 — Subset aFibro and run differential expression

```yaml
status: running
assigned_agent: coding_agent
assigned_rationale: This step requires loading an AnnData (MERFISH) object, subsetting
  by metadata fields, running differential expression, and generating a volcano plot
  — all best handled by the coding_agent with its spatial transcriptomics and Python/R
  analysis capabilities.
skills: []
expected_artifacts:
- tables/de_aFibro_AVN-AVRing_vs_LA-RA.tsv
- tables/aFibro_AVN-AVRing_vs_LA-RA_group_counts.tsv
- figures/volcano_aFibro_AVN-AVRing_vs_LA-RA.png
actual_outputs: []
```

**Description:** Load library/datasets/overall_merfish.h5ad; subset to cells with populations == 'aFibro'. Within these, define the focal group as communities == 'AVN/AV Ring' and the comparison group as communities in {'Left Atria','Right Atria'}. Run differential expression (e.g. Wilcoxon on log-normalized data) contrasting focal vs comparison, compute log2 fold-changes and adjusted P values (BH), and identify AVN/AV Ring marker genes as those with adjusted P < 0.05. Produce a volcano plot of all tested genes.

**Reasoning:** This step establishes whether AVN/AV Ring aFibro cells exhibit distinct transcriptional signatures relative to atrial aFibro elsewhere and creates the quantitative basis (marker set and effect sizes) for subsequent biological interpretation.

## Step 2 — Prepare ranked AVN/AV Ring marker gene list

```yaml
status: pending
assigned_agent: coding_agent
assigned_rationale: Preparing ranked marker lists and writing out gene symbol and
  summary tables is a straightforward data manipulation and file I/O task on DE results,
  for which the coding_agent is the appropriate choice.
skills: []
expected_artifacts:
- tables/markers_aFibro_AVN-AVRing_symbols.txt
- tables/markers_aFibro_AVN-AVRing_summary.tsv
actual_outputs: []
```

**Description:** From tables/de_aFibro_AVN-AVRing_vs_LA-RA.tsv, filter genes with adjusted P < 0.05 to define the AVN/AV Ring marker set. Standardize and deduplicate gene symbols, then rank markers by adjusted P ascending with ties broken by absolute log2 fold-change descending. Keep only the top 10 markers (most significant first) to satisfy the GeneAgent input contract, and write them one per line (no header) to a plain-text gene list file.

**Reasoning:** The GeneAgent operates on a small, high-confidence gene list passed inline rather than directly on DE tables; creating a ranked, size-limited marker list ensures both tractability and focus on the most informative markers.

## Step 3 — Infer and verify biological processes

```yaml
status: pending
assigned_agent: gene_agent
assigned_rationale: This step explicitly calls for using GeneAgent to infer and verify
  biological processes from a gene list, which is precisely the gene_agent’s specialized
  function.
skills: []
expected_artifacts:
- workspace/gene_agent/subpopulation_program_analysis/process_narrative.md
- workspace/gene_agent/subpopulation_program_analysis/process_evidence.json
actual_outputs: []
```

**Description:** Pass the top-10 AVN/AV Ring marker genes (from tables/markers_aFibro_AVN-AVRing_symbols.txt) to the GeneAgent to propose and verify the biological processes they represent. The GeneAgent should use curated resources (e.g. MsigDB) and internal verification to produce a concise, evidence-backed biological-process narrative for this gene list, not an enrichment table or dotplot.

**Reasoning:** A verified process-level interpretation of the marker genes is needed to translate the statistical DE signal into mechanistic insight about whether AVN/AV Ring aFibro follow a distinct developmental program.

## Step 4 — Critically evaluate distinct-program hypothesis

```yaml
status: pending
assigned_agent: critic_agent
assigned_rationale: Critically evaluating whether the evidence supports a distinct
  developmental program, including identifying confounders and alternative explanations,
  directly matches the critic_agent’s remit.
skills: []
expected_artifacts:
- reports/criticism.json
actual_outputs: []
```

**Description:** Have a Critic Agent review the DE results (effect sizes, number and nature of markers), the top-10 gene list, and the GeneAgent’s verified process narrative to assess whether they collectively support a distinct developmental program in AVN/AV Ring aFibro versus atrial aFibro elsewhere. The critic should note strengths, weaknesses, possible confounders (e.g. cell numbers, batch, spatial context), and alternative explanations.

**Reasoning:** A structured critical assessment guards against overinterpretation of DE and process annotations, providing a balanced view of whether observed differences truly reflect a distinct developmental program.

## Step 5 — Synthesize final narrative report

```yaml
status: pending
assigned_agent: coding_agent
assigned_rationale: Synthesizing a final narrative report that integrates quantitative
  DE results with GeneAgent and Critic outputs is a general analysis-and-reporting
  task; no specialist agent is dedicated to report writing, so the general-purpose
  coding_agent is used as the fallback.
skills: []
expected_artifacts:
- reports/avn_avring_aFibro_program_report.md
actual_outputs: []
```

**Description:** Integrate the marker set characteristics (size, key genes, directions of change), the GeneAgent’s verified biological processes, and the critic’s assessment into a concise written report. Explicitly state whether the evidence supports a distinct developmental program for AVN/AV Ring aFibro, summarize the implicated processes, reference the volcano plot and key markers, and clearly list caveats (including the 10-gene cap for process interpretation and any low cell counts or technical limitations).

**Reasoning:** The user needs an interpretable, end-to-end summary that connects statistical results and process-level interpretation to a clear verdict on the distinct-program hypothesis, along with transparent caveats.
